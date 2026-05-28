# 版本更新协作文档

这份文档用于长期记录团队每次重要更新，帮助不同协作者快速了解：

- 本次提交改了什么。
- 影响了哪些模块和接口。
- 对 A/B/C 各自负责部分有什么影响。
- 后续联调、测试、代码评审时需要重点关注什么。

建议每次合并到 `main` 后都追加一条记录。小的文案或样式微调可以合并记录，接口、数据结构、核心流程、跨模块行为变化必须单独记录。

## 维护规则

1. 每条记录以提交 hash、提交信息、日期、负责人开头。
2. 先写用户可感知变化，再写技术实现变化。
3. 如果影响接口字段、数据结构或跨端协作，需要在“协作影响”里明确写出。
4. 如果存在 mock、临时开关、未接真实后端等状态，必须写在“风险与注意事项”里。
5. 如果改动涉及前后端契约，需要同步更新 `docs/api_contract.md`。

## 记录模板

```markdown
## YYYY-MM-DD - <commit short hash> - <type(scope): summary>

负责人：

### 更新概览

- 

### 主要变更

- 

### 涉及文件

- 

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 |  |  |
| B 同学：POI / 路线策略 |  |  |
| C 同学：前端 / UI |  |  |

### 风险与注意事项

- 

### 建议验证

- 
```

---

## 2026-05-24 - `8ae5b55` - `feat(agent): promote structured delta understanding`

负责人：Agent / 后端编排 / A 同学，前端 trace 调试体验 / C 侧联调

### 更新概览

本次继续把多轮理解从“规则补丁”推进到更接近未来 Agent 架构的形态：多轮时优先让 LLM 根据上一轮 `TripState` 输出结构化 `QueryUnderstanding + IntentDelta`，后端只做 schema 校验、标签归一化和确定性 reducer 合并。规则不再承担主要语义理解，只在 LLM 断连、返回非法 JSON 或空 delta 时做保守兜底。

前端侧同步增强了 Agent 思考过程：运行中仍可实时看到处理步骤，完成后默认折叠，但展开后能看到每一步的结构化 details，方便排查“哪一步理解错、哪一步合并错、是不是 fallback 导致”。

### 主要变更

- 多轮理解主路径升级：
  - 新增 `_parse_query_delta()`，多轮时优先调用 LLM 输出 `QueryUnderstanding + IntentDelta`。
  - 新增 `_llm_parse_query_delta()`，提示模型不要重写完整 Intent，而是比较用户本轮消息和上一轮 `TripState` 后输出 delta。
  - 首轮仍由完整 `Intent` 初始化 `TripState`；多轮才进入 structured delta 主路径。
  - `apply_query_delta` trace 新增 `source`，可区分 `llm_structured_delta`、`rule_fallback_delta`、`initial_intent_snapshot`。

- Delta validator 和标签归一化：
  - 新增 `_normalize_intent_delta()`，对 LLM 输出做字段过滤和归一化。
  - 约束 LLM 只能输出系统支持的 canonical labels。
  - `preferences` 支持归一：`吃饭/好吃/餐厅 -> 吃好`、`便宜/高性价比 -> 更省钱`、`出片/打卡/网红 -> 拍照`、`城市漫步/逛逛 -> citywalk` 等。
  - `avoid_tags` 支持归一：`人多/拥挤 -> 人流密集`、`贵/高价 -> 太贵`、`走路多/太累 -> 步行多` 等。
  - 前端 onboarding 画像、seed 用户画像、LLM intent 结果、多轮状态合并、delta 比较都接入同一套 canonical 规则。

- 明确显式约束优先级：
  - `add_constraint` 不再等于“所有硬约束都继承旧状态”。
  - 本轮明确说出的城市、人数、时长、预算、开始时间可以覆盖旧状态。
  - “有朋友和我一起 / 双人 / 两个人”会把 `people_count` 更新为 2。
  - “不要吃饭 / 不安排吃饭”会移除 `吃好` 偏好和 `meal_stop`。
  - `meal_stop` 从隐含建议升级为显式必须时，不再在 trace 中显示成“新增吃饭节点；移除吃饭节点”。

- 前端 trace 调试体验增强：
  - 完成后 Agent 思考过程默认折叠，不再占用大量空间。
  - 桌面端不再隐藏 `.trace-toggle`，完成后仍能看到折叠入口。
  - 展开后每个 step 会显示结构化 details chips，例如本轮类型、是否继承、delta 来源、保留/新增/修改/移除、候选点数量、路线标题等。
  - 运行中仍保持实时展开，便于观察后台处理进度。

- 测试补充：
  - 覆盖 LLM structured delta 作为多轮状态更新主路径。
  - 覆盖 LLM delta 失败时规则 fallback 仍能处理明确约束。
  - 覆盖显式人数覆盖旧状态、否定吃饭移除 meal stop。
  - 覆盖所有偏好和避开标签的 canonical 归一化。
  - 覆盖前端画像字段进入后端 profile/intent 前会归一化。

### 涉及文件

- Agent 状态与理解：
  - `backend/app/agent/orchestrator.py`
  - `backend/app/agent/intent_context.py`
  - `backend/app/agent/intent_enhancer.py`
  - `backend/app/services/profile_service.py`

- 后端测试：
  - `backend/app/tests/test_orchestrator_intent_flow.py`
  - `backend/app/tests/test_query_delta.py`
  - `backend/app/tests/test_intent_enhancer.py`
  - `backend/app/tests/test_profile_request_sync.py`

- 前端 trace 展示：
  - `frontend/src/components/AgentTrace.tsx`
  - `frontend/src/styles/globals.css`

- 文档：
  - `docs/version_log.md`
## 2026-05-24 - `a00f0aa` - `feat(route): 接入高德路线字段并补充协作文档`

负责人：A 同学 / 后端外部 API 接入，B 同学路线策略联调，C 同学地图展示预留

### 更新概览

本次把后端路线规划链路接入高德 Web 服务路线能力。系统现在会优先通过高德计算相邻点之间的真实距离、耗时、路线折线和步骤信息；如果没有配置 key、网络不可用或高德接口失败，则自动回退到本地距离估算，保证 demo 流程不被外部接口阻断。

同时补充了高德接入规划和字段契约文档，并把文档改成中文，方便 B 同学直接理解应该使用哪些路线字段做评分和策略优化。

### 主要变更

- 新增 `AmapService`：
  - 读取 `AMAP_WEB_SERVICE_KEY`。
  - 调用高德 Web 服务步行/驾车路线接口。
  - 将高德原始返回整理成项目自己的 `RouteLeg` 字段。
  - 高德不可用时返回 fallback 路段，避免路线生成中断。

- 扩展 `RouteStop` 路线字段：
  - 新增 `lat`、`lng`，供前端地图标记使用。
  - 新增 `polyline_from_previous`，表示上一站到当前站的地图折线。
  - 新增 `amap_distance_meters_from_previous`、`amap_duration_minutes_from_previous`，保留更细粒度的高德距离和耗时。
  - 新增 `route_leg_source_from_previous`，用于区分当前路段来自 `amap` 还是 `fallback`。

- `RouteService` 接入高德路段补全：
  - 保持原有 POI 组合和路线策略逻辑不变。
  - 在生成每个 stop 时补全真实路段距离、耗时、交通方式和 polyline。
  - B 同学仍然使用 `travel_minutes_from_previous`、`distance_km_from_previous` 和 `transport_mode_from_previous` 做评分。

- 文档补充：
  - 新增 `docs/amap_route_integration_plan.md`，说明整体方案、分工、数据流、B/C 使用方式和测试结果。
  - 新增 `docs/amap_route_contract.md`，说明 `RouteStop` 新字段和 B 同学评分建议。
  - 两份文档均已改为中文说明。

- 前端类型同步：
  - `frontend/src/api/types.ts` 增加地图和高德路段字段，为后续 C 同学接高德 JS 地图展示做准备。

### 涉及文件

- `backend/app/services/amap_service.py`
- `backend/app/services/route_service.py`
- `backend/app/schemas/route.py`
- `backend/app/config.py`
- `backend/app/tests/test_amap_service.py`
- `backend/app/tests/test_route_plan.py`
- `frontend/src/api/types.ts`
- `.env.example`
- `docs/amap_route_integration_plan.md`
- `docs/amap_route_contract.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 多轮状态更新主路径变为 LLM structured delta + deterministic reducer。 | 后续新增语义类型时优先扩展 `IntentDelta` schema 和 validator，不要继续把理解逻辑堆在 `_build_intent_delta` 规则里。 |
| A 同学：Agent / 后端 | trace 能区分 `llm_structured_delta` 和 `rule_fallback_delta`。 | 排查状态 bug 时先看 `parse_query_delta` 和 `apply_query_delta.details.source`。 |
| B 同学：POI / 路线策略 | A 侧会更稳定地产出 canonical 偏好、避开标签和 `meal_stop/rest_stop`。 | B 侧后续消费规划需求时，应直接对齐 canonical labels，不要再依赖用户原话。 |
| C 同学：前端 / UI | Agent 思考过程完成后保留折叠入口，展开后能看到 details。 | 如果后续新增 trace details 字段，前端可以继续复用 details chips，不需要每个字段都定制组件。 |

### 风险与注意事项

- LLM structured delta 是主路径，但依赖模型网关稳定性；如果发生 `ConnectError`，系统会退回 `rule_fallback_delta`。
- 规则 fallback 必须保持保守，避免 LLM 失败时用 fallback Intent 的默认值误改人数、时长、预算等硬状态。
- canonical labels 目前仍是有限枚举；未来 B/C 如果新增策略标签，需要同步扩展 validator 的 allowed values。
- 当前版本还没有把 `/api/chat/stream` 的 NDJSON 事件和 `AgentTraceStep.details` 完整写入 `docs/api_contract.md`，后续应补齐。
| A 同学：Agent / 后端 | 后端已具备高德路线接口封装，Agent 后续可以继续通过 `RouteService` 获取真实路段字段。 | 需要在本地 `.env` 配置 `AMAP_WEB_SERVICE_KEY`；不要把高德原始 JSON 直接暴露给路线策略或前端。 |
| B 同学：POI / 路线策略 | 可以直接使用 `RouteStop` 中的真实距离、耗时、交通方式和来源字段做评分。 | 高德真实步行耗时会比原来的直线估算更长，短时间窗路线可能被过滤，需要考虑 taxi/metro 等交通方式切换策略。 |
| C 同学：前端 / UI | 前端类型已包含 `lat`、`lng` 和 `polyline_from_previous`，后续可用高德 JS API 画 marker 和路线折线。 | 前端地图接入时需要确认使用的是 JS API key 和安全密钥；当前完成的是后端 Web 服务 key 链路。 |

### 风险与注意事项

- 当前后端路线链路已验证高德 key 生效，但普通沙盒环境不允许联网时会走 fallback；真实运行环境需要允许后端访问 `restapi.amap.com`。
- 接入真实步行路线后，4 小时时间窗下部分路线会因为耗时变长被过滤；8 小时时间窗已验证可以正常生成路线并返回 `source=amap` 的路段字段。
- 当前只做两点之间的路段补全，尚未实现全局最优路线算法、实时路况、公交换乘细节或高德 MCP。
- 后端虚拟环境目前缺少 `pytest`，完整 pytest 命令无法运行；已用定向契约检查和 Python 编译检查验证本次核心链路。

### 建议验证

```bash
cd backend
$env:PYTHONPATH='.'
pytest app/tests -q
```

.\.venv\Scripts\python.exe - <<'PY'
from app.services.amap_service import AmapService, GeoPoint

leg = AmapService(timeout_seconds=10).route_leg(
    origin=GeoPoint(lat=31.2304, lng=121.4737),
    destination=GeoPoint(lat=31.2397, lng=121.4998),
    mode="walk",
)
print(leg.source, leg.distance_meters, leg.duration_minutes, bool(leg.polyline))
PY
```

