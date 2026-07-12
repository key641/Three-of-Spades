
## 一句话方向

用 LLM 理解复杂自然语言，用显式状态和少量高层规则保证流程稳定，用 B 侧路线工具执行真实规划，用 trace 和分层测试保证系统可调试、可评估、可持续迭代。

## A 侧核心职责

A 同学主要负责以下模块：

- FastAPI 主入口：`/api/chat`、`/api/chat/stream` 以及必要的调试接口。
- Agent 编排：消息路由、意图解析、状态合并、澄清判断、工具调用、回复生成。
- LLM Provider：OpenAI / DeepSeek 等 provider 切换和 fallback。
- 多轮会话状态：维护当前旅行目标、当前路线、用户补充和历史反馈。
- 用户画像：读取和更新用户偏好、避雷、权重、长期画像。
- 动态事件理解：把“排队太久”“下雨了”“换一家”等自然语言转成结构化事件。
- 路线解释：基于 B 侧返回的结构化路线事实生成用户可读说明。
- Agent trace：暴露每一层判断、状态变化、工具结果和 fallback/error。

## 总体链路

推荐链路如下：

```text
用户输入
  -> MessageRouter / QueryUnderstanding
  -> IntentDelta
  -> TripState
  -> ClarificationPolicy
  -> Policy / Planner
  -> POI / Route / Replan / Amap tools
  -> Response Composer
  -> Agent Trace / Evaluation
```

关键原则：

- LLM 只做理解和表达，不直接自由决定是否重规划、是否调用工具。
- `TripState` 是会话里的真实出行状态，不能继续只依赖 `last_intent`。
- `Policy / Planner` 根据 `turn_type` 和状态选择流程。
- 路线事实必须来自工具返回，不能由 LLM 编造。
- 每一层都要进入 trace，方便定位问题发生在理解、状态继承、工具、总结还是前端展示。

## 核心数据结构

### QueryUnderstanding

`QueryUnderstanding` 只描述“用户这句话是什么意思”，不直接修改状态，也不直接调工具。

建议字段：

```json
{
  "turn_type": "new_plan | add_constraint | modify_constraint | remove_constraint | route_detail | select_route | replace_stop | remove_stop | lock_stop | compare_routes | general_chat",
  "inherit_previous": true,
  "preserve_scenario": true,
  "target_route_ref": "current",
  "target_stop_ref": null,
  "question_type": null,
  "confidence": 0.86,
  "reason": "用户在上一轮路线基础上追加吃饭需求"
}
```

最小验收：

- “我还要吃饭”在有上一轮状态时应识别为 `add_constraint`。
- “两个地点之间怎么过去”在有当前路线时应识别为 `route_detail`。
- “换成杭州吧”应识别为修改城市的 `modify_constraint`，不能当普通聊天。

### IntentDelta

`IntentDelta` 只描述本轮对状态的增量变化。

示例：

```json
{
  "added_hard_constraints": {},
  "modified_hard_constraints": {
    "city": "杭州"
  },
  "removed_hard_constraints": [],
  "added_preferences": ["吃好"],
  "removed_preferences": [],
  "added_implicit_needs": [],
  "removed_implicit_needs": ["meal_stop"],
  "added_must_include": ["meal_stop"],
  "removed_must_include": [],
  "target_route_ref": "current",
  "target_stop_ref": null
}
```

注意：

- `IntentDelta` 不能保存完整旅行状态。
- `add_constraint` 只追加偏好、隐含需求或必须节点。
- `modify_constraint` 只修改用户明确提到的字段。
- 相对表达不要直接改硬字段，例如“更省钱一点”应优先落成优化偏好，而不是覆盖具体预算。

### TripState

`TripState` 保存可持续编辑的旅行状态。

示例：

```json
{
  "city": "上海",
  "people_count": 2,
  "start_time": "09:00",
  "duration_hours": 8,
  "budget_per_person": 300,
  "scenario": "friends_citywalk",
  "hard_constraints": {
    "city": "上海",
    "people_count": 2,
    "duration_hours": 8
  },
  "soft_preferences": ["拍照", "吃好"],
  "implicit_needs": ["rest_stop"],
  "must_include": ["meal_stop"],
  "active_route_id": "route_balanced_1",
  "locked_stop_ids": [],
  "feedback_history": []
}
```

迁移策略：

- 短期保留 `last_intent` 兼容旧链路。
- 新增 `trip_state` 后，逐步让它成为主要状态源。
- `preferences` 可以映射到 `soft_preferences`。
- `avoid_tags` 继续作为路线评分输入。

