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

```bash
cd backend
.venv/bin/python -m compileall app
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