期望联网环境下输出 `amap`，并有距离、耗时和 polyline。

```bash
cd frontend
npm.cmd run build
```

手动联调建议：

- 首轮输入“我一个人在上海玩一天，想拍照和吃饭”。
- 第二轮输入“我不要吃饭，有朋友和我一起”。
- 展开 Agent 思考过程，期望看到：`parse_query_delta` 成功时 source 为 `llm_structured_delta`；人数从 1 改为 2；移除 `吃好/meal_stop`；如果 LLM 断连，则 source 为 `rule_fallback_delta` 且前端能清楚展示 fallback 来源。

---

## 2026-05-24 - `788bac6` - `feat(agent): add state tracing and streaming thinking UI`

负责人：Agent / 后端编排 / A 同学，前端 trace 展示 / C 侧联调

### 更新概览

本次把 A 侧 Agent 从“能生成路线”继续推进到“能解释自己每一步在做什么”。后端新增结构化 TripState / IntentDelta / QueryUnderstanding 契约，并通过 `/api/chat/stream` 实时输出 Agent 处理步骤。前端的“Agent 思考过程”不再只显示固定说明，而是能展示本轮具体判断结果，例如“判定为补充需求”“继承上一轮上下文”“新增吃饭节点”“召回 N 个候选点”“生成 N 条候选路线”。

同时补充了 Agent roadmap 和 B/C 支持需求文档，明确哪些能力 A 侧可以先推进，哪些能力未来需要 B 侧路线策略和 C 侧前端展示配合。

### 主要变更

- Agent 状态契约增强：
  - 新增 `QueryUnderstanding`，记录本轮话术类型、是否继承上一轮、是否保留场景、是否引用上一轮路线。
  - 新增 `IntentDelta`，描述本轮新增、修改、移除的硬约束、软偏好、隐含需求和必须包含节点。
  - 新增 `TripState`，作为跨轮路线状态容器，保存城市、人数、时长、预算、场景、偏好、避开标签、隐含需求、必须包含节点、当前路线等信息。

- 多轮状态合并增强：
  - 新增 `apply_query_delta`，把本轮理解结果合并进上一轮 `SessionState.trip_state`。
  - “我还要吃饭”这类补充需求会保留上一轮上海、2 人、8 小时、拍照场景，并把 `meal_stop` 从隐含建议提升为必须包含节点。
  - Agent 回复正文会把关键状态变化用易懂话术提前说明，例如“我保留了上海、2人、8小时、拍照的设定，新增了吃饭节点。”

- 流式接口新增：
  - 新增 `POST /api/chat/stream`。
  - 使用 NDJSON 逐步返回：`progress`、`final`、`error`。
  - `AgentOrchestrator.handle_message` 支持 `progress_callback`，在 route_message、parse_intent、state merge、画像读取、POI 召回、路线生成、总结等节点实时发出 trace。

- Trace 结构化增强：
  - `AgentTraceStep` 新增 `details` 字段。
  - 后端关键步骤会返回结构化结果：
    - 消息路由：`intent_type`、`turn_type`、是否继承、是否保留场景、置信度。
    - 意图解析：城市、人数、开始时间、时长、预算、偏好、避开标签、场景。
    - 状态合并：保留、新增、修改、移除项。
    - 用户画像：偏好、避开标签、画像 tags。
    - 策略权重：quality、queue、distance、budget、preference。
    - POI 召回：候选点数量、城市、前几个 POI 名称。
    - 路线生成：路线数量、路线标题、目标类型。

- 前端 Agent 思考过程升级：
  - `useChat` 改为调用 `sendChatMessageStream`，发送后实时接收 progress trace。
  - `PlannerPage` 在 loading 时展示 `liveTrace`，用户能看到后台步骤逐步出现。
  - `AgentTrace` 新增“Agent 思考过程”摘要区。
  - 新增 `frontend/src/utils/agentThinking.ts`，把后端 `details` 翻译成用户能读懂的话。
  - mock 模式也补齐结构化 trace，方便后端未启动时预览同样效果。

- 文档补充：
  - 新增 `docs/agent_roadmap.md`，把原 roadmap 升级为 Agent 行为规格，包含 Core Contracts、Policy Matrix、M1/M2/M4 验收方向。
  - 新增 `docs/bc_agent_support_requirements.md`，说明未来如果要推进 meal/rest stop、路线局部编辑、路线解释、前端 trace 展示等能力，需要 B/C 侧提供哪些字段和交互支持。

- 测试补充：
  - 新增 `backend/app/tests/test_query_delta.py`，覆盖状态合并、隐含需求、必须包含节点等行为。
  - 新增 `backend/app/tests/test_chat_stream.py`，验证 `/api/chat/stream` 会先输出 progress，再输出 final。
  - 扩展 `test_orchestrator_intent_flow.py`，覆盖补充吃饭需求时 trace details 必须带出 `turn_type=add_constraint`、继承上一轮、以及新增 `meal_stop`。

### 涉及文件

- Agent 状态与编排：
  - `backend/app/agent/schemas.py`
  - `backend/app/agent/intent_context.py`
  - `backend/app/agent/memory.py`
  - `backend/app/agent/orchestrator.py`
  - `backend/app/schemas/chat.py`

- 后端 API：
  - `backend/app/api/chat.py`

- 后端测试：
  - `backend/app/tests/test_query_delta.py`
  - `backend/app/tests/test_chat_stream.py`
  - `backend/app/tests/test_orchestrator_intent_flow.py`

- 前端 API / 状态 / 展示：
  - `frontend/src/api/chatApi.ts`
  - `frontend/src/api/types.ts`
  - `frontend/src/hooks/useChat.ts`
  - `frontend/src/pages/PlannerPage.tsx`
  - `frontend/src/components/AgentTrace.tsx`
  - `frontend/src/utils/agentThinking.ts`
  - `frontend/src/styles/globals.css`