## 轮次处理策略

不同 `turn_type` 应走不同流程：

| turn_type | 行为 |
| --- | --- |
| `new_plan` | 初始化新 `TripState`，生成新路线 |
| `add_constraint` | 继承硬约束和主场景，追加偏好或必须节点，重新规划 |
| `modify_constraint` | 只修改明确字段，继承其他状态，重新规划 |
| `remove_constraint` | 删除指定偏好、约束或节点，重新规划 |
| `route_detail` | 不重新规划，只基于当前路线回答细节 |
| `select_route` | 更新 `active_route_id` |
| `replace_stop` | 局部替换目标 stop，保留其他点和 locked stops |
| `remove_stop` | 删除目标 stop 并局部重排 |
| `lock_stop` | 更新 `locked_stop_ids` |
| `compare_routes` | 不重新规划，只解释路线差异 |
| `general_chat` | 不写旅行状态，不调路线工具 |

默认冲突处理：

- 用户显式字段优先于历史状态。
- 用户未提到的字段必须继承。
- `add_constraint` 不能把拍照路线改成纯美食路线，除非用户明确要求。
- `route_detail` 和 `compare_routes` 不允许触发 POI search 或 route generation。

## 澄清策略

澄清的目标不是多问问题，而是只在无法生成可执行路线时才问。

必须澄清：

- 城市或明确区域完全缺失，且上下文也没有。
- 出行目标过泛，例如“帮我安排一下”。
- 意图低置信度，无法判断是新规划、全量重规划、局部重规划还是路线追问。
- 局部重规划无法定位目标点，例如当前路线里有多个餐厅，用户只说“换一家”。

不应阻塞规划：

- 人数缺失，可默认 1 人。
- 预算缺失，可默认中等预算。
- 出发时间缺失，可默认 09:00。
- 出发点缺失，可默认城市中心或热门商圈。
- 口味、网红、室内、少排队等偏好可进入评分，不应变成长问卷。

话术原则：

- 默认只问一个最关键问题。
- 问题要短，并说明为什么要问。
- 能继承上下文时不要重复确认。

## 和 B 侧路线工具的边界

B 同学负责 POI 召回、路线候选生成、评分、局部替换和动态重规划。A 同学负责把用户自然语言整理成 B 能消费的结构化输入。

A 应提供给 B 的信息：

- `Intent` 或后续升级后的路线 planner request。
- 用户画像和策略权重。
- `soft_preferences`、`implicit_needs`、`must_include`。
- 动态事件的 `event_type` 和 `event_payload`。
- 当前路线、已完成点、锁定点、当前时间和当前位置。

B 不应该负责：

- 理解自然语言。
- 判断用户说的是全量重规划还是局部替换。
- 读取 LLM 输出长文本。
- 解析高德原始 JSON。

特别注意：

- `meal_stop` 和 `rest_stop` 要成为结构化字段，不要只靠关键词。
- `must_include` 无法满足时，B 应返回机器可读的 `unmet_requirements`，A 负责进入 trace 和用户回复。
- A 总结路线时优先引用 `Route.summary`、`Route.reasons`、`RouteStop.reason`、交通字段和评分字段。
- 不要让 LLM 编造新的 POI、价格、时间、交通路线。

## 和高德路线接入的边界

高德接入第一版目标是做路段信息补全：

```text
POI 顺序
  -> 查询高德相邻点路线
  -> 统一成项目字段
  -> 写入 RouteStop
  -> 用于评分和前端地图展示
```

`AmapService` 负责：

- 读取 `AMAP_WEB_SERVICE_KEY`。
- 调用高德 Web 服务路线接口。
- 处理无 key、超时、接口失败。
- 把高德原始返回转成项目统一字段。
- 高德不可用时 fallback 到本地距离估算。

统一字段：

```json
{
  "mode": "walk",
  "distance_meters": 1200,
  "duration_minutes": 16,
  "polyline": "121.473,31.230;121.480,31.232",
  "steps": [],
  "source": "amap"
}
```

`RouteStop` 中和上一站有关的字段：

- `travel_minutes_from_previous`
- `distance_km_from_previous`
- `transport_mode_from_previous`
- `polyline_from_previous`
- `amap_distance_meters_from_previous`
- `amap_duration_minutes_from_previous`
- `route_leg_source_from_previous`

A 侧注意事项：

