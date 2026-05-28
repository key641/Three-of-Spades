# 出行规划 Agent 行为规格与路线图

更新时间：2026-05-23  
适用范围：A 同学 Agent / 后端编排为主，B 同学路线策略、C 同学前端体验协同。  
参考基准：[Anthropic Engineering - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 目标

把当前系统从“聊天触发路线生成”升级为“有状态、可解释、可调试、可回归评估的出行规划 Agent”。

核心判断：

- LLM 负责理解用户自然语言，不直接自由调度一切。
- `TripState` 负责记住旅行目标、约束、路线选择和上下文。
- `Policy / Planner` 负责基于状态和轮次类型选择稳定流程。
- 路线工具负责真实生成、调整和解释路线，不靠 LLM 编造路线事实。
- `Trace / Evaluation` 负责暴露每一层的理解、继承、工具结果和失败原因。

当前成熟度判断：方向正确，已经具备 `MessageRouter`、`turn_type`、`inherit_previous`、`preserve_scenario`、`apply_session_context` 和 demo case 的雏形；下一步要把它从“方向性路线图”补全为可执行的行为契约。

## 设计原则

### 1. LLM 做理解，不直接自由决策

LLM 只输出本轮用户话语的结构化理解。例如：

```text
我还要吃饭
```

应该被理解为：

```json
{
  "turn_type": "add_constraint",
  "inherit_previous": true,
  "preserve_scenario": true,
  "intent_delta": {
    "added_preferences": ["吃好"],
    "added_must_include": ["meal_stop"]
  }
}
```

系统最终是否继承城市、人数、时长、主场景，是否调用路线生成工具，必须由 `Policy / Planner` 和状态合并规则决定。

### 2. 明确区分约束层级

出行需求必须拆成四层：

- `hard_constraints`：城市、人数、时长、预算、开始时间等明确条件。
- `soft_preferences`：拍照、少排队、少走路、吃好等偏好。
- `implicit_needs`：根据业务常识推导出的建议项，例如一日游默认饭点、休息点。
- `must_include`：用户显式要求必须包含的节点，例如明确说“要吃饭”后的 `meal_stop`。

示例：

```text
两个人上海一日游，喜欢拍照
```

```json
{
  "hard_constraints": {
    "city": "上海",
    "people_count": 2,
    "duration_hours": 8
  },
  "soft_preferences": ["拍照"],
  "implicit_needs": ["meal_stop", "rest_stop"],
  "must_include": []
}
```

用户补充：

```text
我还要吃饭
```

状态应变成：

```json
{
  "hard_constraints": {
    "city": "上海",
    "people_count": 2,
    "duration_hours": 8
  },
  "soft_preferences": ["拍照", "吃好"],
  "implicit_needs": ["rest_stop"],
  "must_include": ["meal_stop"]
}
```

一日游默认建议包含饭点；用户明确说吃饭时，饭点从“建议包含”升级为“必须包含”。

### 3. 少量高层规则，词表只做 fallback

保留三类规则：

- 状态规则：`add_constraint` 继承上一轮，`route_detail` 不重新规划。
- 业务常识规则：一日游默认饭点/休息点，显式吃饭必须包含饭点。
- 安全和可观测规则：LLM 不可用必须显示，工具失败必须进入 trace。

词表只能作为 LLM 不可用时的 fallback，不作为主决策方式。

## 建议架构

```text
用户输入
  ↓
1. Query Understanding 用户话语理解
  ↓
2. IntentDelta 本轮变更
  ↓
3. TripState 旅行状态
  ↓
4. Policy / Planner 决策层
  ↓
5. Tools 路线和 POI 工具层
  ↓
6. Response Composer 回复生成
  ↓
7. Trace / Evaluation 可观测与评估
```

Anthropic 的有效 agent 建议可以落到这里：先保持简单 workflow，把 LLM 增强为带工具和记忆的系统，再通过清晰工具接口、环境反馈和评估闭环逐步提升，不一开始就引入重框架或完全自治 agent。

## Core Contracts

### 1. QueryUnderstanding

职责：只描述“用户这一句话是什么意思”。  
来源：优先 LLM JSON 输出，失败时由 fallback classifier 输出。  
所有权：A 同学 Agent 层，建议放在 `backend/app/agent/query_understanding.py` 或 `backend/app/agent/schemas.py`。  
边界：不得直接覆盖 `TripState`，不得直接调用路线工具。

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

- `我还要吃饭` 在有上一轮状态时必须是 `add_constraint`。
- `两个地点之间怎么过去` 在有当前路线时必须是 `route_detail`。
- `换成杭州吧` 必须标记为会修改城市的 `modify_constraint`，不能被当成普通聊天。

### 2. IntentDelta

职责：描述本轮对状态的增量修改。  
来源：`QueryUnderstanding` + 结构化解析 + fallback 词表增强。  
所有权：A 同学 Agent 层。  
边界：只表达变更，不保存完整旅行状态。

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

合并规则：

- `new_plan`：用 delta 初始化新的 `TripState`，旧路线仅保留在历史记录中。
- `add_constraint`：继承上一轮硬约束和主场景，只追加偏好或必须节点。
- `modify_constraint`：只修改 delta 明确指定的字段，未提到的字段保持不变。
- `remove_constraint`：只删除 delta 指定的偏好、约束或节点。
- 显式城市切换优先于 onboarding city 和上一轮 city。

### 3. TripState

职责：保存可持续编辑的旅行目标和当前路线上下文。  
来源：`SessionMemory`，由 `apply_query_delta` 写入。  
所有权：A 同学 Agent 编排层，B/C 只消费必要字段。  
边界：不保存 LLM 原始长文本推理，只保存可测试、可解释字段。

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
  "feedback_history": [
    {
      "turn_id": "turn_002",
      "type": "add_constraint",
      "summary": "新增吃饭节点"
    }
  ]
}
```

迁移策略：

- 短期兼容当前 `Intent`：`preferences` 映射到 `soft_preferences`，`avoid_tags` 保留为路线评分输入。
- 新增字段先进入 agent schema，再逐步同步到 route planner 和前端展示。
- `last_intent` 可以继续保留，但必须降级为兼容字段，不能再作为唯一状态源。

### 4. Route Planner Contract

路线工具必须消费 `soft_preferences`、`implicit_needs`、`must_include`，而不是只靠关键词。

节点语义：

- `meal_stop`：餐厅、小吃、咖啡、轻食等可满足正餐或休息的节点。
- `rest_stop`：咖啡、室内空间、公园休息点、低强度街区等可降低疲劳的节点。
- `must_include`：必须出现在至少一条主推路线中；无法满足时 trace 必须标出原因。
- `implicit_needs`：优先满足；若因候选点不足或时间不足被跳过，trace 必须可见。

路线形态：

```text
上午：主兴趣点
中午：餐饮/休息
下午：主兴趣点
傍晚：轻量打卡/夜景
```

避免：

```text
餐厅 -> 餐厅 -> 餐厅
```

## Policy Matrix

| `turn_type` | 继承城市/人数/时长 | 继承主场景 | 是否重规划 | 是否只答细节 | 状态写入 |
| --- | --- | --- | --- | --- | --- |
| `new_plan` | 否 | 否 | 是 | 否 | 初始化 `TripState` |
| `add_constraint` | 是 | 是 | 是 | 否 | 追加偏好、隐含需求或必须节点 |
| `modify_constraint` | 是，除非 delta 明确修改 | 默认是 | 是 | 否 | 修改 delta 指定字段 |
| `remove_constraint` | 是 | 是 | 是 | 否 | 删除 delta 指定字段 |
| `route_detail` | 是 | 是 | 否 | 是 | 不改路线，仅记录问答 |
| `select_route` | 是 | 是 | 否 | 否 | 更新 `active_route_id` |
| `replace_stop` | 是 | 是 | 局部重算 | 否 | 更新目标 stop，保留 locked stops |
| `remove_stop` | 是 | 是 | 局部重算 | 否 | 删除目标 stop |
| `lock_stop` | 是 | 是 | 否 | 否 | 更新 `locked_stop_ids` |
| `compare_routes` | 是 | 是 | 否 | 是 | 不改路线，仅生成比较解释 |
| `general_chat` | 否 | 否 | 否 | 否 | 不写旅行状态 |

默认冲突处理：

- 用户显式修改字段优先于上一轮状态。
- 用户未提到字段必须继承，不允许 LLM 用默认值覆盖。
- `add_constraint` 不允许把拍照路线改成纯美食路线，除非用户明确说“改成美食路线”。
- `route_detail`、`compare_routes` 不允许触发 POI search 或 route generation。

## Trace / Evaluation Contract

Trace 必须按层暴露，便于前端和 regression suite 判断哪一层错了。

| 层级 | 示例 step | 必须包含 | 失败状态 |
| --- | --- | --- | --- |
| `understanding` | `query_understanding` | `turn_type`、confidence、fallback 标记 | `fallback` / `error` |
| `state_merge` | `apply_query_delta` | `kept`、`added`、`changed`、`removed` | `error` |
| `planning_policy` | `select_policy` | 选择的流程、是否重规划、原因 | `error` |
| `tool_result` | `search_pois` / `generate_routes` | 候选数、路线数、未满足 must_include | `fallback` / `error` |
| `response_composer` | `summarize_routes` | LLM 是否可用、使用哪些结构化事实 | `fallback` / `error` |
| `evaluation` | `demo_case_assertions` | 失败层级、断言名称、实际值 | `fail` |

用户可见回复必须基于结构化事实骨架，再由 LLM 润色。

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

用户可见回复示例：

```text
我保留了你们上海两人一日游、喜欢拍照的设定，并加入吃饭节点。
这版路线包含拍照点和餐饮休息点，总路程约 5.7 公里，交通约 35 分钟。
```

## 里程碑

### M1：多轮理解稳定版

目标：不丢上下文，不乱覆盖主场景，让每次用户补充都能解释成 delta。

当前已具备：

- `MessageRouter` 已有 `turn_type`、`inherit_previous`、`preserve_scenario`。
- `apply_session_context` 已能在部分追问中继承上一轮 `Intent`。
- 已有测试覆盖“我还要吃饭”保留上海两人拍照一日游的大方向。

关键缺口：

- 还没有独立的 `QueryUnderstanding` / `IntentDelta` schema。
- `last_intent` 仍是唯一主要状态源，缺少显式 `TripState`。
- trace 只显示流程步骤，尚未稳定输出 `kept / added / changed / removed`。

任务：

1. 新增 `QueryUnderstanding` / `IntentDelta` schema。
2. 让 `MessageRouter` 输出完整结构化理解，fallback 只兜底 `turn_type` 和关键 delta。
3. 把 `apply_session_context` 升级为 `apply_query_delta`。
4. 在 `SessionState` 中引入 `TripState`，并保持旧 `last_intent` 兼容。
5. Trace 增加 `kept / added / changed / removed`。
6. 补多轮回归测试。

验收 case：

```text
用户：上海两人一日游，喜欢拍照
用户：我还要吃饭