- 文档：
  - `docs/agent_roadmap.md`
  - `docs/bc_agent_support_requirements.md`
  - `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | Agent 已有更清晰的理解层、状态层、delta 合并层和 trace 层。 | 后续新增多轮能力时优先扩展 `TripState` / `IntentDelta`，不要把状态散落在 router、intent、memory 各处。 |
| A 同学：Agent / 后端 | `/api/chat/stream` 已可实时输出后台处理步骤。 | 如果部署环境或代理不支持流式响应，需要前端 fallback 到 `/api/chat`，或统一网关配置。 |
| B 同学：POI / 路线策略 | A 侧已能表达 `meal_stop`、`rest_stop`、`must_include`、`implicit_needs` 等规划需求。 | 当前 B 侧 route planner 还没有完整消费这些 schema，未来要支持“必须安排吃饭/休息”时需要在路线生成契约中明确 stop type 和约束语义。 |
| B 同学：POI / 路线策略 | 前端 trace 会展示 POI 召回数量和路线生成数量。 | 如果候选点不足或路线为空，建议 B 侧未来返回更明确的过滤原因，方便 A/C 展示可解释 fallback。 |
| C 同学：前端 / UI | 前端现在能实时展示 Agent 处理过程，而不是等最终结果。 | UI 应继续把 `details` 翻译成用户语言，不展示原始内部字段名；不要展示模型原始链路推理，只展示可解释步骤和结果。 |
| C 同学：前端 / UI | `AgentTraceStep.details` 是新增可选字段。 | 老接口只返回 `step/label/status` 时仍需兼容；新增 step 或 status 时要同步 `agentThinking.ts` 和 trace icon 映射。 |

### 风险与注意事项

- `/api/chat/stream` 是新增接口，前端真实联调时需要确认 `VITE_API_BASE_URL` 指向运行了新代码的后端；旧后端只会有 `/api/chat`，会返回 404。
- Vite `.env` 只在 dev server 启动时读取；如果切换 `VITE_API_BASE_URL` 或 mock 开关，需要重启前端 dev server。
- `AgentTraceStep.details` 目前还没有同步进 `docs/api_contract.md`，后续需要补充 `/api/chat/stream` 的 NDJSON 事件格式和 trace details 字段说明。
- 当前 `meal_stop/rest_stop` 已进入 A 侧状态语义，但 B 侧路线规划还需要后续按 schema 消费，否则只能部分体现在偏好和文本解释里。
- 当前 trace 是“可解释处理过程”，不是模型原始 chain-of-thought；前端文案应继续避免展示不可控或过细的内部推理。

### 建议验证

```bash
cd backend
$env:PYTHONPATH='.'
pytest app/tests -q
```

```bash
cd frontend
npm.cmd run build
```

手动联调建议：

- 启动新后端，确认 `/api/chat/stream` 可访问。
- 首轮输入“我想两个人在上海一日游，喜欢拍照”。
- 第二轮输入“我还要吃饭”。
- 期望前端 Agent 思考过程实时显示：本轮判定为补充需求、继承上一轮上下文、保留上海/2 人/8 小时/拍照、新增吃饭节点，并继续展示 POI 召回和路线生成结果。

---

## 2026-05-21 - `pending` - `fix(agent): adapt route explanations to enriched route fields`

负责人：Agent / 后端编排 / A 同学

### 更新概览

本次针对 LYNN 合入后的 POI/RouteStop 丰富字段做 A 侧适配。Agent 现在能更准确解释新路线字段中的组合交通方式，并在没有候选路线时返回明确的“候选点不足”提示，不再误说已经生成路线。同时 `_summarize_route_result` 会把 B 侧新增的站点解释字段传给 LLM，便于后续生成更具体的路线总结。

### 主要变更

- `RouteDetailHandler` 扩展交通方式映射：
  - 支持 `metro/bike`、`metro/bus`、`drive/taxi` 等组合交通。
  - 支持单项 `metro`、`taxi`、`walk`、`bike`、`bus`、`drive` 的中文解释。

- `AgentOrchestrator._summarize_route_result` 调整：
  - 当 `routes=[]` 时直接返回候选点不足提示，包含当前城市名。
  - LLM 总结输入新增 `total_travel_minutes`、`total_distance_km`。
  - 每个 stop 传入 `district`、`address`、`travel_minutes_from_previous`、`distance_km_from_previous`、`transport_mode_from_previous`、`walking_intensity`、`recommended_transport`、`highlight_text`、`ugc_tip`、`reason`。

- 新增 A 侧 demo case 脚本：
  - `scripts/demo_cases.py` 直接调用 `AgentOrchestrator`。
  - 覆盖上海路线生成、多轮调整、路线交通追问、北京/杭州城市意图识别。
  - 当前用于区分 A 侧意图/上下文是否稳定，以及 B 侧数据是否覆盖对应城市。

- `docs/api_contract.md` 补充 `RouteStop` 新字段说明。

- `AgentOrchestrator` 路线总结提示词增强：
  - 要求聊天回复文本优先使用 `total_distance_km`、`total_travel_minutes`、`highlight_text`、`ugc_tip`、`reason`、`transport_mode_from_previous`、`distance_km_from_previous` 等结构化字段。
  - LLM 不可用时，`message` 会明确提示“LLM 总结不可用”，再展示路线引擎生成的结构化结果，不再伪装成正常 LLM 总结。
  - `AgentTrace` 折叠状态会标出 fallback/error 数量，前端可以同时看到路线输出和系统运行问题。

- `MessageRouter` 新增结构化轮次类型：
  - `MessageRoute` 增加 `turn_type`、`inherit_previous`、`preserve_scenario`。
  - “我还要吃饭 / 加一个餐厅 / 也想拍照”这类追问会归为 `add_constraint`，默认继承上一轮路线意图。
  - `apply_session_context` 对 `add_constraint` 保留上一轮城市、人数、时长、开始时间和主场景，只合并新增偏好，避免“上海两人拍照一日游 + 吃饭”被覆盖成纯美食路线。

### 涉及文件

- `backend/app/agent/route_detail_handler.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_route_detail_handler.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `backend/app/tests/test_demo_cases_script.py`
- `scripts/demo_cases.py`
- `scripts/README.md`
- `docs/api_contract.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 路线解释现在能消费 B 侧新增字段。 | 后续做更强路线解释时，优先使用结构化字段，不要让 LLM 编造交通和站点信息。 |
| B 同学：POI / 路线策略 | `transport_mode_from_previous` 的组合值会被 Agent 翻译给用户。 | 推荐交通字段如果新增取值，需要同步 A/C 更新映射。 |
| C 同学：前端 / UI | API 文档已补充 RouteStop 新字段。 | 前端可以逐步展示 `highlight_text`、`ugc_tip`、`reason`、`recommended_transport` 等字段。 |

### 风险与注意事项

- A 侧 demo case 当前显示上海路线可生成，北京/杭州城市能识别但 routes 为 0，说明 seed 数据主要覆盖上海。
- 空路线提示只处理“候选不足”场景；如果后续有城市但被强约束过滤空，需要 B/A 再细化提示原因。

### 建议验证

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s app\tests
```

```bash
cd frontend
npm.cmd run build
```

```bash
.\backend\.venv\Scripts\python.exe scripts\demo_cases.py --verbose
```

---

## 2026-05-21 - `cac0a27` - `feat(agent): route message intent before planning`

负责人：Agent / 后端编排 / A 同学

### 更新概览

本次将 `/api/chat` 的主流程从“先用关键词判断是否路线相关”升级为“先做消息路由，再分发到对应 handler”。词表仍作为兜底，但不再承担主要决策职责。新增 `route_detail_question` 分支后，用户追问“刚刚那俩地之间怎么过去”时，Agent 会读取上一轮 `SessionState.current_routes` 回答路线段交通，而不是误走普通聊天或重新规划路线。

同时前端真实后端联调时不再每轮重复发送 onboarding 画像字段。会话首轮发送完整画像，后续只发送消息和会话信息，让后端 session memory 维护当前上下文，避免默认画像城市覆盖用户在对话中明确切换的城市。

### 主要变更

- 新增 `MessageRouter`：
  - 优先使用 LLM 输出结构化分类：`new_plan`、`modify_plan`、`route_detail_question`、`general_chat`。
  - LLM 路由失败时保留轻量 fallback，识别路线详情追问和基础路线相关消息。
  - `AgentOrchestrator` 每轮先执行 `route_message` trace，再按分类分发。

- 新增 `RouteDetailHandler`：
  - 当用户询问上一轮路线细节时，直接读取 `SessionState.current_routes`。
  - 当前 MVP 支持回答相邻站点之间的交通方式、预计时间和距离。
  - 如果没有可引用路线，会返回追问提示，要求先生成路线。

- `AgentOrchestrator` 分发逻辑调整：
  - `route_detail_question`：走 `RouteDetailHandler`，不调用 `POIService` / `RouteService`。
  - `general_chat`：继续走直接 LLM 对话。
  - `new_plan` / `modify_plan`：继续沿用现有 intent 解析、POI 召回、路线生成和总结链路。

- 前端画像发送策略调整：
  - `useChat` 使用 `hasSentProfile` 记录当前会话是否已发送画像。
  - `sendChatMessage` 新增 `includeProfile` 参数。
  - 首轮发送完整 onboarding 画像；后续轮次不再重复发送 `city/preferences/avoid_tags/budget_level/preference_weights`。

- 多轮上下文城市保护：
  - 当 session 中已有上一轮 intent，且当前消息没有显式城市时，后端不会再让 request 中的 onboarding `city` 覆盖当前会话城市。
  - 补充“改一下 / 刚刚的方案 / 打车 / 不走路”等续改表达。

### 涉及文件

- `backend/app/agent/message_router.py`
- `backend/app/agent/route_detail_handler.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/agent/intent_context.py`
- `backend/app/agent/memory.py`
- `backend/app/agent/schemas.py`
- `backend/app/tests/test_message_router.py`
- `backend/app/tests/test_route_detail_handler.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `backend/app/tests/test_intent_context.py`
- `backend/app/tests/test_session_state.py`
- `frontend/src/api/chatApi.ts`
- `frontend/src/hooks/useChat.ts`
- `docs/api_contract.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `/api/chat` 现在先经过消息路由，再决定是否规划、修改、回答路线细节或普通聊天。 | 后续新增意图类型时优先扩展 `MessageRouter` 和 handler，不要继续扩大 `_looks_route_related` 词表。 |
| A 同学：Agent / 后端 | 路线细节追问会复用 `SessionState.current_routes`。 | 当前只回答相邻 stop 交通；后续可扩展指定 route_id、指定第几个 stop、费用/排队/营业时间等 detail type。 |
| B 同学：POI / 路线策略 | 本次不修改 POI 召回、路线生成、评分算法。 | 用户追问路线细节时不会重新调用 `RouteService.generate_routes`，减少无意义重规划。 |
| C 同学：前端 / UI | 前端真实后端请求只在首轮发送完整画像，后续依赖后端 session memory。 | 如果用户点击“重置画像/重开会话”，需要同步调用 `reset()`，让下一轮重新发送画像。 |

### 风险与注意事项

- `MessageRouter` 目前是 MVP 路由器，LLM 失败时仍有少量关键词兜底。
- `RouteDetailHandler` 当前默认使用第一条路线和相邻站点，尚未支持用户指定“第二条路线 / 第二站到第三站”。
- 如果后端进程重启，内存态 `SessionState.current_routes` 会丢失，路线详情追问会要求先生成路线。
- 前端仍固定使用 `session_id: "session_demo"`，多用户或多标签页并行联调时会共享同一个后端内存会话。