- 不要把高德原始 JSON 透传给 B 或 C。
- 总结交通时使用统一字段。
- `route_leg_source_from_previous = fallback` 时，用户解释里要避免说得过度确定。
- 接入真实高德后，步行耗时可能明显变长，短时间窗路线被过滤是正常现象。

## 和 C 侧前端的边界

C 同学主要消费 `/api/chat`、路线卡片字段和 `agent_trace`。

A 需要保证：

- `/api/chat` 响应结构稳定。
- `message`、`routes`、`agent_trace`、`need_clarification`、`clarifying_question` 字段兼容。
- trace 至少保留 `step`、`label`、`status`。
- 新增 trace 字段时尽量有可读 label，方便前端中文化。
- 每轮 trace 应绑定到当前 assistant 消息，不要被下一轮覆盖。

未来 trace 建议分层：

- `understanding`：用户这句话被理解成什么。
- `state_merge`：保留、新增、修改、删除了哪些状态。
- `planning_policy`：为什么重规划或不重规划。
- `tool_result`：POI 和路线工具结果。
- `response_composer`：回复是否使用 LLM，是否 fallback。

前端可展示的状态变化摘要：

```text
保留：上海、2人、一日游、拍照
新增：meal_stop
修改：城市 上海 -> 杭州
```

## Response Composer 原则

回复生成必须基于结构化事实骨架，再由 LLM 润色。

事实骨架示例：

```json
{
  "kept": ["上海", "2人", "一日游", "拍照"],
  "added": ["meal_stop"],
  "changed": {},
  "removed": [],
  "route_summary": {
    "distance_km": 5.7,
    "travel_minutes": 35,
    "meal_stop": "某餐厅"
  },
  "system_status": {
    "query_understanding": "done",
    "route_generation": "done",
    "llm_summary": "fallback"
  }
}
```

用户可见回复可以是：

```text
我保留了你们上海两人一日游、喜欢拍照的设定，并加入吃饭节点。
这版路线包含拍照点和餐饮休息点，总路程约 5.7 公里，交通约 35 分钟。
```

注意：

- LLM 不可用时必须有 fallback 文案。
- 工具失败或未满足要求时不能假装成功。
- 路线点评接口只做点评，不重新规划。
- 交通方式要把 `walk`、`metro/taxi` 等字段映射成用户可读中文。

## Trace 契约

trace 是调试契约，不是装饰性“思考过程”。

建议每层至少包含：

| 层级 | step 示例 | 必须包含 |
| --- | --- | --- |
| `understanding` | `query_understanding` | `turn_type`、confidence、fallback 标记 |
| `state_merge` | `apply_query_delta` | `kept`、`added`、`changed`、`removed` |
| `planning_policy` | `select_policy` | 是否重规划、选择原因 |
| `tool_result` | `search_pois` / `generate_routes` | 候选数、路线数、未满足项 |
| `response_composer` | `summarize_routes` | LLM 是否可用、使用了哪些事实 |
| `evaluation` | `demo_case_assertions` | 失败层级、断言名、实际值 |

必须进入 trace 的情况：

- LLM 解析 fallback。
- LLM 总结 fallback。
- 高德路线 fallback。
- `must_include` 未满足。
- 意图低置信度。
- 澄清触发原因。
- 工具返回空结果。

## 推荐实施顺序

### 阶段 1：多轮状态稳定

目标：用户追加或修改需求时，不丢上下文、不乱覆盖主场景。

任务：

1. 检查现有 `MessageRouter`、`SessionState`、`ClarificationPolicy` 的实现。
2. 新增或补齐 `QueryUnderstanding` / `IntentDelta` schema。
3. 把 `apply_session_context` 升级为 `apply_query_delta`。
4. 在 `SessionState` 中引入 `trip_state`，保留 `last_intent` 兼容。
5. trace 增加 `kept / added / changed / removed`。
6. 补多轮回归测试。

### 阶段 2：路线结构化需求接入

目标：让路线工具消费结构化需求，而不是只看关键词。

任务：

1. planner request 增加 `soft_preferences`、`implicit_needs`、`must_include`。
2. 一日游默认加入 `meal_stop` 和 `rest_stop` 作为隐含需求。
3. 用户显式说吃饭时，把 `meal_stop` 升级为 `must_include`。
4. B 侧无法满足时，A 将 `unmet_requirements` 写入 trace 和回复。

### 阶段 3：交互式路线修改

目标：用户围绕当前路线持续编辑，而不是每次整条路线重来。