断言：
- QueryUnderstanding.turn_type == add_constraint
- IntentDelta.added_must_include 包含 meal_stop
- TripState.city == 上海
- TripState.people_count == 2
- TripState.duration_hours == 8
- TripState.soft_preferences 包含 拍照、吃好
- TripState.must_include 包含 meal_stop
- Trace.state_merge.added 包含 meal_stop
```

### M2：真实路线结构版

目标：路线像一天安排，不像 POI 列表。

任务：

1. Route planner request 增加 `soft_preferences`、`implicit_needs`、`must_include`。
2. 一日游 `duration_hours >= 6` 默认加入 `implicit_needs: ["meal_stop", "rest_stop"]`。
3. 半日游 `duration_hours >= 4` 默认加入 `implicit_needs: ["rest_stop"]` 或 `["cafe"]`。
4. `must_include: ["meal_stop"]` 必须驱动路线中出现餐饮/休息节点。
5. 餐饮节点插入到午餐、晚餐或中途休息时间段，不覆盖主兴趣点。
6. 同类点去重，避免连续多个餐厅或连续多个纯打卡点。
7. 工具无法满足 `must_include` 时写入 trace。

验收 case：

```text
输入：上海两人一日游，喜欢拍照；我还要吃饭

断言：
- 至少一条主推路线包含 meal_stop
- 至少一条主推路线包含 photo/citywalk/landmark 类主兴趣点
- 不允许所有 stop 都是 restaurant/cafe
- Trace.tool_result 未满足项为空，或明确说明无法满足原因
```

### M3：交互式修改版

目标：用户能围绕一条路线持续编辑，而不是每次都整条路线重来。

任务：

1. `TripState` 支持 `active_route_id`。
2. 支持 `select_route` 更新当前路线。
3. 支持 `replace_stop`，只替换目标 stop。
4. 支持 `remove_stop`，只删除目标 stop 并局部重排。
5. 支持 `lock_stop`，后续重规划保留锁定节点。
6. 支持 `compare_routes`，只解释不同路线的取舍，不触发重规划。

验收 case：

```text
用户：第二个点换个餐厅