### 建议验证

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s app\tests
```

```bash
cd frontend
npm.cmd run build
```

手动联调建议：

- 先生成一条上海路线。
- 继续输入“就你刚刚生成的方案，那俩地之间怎么过去”。
- 期望 Agent 直接回答上一轮路线中相邻站点之间的交通方式、预计时间和距离，不再反问地点名，也不重新生成路线。

---

## 2026-05-21 - `f536727` - `feat(agent): sync intent parsing with route strategy`

负责人：Agent / 后端编排 / A 同学

### 更新概览

本次同步 A 侧对接了 C 的 onboarding 画像字段和 B 的路线策略输入要求。后端 `/api/chat` 现在可以接收前端传来的城市、场景、偏好、避开标签、预算档位和偏好权重，并在 Agent 编排时合并到 `Intent`、`UserProfile` 和 `StrategyWeights` 中。同时前端 mock/真实后端连接改为环境变量配置。

另外新增了 Agent 意图规则增强层：LLM 解析成功或 fallback 后，都会再从用户原话中确定性提取城市、时长、人数、预算、开始时间、偏好标签和避开标签，保证“北京一日游”这类核心话术能稳定进入 B 的路线策略接口。

### 主要变更

- `ChatRequest` 新增 onboarding 字段：
  - `city`
  - `scenarios`
  - `scenario`
  - `preferences`
  - `avoid_tags`
  - `budget_level`
  - `preference_weights`

- `UserProfile` 新增前端兼容字段：
  - `preferences`
  - `avoid_tags`

- `ProfileService` 新增 A/B/C 对齐逻辑：
  - 支持从 `ChatRequest` 构造 `UserProfile`。
  - 当前端未传画像时，会按 `user_id` 从 `data/seed/user_profiles.json` 读取 seed 用户画像。
  - 支持把请求中的城市、场景、偏好、避开标签、预算档位合并进 LLM 解析出的 `Intent`。
  - `budget_level` 当前映射为：`low -> 100`、`mid -> 300`、`high -> 600`。
  - 构造 `StrategyWeights` 时会保留前端传来的更高权重，不再把 onboarding boost 降回默认值。

- 前端联调配置：
  - `frontend/src/api/chatApi.ts` 不再硬编码 `USE_MOCK = true`。
  - 新增 `VITE_USE_MOCK_CHAT`，默认不配置或不等于 `false` 时使用 mock。
  - 设置 `VITE_USE_MOCK_CHAT=false` 时，请求 `VITE_API_BASE_URL` 指向的真实后端。
  - 新增 `frontend/.env.example`。

- `AgentOrchestrator` 同步：
  - 解析 intent 后先合并前端 onboarding 字段。
  - 解析 intent 后会先经过 `intent_enhancer` 规则增强，纠偏 LLM 或 fallback 的缺失字段。
  - 获取用户画像时传入完整 `ChatRequest`。
  - POI 召回和路线规划会使用合并后的 intent/profile/weights。
  - 每轮结束后保存结构化 `SessionState`，包括最近消息、上一轮 intent、当前 routes 和 user_profile。

- 新增框架友好的 Agent 状态边界：
  - `ChatTurn`：保存单条对话消息。
  - `SessionState`：保存跨轮会话状态。
  - `AgentState`：描述单轮 agent 编排过程中的状态快照。
  - `SessionMemory` 从只保存 routes 升级为保存完整 `SessionState`，同时保留 `save_current_routes/get_current_routes` 兼容旧调用。

- 新增第二轮调整指令上下文继承：
  - 新增 `intent_context`，识别“预算低一点”“别排队”“不想排队”“少走路”“不要太累”“换一家”“换成杭州吧”等调整指令。
  - 当本轮是调整指令且没有显式新城市时，会继承 `SessionState.last_intent`。
  - 支持把本轮新增偏好合并进上一轮 intent，例如“预算低一点，别排队”会继承上一轮城市/时长，并新增 `更省钱`、`少排队`、`排队久`。
  - 支持连续多轮叠加约束，例如“上海一日游” -> “预算低一点，别排队” -> “再少走路一点，安静些”。
  - “少走路/不要太累”现在会同时进入 `preferences=少走路` 和 `avoid_tags=步行多`。
  - “不想排队”现在会被识别为调整指令，避免第二轮漏继承上一轮城市后被 onboarding 城市覆盖。
  - “再/继续/更/一点/一些”这类短跟进表达会被识别为调整消息，用于继承上一轮上下文。
  - “换成/换到/改成 + 城市”会及时切换到本轮显式城市，同时继承上一轮未被明确改写的时长、偏好和避开标签。
  - 如果本轮明确说了新城市，例如“我想在北京一日游”，则不会继承旧城市。

- 新增 `intent_enhancer`：
  - 支持城市提取：北京、上海、广州、深圳、成都、杭州、南京、武汉、西安、苏州、重庆等。
  - 支持时长提取：一日游/一天、半日游/半天、N 天、N 小时。
  - 支持人数、预算、开始时间提取。
  - 支持偏好标准化：少排队、吃好、更省钱、少走路、citywalk、拍照、亲子友好、室内、安静。
  - 支持避开标签标准化：人流密集、排队久、太贵、商业街、辣、步行多。
  - 本轮消息显式提到城市时，会标记 `city_from_message=true`，避免被 onboarding 默认城市覆盖。
  - 会清理 `一日游`、`半日游` 等时长词，避免它们被当成偏好标签传给 B 策略。
  - 当本轮消息已提取到城市、时长或偏好信息时，会把 `need_clarification` 纠正为 `false`。

- 新增测试：
  - `backend/app/tests/test_profile_request_sync.py`
  - 覆盖 ChatRequest 接收前端字段、ProfileService 构造 profile、合并 intent、保留前端权重 boost。
  - `backend/app/tests/test_intent_enhancer.py`
  - `backend/app/tests/test_orchestrator_intent_flow.py`
  - `backend/app/tests/test_session_state.py`
  - `backend/app/tests/test_intent_context.py`
  - 覆盖“北京一日游”“2 人 / 人均 200 / 少排队 / 吃好”“今晚上海半天 citywalk”等话术。
  - 覆盖本轮显式城市优先于 onboarding 城市，以及 `一日游` 不进入 preferences。
  - 覆盖结构化 session state 保存和 orchestrator 写入会话状态。
  - 覆盖第二轮“预算低一点，别排队”继承上一轮“上海一日游”上下文。
  - 覆盖第三轮继续叠加“少走路、安静、步行多”等约束。
  - 覆盖 onboarding 城市为北京、上一轮为上海时，第二轮“不想排队”仍继承上海。
  - 覆盖 onboarding 城市为北京、上一轮为上海时，第二轮“换成杭州吧”会切换到杭州，并保留上一轮一日游和少排队约束。

### 涉及文件

- `backend/app/agent/orchestrator.py`
- `backend/app/agent/intent_enhancer.py`
- `backend/app/agent/intent_context.py`
- `backend/app/agent/memory.py`
- `backend/app/agent/schemas.py`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/user.py`
- `backend/app/services/profile_service.py`
- `backend/app/tests/test_profile_request_sync.py`
- `backend/app/tests/test_intent_enhancer.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `backend/app/tests/test_session_state.py`
- `backend/app/tests/test_intent_context.py`
- `frontend/src/api/chatApi.ts`
- `frontend/.env.example`
- `docs/api_contract.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `/api/chat` 已开始消费前端 onboarding 字段，也支持 seed 用户画像 fallback，并新增规则增强层。 | 后续 prompt 和 memory 逻辑要继续使用增强且合并后的 `Intent`；本轮用户显式城市应优先于历史画像城市。 |
| A 同学：Agent / 后端 | `SessionMemory` 已升级为结构化状态存储。 | 下一步支持真正多轮时，应优先复用 `SessionState.last_intent/current_routes/recent_messages`，不要再新增散落的 dict。 |
| A 同学：Agent / 后端 | 第二轮调整指令已能继承上一轮 intent。 | 目前是重新生成路线，不是基于 `current_routes` 做局部替换；“换一家”后续还需要接 replan/replace 逻辑。 |
| B 同学：POI / 路线策略 | POI 召回现在能拿到前端偏好和权重。 | 策略调参时可以假设 `user_profile.tags/preferences/preference_weights` 会来自前端画像。 |
| C 同学：前端 / UI | 前端传出的 `preferences/avoid_tags/preference_weights` 不再被后端静默丢弃。 | 联调真实后端时在 `frontend/.env` 设置 `VITE_USE_MOCK_CHAT=false` 和 `VITE_API_BASE_URL=http://localhost:8000`。 |

### 风险与注意事项

- 当前 `ProfileService` 只做了 seed 用户画像的 MVP 映射，复杂字段如历史行为、默认出发点还没有全部进入 `Intent`。
- `intent_enhancer` 是规则增强层，不替代 LLM；同义词表需要随着 B 的策略标签持续维护。
- 第二轮上下文继承目前只覆盖偏好/约束调整；路线局部编辑、已完成 POI、指定 route_id 还没接入。
- `budget_level` 到具体金额的映射是 MVP 约定，后续如产品口径变化需要同步前后端。
- 真实反馈闭环 `/api/feedback` 还没有和前端本地画像更新打通。
- 评分值域和前端展示仍需继续统一：后端真实路线当前按 0-100 输出，前端 mock 仍偏 10 分制。

### 建议验证

```bash
cd backend
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest app.tests.test_profile_request_sync
```

```bash
cd backend
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest app.tests.test_intent_enhancer app.tests.test_orchestrator_intent_flow
```

```bash
cd backend
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest app.tests.test_session_state
```

```bash
cd backend
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m unittest app.tests.test_intent_context
```

```bash
cd frontend
npm.cmd run build
```

## 2026-05-21 - `9544b8e` - `Merge branch 'LYNN' into keyki`

负责人：路线策略 / POI 数据 / B 同学

### 更新概览

本次合入主要完成了路线策略和 POI 数据层的大升级：POI 从写死样例切换为读取 `data/seed/pois.json`，路线生成从简单排序升级为多目标规划，并补充了距离、交通、路段原因、总路程等字段。前端类型同步了新增字段，为后续展示更完整的路线解释做准备。