任务：

1. 支持 `active_route_id`。
2. 支持 `select_route`。
3. 支持 `replace_stop`、`remove_stop`、`lock_stop`。
4. 自然语言动态事件转成 `/api/routes/replan` 的结构化请求。
5. 回复中引用 `changed_stops`、`live_warnings`、`replan_reason`。

### 阶段 4：可评估 Agent

目标：知道 Agent 稳定性是否提升，而不是只看最终文案。

任务：

1. 扩展 demo case 为分层断言。
2. 每个 case 检查 understanding、state、routes、message、trace。
3. 失败时输出层级、断言名、期望值、实际值。
4. 提交前跑核心 case。
5. 增加 LLM 不可用和工具 fallback 场景。

## 核心验收用例

### 追加吃饭

输入：

```text
上海两人一日游，喜欢拍照
我还要吃饭
```

断言：

- `QueryUnderstanding.turn_type == add_constraint`
- `IntentDelta.added_must_include` 包含 `meal_stop`
- `TripState.city == 上海`
- `TripState.people_count == 2`
- `TripState.duration_hours == 8`
- `TripState.soft_preferences` 包含 `拍照` 和 `吃好`
- `TripState.must_include` 包含 `meal_stop`
- 至少一条路线包含餐饮/休息节点
- 路线不能全部都是 restaurant/cafe
- trace 中能看到保留和新增项

### 路线细节追问

输入：

```text
两个地点之间怎么过去
```

前置条件：session 中已有当前路线。

断言：

- `turn_type == route_detail`
- 不触发 POI search。
- 不触发 route generation。
- 回复基于当前路线中的相邻 stop 交通字段。

### 城市修改

输入：

```text
换成杭州吧
```

断言：

- `turn_type == modify_constraint`
- 只修改 city。
- 人数、预算、时长等未提到字段继承。
- trace 中显示 `changed: city 上海 -> 杭州`。

### 全量重规划

输入：

```text
少排队一点
```

断言：

- 继承城市、人数、时长、预算。
- 增加少排队偏好或优化目标。
- 重新生成候选路线。
- 不改硬预算。

### 局部重规划

输入：

```text
第二个点换个餐厅
```

断言：

- `turn_type == replace_stop`
- `target_stop_ref` 指向第二个 stop。
- 只替换目标 stop。
- `locked_stop_ids` 中的点不变。
- `active_route_id` 不变。

### 澄清

输入：

```text
周末帮我安排一日游
```

断言：

- 缺城市时触发澄清。
- 只问一个关键问题。
- 不同时追问人数、预算、出发点、口味等非必要字段。

## 常见风险

- 继续只维护词表，会导致自然语言覆盖越来越困难。
- 让 LLM 自由调工具，会造成过度重规划、上下文覆盖和工具误用。
- `TripState` 不成为主要状态源，`Intent` 默认值可能覆盖上一轮真实上下文。
- `meal_stop` / `rest_stop` 不进入 schema，路线策略会退回关键词规则。
- trace 只做展示，不暴露失败原因，会让调试变成猜测。
- `/api/chat` 字段随意变化，会影响 C 侧联调。
- 路线解释让 LLM 自由发挥，会编造交通、价格、时间或地点。

## 开发注意事项

- A 侧主要修改 `backend/app/api/chat.py`、`backend/app/agent/`、`backend/app/llm/`、`backend/app/services/profile_service.py` 和相关 tools。
- 如果改 `backend/app/schemas/`，必须同步前端类型和 `docs/api_contract.md`。
- 每次改后至少跑：

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

- 如果涉及路线、重规划或 trace，建议补对应测试或 demo case。
- 不要把 API key 写进代码，统一使用 `.env`。
- 不要让 AI 大范围重构别人负责的模块。

## 给 A 同学的实现判断标准

一个实现是否走在正确方向上，可以用这几个问题检查：

1. 用户本轮话语是否先被解释成结构化 `turn_type` 和 delta？
2. 未提到的城市、人数、时长、预算是否稳定继承？
3. 是否只有 `Policy / Planner` 决定重规划、局部重规划或只回答细节？
4. 路线事实是否都来自工具返回？
5. LLM 不可用、工具失败、高德 fallback 是否不会让 demo 崩？
6. trace 是否能说明“为什么这么做”和“哪里失败了”？
7. B/C 是否可以只消费稳定字段，而不理解 A 内部实现？

如果这些问题答案都是“是”，A 侧 Agent 编排就基本站稳了。
