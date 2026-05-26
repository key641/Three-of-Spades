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
  - 覆盖“北京一日游”“2 人 / 人均 200 / 少排队 / 吃好”“今晚上海半天 citywalk”等话术。
  - 覆盖本轮显式城市优先于 onboarding 城市，以及 `一日游` 不进入 preferences。

### 涉及文件

- `backend/app/agent/orchestrator.py`
- `backend/app/agent/intent_enhancer.py`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/user.py`
- `backend/app/services/profile_service.py`
- `backend/app/tests/test_profile_request_sync.py`
- `backend/app/tests/test_intent_enhancer.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `frontend/src/api/chatApi.ts`
- `frontend/.env.example`
- `docs/api_contract.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `/api/chat` 已开始消费前端 onboarding 字段，也支持 seed 用户画像 fallback，并新增规则增强层。 | 后续 prompt 和 memory 逻辑要继续使用增强且合并后的 `Intent`；本轮用户显式城市应优先于历史画像城市。 |
| B 同学：POI / 路线策略 | POI 召回现在能拿到前端偏好和权重。 | 策略调参时可以假设 `user_profile.tags/preferences/preference_weights` 会来自前端画像。 |
| C 同学：前端 / UI | 前端传出的 `preferences/avoid_tags/preference_weights` 不再被后端静默丢弃。 | 联调真实后端时在 `frontend/.env` 设置 `VITE_USE_MOCK_CHAT=false` 和 `VITE_API_BASE_URL=http://localhost:8000`。 |

### 风险与注意事项

- 当前 `ProfileService` 只做了 seed 用户画像的 MVP 映射，复杂字段如历史行为、默认出发点还没有全部进入 `Intent`。
- `intent_enhancer` 是规则增强层，不替代 LLM；同义词表需要随着 B 的策略标签持续维护。
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