本次合入共变更 `12` 个文件，新增约 `14559` 行，删除约 `208` 行，主要增量来自 `pois.json` 和 `user_profiles.json` 两份 seed 数据。

### 主要变更

- POI 召回改为数据驱动：
  - `POIService` 不再使用代码内写死的 sample POI。
  - 现在从 `data/seed/pois.json` 读取 POI 数据。
  - 新增预算、偏好、避开标签、距离、用户画像权重等召回和排序逻辑。

- 路线生成逻辑大幅增强：
  - `RouteService` 支持多种路线目标：综合最优、少排队、更省钱、少走路、吃好优先、拍照 Citywalk、室内雨天。
  - 会根据用户偏好和策略权重自动选择 3 个路线目标。
  - 路线生成会考虑总时长窗口、点位访问时长、排队时间、路段交通时间。
  - 单条路线最多选 5 个 stop，短路线会尝试补足到 3 个 stop。

- 评分体系升级：
  - `ScoringService` 从固定评分改为可解释评分。
  - 评分维度包括品质、排队、预算、距离、偏好。
  - 总分会结合 `StrategyWeights`，并对当前路线目标做轻微加权。

- 接口字段扩展：
  - `Intent` 新增起点信息字段：`start_location_name`、`start_lat`、`start_lng`。
  - `RouteStop` 新增路段字段：`travel_minutes_from_previous`、`distance_km_from_previous`、`transport_mode_from_previous`、`reason`。
  - `Route` 新增汇总字段：`total_travel_minutes`、`total_distance_km`。
  - 前端 `frontend/src/api/types.ts` 已同步这些字段。

- Agent 编排同步：
  - `AgentOrchestrator` 调用 POI 召回时会传入 `user_profile`。
  - LLM intent schema 和结果归一化逻辑支持起点名称与经纬度。

- 测试补充：
  - 新增 `backend/app/tests/test_poi_service.py`。
  - 扩展 `backend/app/tests/test_route_plan.py`，覆盖空候选、短时长、预算优先、少排队、吃好优先、起点路段字段等场景。

### 涉及文件

- Agent 与 schema：
  - `backend/app/agent/orchestrator.py`
  - `backend/app/schemas/intent.py`
  - `backend/app/schemas/route.py`

- 路线与 POI 服务：
  - `backend/app/services/poi_service.py`
  - `backend/app/services/route_service.py`
  - `backend/app/services/scoring_service.py`

- 测试：
  - `backend/app/tests/test_poi_service.py`
  - `backend/app/tests/test_route_plan.py`

- 数据：
  - `data/seed/pois.json`
  - `data/seed/user_profiles.json`

- 前端类型与展示：
  - `frontend/src/api/types.ts`
  - `frontend/src/components/RouteCard.tsx`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `Intent` 支持起点名称和经纬度，Agent 的 structured output 可以开始抽取起点信息。 | prompt 和解析逻辑要尽量稳定输出 `start_location_name`、`start_lat`、`start_lng`；如果不知道经纬度，应返回 `null`，不要乱填。 |
| A 同学：Agent / 后端 | POI 召回现在依赖 `user_profile` 参与排序。 | 真实用户画像里的 `tags` 和 `preference_weights` 会影响结果，需要确认画像字段和前端 onboarding 字段如何映射。 |
| A 同学：Agent / 后端 | 路线结果字段增加，Agent 总结路线时可以引用交通时间、距离和每站推荐理由。 | 如果后续 LLM 生成自然语言解释，需要避免和 `Route.summary`、`RouteStop.reason` 重复或矛盾。 |
| B 同学：POI / 路线策略 | POI 数据结构更复杂，召回逻辑依赖 `location`、`visit_info`、`quality`、`suitability`、`planning_features` 等字段。 | 继续扩数据时要保持 JSON 字段完整；缺字段虽然有 fallback，但会影响排序和展示质量。 |
| B 同学：POI / 路线策略 | 路线目标从 3 类扩展到 7 类。 | 后续调参时要重点看不同目标是否真的有差异，避免三条路线点位高度重复。 |
| B 同学：POI / 路线策略 | 新增测试覆盖核心策略行为。 | 当前本地环境没有安装 `pytest` 时跑不了测试，需要在后端依赖或协作说明里补齐测试安装方式。 |
| C 同学：前端 / UI | 前端类型已同步路段交通、距离、交通方式、站点 reason、总路程等字段。 | `RouteCard.tsx` 目前只同步了类型，尚未完整展示 `total_travel_minutes`、`total_distance_km` 和 `RouteStop.reason`。 |
| C 同学：前端 / UI | `RouteCard.tsx` 新增了 `MapPinned` import。 | 当前 `MapPinned` 尚未使用，后续可以用于展示总路程；如果不展示，应删除未使用 import。 |
| C 同学：前端 / UI | 后端真实响应更丰富，前端 mock 数据可能落后。 | 如果继续使用 `USE_MOCK = true`，需要同步 mock routes 字段，否则联调和演示看到的数据形态会不一致。 |

### 风险与注意事项

- `docs/api_contract.md` 尚未同步本次新增字段，包括 `Intent.start_*`、`RouteStop.travel_*`、`RouteStop.reason`、`Route.total_travel_minutes`、`Route.total_distance_km`。
- `frontend/src/components/RouteCard.tsx` 目前引入了 `MapPinned` 但没有使用。前端构建能通过，但后续应删除或补展示。
- `pytest` 当前本地后端虚拟环境里不可用，新增测试没有实际跑通。
- 后端 `compileall` 因写入 `__pycache__` 权限问题失败；已通过 `PYTHONDONTWRITEBYTECODE=1` 的核心模块 import 检查。
- seed 数据增量很大，后续合并时 `data/seed/pois.json` 和 `data/seed/user_profiles.json` 可能成为冲突高发文件。
- 路线评分和召回排序现在依赖很多中文标签和别名匹配，后续新增标签时需要注意同义词覆盖。

### 建议验证

- 前端构建：

```bash
cd frontend
npm.cmd run build
```

- 后端 import 检查：

```bash
cd backend
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -c "from app.agent.orchestrator import AgentOrchestrator; from app.services.poi_service import POIService; from app.services.route_service import RouteService; from app.services.scoring_service import ScoringService; print('imports ok')"
```