断言：
- QueryUnderstanding.turn_type == replace_stop
- target_stop_ref 指向第二个 stop
- 只有目标 stop 被替换
- locked_stop_ids 中的点不变
- active_route_id 不变
```

### M4：可评估 Agent 版

目标：知道 agent 是不是越来越稳定，而不是只看回复像不像。

当前已具备：

- `scripts/demo_cases.py` 能直接调用 `AgentOrchestrator`。
- 已能检查城市、路线数量、trace 是否存在。

关键缺口：

- demo case 仍偏冒烟测试，缺少分层断言。
- 失败输出不能稳定定位到理解、状态继承、路线结构、总结或前端展示哪一层。

任务：

1. 将 `DemoCase` 扩展为分层断言模型。
2. 每个 case 至少检查 `understanding`、`state`、`routes`、`message`、`trace`。
3. 失败时输出层级、断言名、期望值、实际值。
4. 核心 case 进入提交前必跑列表。
5. 增加 LLM 不可用场景，确保 fallback 明确暴露。

建议断言模型：

```json
{
  "name": "上海拍照一日游追加吃饭",
  "turns": [
    "上海两人一日游，喜欢拍照",
    "我还要吃饭"
  ],
  "assertions": {
    "understanding": {
      "last_turn_type": "add_constraint"
    },
    "state": {
      "city": "上海",
      "people_count": 2,
      "duration_hours": 8,
      "must_include_contains": ["meal_stop"],
      "soft_preferences_contains": ["拍照", "吃好"]
    },
    "routes": {
      "min_routes": 1,
      "must_have_stop_type": ["meal_stop"],
      "must_not_all_stop_types": ["restaurant", "cafe"]
    },
    "message": {
      "must_mention": ["保留", "吃饭"]
    },
    "trace": {
      "must_have_steps": ["query_understanding", "apply_query_delta", "generate_routes"],
      "must_expose_fallback": true
    }
  }
}
```

核心 case：

- 上海两人一日游喜欢拍照。
- 我还要吃饭。
- 少排队一点。
- 两个地点之间怎么过去。
- 换成杭州。
- 不要这个景点。
- 晚饭换一家。
- LLM 总结不可用时使用结构化 fallback。

## 下一步建议

优先做 M1 的完整版本，因为它是后续 M2/M3/M4 的状态基础。

建议拆分：

1. 新增 `backend/app/agent/query_understanding.py`。
2. 新增 `QueryUnderstanding` / `IntentDelta` schema。
3. 让 `MessageRouter` 输出更完整的结构化理解。
4. 把 `apply_session_context` 升级为 `apply_query_delta`。
5. 在 `SessionState` 中引入 `trip_state`，旧 `last_intent` 暂时保留兼容。
6. Trace 增加 `kept / added / changed / removed`。
7. demo case 加入分层断言。

## 当前风险

- 如果继续只维护词表，后续会越来越难覆盖自然语言表达。
- 如果让 LLM 直接自由调工具，容易出现过度重规划、上下文覆盖和工具误用。
- 如果 `meal_stop` / `rest_stop` 不进入 schema 和 route planner contract，M2 会退回关键词规则。
- 如果 `TripState` 不成为唯一状态源，`Intent` 默认值仍可能覆盖上一轮真实上下文。
- 如果没有分层 regression case，agent 每次优化都可能修好一个场景、弄坏另一个场景。

## 一句话方向

用 LLM 理解复杂语言，用显式状态和少量高层规则保证流程稳定，用路线工具执行真实规划，用 trace 和分层测试让系统可调试、可评估、可持续演进。