- 后端测试，需先确保安装 `pytest`：

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest app\tests
```

### 后续建议

- 更新 `docs/api_contract.md`，补齐本次新增的请求和响应字段。
- 前端展示 `total_travel_minutes`、`total_distance_km` 和 `RouteStop.reason`，让 B 侧策略解释真正被用户看到。
- 将 `frontend/src/api/chatApi.ts` 的 mock route 数据同步到新字段，或尽快切换真实后端联调。
- 在 `backend/requirements.txt` 中确认是否需要加入 `pytest`，保证队友能跑新增测试。

## 2026-05-20 - `0e75842` - `feat(frontend): mobile-first UI — onboarding, mock chat, replan & feedback flow`

负责人：前端 / C 同学

### 更新概览

本次提交是一次前端体验大版本更新，目标是把 Demo 从“基础页面展示”推进到“手机优先、可完整演示”的路线规划产品形态。核心变化包括：新增 onboarding 用户画像采集、重做移动端布局、引入 mock chat 响应、完善路线卡片展示、接通重规划入口、增加行程反馈闭环。

本次提交共变更 `20` 个前端文件，新增约 `2554` 行，删除约 `267` 行。

### 主要变更

- 新增 onboarding 引导流程：
  - 用户首次进入时需要完成 3 步设置：出行场景、偏好/避开标签、预算/城市/昵称。
  - 完成后将用户画像保存到 `localStorage`。
  - App 启动时如果检测到已有画像，会跳过 onboarding 直接进入规划页。

- 重做 Planner 主页面：
  - 改为移动端优先布局。
  - 增加固定顶部标题栏、固定底部输入栏、可滚动主内容区。
  - 聊天区改为消息气泡形式，支持欢迎语、快捷 chips、loading 打字动效。
  - 输入框支持 Enter 发送、Shift+Enter 换行、自适应高度。

- 新增 mock chat 能力：
  - `frontend/src/api/chatApi.ts` 中增加 `USE_MOCK = true`。
  - 后端未启动时也能演示完整流程。
  - mock 数据覆盖普通聊天、路线规划、用户画像、3 条路线、评分拆解、Agent trace。

- 完善路线展示：
  - 路线结果在移动端支持横向滑动，桌面端保持多列对比。
  - 新增 `ScoreBreakdown` 组件，展示品质、排队、预算、距离、偏好等评分维度。
  - 路线卡片、时间线、标签、核心指标和操作按钮样式都有更新。

- 接通路线操作和动态重规划入口：
  - ActionBar 操作会生成对应请求文案，例如“降低人均消费”“避开排队地点”“加入亲子友好筛选条件”。
  - 新增突发事件模拟入口，支持餐厅排队、交通堵车、用户疲惫等场景。
  - 手机端通过底部抽屉选择事件，桌面端保留内联按钮组。

- 增加反馈闭环：
  - 反馈面板从滑杆改为星级评分。
  - 评分项包括路线合理性、餐厅满意度、时间安排、预算控制、AI 准确度。
  - 提交反馈后会根据评分更新本地用户偏好权重。

- 扩展全局样式系统：
  - `globals.css` 大幅扩展为完整 UI 样式层。
  - 增加 CSS 变量、按钮体系、消息气泡、路线卡、抽屉、onboarding、骨架屏、响应式桌面覆盖等样式。

### 涉及文件

- 应用入口：
  - `frontend/src/App.tsx`

- API 与类型：
  - `frontend/src/api/chatApi.ts`
  - `frontend/src/api/types.ts`

- 页面：
  - `frontend/src/pages/OnboardingPage.tsx`
  - `frontend/src/pages/PlannerPage.tsx`

- Hooks：
  - `frontend/src/hooks/useChat.ts`
  - `frontend/src/hooks/useOnboarding.ts`

- 组件：
  - `frontend/src/components/ActionBar.tsx`
  - `frontend/src/components/AgentTrace.tsx`
  - `frontend/src/components/ChatPanel.tsx`
  - `frontend/src/components/FeedbackPanel.tsx`
  - `frontend/src/components/ReplanPanel.tsx`
  - `frontend/src/components/RouteCard.tsx`
  - `frontend/src/components/RouteCompare.tsx`
  - `frontend/src/components/RouteTimeline.tsx`
  - `frontend/src/components/ScoreBreakdown.tsx`
  - `frontend/src/components/UserProfileBadge.tsx`

- 工具与样式：
  - `frontend/src/utils/categoryLabels.ts`
  - `frontend/src/utils/traceIcons.ts`
  - `frontend/src/styles/globals.css`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 前端请求 `/api/chat` 时现在会附带更多画像字段，包括 `city`、`scenarios`、`preferences`、`avoid_tags`、`budget_level`、`preference_weights`。 | 后端 `ChatRequest` 如果还没支持这些字段，需要补齐或容忍额外字段。需要确认真实 Agent 是否使用这些画像字段生成策略权重。 |
| A 同学：Agent / 后端 | 前端 UI 现在会展示 `need_clarification` 和 `clarifying_question`。 | 如果 Agent 需要追问，返回结构要和 `frontend/src/api/types.ts` 保持一致。 |
| A 同学：Agent / 后端 | 前端会展示 `agent_trace`，并根据 step/status 做图标和状态渲染。 | 建议保持 trace 字段稳定：`step`、`label`、`status`。新增状态时需要和前端同步。 |
| B 同学：POI / 路线策略 | 路线卡片现在会展示 `score_breakdown`。 | 路线策略输出最好包含 `quality`、`queue`、`budget`、`distance`、`preference` 五个维度。前端兼容 0-1 和 0-10 两种值域，但建议团队统一一种。 |
| B 同学：POI / 路线策略 | 时间线、预算、排队、标签等信息在 UI 中更突出。 | `Route.stops` 中的 `start_time`、`end_time`、`estimated_cost`、`queue_minutes`、`tags` 会直接影响展示质量，需要保证数据可读、合理。 |
| B 同学：POI / 路线策略 | 动态重规划入口已接到聊天 send，而不是直接调用 `/api/routes/replan`。 | 如果后续要改成直接调用 replan API，需要和 C 同学约定接口和前端状态更新方式。 |
| C 同学：前端 / UI | 前端主结构已从桌面 panel 页面变为移动端优先应用。 | 后续新增组件时优先保证手机端体验，再补桌面端覆盖样式。 |
| C 同学：前端 / UI | `chatApi.ts` 当前启用 `USE_MOCK = true`。 | 联调真实后端前必须改为 `false`，并确认真实响应字段覆盖当前 UI 需要。 |
| C 同学：前端 / UI | 用户画像现在保存在 localStorage。 | 调试 onboarding 时需要清理本地缓存，或通过页面里的重置入口重新设置画像。 |

### 风险与注意事项

- 当前 `frontend/src/api/chatApi.ts` 中 `USE_MOCK = true`，意味着前端不会真正请求后端 `/api/chat`。这适合演示 UI，但不适合联调真实 Agent。
- 本次前端向 `/api/chat` 请求体增加了用户画像相关字段，但 `docs/api_contract.md` 目前还没有同步这些字段。后续联调前建议更新接口文档。
- `score_breakdown` 已成为 UI 展示的一部分，后端真实路线如果不返回该字段，前端需要确认是否有 fallback；后端也可以直接按新字段输出。
- `FeedbackPanel` 当前更新的是本地画像权重，不是调用真实 `/api/feedback`。如果要形成真实闭环，需要 A/C 对齐反馈 API。
- 动态重规划当前通过构造聊天消息调用 `send`，并非直接使用 `/api/routes/replan`。这对 Demo 简单，但后续如果要展示“重规划前后对比”，可能需要单独接口或更明确的响应结构。
- 大量样式集中在 `frontend/src/styles/globals.css`，后续多人同时改 UI 时容易产生冲突。建议 C 同学拆任务时尽量按组件范围拆分，提交前重点检查样式影响面。

### 建议验证

- 前端构建：

```bash
cd frontend
npm run build
```

- 手动验证：
  - 清空浏览器 localStorage 后进入页面，应显示 onboarding。
  - 完成 onboarding 后，应进入规划页并看到个性化欢迎语。
  - 输入“上海半天 citywalk，2人，预算200”，应展示 3 条 mock 路线。
  - 点击路线操作按钮，应向聊天流发送对应优化请求。
  - 点击突发事件模拟，应能打开抽屉并触发重规划请求。
  - 提交星级反馈后，应显示感谢提示，并更新本地画像权重。

### 后续建议

- 将 `docs/api_contract.md` 补充到当前前端实际使用字段。
- 联调真实后端前，把 `USE_MOCK` 改为环境变量或开发配置，不建议长期硬编码。
- 明确 `score_breakdown` 的值域，建议统一为 0-1 或 0-10。
- 如果第三周要展示“重规划前后变化”，需要补充响应结构，例如 `previous_route`、`updated_route`、`changed_stops`、`replan_reason`。

## 2026-05-21 - `c5a4633` - `Complete mock POI seed fields`

负责人：路线策略 / POI 数据 / B 同学

### 更新概览

本次提交对 `data/seed/pois.json` 做了一轮字段质量补全。POI seed 原本已经具备主要字段结构，但部分 mock 值不完整，例如 `last_entry_time` 为空、非餐饮 POI 的 `meal_type` 为空、封面图片仍使用 `example.com/mock/...` 占位链接。此次更新按字段设计统一补齐这些弱 mock 值，让 POI 召回、路线规划和前端展示有更稳定的数据基础。

### 主要变更

- POI seed 元信息更新：
  - `schema_version` 从 `1.0.0` 更新为 `1.0.1`。
  - `description` 改为说明当前数据已补齐路线召回和规划需要的 MVP 字段。

- 补齐访问信息：
  - 为所有缺失的 `visit_info.last_entry_time` 生成合理值。
  - 全天开放类点位补为 `23:30`。
  - 普通营业点位按 `close_time - 60 分钟` 推导最后入场时间。

- 补齐规划特征：
  - 为所有空的 `planning_features.meal_type` 补值。
  - 非餐饮类统一为 `non_meal`。
  - 餐饮、咖啡、集市类保留或映射为 `local_food`、`cafe`、`light_meal`、`fine_dining`、`fast_food` 等类型。

- 替换弱 mock 图片链接：
  - 将所有 `https://example.com/mock/...` 替换为按分类和 POI id 生成的稳定 mock 图片 URL。
  - 解决前端展示时封面 URL 明显不可用的问题。

- 保持原有字段契约：
  - 未新增后端暂时不用的大字段。
  - 未改变 `POIService` 当前读取的字段路径。
  - `risk_flags` 和 `avoid_reasons` 允许为空数组，表示无明显风险或避雷原因。

### 涉及文件

- `data/seed/pois.json`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | Agent 编排逻辑无接口变化。 | 如果后续让 Agent 解释 POI，可更放心引用营业、餐饮类型和封面字段。 |
| B 同学：POI / 路线策略 | POI 召回和路线规划的数据质量更稳定，`meal_type`、`last_entry_time`、封面 URL 不再为空或明显占位。 | 后续扩充 POI 时应继续保持字段完整，尤其是 `visit_info`、`quality`、`suitability`、`planning_features`。 |
| C 同学：前端 / UI | 前端展示 POI/路线时不再看到 `example.com/mock` 这类无效封面链接。 | 如果前端后续真正渲染封面，需要确认外链加载策略和图片兜底状态。 |

### 风险与注意事项

- 图片链接仍是 mock 图片服务，不是真实 POI 图片。
- `meal_type=non_meal` 是为了消除空值的 MVP 约定，后续如果做更细餐饮推荐，需要再细化类型枚举。
- `last_entry_time` 是根据营业结束时间推导的 mock 值，不代表真实景区或商户规则。
- 本次只改 POI seed 数据，没有改接口、schema 或服务代码。

### 建议验证

```bash
cd backend
.venv/bin/python - <<'PY'
from app.tests import test_poi_service, test_route_plan
for module in [test_poi_service, test_route_plan]:
    for name in dir(module):
        if name.startswith("test_"):
            getattr(module, name)()
            print(f"PASS {module.__name__}.{name}")
PY
```

## 2026-05-21 - `7d7291b` - `Merge remote-tracking branch 'origin/main' into LYNN`

负责人：协作同步 / LYNN 分支

### 更新概览

本次提交是一次分支同步操作：将 `origin/main` 上其他成员的最新变动合并到本地 `LYNN` 分支，方便继续开发时能看到 A/C 同学近期提交的 Agent、前端、接口文档和版本日志更新。本次合并无冲突。

### 主要变更

- 同步了 `origin/main` 上的最新协作内容：
  - A 侧 Agent intent 增强、画像字段同步和相关测试。
  - C 侧移动端优先前端、onboarding、mock chat、反馈与重规划 UI。
  - 文档侧 `docs/api_contract.md`、`docs/git_workflow.md`、`docs/version_log.md` 等更新。

- 保留了 LYNN 分支上的 B 侧改动：
  - POI 召回实现。
  - 路线生成增强。
  - POI seed 字段补全。

### 涉及文件

- 本次是 merge commit，涉及文件来自 `origin/main` 已有提交。
- 主要覆盖后端 Agent、前端 UI、接口文档和协作日志相关文件。

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | LYNN 分支已同步 A 侧最新 intent/profile 编排逻辑。 | 后续若继续改 Agent，应基于合并后的 `orchestrator.py`、`intent_enhancer.py` 和 profile 逻辑。 |
| B 同学：POI / 路线策略 | B 侧 POI/路线改动已和 main 最新内容共存。 | 后续调试时要注意新 onboarding/profile 字段会影响 POI 召回和路线目标选择。 |
| C 同学：前端 / UI | LYNN 分支已包含 C 侧最新前端页面和组件。 | 若要联调真实后端，需要继续确认 mock/真实请求开关和后端响应字段一致。 |

### 风险与注意事项

- 合并后本地 `LYNN` 分支领先 `origin/LYNN`，如果需要云端也看到这次同步，需要再 push。
- `.gitignore` 仍有本地未提交改动，未包含在本次 merge commit 中。
- 本次合并本身不代表功能验收，只是把其他成员变动同步到当前开发分支。

### 建议验证

```bash
cd backend
.venv/bin/python -m compileall app
```

```bash
cd backend
.venv/bin/python - <<'PY'
from app.tests import test_poi_service, test_route_plan
for module in [test_poi_service, test_route_plan]:
    for name in dir(module):
        if name.startswith("test_"):
            getattr(module, name)()
            print(f"PASS {module.__name__}.{name}")
PY
```

## 2026-05-22 - `2ab6fd7` - `feat(route): improve POI semantics and route diversity scoring`

负责人：路线策略 / POI 数据 / B 同学

### 更新概览

本次更新优化了 POI 召回、路线结构和路线评分逻辑，解决演示中出现的“推荐过度依赖 POI 标签”“路线里连续出现两个咖啡店或同质点位”“POI 分类过于单一，无法表达点位在路线里的角色”等问题。

用户可感知的变化是：推荐路线不再只是把高分 POI 拼在一起，而是会更像一条有结构的行程，例如包含主活动点、餐饮点、咖啡/休息点、拍照点等不同角色；每个目标下仍会先生成候选路线并评分，再只返回该目标下评分最高的推荐路线。

### 主要变更

- 扩展 POI 语义字段：
  - `POI` 新增 `primary_category`、`secondary_categories`、`route_roles`、`experience_tags`。
  - `RouteStop` 同步新增这些字段，方便前端展示和调试每个点在路线中的角色。
  - 保留原有 `category`、`tags`、`meal_type` 字段，避免破坏现有前后端契约。

- POI 召回从标签匹配升级为规则语义增强：
  - `POIService` 会从现有 `category`、`meal_type`、`tags`、`highlight_text_tags`、`suitability`、`planning_features` 自动推导语义字段。
  - 搜索文本纳入主类别、辅助类别、路线角色和体验标签，减少只依赖原始标签命中的局限。
  - 暂不要求立即重写 `data/seed/pois.json`，旧 seed 数据可以通过推导逻辑继续使用。

- 路线生成加入结构约束：
  - 默认每条路线最多 1 个 `coffee_break`，除非用户明确表达“咖啡探店 / 咖啡路线 / 多家咖啡”。
  - 默认每条路线最多 1 个正餐 `meal`，除非用户明确表达“美食路线 / 扫街 / 吃很多家”。
  - 每条推荐路线会倾向包含至少 1 个 `main_activity`，避免路线全是吃喝。
  - `photo_citywalk` 会补足 `photo_stop` 和 `main_activity`。
  - `indoor_rainy` 会优先补足室内主活动点。
  - 连续同类 `primary_category` 或重复 `route_roles` 会在选点时被扣分。

- 路线评分加入结构合理性：
  - `ScoringService` 升级为基于 POI 原始字段和路线结构的五维评分。
  - 评分继续输出 `quality`、`queue`、`budget`、`distance`、`preference`，前端接口字段不变。
  - 缺少主活动点、目标必需角色缺失、重复咖啡/重复正餐、连续同类点都会形成 hard penalty 或 preference penalty。
  - 每个 objective 内部生成多条候选路线后，会按评分排序并只返回 `route_<objective>_best`。

- 测试补充：
  - 增加 POI 语义字段推导测试。
  - 增加路线结构测试，覆盖不重复咖啡、包含主活动、拍照路线包含拍照/主活动、室内雨天路线包含室内主活动等场景。
  - 完整后端测试已通过 `37 passed`。

### 涉及文件

- `backend/app/schemas/poi.py`
- `backend/app/schemas/route.py`
- `backend/app/services/poi_service.py`
- `backend/app/services/route_service.py`
- `backend/app/services/scoring_service.py`
- `backend/app/tests/test_poi_service.py`
- `backend/app/tests/test_route_plan.py`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `/api/chat` 返回的路线 stop 现在带有更丰富的语义角色字段，Agent 总结可以引用“主活动 / 餐饮 / 咖啡休息 / 拍照点”等概念。 | LLM prompt 如果后续解释路线，可以优先使用 `Route.summary`、`Route.reasons` 和 `route_roles`，避免只复述标签。 |
| B 同学：POI / 路线策略 | POI 召回和路线生成从单点标签匹配升级为“语义画像 + 路线结构”。 | 后续扩充 `pois.json` 时可以直接补 `primary_category`、`secondary_categories`、`route_roles`、`experience_tags`；不补也会自动推导，但人工维护会更准。 |
| C 同学：前端 / UI | API 兼容旧字段，同时 `RouteStop` 新增语义字段，可用于调试或展示路线结构。 | 如果前端希望展示“主活动 / 咖啡休息 / 餐饮点”标签，可以读取 `route_roles`；当前不展示也不影响页面。 |

### 风险与注意事项

- 新语义字段目前主要由规则推导，不是真实人工标注；部分 POI 的角色可能仍需后续手动校准。
- `primary_category` 和 `route_roles` 的枚举还不是正式产品枚举，后续如果接地图或商户真实分类，需要统一字典。
- 当前没有引入 embedding 或向量召回，语义能力仍是规则增强，适合当前 hackathon seed 数据规模。
- 如果用户明确要求“咖啡探店”或“美食扫街”，系统会放宽重复咖啡/重复餐饮限制；其他普通路线默认避免同质重复。
- 本次新增了后端响应字段，但未同步更新 `docs/api_contract.md`；如果 C 侧要正式展示这些字段，建议补充接口文档。

### 建议验证

```bash
cd backend
.venv/bin/python -m pytest app/tests
```

```bash
cd backend
.venv/bin/python - <<'PY'
from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService

intent = Intent(preferences=["citywalk", "吃好", "少排队"], avoid_tags=["人多"], budget_per_person=300)
profile = ProfileService().get_profile("user_demo")
pois = POIService().search(intent, user_profile=profile)
routes = RouteService().generate_routes(RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)).routes

for route in routes:
    print(route.objective, route.score, route.summary)
    for stop in route.stops:
        print(" -", stop.name, stop.primary_category, stop.route_roles)
PY
```

## 2026-05-24 - `42698d9` - `feat(route): add map-aware dynamic route replanning`

负责人：动态重规划 / 地图适配 / B 同学

### 更新概览

本次更新为“用户已选路线并开始行进后的实时调整”补齐了后端基础能力。路线不再只能一次性生成，而是可以在排队暴增、POI 临时不可用、交通拥堵、用户累了、天气变化等事件发生后，保留已完成点位，只对后续受影响部分进行局部重规划。

同时为后续接入真实地图 API 做了适配层设计：业务逻辑不直接绑定高德、百度、Google 或 Mapbox，而是通过统一的 `MapProvider` 获取实时通勤、地点状态和附近替代 POI。当前实现使用 mock provider 跑通流程，后续替换真实 provider 即可。

### 主要变更

- 新增地图 API 适配层：
  - 新增 `MapProvider` 协议和 `MockMapProvider`。
  - 统一封装实时路程估算、路线选项、附近 POI 搜索、地点状态、地理编码和反向地理编码。
  - 业务层只消费统一模型，不依赖具体地图供应商。

- 新增实时地图数据结构：
  - `LiveLegEstimate`：表示实时距离、通勤时间、交通倍率、交通状态和数据来源。
  - `ExternalPOIStatus`：表示 POI 是否营业、是否可达、实时排队、人流和状态原因。
  - `ExternalPOICandidate`：表示地图 API 搜出的外部候选 POI。

- 扩展 POI 地图映射字段：
  - `external_place_ids`
  - `source_provider`
  - `source_updated_at`
  - `map_category`
  - `map_category_code`
  - `geohash`
  - `canonical_poi_id`
  - 这些字段用于后续把本地 POI 和真实地图 place id 对齐，同时不覆盖本地维护的路线角色、体验标签和推荐语义。

- 重写动态重规划逻辑：
  - `ReplanService` 不再只返回原路线占位文案。
  - 支持保留 `completed_poi_ids`，避免已完成点位被删除。
  - 支持 `locked_poi_ids`，默认不改用户锁定的后续点位。
  - 针对 `queue_spike`、`poi_closed`、`traffic_jam`、`user_tired`、`weather_change` 做局部重规划。
  - 优先用本地 POI 找同角色替代点；本地候选不足时，可通过地图 provider 搜附近外部候选并归一化为本地 POI。
  - 重规划后会重新计算 stops 时间线、总排队、总交通、总距离、总成本和路线评分。

- 扩展 `/api/routes/replan` 前后端契约：
  - 请求新增 `selected_route_id`、`current_poi_id`、`current_lat/current_lng`、`current_time`、`locked_poi_ids`、`event_payload`、`intent`、`user_profile`。
  - 响应路线新增 `changed_stops`、`live_warnings`、`data_sources`。
  - 前端 TypeScript 类型同步增加这些可选字段，现有页面不展示时也保持兼容。

- 新增测试：
  - 覆盖排队暴增后替换未来点位并保留已完成点位。
  - 覆盖 POI 临时关闭后必须从后续路线移除。
  - 覆盖交通拥堵后重新计算通勤并返回实时 warning。
  - 覆盖本地替代点不足时使用 mock 地图外部候选兜底。
  - 完整后端测试已通过 `41 passed`。

### 涉及文件

- `backend/app/schemas/map.py`
- `backend/app/schemas/poi.py`
- `backend/app/schemas/route.py`
- `backend/app/services/map_provider.py`
- `backend/app/services/poi_service.py`
- `backend/app/services/replan_service.py`
- `backend/app/tests/test_replan_service.py`
- `docs/api_contract.md`
- `frontend/src/api/types.ts`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | Agent 后续可以在用户反馈“排队太久 / 堵车 / 累了 / 下雨了”时调用 `/api/routes/replan`，并把事件结构化放入 `event_payload`。 | prompt 或工具调用需要传入当前路线、已完成 POI、当前时间和事件类型；总结时可优先引用 `replan_reason`、`changed_stops`、`live_warnings`。 |
| B 同学：POI / 路线策略 | 动态重规划开始复用 POI 语义角色和路线评分，并为真实地图 API 预留 place id 映射。 | 后续补 `pois.json` 时可逐步增加 `external_place_ids`、`map_category`、`canonical_poi_id`；真实地图数据进入路线前仍需保留本地语义归一化。 |
| C 同学：前端 / UI | `Route` 新增可选字段，可用于展示“路线已动态调整”“替换了哪个点”“实时风险提示”。 | 现有页面只展示 `replan_reason` 仍可工作；如要增强 UI，可读取 `changed_stops/live_warnings/data_sources` 做差异卡片。 |

### 风险与注意事项

- 当前地图适配层仍使用 `MockMapProvider`，尚未接入真实高德、百度、Google 或 Mapbox。
- 外部 POI 候选是 mock 数据，主要用于验证“地图 API 搜附近替代点”的链路。
- 重规划以局部替换为主，不会整条路线推倒重来；如果本地候选不足且未允许外部候选，可能保留原路线并只返回 warning。
- 新增的 `changed_stops/live_warnings/data_sources` 是响应增强字段，前端不展示也不会影响原有路线卡片。
- `docs/api_contract.md` 已同步 `/api/routes/replan` 的新增请求与响应字段。

### 建议验证

```bash
cd backend
.venv/bin/python -m pytest app/tests
```

```bash
cd backend
.venv/bin/python - <<'PY'
from app.schemas.intent import Intent
from app.schemas.route import ReplanRequest, RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.replan_service import ReplanService

intent = Intent(preferences=["citywalk", "吃好", "少排队"], budget_per_person=300)
profile = ProfileService().get_profile("user_demo")
pois = POIService().search(intent, user_profile=profile)
route = RouteService().generate_routes(RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)).routes[0]
affected = route.stops[1]

response = ReplanService().replan(
    ReplanRequest(
        session_id="session_demo",
        selected_route_id=route.route_id,
        event_type="queue_spike",
        event_label="排队突然变久",
        current_routes=[route],
        completed_poi_ids=[route.stops[0].poi_id],
        current_time=route.stops[0].end_time,
        event_payload={"affected_poi_id": affected.poi_id, "queue_minutes": 90},
        intent=intent,
        user_profile=profile,
    )
)

updated = response.routes[0]
print(updated.replan_reason)
print(updated.live_warnings)
print([(change.from_name, change.to_name, change.reason) for change in updated.changed_stops])
PY
```

## 2026-05-27 - `uncommitted` - `feat(route): stabilize POI seeds and enhance replan tooling`

负责人：POI 数据 / 路线策略 / 路线调整工具 / B 同学

### 更新概览

本次更新围绕 Demo 稳定性和路线调整工具可用性做了一轮集中增强。POI mock 数据从单一上海样例扩展为多城市候选池，避免北京、杭州、成都等常见测试城市返回空结果；路线召回增加了城市兜底和最小候选保障，让路线生成更稳定。

同时新增了路线点评接口 `/api/routes/evaluate`，方便 A 同学后续把已生成路线交给大模型做逐条点评；并进一步增强 `/api/routes/replan`，让路线调整工具不仅能处理排队、闭店、堵车、下雨、累了，也能处理“用户不喜欢某个 POI，希望只换这个点、其他保留”的主动调整场景。

### 主要变更

- 扩充 POI mock 数据：
  - `data/seed/pois.json` 扩展到 220 条 POI。
  - 保留上海 80 条，并新增北京、杭州、成都、广州、深圳、南京、苏州各 20 条。
  - 新增城市覆盖地标、博物馆/展览、餐厅、小吃/市集、咖啡、商场/室内、夜景、公园/街区等类型。
  - 所有新增 POI 保持唯一 `poi_id`，并补齐价格、排队、营业时间、适合时段、步行强度、室内/雨天/夜间/亲子/拍照等路线策略字段。

- 增强 POI 召回稳定性：
  - `POIService.search()` 在目标城市无数据时返回 mock fallback 候选，避免直接空结果。
  - 增加最小候选保障，默认尽量补足 12 条候选。
  - 当严格偏好过滤结果过少时，会放宽到同城低风险候选。
  - 扩展偏好别名，覆盖亲子友好、安静、人少、本地感、艺术展、夜游、情侣、老人友好等测试话术。
  - 调轻 fallback intent，避免用户没明确表达偏好时默认塞入过多过滤条件。

- 新增路线点评接口：
  - 新增 `POST /api/routes/evaluate`。
  - 输入已生成的 `routes + intent + 可选 user_profile`，不重新生成路线。
  - 输出每条路线的 `score`、`summary`、`highlights`、`risks`、`recommendation`、`source`。
  - LLM 可用时返回 `source: "llm"`；LLM 不可用时返回稳定 fallback，方便前端和 A 同学先联调。
  - `docs/api_contract.md` 已说明该接口应接在“路线生成之后、前端展示之前”，用于把 B 的结构化路线结果转成用户可读短评。

- 增强路线调整工具：
  - 继续复用 `POST /api/routes/replan`，不新增第二个路线调整接口。
  - 新增 `event_type`：`replace_poi`、`avoid_poi`、`preference_change`。
  - 扩展 `event_payload`：`affected_poi_id(s)`、`preserve_poi_ids`、`avoid_tags`、`prefer_tags`、`replacement_category`、`force_replace`、`warning_only`。
  - 支持用户主动要求“换掉某个 POI”，并尽量只替换指定点，保留其他点。
  - 支持“换成咖啡馆 / 餐厅 / 室内展览”等指定替代类型。
  - `preserve_poi_ids` 会阻止普通替换，除非 POI 已关闭、不可达或售罄。
  - 对轻度排队、人流变化、堵车等情况支持只返回 `live_warnings`，不强制替换。
  - 替代 POI 排序加入偏好标签、避让标签、预算、目标适配、距离和实时状态。

- 补充测试：
  - POI 数据质量和多城市覆盖测试。
  - 北京、杭州、成都等城市召回不为空。
  - 常见偏好组合召回不为空。
  - 多城市路线生成测试。
  - 路线点评 LLM/fallback 测试。
  - 用户主动替换 POI、指定替代类型、保留点不被替换、轻度排队只提醒、warning-only 不替换测试。
  - 完整后端测试已通过 `55 passed`。

### 涉及文件

- `data/seed/pois.json`
- `backend/app/services/poi_service.py`
- `backend/app/services/route_service.py`
- `backend/app/services/replan_service.py`
- `backend/app/services/route_evaluation_service.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/api/routes.py`
- `backend/app/schemas/route.py`
- `backend/app/tests/test_poi_service.py`
- `backend/app/tests/test_route_plan.py`
- `backend/app/tests/test_replan_service.py`
- `backend/app/tests/test_route_evaluation_service.py`
- `docs/api_contract.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 可以更稳定地调用 B 的 POI/路线工具，即使用户说北京、杭州、成都等城市也不会轻易空结果。 | 调用 `/api/routes/replan` 时，需要把自然语言解析成 `event_type + event_payload`；路线点评可调用 `/api/routes/evaluate`，不要让大模型重选 POI 或编造路线。 |
| B 同学：POI / 路线策略 | POI 数据和召回兜底更稳定；路线调整工具支持主动换点和 warning-only。 | 后续扩数据时要保持字段完整；路线调整仍以局部修复为主，不应推倒重来生成三条新路线。 |
| C 同学：前端 / UI | 路线和重规划结果更稳定，`live_warnings`、`changed_stops`、`replan_reason` 可用于展示调整过程。 | 如要展示大模型路线点评，可读取 `/api/routes/evaluate` 返回的 `evaluations` 并按 `route_id` 匹配路线卡片。 |

### 风险与注意事项

- 多城市 POI 仍是 mock 数据，不代表真实门店、真实价格或实时营业状态。
- `/api/routes/evaluate` 当前只是为 A 同学预留大模型点评接口，真实输出质量取决于后续 LLM provider 和 prompt 调试。
- 路线调整工具依赖 A 同学传入结构化 `event_type/event_payload`；B 侧不负责自然语言解析。
- `warning_only` 只阻止可用 POI 的普通替换；如果 POI 关闭、不可达或售罄，仍应允许替换。
- 重规划仍以局部替换为主，不会整条路线重新生成。

### 建议验证

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest
```

```bash
cd backend
PYTHONPATH=. .venv/bin/python - <<'PY'
from app.schemas.intent import Intent
from app.schemas.route import ReplanRequest, RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.replan_service import ReplanService

intent = Intent(city="北京", preferences=["citywalk", "拍照"], budget_per_person=300)
profile = ProfileService().get_profile("user_demo")
pois = POIService().search(intent, user_profile=profile)
route = RouteService().generate_routes(RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)).routes[0]
affected = route.stops[1]

response = ReplanService().replan(
    ReplanRequest(
        session_id="session_demo",
        selected_route_id=route.route_id,
        event_type="replace_poi",
        event_label="用户不想去这个点，换成咖啡馆",
        current_routes=[route],
        event_payload={
            "affected_poi_id": affected.poi_id,
            "replacement_category": "咖啡馆",
            "prefer_tags": ["安静", "咖啡"],
            "force_replace": True,
        },
        intent=intent,
        user_profile=profile,
    )
)

updated = response.routes[0]
print(updated.replan_reason)
print(updated.live_warnings)
print([(change.from_name, change.to_name, change.reason) for change in updated.changed_stops])
PY
```
