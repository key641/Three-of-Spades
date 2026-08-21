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

## 2026-08-21 - `uncommitted` - `perf(agent): Harness V3 类型边界、领域推断与诊断恢复优化`

负责人：Agent / 后端 / 评测

### 更新概览

- 在独立分支 `codex/travel-agent-harness-v3` 上验证架构级优化，保留 `keykii` 作为可回退基线。
- 增加模型输出类型归一、类型化歧义、确定性阻断 Policy、统一饭点需求引擎和 canonical 偏好 taxonomy。
- 路线无解时根据诊断执行 `3 → 2 → 1` 最少站点恢复，不再同参数机械重试。
- 同一套 30 条能力评测从 13/30（43.3%）提升到 24/30（80.0%），平均分从 79.2 提升到 97.7，未捕获异常从 3 降到 0。
- 剩余 6 个失败全部收敛到路线不足，下一阶段集中统一候选、约束验证和最终选路口径。

### 验证

- 后端全量回归：`284 passed`。
- 当前评测为单轮结果，尚不能作为 `stable-pass@3` 发布门禁。
- 本轮未提交、未推送、未合并；正式启用前继续保留 V1 回退路径。

### 详细文档

- `docs/agent_harness_v3_version_notes_20260821.md`
- `docs/agent_harness_v3_architecture.md`
- `docs/agent_v2_capability_eval_20260821.md`

---

## 2026-08-21 - `15d1667` - `feat(agent): Agent V2 稳定性、评测与诊断架构升级`

负责人：Agent / 后端 / 评测

### 更新概览

- 新增 `TripStateV2`、字段来源优先级、纯函数 Reducer 和 SQLite 状态事件，实现可恢复、可回放的权威旅行状态。
- 将每轮理解统一为 `TurnUnderstanding`，由确定性 Policy 决定回答、追问、规划或重规划。
- 新增标准工具协议和最多 5 步的 Plan–Act–Observe 执行器，按失败诊断执行扩大召回、减少站点或精准追问。
- 路线不足 3 条时保留已有合法路线；所有结果经 `OutcomeVerifier` 检查后再返回。
- 保留 LYNN、多目标 Fine Rank、现有路线服务、`/api/chat`、流式接口和前端兼容。
- 新增 V1/Shadow/V2 运行模式，默认仍为 V1。
- Eval V3 支持 Golden Patch、Golden State、工具与恢复动作、单 Case 超时、`pass@1`、`stable-pass@3` 和版本记录。
- 行程覆盖午餐或晚餐时推断 `implicit_needs: meal`，确保路线包含正餐；明确不吃饭时取消该需求。

### 用户可感知改进

- 明确起点不会再被 GPS 覆盖，未明确起点时优先使用当前位置。
- 凑不够三条路线时能出几条出几条，不再直接清空。
- LLM 总结失败时仍能看到路线，不再暴露 `ConnectError`、`AttributeError` 等内部异常。
- 路线无解时能够说明具体约束原因，并采取对应恢复动作。
- 覆盖饭点的行程会自动安排吃饭。

### 验证

- 合并前全量后端回归：`276 passed`。
- 前端 TypeScript 与生产构建通过。
- V2 实际烟测返回 3 条路线；饭点烟测中 3 条路线均包含正餐节点。

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| Agent / 后端 | V2 以 `TripStateV2` 为唯一权威状态，旧 Intent 仅为兼容投影 | 新字段应先进入 State Patch 和 Reducer，不要新增第二份可写状态 |
| POI / 路线策略 | 路线算法继续由 LYNN 和 Fine Rank 提供，V2 通过工具协议调用 | 工具必须返回结构化诊断，部分合法路线不能清空 |
| 前端 / UI | `ChatResponse` 新增可选 outcome/version/trace/warnings/degradation | 旧响应仍兼容；可逐步展示 partial 和 degradation 状态 |

### 风险与注意事项

- 合并后默认运行模式仍为 `v1`；需要通过环境变量显式启用 `shadow` 或 `v2`。
- Shadow 只读执行，不应重复写画像、曝光或状态事件。
- 灰度前应使用真实 Query 批量评测，不建议直接全量切换。

### 详细文档

- `docs/agent_v2_test_architecture_and_improvements.md`
- `docs/agent_architecture_v2.md`
- `docs/evaluation.md`

---

## 2026-07-21 - `uncommitted` - `perf(route): 收口三路线率、性能与发布门禁`

- 必去点和必要角色进入 Beam 状态；增加 objective Top30、角色配额和邻近候选保护。
- 路线选择采用全局组合重排及四级软多样性降级，短场景允许带 warning 的两站轻量路线。
- Mock 地图单例缓存、统一路段缓存、双交通方式比较和精排批处理显著降低 P95。
- 120 案例支持逐案例诊断、分桶、候选规模及模块消融，并可作为 CI 发布门禁。
- 路线曝光和反馈迁移到 SQLite，新增 JSONL 导出、路线模型训练准入及模型启用保护。
- 新增 Python 3.12 / Node 20 CI 和定时消融工作流。

---

## 2026-07-21 - `uncommitted` - `feat(route): 路线策略 v2 完整漏斗与可靠性升级`

负责人：路线策略 / B 同学

### 更新概览

- 正式接通多路召回、加权 RRF、粗排和 objective 专属精排，自适应候选池替代固定 40 条。
- 路线生成升级为状态级 Beam Search，近似路段用于搜索，前 8 条候选再补完整地图信息。
- 恢复路线级动态重排，跨路线从零重合改为 50% 软重合，must-include 锚点允许共享。
- 新增统一约束评估和 P50/P80、缓冲、可靠性、风险与 warning 字段。
- 动态重规划结合剩余缓冲判断排队替换阈值，反馈接口记录路线级学习信号。
- 新增 120 case 离线评测、候选规模消融和主链路集成测试。

### 兼容性

- 现有 Route 和 API 核心字段不变，新增字段均为可选或有默认值。
- `poi_relevance_scores` 继续作为 `balanced` fallback。
- 可用 `PLANNING_PIPELINE_V2` 和 `PLANNING_PIPELINE_SHADOW` 切换或影子比较 POI 漏斗。

---

## 2026-06-07 - `2376eb6` - `feat(frontend): 优化 Agent 思考过程展示`

负责人：前端 / UI / C 同学

### 更新概览

本次更新对聊天页「Agent 思考过程」展示面板进行全面优化，将原来一次性弹出的结构化数据列表改为打字机逐字输出的自然语言叙述，同时清除所有面向用户不友好的内部技术信息。

用户可感知的变化：
- 思考过程展开后文字以打字机效果逐字输出（32ms/字符），配合末尾闪烁光标，体验更流畅自然。
- 叙述内容改为纯自然语言，不再出现「置信度 87%」「召回 46 个候选点」「等待后端…」等技术词汇。
- 后端处理出现内部异常（如 ValidationError）时，前端静默处理，不向用户暴露错误细节。
- 所有阶段性进度提示统一显示「正在思考」，消除技术感。

### 主要变更

- **打字机输出**：
  - `AgentTrace` 组件引入 `useTypewriter` hook，`narrative` 字符串变化时从上次结束位置继续逐字追加，不重头播放。
  - 打字过程中末尾显示绿色竖线光标（`trace-typewriter-cursor`），打字结束后消失。
  - loading 阶段打字完成后才在末尾显示旋转图标 + 进度文字，避免与光标抢位。
- **去除内部数据展示**：
  - `route_message` 步骤去除置信度百分比。
  - `build_strategy_weights` 步骤不再展示权重排名数值，改为「正在根据你的偏好生成路线排序策略」。
  - `search_pois` 步骤去除召回数量，改为「筛选周边候选地点」。
  - `generate_routes` 步骤去除路线数量，改为「生成候选路线」。
- **错误静默**：`fallback` / `error` 状态步骤直接跳过，不拼入叙述文本。
- **进度文案统一**：`NEXT_STEP_HINTS` 所有条目及兜底值统一改为「正在思考」。
- **折叠按钮状态文案**：`已记录 N 个处理步骤` → `思考完毕`，`N 项需要关注` → `处理过程中遇到了一些问题`。

### 涉及文件

- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/utils/agentThinking.ts`
- `frontend/src/styles/globals.css`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 无 | 后端 trace 数据结构无需变更，前端只改展示逻辑 |
| B 同学：POI / 路线策略 | 无 | — |
| C 同学：前端 / UI | 涉及 AgentTrace 组件和全局样式 | 打字机速度可在 `useTypewriter` 调用处调整 speed 参数 |

### 风险与注意事项

- 打字机为纯前端动画，不影响数据流和请求逻辑。
- loading 阶段 narrative 字符串会随 steps 增长而变长，打字机增量追加，不会重置，但若同一轮 narrative 缩短（理论上不会）则会重置重播。

### 建议验证

- 发起一次新路线规划，确认思考面板文字逐字打出、光标闪烁、打字结束后显示「正在思考」旋转图标。
- 确认展开已完成的思考面板，文字重新打字机输出且无置信度/数量等内容。
- 确认后端返回 fallback/error 步骤时，思考面板不出现 ValidationError 等字样。

---

## 2026-06-06 - `uncommitted` - `feat(route): 局部 POI 修改升级为候选生成链路`

负责人：路线策略 / 局部重规划 / B 同学

### 更新概览

本次更新把“修改路线中的一些 POI”从单点贪心替换升级为小型推荐链路。局部修改会先确定受影响的 future stops，再为每个位置召回多个替代 POI，用 beam search 组合成多条局部候选路线，最后复用路线评分和路线层重排选出最佳修改版本。

用户可感知的变化是：一次可以同时替换多个路线点；替换结果不再只找同类 POI，而是综合路线角色、偏好、时间、预算、排队、交通和精排 relevance；替换后会重新计算后续时间线和交通步骤。

### 主要变更

- `ReplanService` 支持多点局部修改：
  - `event_payload.affected_poi_ids` 可指定多个受影响 POI。
  - `replace_count` 可限制本次最多替换几个点，不传时默认等于 affected 数量。
  - `preserve_poi_ids` 和 `locked_poi_ids` 继续默认保留，闭店、不可达、售罄除外。
- 替代候选链路升级：
  - 每个待替换位置默认召回 top 8 个替代 POI。
  - 候选不只限同 category，会按 route_roles、primary_category、experience_tags、suitable_time_slots、prefer/avoid tags、预算、排队、距离和营业情况综合召回。
  - 替代评分叠加 `FineRankService` 的 POI relevance。
- 局部候选路线生成：
  - 多点替换用 beam search 组合候选，默认 beam width 为 6，最多生成 10 条局部候选路线。
  - 每条局部候选都会重建后续 stops 的开始/结束时间、交通方式、距离和 `route_steps_from_previous`。
  - 最终复用 `ScoringService` 和 `RouteRerankService` 选择最佳局部修改路线。
- API 兼容：
  - 继续使用 `POST /api/routes/replan`。
  - 返回结构仍是原有 `RoutePlanResponse`，通过 `changed_stops / live_warnings / replan_reason` 表达差异。

### 涉及文件

- `backend/app/services/replan_service.py`
- `backend/app/tests/test_replan_service.py`
- `docs/api_contract.md`
- `docs/route_strategy_logic.md`
- `docs/version_log.md`
## 2026-06-06 - `8ed898f` - `feat(frontend): 地图节点联动、行程结束评价修复及交互优化`

负责人：前端 / UI / C 同学

### 更新概览

本次提交集中解决了「删节点后地图不响应」的问题，修复了「行程结束」评价弹窗在删节点后无法触发的 bug，同时完成了追问体验优化、方案选择重构和总结页地图一致性改造。

用户可感知的变化：
- 在展开详情视图或行程轨道里删除任意节点后，地图立即同步移除对应标点并重绘路线连线。
- 每条方案最少保留 1 个节点，删除按钮在只剩 1 个节点时显示"至少保留 1 个节点"并禁用。
- 删节点后点击「行程结束」按钮，评价卡片正常弹出，不再静默失效。
- AI 回复前统一显示"理解！正在规划"或"我想知道这些信息帮助规划"前置引导语。
- 首页「猜你喜欢」和「我的行程」中的「选这条」按钮，点击后生成包含路线信息的提示词注入聊天框，启动基于该参考的新规划，而非直接跳转。
- 地图不再在结束行程、切换方案等操作时自动全屏（peek），只有手动上划面板才触发地图全屏。
- 总结页地图替换为与规划页一致的高德瓦片 Leaflet 地图，展示真实路线节点和连线。

### 主要变更

- **地图数据流重构（核心）**：
  - `PlannerPage` 新增 `mapStops` state，作为驱动 `MapPanel` 的唯一数据源，完全与 `response.routes` 解耦。
  - 用户点击「选这条」或「查看地图」时，`setMapStops([...route.stops])` 立即初始化地图。
  - 删节点时，`setMapStops(newStops)` 直接更新地图，不经过 `routes` 引用变化链路。
  - `MapPanel.useEffect` 依赖简化，停止 fallback 到 `routes`，只响应 `liveStops`。

- **修复展开详情视图删节点地图不响应**：
  - 根因：`RouteCard → RouteTimeline` 的 `onStopsChange` 只更新 `RouteCard` 内部 `localStops`，不会冒泡到父级。
  - 修复：`RouteCard` 新增 `onStopsChange` prop（签名 `(routeId, stops) => void`），在本地 state 更新的同时向上回调。
  - `RouteCompare` 展开详情里的 `RouteCard` 接入 `onStopsChange={(routeId, newStops) => onLiveStopsChange?.(routeId, newStops)}`，打通完整冒泡链路。

- **删除按钮最少 1 节点限制**：
  - `RouteTimeline` 的 `PoiPopover` 删除按钮新增 `disabled={stopsTotal <= 1}` 和"至少保留 1 个节点"文案。
  - `ActiveTripBar` 节点操作菜单删除按钮同样加入 `disabled` 和文案保护。

- **修复删节点后「行程结束」评价不弹出**：
  - 根因：`handleDeleteStop` 会把 `activeIdx` clamp 到新末站（`Math.min(prev, newStops.length - 1)`），导致 `handleArrived` 里的条件 `activeIdx !== stops.length - 1` 为 false，`setShowFeedback(true)` 无法执行。
  - 修复：将条件改为 `!showFeedback && !tripEnded`，只要评价卡片未展示过，到达末站就触发。

- **追问体验优化**：
  - `useChat` 拦截后端响应，根据 `need_clarification` 状态动态在正文前插入引导消息。
  - 不需要追问时显示"理解！正在规划"；需要追问时显示"我想知道这些信息帮助规划"。
  - 后端 `ClarificationPolicy` 同步优化：每轮会话最多追问 1 次，单次最多合并 3 个问题。

- **方案选择重构**：
  - 首页和「我的行程」的「选这条，出发！」改为「选这条」。
  - 点击后构造包含路线标题、节点和偏好的自然语言提示词，注入 `PlannerPage` 聊天框，触发基于参考的新规划。

- **总结页地图替换**：
  - `TripSummaryOverlay` 新增 `SummaryMap` 组件，使用 Leaflet + 高德瓦片渲染。
  - 复用 `MapPanel` 的坐标解析、颜色和标记逻辑，与规划页地图完全一致。

- **地图自动全屏行为移除**：
  - `onRoutePreview`、`onLiveStopsChange` 等回调中移除了 `setSheetSnap("peek")` 调用。
  - 地图全屏仅由用户手动上划面板触发。

### 涉及文件

- `frontend/src/pages/PlannerPage.tsx`
- `frontend/src/components/MapPanel.tsx`
- `frontend/src/components/RouteCard.tsx`
- `frontend/src/components/RouteCompare.tsx`（含 `ActiveTripBar`）
- `frontend/src/components/RouteTimeline.tsx`
- `frontend/src/components/TripSummaryOverlay.tsx`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/hooks/useOnboarding.ts`
- `frontend/src/api/chatApi.ts`
- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/styles/globals.css`
- `backend/app/agent/clarification_policy.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/main.py`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 解析局部修改时可以传多个 `affected_poi_ids` 和 `replace_count`，不需要新增工具接口。 | 如果用户说“这两个点都换掉”，应结构化为 `affected_poi_ids`；如果说“先换一个”，应传 `replace_count=1`。 |
| B 同学：POI / 路线策略 | 局部修改开始复用候选生成、精排和路线重排思想。 | 调试时需要看替代候选、beam 组合、最终 changed_stops，而不是只看单个 replacement_score。 |
| C 同学：前端 / UI | API 返回结构不变，但 `changed_stops` 可能包含多条替换记录。 | 前端差异展示需要支持一次展示多个替换项；原有单条展示逻辑仍可兼容第一条。 |

### 风险与注意事项

- 本阶段仍是局部修改，不会生成三条全新路线。
- 外部地图候选仍是兜底能力，默认优先本地 POI。
- 多点替换会增加少量计算，但候选数量限制在 10 条局部路线以内。

### 建议验证

- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests/test_replan_service.py -q`
- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests/test_route_plan.py app/tests/test_predictive_route_service.py app/tests/test_route_rerank_service.py -q`
- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests -q`
| A 同学：Agent / 后端 | `ClarificationPolicy` 新增最多追问 1 次、单次合并 3 个问题的限制。 | 后续调整追问策略时修改 `MAX_CLARIFICATION_ROUNDS` 和 `MAX_QUESTIONS_PER_ROUND` 常量；`clarification_count` 由 `SessionState` 维护，确保多轮正确累加。 |
| B 同学：POI / 路线策略 | 本次不涉及 POI 召回、路线生成或评分算法。 | 无需关注。 |
| C 同学：前端 / UI | 地图数据流已解耦为独立 `mapStops` state；删节点操作同时更新地图和底层 `response.routes`（通过 `patchRouteStops`）。 | 后续新增地图操作时，直接调用 `setMapStops` 即可驱动地图，无需关心 `routes` 引用变化；`activeRouteIndex < 0` 时地图不渲染任何标记，需确保操作前已调用 `setMapRouteIndex`。 |

### 风险与注意事项

- `mapStops` state 与 `response.routes` 已解耦，删节点后两者都会更新（`setMapStops` + `patchRouteStops`），但若只更新其中一个会导致地图与底层数据不一致，后续修改时需保持同步。
- `RouteTimeline` 删节点有约 1080ms 动画延迟（280ms 淡出 + 800ms 重算），地图更新会在这之后触发，属正常行为。
- `TripSummaryOverlay` 的 `SummaryMap` 使用高德瓦片，依赖网络，离线环境下会退化为空白底图但标记仍可显示。
- 追问前置引导语通过前端拦截插入，不是后端返回的消息，重置会话时需注意清理。

### 建议验证

- 展开任意方案详情 → 点击节点 `···` → 删除该节点 → 确认地图同步移除对应标点并重绘连线。
- 选择方案后在行程轨道中删除节点 → 确认地图同步更新。
- 方案只剩 1 个节点时，确认删除按钮显示"至少保留 1 个节点"并不可点击。
- 到达末站后删除某节点，再点击「行程结束」→ 确认评价卡片正常弹出。
- 首页点击「选这条」→ 确认跳转规划页并在聊天框预填路线相关提示词。
- 完成行程后进入总结页 → 确认地图与规划页一致，显示高德底图和路线节点。

---

## 2026-06-05 - `uncommitted` - `feat(route): 增加路线常识约束和交通步骤兜底`

负责人：路线策略 / Mock 地图 / B 同学

### 更新概览

本次更新解决路线生成中“分数高但现实不合理”的问题。路线生成不再只考虑 POI 质量、偏好和距离，而是在候选扩展、路线评分和最终重排里加入时间、天气、人群、餐饮节奏、体力和交通常识。

用户可感知的变化是：夜间夜景路线不会再默认推荐普通咖啡店；雨天、高温、少走路、亲子/老人等场景下，路线会更倾向室内、低步行、交通更顺的点位；每段交通也会稳定带有可读步骤，不会只给空的交通方式。

### 主要变更

- 路线生成新增常识约束：
  - `RouteService` 增加 `_common_sense_penalty()`、`_is_contextually_reasonable_poi()` 和 `_route_common_sense_penalty()`。
  - `20:00` 后普通夜游路线不再补普通咖啡店；明确“咖啡/咖啡探店”时允许咖啡，但每条路线最多一个。
  - 正餐和咖啡拆分判断，避免把“吃好”和“咖啡休息”互相替代。
  - 雨天、高温、少走路、亲子、老人等场景会降低户外高强度 POI 和连续高强度点位。
- 路线评分和重排同步兜底：
  - `ScoringService.hard_penalty()` 增加常识惩罚。
  - `RouteRerankService` 在最终路线层继续惩罚夜间咖啡、恶劣天气高强度户外、低体力用户高强度路线。
  - 推荐理由可补充“时间、天气和体力安排更符合实际”。
- 交通路线增强：
  - 夜间中长距离更倾向打车，公共交通只有在耗时仍合理时胜出。
  - 少走路用户继续避免超过 1 公里的步行段。
  - `AmapService` fallback 也会生成 `route_steps_from_previous`，例如步行、打车、地铁/公交衔接说明。
- 测试同步：
  - 新增夜间非咖啡意图不出咖啡、显式夜间咖啡最多一个、雨天高温避开高强度户外、交通步骤具体可读等测试。

### 涉及文件

- `backend/app/services/route_service.py`
- `backend/app/services/scoring_service.py`
- `backend/app/services/route_rerank_service.py`
- `backend/app/services/amap_service.py`
- `backend/app/tests/test_route_plan.py`
- `docs/route_strategy_logic.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 路线结果更符合现实语境，夜间/雨天/少走路等偏好不需要额外由 LLM 兜底解释。 | 总结路线时可直接引用 `Route.reasons` 和 stop 交通字段，不要自行编造交通细节。 |
| B 同学：POI / 路线策略 | 路线生成新增上下文常识分，调参时需要同时看 POI 分、常识惩罚、路线重排原因。 | 扩充 POI 时要维护 `suitable_time_slots`、`night_activity`、`indoor`、`walking_intensity`、`route_roles`。 |
| C 同学：前端 / UI | API 字段不变，但 `route_steps_from_previous` 更稳定，可用于路线详情展示。 | 前端展示交通时优先使用 steps；如果 steps 为空再兜底展示 mode/distance/minutes。 |

### 风险与注意事项

- 常识约束仍是规则模型，不是路线级机器学习模型。
- 除闭店、超时、最晚入场和夜间普通咖啡这类强错误外，大部分常识以降权为主，避免候选池被清空。
- mock/fallback 交通步骤追求演示可信，不代表真实导航精度。

### 建议验证

- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests/test_route_plan.py -q`
- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests/test_predictive_route_service.py app/tests/test_replan_service.py app/tests/test_route_rerank_service.py -q`
- `cd backend && PYTHONPATH=. .venv/bin/pytest app/tests -q`

---

## 2026-06-05 - `8b4f6e0` - `feat(route): 动态路线层重排`

负责人：路线策略 / B 同学

### 更新概览

本次更新把最终排序从“每个 objective 内部选最高分路线”升级为路线集合级动态重排。路线最终分不再使用固定死权重，而是根据用户偏好、画像敏感度、策略标签和路线目标动态调整：省钱用户更看重预算风险，少走路用户更看重交通效率，拍照 citywalk 用户更看重体验和结构完整性。

### 主要变更

- 新增 `RouteRerankService`：
  - 汇总所有 objective 的 scored candidates 后统一重排。
  - 动态融合 POI 精排均值、路线结构、交通效率、objective 匹配、预算排队风险和路线多样性。
  - 根据已选路线实时计算剩余路线的 POI 重合率，降低高度重复路线。
- `RouteService.generate_routes_for_objectives()` 改为：
  - 先生成并评分所有候选路线。
  - 再调用路线层 rerank。
  - 最终仍返回原有 `RoutePlanResponse(routes)` 结构。
- 推荐理由增强：
  - 将“更符合少走路偏好”“预算和排队风险更稳”“路线结构更完整”“重复点少”等重排原因追加到 `Route.reasons`。
- 测试同步：
  - 新增动态重排单测，覆盖预算、少走路、美食扫街放宽、多样性等场景。
  - 更新旧测试中“balanced 不能排第一”的假设，因为动态重排后 balanced 可以因风险稳定性排在首位。

### 涉及文件

- `backend/app/services/route_rerank_service.py`
- `backend/app/services/route_service.py`
- `backend/app/tests/test_route_rerank_service.py`
- `backend/app/tests/test_route_plan.py`
- `docs/route_strategy_logic.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 路线返回结构不变，但最终路线顺序现在会受用户画像和偏好动态影响。 | 如果 trace 中看到 balanced 排第一，这是允许的，说明路线层认为它对当前用户更稳。 |
| B 同学：POI / 路线策略 | 路线排序从单条路线评分升级为路线集合重排。 | 调参时需要同时看单路线 `score_breakdown` 和路线间重合、多样性、风险原因。 |
| C 同学：前端 / UI | API 字段不变，路线理由可能出现新的解释文案。 | 前端无需改类型；展示 `reasons` 时要允许更偏策略解释的短语。 |

### 风险与注意事项

- 当前动态权重仍是规则模型，不是路线级学习排序模型。
- `RouteScoreBreakdown` 未扩字段，前端看不到独立 rerank breakdown；目前通过 `reasons` 和 `summary` 解释。
- 强偏好用户会弱化多样性权重，避免为了不同而牺牲核心目标。

### 建议验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests/test_route_rerank_service.py -q`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests/test_route_plan.py backend/app/tests/test_predictive_route_service.py backend/app/tests/test_replan_service.py -q`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests -q`
  - 当前验证结果：`190 passed, 11 subtests passed`

---

## 2026-06-05 - `4b4cc80` - `feat(route): 路线候选生成升级为 beam search`

负责人：路线策略 / B 同学

### 更新概览

本次更新解决“高分 POI 直接拼起来不一定是好路线”的问题。路线生成从每个 objective 最多 4 条贪心候选，升级为多 seed + beam search 的路线候选生成：先从精排 POI 中选多类目 seed，再扩展多条 partial route，最终生成约 10-30 条内部候选路线进入评分和重排。

### 主要变更

- `RouteService` 新增内部候选生成参数：
  - `INTERNAL_CANDIDATES_PER_OBJECTIVE = 10`
  - `START_SEEDS_PER_OBJECTIVE = 12`
  - `BEAM_WIDTH = 6`
  - `BRANCH_FACTOR = 8`
- 路线生成逻辑升级：
  - `_diverse_start_seeds()` 从高分 POI 中选择多类目 seed。
  - `_build_beam_candidates()` 用 beam search 扩展路线。
  - `_beam_next_candidates()` 每轮只扩展可行的 top POI。
  - 保留 `_build_candidate()` 贪心逻辑作为候选不足时的兜底。
- 候选质量控制：
  - 按 stop poi_id 序列去重。
  - 过滤高度重合路线。
  - 扩展时继续复用 `_poi_score()`、`nearby_bonus`、`distance_penalty`、`diversity_penalty` 和 `missing_role_bonus`。
- 测试同步：
  - 新增内部候选数量、总候选数量、多 seed 覆盖、beam 结果不等于纯 POI 分顺序等测试。

### 涉及文件

- `backend/app/services/route_service.py`
- `backend/app/tests/test_route_plan.py`
- `docs/route_strategy_logic.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | `RouteService.generate_routes()` 接口不变，但内部候选更多，路线结果更像完整行程而不是高分 POI 列表。 | 如果请求变慢，优先看候选数量、地图路段和 mock/高德 provider。 |
| B 同学：POI / 路线策略 | 路线生成开始依赖多 seed、beam 扩展和结构约束共同决定候选池。 | 调路线时不能只看 POI 分数，还要看路段、角色补全、候选去重和重合过滤。 |
| C 同学：前端 / UI | API 返回结构不变，路线卡仍展示同一套 Route/RouteStop 字段。 | 路线顺序和 POI 组合可能更丰富，前端无需新增字段。 |

### 风险与注意事项

- 当前没有引入 OR-Tools 或全局路径优化，仍是可解释 beam search。
- 候选数量增多会增加一些路线生成耗时，但默认控制在 10-30 条内部候选。
- 强约束或候选不足时会退回贪心兜底，优先保证可用路线不为空。

### 建议验证

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests/test_route_plan.py -q`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests/test_predictive_route_service.py backend/app/tests/test_replan_service.py -q`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/app/tests -q`
  - 提交时验证结果：`186 passed, 11 subtests passed`

---

## 2026-05-31 - `5c38be4` - `feat(stream): 高德路线缓存与路线渐进返回`

负责人：后端路线生成 / 前端流式展示 / A、B、C 同学

### 更新概览

本次更新针对路线生成慢、重复请求高德的问题做优化：后端会按 `origin + destination + mode` 对高德路径结果做内存缓存，重复计算同一段路时直接复用结果；同时流式接口新增路线增量事件，后端每生成出一条可用方案，就先推给前端展示，剩余方案继续在后台生成。

### 主要变更

- `AmapService.route_leg()` 增加内存缓存：
  - 缓存键为起点、终点和交通模式。
  - 同一段路并发请求时只放行一个高德请求，其他相同请求等待并复用结果。
  - 高德不可用时生成的兜底路段也会缓存，避免反复失败重试。
- `RouteService.generate_routes()` 增加 `on_route` 回调：
  - 每个目标路线选出最佳方案后立即回调。
  - 最终仍返回完整 `RoutePlanResponse`，不影响原有调用方。
- `/api/chat/stream` 新增 `routes` 流式事件：
  - 前端收到后立即更新路线卡。
  - 没有路线时继续显示骨架屏，有第一条路线后直接展示真实卡片。
- 前端 `useChat`、`chatApi`、类型定义同步支持增量路线事件。
- `RouteCompare` 增加前端渐进露出：
  - 即使浏览器或后端 final 一次性拿到多条路线，也会先显示第一条，再按节奏补齐后续方案。
  - 标题会显示“已生成 x / y 条”，让用户知道剩余方案还在出现。

### 涉及文件

- `backend/app/services/amap_service.py`
- `backend/app/services/route_service.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/api/chat.py`
- `backend/app/tests/test_amap_service.py`
- `backend/app/tests/test_chat_stream.py`
- `backend/app/tests/test_route_plan.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/chatApi.ts`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/components/RouteCompare.tsx`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 流式接口会在最终回答前多次发送路线增量事件。 | 后续新增耗时步骤时，可以继续用 progress 或 routes 事件提前反馈。 |
| B 同学：POI / 路线策略 | 高德同路段结果会复用，减少重复请求和等待时间。 | 如果后续接实时路况，需要考虑缓存过期时间；当前 demo 阶段是进程内短期缓存。 |
| C 同学：前端 / UI | 路线卡可以先展示第一条方案，后续方案逐步补齐；即使一次收到多条也会渐进露出。 | 前端需要把 `routes` 事件视为中间态，最终仍以 `final.response.routes` 为准。 |

### 风险与注意事项

- 当前缓存是进程内内存缓存，服务重启后会清空。
- 当前没有设置 TTL，适合 demo 阶段减少重复请求；如果接入实时路况，应增加过期时间或按路况模式关闭缓存。
- 增量路线事件只影响 `/api/chat/stream`，普通 `/api/chat` 仍一次性返回完整结果。

### 建议验证

- `.\backend\.venv\Scripts\python.exe -m unittest app.tests.test_chat_stream`
- 手动运行 `test_amap_service.py` 中的高德缓存测试，确认同一路段只请求一次。
- 在 `frontend` 目录运行 `npx.cmd tsc --noEmit`

## 2026-05-31 - `0308334` - `fix(ui): 每轮保留 Agent 思考过程并中文化字段`

负责人：前端 / Agent trace 展示 / C 同学

### 更新概览

修复上一轮对话的 Agent 思考过程在下一轮开始时消失的问题，并继续把 trace details 中的英文字段翻译成通俗中文。现在每条 assistant 消息会携带自己的 Agent trace，后续发送新消息时不会覆盖旧轮次的思考过程。

### 主要变更

- `useChat` 在最终响应返回后，把 `agent_trace` 写入当前 assistant 消息。
- `ChatPanel` 在每条 assistant 消息下方展示对应轮次的 `AgentTrace`。
- `AgentTrace` 优化 details 展示：
  - 去掉重复机器字段。
  - 增加更多字段和值的中文映射。
  - `done/fallback/error` 状态显示为中文。
- 运行中的 trace 仍使用 `liveTrace` 实时展示，完成后沉淀到消息历史中。

### 涉及文件

- `frontend/src/hooks/useChat.ts`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/utils/agentThinking.ts`
- `frontend/src/utils/traceIcons.ts`
- `frontend/src/styles/globals.css`
- `frontend/src/api/chatApi.ts`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 每轮 trace 都会长期展示，便于定位意图和状态合并问题。 | 新增 trace 字段时最好给出可读 label 或同步前端映射。 |
| B 同学：POI / 路线策略 | 旧轮次的召回、路线生成信息不会被下一轮覆盖。 | 调路线为空或评分异常时，可以回看对应轮次 trace。 |
| C 同学：前端 / UI | Agent 思考过程现在绑定在消息维度，而不是全局单份状态。 | 后续可考虑折叠默认策略和移动端高度优化。 |

### 风险与注意事项

- trace 是可解释过程记录，不是模型原始推理内容。
- 如果后端返回新的英文枚举，前端仍需要继续补中文映射。

### 建议验证

- 连续发送两轮消息，第一轮 assistant 下方的 Agent 思考过程仍保留。
- 展开 trace，常见字段应显示中文且无明显重复。

---

## 2026-05-31 - `0308334` - `feat(route-ui): 路线卡展示站点间交通信息`

负责人：路线策略 / 前端展示 / B、C 同学

### 更新概览

路线时间线现在会在相邻站点之间展示交通方式、预计耗时和距离，方便用户理解每一段怎么走。后端在用户没有提供起点坐标时，会使用城市中心坐标作为默认起点，避免首段路线缺少交通字段。

### 主要变更

- `RouteService` 增加城市中心默认起点：
  - 当 `start_lat/start_lng` 为空时，按城市补一个中心坐标。
  - 这样首个 POI 也能生成 `travel_minutes_from_previous`、`distance_km_from_previous`、`transport_mode_from_previous` 等字段。
- `RouteTimeline` 增加路段交通展示：
  - 从第二个站点开始展示从上一站过来的交通方式。
  - 支持步行、地铁、公交、打车、驾车、骑行等中文映射。
  - 展示预计分钟数和公里 / 米级距离。
- mock 数据补充站点间交通字段，便于前端独立预览。

### 涉及文件

- `backend/app/services/route_service.py`
- `frontend/src/components/RouteTimeline.tsx`
- `frontend/src/styles/globals.css`
- `frontend/src/api/chatApi.ts`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 路线解释和前端展示都能读取更完整的路段信息。 | 如果用户提供真实出发点，应优先使用真实坐标而不是城市中心。 |
| B 同学：POI / 路线策略 | 默认起点会影响首段交通耗时和总路程。 | 后续可把默认起点改成用户画像里的常用出发地。 |
| C 同学：前端 / UI | 路线卡时间线会显示相邻点交通方式、耗时和距离。 | 如果新增交通方式枚举，需要同步中文映射。 |

### 风险与注意事项

- 城市中心只是 demo 默认值，不代表用户真实出发点。
- 地图可视化阶段仍应鼓励用户补充出发位置，以提升首段交通准确性。

### 建议验证

- 前端路线卡中，从第二站开始能看到“步行/地铁/打车 + 分钟 + 距离”。
- 后端无起点坐标时，路线 stop 中仍有 `travel_minutes_from_previous` 和 `distance_km_from_previous`。

---

## 2026-05-31 - `0308334` - `fix(stream): Agent 思考步骤实时刷出`

负责人：Agent / 后端编排 / 前端联调

### 更新概览

修复 Agent 思考过程中只有第一步能实时显示，后续“继承上一轮上下文、解析状态变更、召回 POI、生成路线”等步骤要等规划完成后才一起出现的问题。现在后端每推送一个流式事件后会主动让出事件循环，让前端可以及时收到进度。

### 主要变更

- `/api/chat/stream` 新增 `enqueue_stream_event()`：
  - 写入 progress/final/error/done 事件后执行一次事件循环让出。
  - 避免同步路线生成逻辑把已经进入队列的进度事件憋到最后。
- 新增流式测试：
  - 验证入队后等待中的消费者能立即拿到 progress。
  - 保留原有“progress 早于 final”的接口测试。

### 涉及文件

- `backend/app/api/chat.py`
- `backend/app/tests/test_chat_stream.py`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 流式事件会更及时推到前端。 | 后续新增长耗时步骤时，继续通过 progress_callback 发 trace。 |
| B 同学：POI / 路线策略 | POI 召回和路线生成前后的 trace 会更早展示。 | 如果某个策略步骤耗时长，建议拆出更细粒度 trace。 |
| C 同学：前端 / UI | AgentTrace 不需要改逻辑即可实时显示更多步骤。 | 如果仍有卡顿，优先看浏览器 Network 的流式 chunk 是否及时到达。 |

### 风险与注意事项

- 这是流式刷新节奏优化，不改变最终路线结果。
- 若某个单独同步函数内部耗时很长，只有函数前后的 trace 能实时展示；函数内部还需要额外埋点才能更细。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_chat_stream`

---

## 2026-05-31 - `0308334` - `fix(agent): 相对省钱诉求不再覆盖硬预算`

负责人：Agent / 后端编排 / A 同学

### 更新概览

修复用户要求“重新规划、降低人均消费”后，人均预算从上一轮 200 被错误改回默认 300 的问题。现在没有明确金额的相对省钱诉求，只会作为“更省钱”偏好参与路线评分，不会改写 `budget_per_person` 硬约束。

### 主要变更

- 在状态变更归一化层增加预算保护：
  - 如果用户没有明确说出金额，例如“降低人均消费”“更省钱一点”，会移除 LLM 误写入的 `budget_per_person`。
  - 同时补充“更省钱”偏好，让路线策略按省钱目标重新排序。
  - 如果用户明确说“人均150以内”“总预算300”，仍允许更新硬预算。
- 新增回归测试覆盖：
  - 相对省钱诉求不能把上一轮预算 200 改成默认 300。
  - 明确金额诉求可以把预算改成指定值。

### 涉及文件

- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | LLM 状态变更结果会被预算保护层校验。 | 后续相对表达不要直接落硬字段，先落偏好或策略目标。 |
| B 同学：POI / 路线策略 | “更省钱”会通过偏好和权重影响候选排序。 | 如果需要更激进降价，需要用户给明确金额或后续定义预算降幅策略。 |
| C 同学：前端 / UI | trace 中不会再显示预算从 200 变 300 的错误变更。 | 可以提示用户“要不要设定具体人均预算”。 |

### 风险与注意事项

- 当前不会自动把 200 降成某个固定数值，因为“降低”没有明确目标金额；系统只会把目标改成省钱优先。
- 后续如果需要“自动降低 20%”这类策略，应作为单独产品规则设计。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_orchestrator_intent_flow.OrchestratorIntentFlowTest.test_relative_budget_request_does_not_raise_previous_budget_to_default app.tests.test_orchestrator_intent_flow.OrchestratorIntentFlowTest.test_explicit_budget_amount_can_change_previous_budget`
- `.\.venv\Scripts\python.exe -m unittest app.tests.test_unit_normalizer app.tests.test_intent_context`

---

## 2026-05-31 - `0308334` - `fix(agent): 明确重规划意图不再重复澄清`

负责人：Agent / 后端编排 / A 同学

### 更新概览

修复用户已经明确点击或输入“重新生成路线”“只替换这个地点”后，系统仍把它当成全量重规划 / 局部重规划之间的歧义并继续追问的问题。现在模型仍负责主判定，后端只在用户原话非常明确时做校准兜底。

### 主要变更

- 强化 `MessageRouter` 的 LLM 路由提示词：
  - 明确 `full_replan` 与 `partial_replan` 的边界。
  - 要求输出 `reason` 和 `evidence`，方便 trace 解释判断依据。
  - 只有真正不确定时才输出 `candidate_planning_modes`。
- 增强 `IntentConfidenceCalibrator`：
  - 对“重新生成路线 / 重新规划 / 换一条路线”等明确全量重规划表达，清空候选意图并提升置信度。
  - 对“只替换这个地点 / 只换这个地点”等明确局部替换表达，校准为局部重规划并清空候选意图。
- Agent trace 和前端字段补充“判断理由”“依据原话”的中文展示。

### 涉及文件

- `backend/app/agent/message_router.py`
- `backend/app/agent/intent_confidence.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_message_router.py`
- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/utils/agentThinking.ts`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 明确重规划表达会直接进入对应链路，不再触发意图澄清。 | 后续新增按钮文案时，要把明确表达纳入路由 few-shot 或校准词表。 |
| B 同学：POI / 路线策略 | 明确“重新生成路线”会直接进入路线生成，减少无效等待。 | 如果用户表达模糊，仍可能先澄清再生成。 |
| C 同学：前端 / UI | trace 可展示判断理由和依据原话。 | 快捷按钮文案应尽量使用明确表达，例如“重新生成路线”“只替换这个地点”。 |

### 风险与注意事项

- 后端校准只处理非常明确的短语，不替代 LLM 主分类。
- “换个便宜点的”这类仍保留为歧义候选，因为它可能是整条路线更省钱，也可能是只换当前店。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_message_router app.tests.test_intent_confidence app.tests.test_clarification_policy`
- `npx.cmd tsc --noEmit`

---

## 2026-05-31 - `0308334` - `fix(agent): 校准意图置信度并解释来源`

负责人：Agent / 后端编排 / A 同学

### 更新概览

修复 Agent trace 中意图置信度经常显示 `0%` 的问题。现在置信度不再只依赖 LLM 自报字段；当 LLM 未返回置信度、返回多个候选规划方式、或字段存在冲突时，后端会进行可解释校准，并在 trace 中展示来源和原因。

### 主要变更

- 新增 `IntentConfidenceCalibrator`：
  - LLM 未返回 `confidence` 时，根据 query、上下文、是否引用路线等信号补合理分数。
  - 存在多个候选规划方式时自动降到低置信度区间，触发澄清。
  - 保留 `raw_confidence`，并输出 `confidence_source` 和 `confidence_reasons`。
- `MessageRouter.classify()` 统一经过校准层：
  - LLM 路由结果标记为 `LLM 返回` 或 `后端校准`。
  - 规则兜底结果标记为 `规则兜底`。
- Agent trace 增加置信度来源和说明字段，前端同步中文展示。

### 涉及文件

- `backend/app/agent/intent_confidence.py`
- `backend/app/agent/message_router.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_intent_confidence.py`
- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/utils/agentThinking.ts`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 置信度现在是后端可解释校准结果，不再默认 0。 | 后续新增意图时要补充校准规则和降分原因。 |
| B 同学：POI / 路线策略 | 低置信度会先澄清，减少误入路线生成。 | 如果没有召回路线，先看 trace 是否因为低置信度停住。 |
| C 同学：前端 / UI | trace 会多显示置信度来源和说明。 | 可以把 `confidence_reasons` 做成更友好的提示。 |

### 风险与注意事项

- 这不是机器学习校准分，而是 demo 阶段的工程可解释置信度。
- 真正线上应结合标注数据、top1/top2 分布、用户纠错行为做离线校准。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_intent_confidence app.tests.test_message_router app.tests.test_clarification_policy`
- `npx.cmd tsc --noEmit`

---

## 2026-05-31 - `0308334` - `feat(agent): 接入意图澄清策略层`

负责人：Agent / 后端编排 / A 同学

### 更新概览

根据 `docs/intent_clarification_plan.md` 落地最小可用澄清机制。系统现在会先判断用户 query 的意图类型和置信度，再决定是否继续规划；当缺少路线生成必要信息，或无法在全量重规划、局部重规划等链路之间稳定判断时，会先发起轻量追问，避免替用户做不清晰的决定。

### 主要变更

- 新增 `ClarificationPolicy`：
  - 支持必要字段缺失澄清，例如新规划缺城市。
  - 支持意图低置信度澄清，例如无法区分“整条路线更省钱”和“只换当前某个点”。
  - 非必要字段如出发点、预算、人数不阻塞路线生成。
- `MessageRoute` 新增 `candidate_planning_modes`：
  - fallback 路由能标记多种可能处理链路。
  - 例如“换个便宜点的”会标记为 `full_replan / partial_replan` 候选，交给澄清策略确认。
- `AgentOrchestrator` 接入澄清分支：
  - 需要澄清时直接返回 `need_clarification=true`。
  - 不再继续调用 LLM 解析、POI 召回或路线生成。
  - Agent trace 新增 `clarify_intent` 步骤。
- 前端 trace 文案补充澄清相关字段中文展示。

### 涉及文件

- `backend/app/agent/clarification_policy.py`
- `backend/app/agent/message_router.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_clarification_policy.py`
- `backend/app/tests/test_message_router.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `frontend/src/components/AgentTrace.tsx`
- `frontend/src/utils/agentThinking.ts`
- `frontend/src/utils/traceIcons.ts`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 意图路由后新增澄清策略层，避免低置信度时误执行。 | 后续新增意图类型时，要同步补充澄清策略和候选链路。 |
| B 同学：POI / 路线策略 | 信息不够时不会再强行进入 POI 召回和路线生成。 | 调试路线为空时先看 trace 是否停在 `clarify_intent`。 |
| C 同学：前端 / UI | 后端会返回 `need_clarification=true` 和澄清问题。 | 前端可把它当普通 assistant 消息展示，后续可做快捷选项。 |

### 风险与注意事项

- 当前澄清策略是 demo 级规则层，优先覆盖城市缺失、目标过泛、重规划歧义。
- 后续如果接更多场景，需要为不同场景补充“必问字段”和“可默认字段”。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_clarification_policy app.tests.test_message_router app.tests.test_orchestrator_intent_flow.OrchestratorIntentFlowTest.test_missing_required_city_returns_clarification_without_planning app.tests.test_orchestrator_intent_flow.OrchestratorIntentFlowTest.test_low_confidence_between_replan_modes_asks_before_parsing_or_planning`
- `npx.cmd tsc --noEmit`

---

## 2026-05-31 - `0308334` - `feat(profile): 扩展用户画像维度并接入 POI 排序`

负责人：Agent / 后端编排 / A 同学

### 更新概览

用户画像从“偏好标签 + 避开标签 + 五类权重”扩展为更贴近路线算法的结构化画像。新的画像字段会从 seed/runtime JSON 读取，并参与 POI 排序，不只是展示字段。

### 主要变更

- `UserProfile` 新增长期画像维度：
  - 行为敏感度：预算敏感、步行耐受、人群耐受、节奏紧凑度、新鲜感偏好、舒适度偏好。
  - 算法偏好：品类偏好、路线角色偏好、体验标签偏好、时段偏好、交通偏好。
  - 历史行为：喜欢 POI、不喜欢 POI、跳过品类、常见调整动作。
- `ChatRequest` 支持接收这些细画像字段，后续前端 onboarding 或真实画像系统可以逐步补充。
- `ProfileService` 现在会：
  - 从 `data/seed/user_profiles.json` 读取 `preference_profile`、`category_preferences`、`history_behavior`。
  - 从对话偏好中推导路线角色、体验标签、交通/时段偏好。
  - 用预算、步行、人群、舒适度、新鲜感等长期画像更新策略权重。
- `POIService` 召回排序新增画像维度分：
  - 品类、路线角色、体验标签、时段、交通匹配会加分。
  - 喜欢过的 POI 加分，不喜欢的 POI 和跳过品类降权。
- `docs/team_plan.md` 补充“用户画像维度”说明，方便 A/B/C 对齐字段含义。

### 涉及文件

- `backend/app/schemas/user.py`
- `backend/app/schemas/chat.py`
- `backend/app/services/profile_service.py`
- `backend/app/services/poi_service.py`
- `backend/app/tests/test_profile_request_sync.py`
- `backend/app/tests/test_poi_service.py`
- `frontend/src/api/types.ts`
- `docs/team_plan.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 画像字段更完整，长期画像和本次要求仍保持分离。 | 后续接数据库时按这些字段建表或 JSON 列即可。 |
| B 同学：POI / 路线策略 | POI 排序开始消费品类、路线角色、体验标签、时段、交通、历史行为。 | 调参时可以直接看 `user_profile` 细字段，不必只依赖文本标签。 |
| C 同学：前端 / UI | 接口返回的 `user_profile` 字段更多，类型已兼容。 | onboarding 暂时不用一次性采全，后续可逐步增加入口。 |

### 风险与注意事项

- 这仍是 demo 级画像更新，不做复杂置信度和衰减；用户明确表达长期偏好时才写 runtime JSON。
- 真实线上需要补充画像字段的来源、置信度、更新时间和删除机制。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_profile_request_sync`
- 直接调用 `app.tests.test_poi_service.test_algorithm_profile_dimensions_affect_poi_ranking`

---

## 2026-05-31 - `0308334` - `feat(profile): 接入 JSON 用户画像运行时存储`

负责人：Agent / 后端编排 / A 同学

### 更新概览

在上一版 `update_from_chat()` 画像更新入口基础上，接入 demo 阶段可用的 JSON 运行时存储。用户在对话中体现出的偏好和避开项会写入 `data/runtime/user_profiles.json`，后端重启后仍可读取。

### 主要变更

- `ProfileService` 新增 `runtime_data_path`：
  - 默认路径：`data/runtime/user_profiles.json`。
  - 读取顺序：本轮请求画像 > runtime JSON 画像 > seed 画像 > 默认画像。
- `update_from_chat()` 现在会：
  - 合并 `preferences`、`tags`、`avoid_tags`。
  - 根据本轮意图更新权重。
  - 仅在用户明确表达长期偏好时，将更新后的 `UserProfile` 写入 runtime JSON。
- 长期画像和本次行程要求已拆开：
  - onboarding 首轮画像会作为长期画像基线写入 JSON。
  - “以后 / 长期 / 一直 / 默认 / 我喜欢 / 我不喜欢 / 记住”等表达会更新长期画像。
  - “这次 / 本次 / 今天 / 当前路线 / 刚刚 / 临时”等表达只影响当前会话，不覆盖长期画像。
- `data/runtime/.gitignore` 忽略真实运行时画像文件，避免把演示用户数据误提交。

### 涉及文件

- `backend/app/services/profile_service.py`
- `backend/app/tests/test_profile_request_sync.py`
- `data/runtime/.gitignore`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 画像已从 session 级升级为 JSON 持久化。 | 后续可把 JSON 存储替换为 SQLite/数据库仓库。 |
| B 同学：POI / 路线策略 | 下一轮路线可读取用户历史偏好和避开项。 | 召回和评分侧继续使用 `user_profile.preferences/avoid_tags/preference_weights`。 |
| C 同学：前端 / UI | 不需要改接口；首轮仍传 onboarding 画像。 | 演示时可打开 `data/runtime/user_profiles.json` 查看画像变化。 |

### 风险与注意事项

- JSON 文件适合 demo，不适合高并发多用户生产环境。
- `data/runtime/user_profiles.json` 被忽略，不会随 git 提交。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_profile_request_sync`

---

## 2026-05-30 - `0308334` - `feat(agent): 区分全量重规划和局部重规划`

负责人：Agent / 后端编排 / A 同学

### 更新概览

本次把“重新规划”拆成两种处理模式：`full_replan` 表示基于新偏好重新生成候选路线，`partial_replan` 表示在原方案基础上局部替换或调整。这样“更省钱、少排队”不会误走局部替换，“换一家、不喜欢这家、下雨、堵车、排队 90 分钟”可以直接进入 B 侧的局部重规划链路。

### 主要变更

- `MessageRouter` 新增 `PlanningMode`：
  - `full_replan`：整体偏好变化，继续走 `RouteService.generate_routes()`。
  - `partial_replan`：局部点位或突发事件调整，走 `ReplanService.replan()`。
- 新增 `ReplanIntentParser`：
  - 解析“换一家 / 不喜欢这家 / 排队 90 分钟 / 下雨 / 堵车 / 关门 / 累了”等话术。
  - 输出 `event_type`、`selected_route_id`、`current_poi_id`、`event_payload`。
- `AgentOrchestrator` 新增局部重规划分支：
  - 有上一轮路线且 `planning_mode=partial_replan` 时，不再完整重新生成路线。
  - 直接构造 `ReplanRequest` 并调用 `ReplanService.replan()`。
- `docs/team_plan.md` 补充全量重规划和局部重规划边界说明。

### 涉及文件

- `backend/app/agent/message_router.py`
- `backend/app/agent/replan_intent_parser.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_message_router.py`
- `backend/app/tests/test_replan_intent_parser.py`
- `backend/app/tests/test_orchestrator_intent_flow.py`
- `docs/team_plan.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 意图层现在会输出全量/局部两种重规划模式。 | 后续新增话术时先判断改动范围，再扩展规则或 prompt。 |
| B 同学：POI / 路线策略 | 局部重规划会直接进入 `ReplanService.replan()`，全量重规划仍进入路线生成。 | `ReplanService` 需要继续增强目标 POI 定位和替换候选质量。 |
| C 同学：前端 / UI | “换一家”等按钮对应局部重规划，“更省钱/少排队”对应全量重规划。 | 后续可展示 `replan_reason`、`changed_stops`、`live_warnings`。 |

### 风险与注意事项

- 目前局部重规划事件解析以规则为主，能覆盖 Demo 常见话术；更复杂表达后续可加 LLM 兜底。
- 若当前 session 没有已生成路线，即使识别到局部重规划，也会回退到普通规划链路。

### 建议验证

- `.\.venv\Scripts\python.exe -m unittest app.tests.test_message_router app.tests.test_replan_intent_parser app.tests.test_orchestrator_intent_flow.OrchestratorIntentFlowTest.test_partial_replan_uses_replan_service_without_full_regeneration app.tests.test_intent_context app.tests.test_unit_normalizer app.tests.test_replan_service`
- `npm.cmd run build`

---

## 2026-05-30 - `ce294de` - `fix(agent): 标准化单位换算并保护局部路线编辑约束`

负责人：Agent / 后端编排 / A 同学

### 更新概览

本次修复两类同源问题：一是 LLM 结构化输出时可能把“1天”写成 `duration_hours=1`，二是点击“换一家 / 替代方案”这类局部路线操作后，LLM 可能把它当成完整新规划，误改预算、开始时间和时长。

修复策略不是只补单个 case，而是新增通用单位标准化层，并在上下文合并层保护局部路线编辑的硬约束。以后“天/半天/分钟/小时/总预算/人均预算/下午两点”等自然语言单位，会统一换算成系统标准字段。

### 主要变更

- 新增 `unit_normalizer`：
  - `一天 / 一日游 / 1天 -> duration_hours=8`。
  - `半天 / 半日游 -> duration_hours=4`。
  - `2天 -> duration_hours=16`。
  - `120分钟 -> duration_hours=2`。
  - `下午两点 / 晚上7点 -> 24 小时制 start_time`。
  - `两个人总预算400 -> budget_per_person=200`。
  - `两个人人均400 -> budget_per_person=400`。

- 强化 LLM delta prompt：
  - 明确要求所有结构化字段必须输出系统标准单位，不能直接抽取原文数字。
  - 增加 few-shot 说明，覆盖一天、总预算、人均预算等易错场景。

- 保护局部路线编辑：
  - “换一家 / 替代方案 / 等待时间短 / 排队 / 当前路线”等操作默认继承上一轮 `city`、`people_count`、`start_time`、`duration_hours`、`budget_per_person`、`scenario`。
  - 只有用户明确说“改时间、改预算、改人数、换城市”等硬约束时，才允许覆盖。
  - 避免 LLM 把“餐厅排队 90 分钟”误当作新的 2 小时餐饮规划。

- 沉淀通用修 bug 原则：
  - 新增 `docs/skills/generalized-bugfix/SKILL.md` 草案。
  - 约定以后修 bug 先抽象问题类别，再做通用修复，不能只修单个触发样例。

### 涉及文件

- `backend/app/agent/unit_normalizer.py`
- `backend/app/agent/intent_context.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/tests/test_unit_normalizer.py`
- `backend/app/tests/test_intent_context.py`
- `docs/skills/generalized-bugfix/SKILL.md`
- `docs/version_log.md`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 多轮状态变更现在有通用单位标准化兜底，局部路线编辑不会轻易改写硬约束。 | 后续新增结构化字段时，要同步声明标准单位，并补充 normalizer / 测试。 |
| B 同学：POI / 路线策略 | 收到的 `duration_hours`、`budget_per_person` 更稳定，避免因为 Agent 误把“一天”当 1 小时导致路线只剩一个点。 | 如果发现路线过短，先看 Agent trace 里的 `duration_hours` 和 `apply_query_delta` 是否符合预期。 |
| C 同学：前端 / UI | 点击“换一家 / 少排队”等局部操作后，后端会默认保留原路线框架。 | 后续最好把 ActionBar 操作从纯自然语言升级为结构化 action，进一步减少 LLM 误解。 |

### 风险与注意事项

- 当前 `unit_normalizer` 覆盖了时间、人数、预算三类核心单位；距离、排队上限等字段未来如果进入正式 schema，需要继续扩展。
- “排队 90 分钟”现在不会再改行程时长，但如果未来需要表达 `max_queue_minutes`，应新增专门字段，而不是复用 `duration_hours`。
- `docs/skills/generalized-bugfix` 目前是项目内 skill 草案，还没有安装到全局 Codex skills 目录。

### 建议验证

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest app.tests.test_unit_normalizer app.tests.test_intent_context app.tests.test_query_delta app.tests.test_intent_enhancer
```

```bash
cd backend
$env:PYTHONPYCACHEPREFIX='D:\Document\New project\.pytest_cache\pycache_check'
.\.venv\Scripts\python.exe -m compileall app
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

## 2026-06-02 - `uncommitted` - `feat(route): add high-fidelity mock data, mock map, and predictive routes`

负责人：POI 数据 / 路线策略 / Mock 地图 / 预制路线 / B 同学

### 更新概览

本次更新围绕 B 侧 Demo 稳定性做了一轮集中增强：重新生成北京、上海两城 POI mock 数据，补齐更可信的 mock 地图路线能力，并新增 mock 天气 + 用户画像的预制路线服务。目标是让路线规划、局部修改和前端预推荐都能在没有真实高德 key、没有真实天气接口的情况下稳定工作，同时返回接近真实地图服务的交通方式、耗时、距离、polyline 和分段说明。

同时新增 `docs/route_strategy_logic.md`，系统整理当前路线策略的召回、排序、评分、普通规划、局部修改和预制路线逻辑，方便 A/B/C 同学对齐。

### 主要变更

- 重新生成 POI mock 数据：
  - `data/seed/pois.json` 调整为只覆盖上海和北京。
  - 每城 420 个 POI，共 840 个 POI。
  - 每城类目数量为：餐厅 70、咖啡 60、市集/小吃 40、购物 40、地标 40、博物馆 35、美术馆 35、公园 35、夜景 35、剧场 30。
  - 文件顶部新增简洁 `mock_poi_intro`，说明城市、类目和数量。
  - POI 字段继续覆盖路线策略需要的价格、排队、营业时间、适合时段、室内、雨天、夜间、步行强度、交通建议、路线角色和体验标签。

- 增强 POI 召回：
  - `POIService.search()` 保持城市过滤、偏好匹配、避开标签、预算过滤和低风险兜底。
  - 增加召回结果类目多样性处理，避免前几十个候选被餐厅或咖啡单一类目占满。
  - 城市无数据时仍保留 fallback 机制，但当前主数据只保证北京、上海。

- 新增高仿真 mock 地图：
  - 新增 `data/seed/mock_map.json`，覆盖北京、上海的 mock 地铁线、公交线、站点、交通参数和高峰时段。
  - 新增 `MockRouteMapService`，统一返回 `RouteLeg`。
  - 支持 `walk / metro / bus / taxi`。
  - 默认 `MAP_ROUTE_PROVIDER=mock`，不配置高德 key 时也能返回稳定路线字段。
  - 高德 API 仍保留，可通过配置切换。
  - mock 地图会返回：
    - `transport_mode_from_previous`
    - `travel_minutes_from_previous`
    - `distance_km_from_previous`
    - `polyline_from_previous`
    - `route_leg_source_from_previous = "mock_map"`
    - `route_steps_from_previous`
  - 地铁优先匹配起终点附近站点，支持同线直达和简单一次换乘；公交用于补充短中距离；无法可靠匹配时回退打车或步行。
  - 距离和耗时不再是纯直线估算，会按交通方式加入绕路系数、等待时间、进出站时间和高峰倍率。

- 新增 mock 天气数据：
  - 新增 `data/seed/mock_weather.json`。
  - 覆盖上海、北京。
  - 每城包含 `sunny`、`rainy`、`hot`、`cloudy`、`night` 五类场景。
  - 字段包含 `condition`、`temperature_c`、`rain_probability`、`wind_level`、`comfort_level`、`suggested_preferences`。
  - 天气偏好转换规则：
    - 雨天、大风：`室内`、`雨天`、`少走路`。
    - 高温：`室内`、`少走路`、`咖啡`。
    - 晴天、阴天且舒适：`citywalk`、`拍照`、`自然风景`。
    - 夜间：`晚上`、`夜景`。

- 新增预制路线服务：
  - 新增 `PredictiveRouteService` 和 `PredictiveRouteRequest`。
  - 输入支持 `user_id`、`city`、`weather_scenario`、`start_time`、`duration_hours`、`start_lat/start_lng`、可选 `user_profile`。
  - 输出继续复用 `RoutePlanResponse`，不改前端路线结构。
  - 默认预制时长为 5 小时，更容易生成 3-4 个 POI 的半日路线。
  - 预制路线强制每条最多 4 个 POI；短时长、雨天、少走路、亲子、老人友好时倾向最多 3 个。
  - 有画像用户固定生成两个画像目标 + `balanced`。
  - 新用户不使用默认 fallback 画像，从全部 objective 候选里按评分和差异选择 3 条。
  - 三条路线会做差异过滤：objective 不重复、POI 组合不完全相同、默认 POI 重合率不超过 50%，不足时放宽到 70%。

- 扩展路线生成入口：
  - `RouteService.generate_routes()` 继续服务普通规划。
  - 新增 `RouteService.generate_routes_for_objectives()`，允许预制路线指定 objectives、限制 `max_stops`，并为同一 objective 生成多条候选。
  - 普通聊天路线规划不受预制路线 POI 数限制影响。

- 补充路线策略文档：
  - 新增 `docs/route_strategy_logic.md`。
  - 覆盖普通规划、局部修改、预制路线三条链路。
  - 详细说明 POI 召回、初排、objective 选择、候选生成、结构约束、交通路段、五维评分、硬惩罚、差异过滤和调试建议。

### 目前的变动逻辑

普通规划当前逻辑：

```text
用户消息
-> Orchestrator 解析 Intent、读取 UserProfile
-> StrategyService 推断策略标签
-> ProfileService 生成策略权重
-> POIService 从北京/上海 mock POI 中召回并初排
-> RouteService 选择 2 个偏好 objective + balanced
-> 每个 objective 生成多条候选，补 mock_map 交通字段
-> ScoringService 做五维评分和硬惩罚
-> 每个 objective 返回 best 路线
```

局部修改当前逻辑：

```text
current_routes + selected_route_id + event_type/event_payload
-> ReplanService 只检查未完成的 future stops
-> 根据 replace/avoid/queue/weather/tired/traffic 判断是否替换
-> 优先从本地 POI 找同城市、同角色、同类目替代点
-> 重建后续 stop 的时间、交通、距离和评分
-> 返回 changed_stops / live_warnings / replan_reason
```

预制路线当前逻辑：

```text
user_id + city + mock weather + 可选 profile
-> PredictiveRouteService 读取 mock_weather
-> 天气转偏好，画像转 objective
-> POIService 召回 48 个候选
-> RouteService.generate_routes_for_objectives(max_stops<=4, routes_per_objective=3)
-> 按 objective 和 POI 重合率做差异过滤
-> 返回最多 3 条 RoutePlanResponse.routes
```

有画像用户：

```text
[profile_objective_1, profile_objective_2, "balanced"]
```

新用户：

```text
从全部 objective 候选中按 route.score 和差异度选 3 条，不强制包含 balanced
```

mock 地图当前逻辑：

```text
RouteService 请求 AmapService.route_leg()
-> 默认 provider=mock
-> MockRouteMapService 根据起终点匹配城市、线路和交通方式
-> metro/bus 可返回线路名、站名、站数、耗时、距离、polyline、steps
-> 匹配失败稳定 fallback 到 taxi 或 walk
```

### 涉及文件

- `.env.example`
- `data/seed/pois.json`
- `data/seed/mock_map.json`
- `data/seed/mock_weather.json`
- `backend/app/config.py`
- `backend/app/schemas/route.py`
- `backend/app/services/amap_service.py`
- `backend/app/services/mock_route_map_service.py`
- `backend/app/services/poi_service.py`
- `backend/app/services/profile_service.py`
- `backend/app/services/route_service.py`
- `backend/app/services/predictive_route_service.py`
- `backend/app/tests/test_amap_service.py`
- `backend/app/tests/test_poi_service.py`
- `backend/app/tests/test_route_plan.py`
- `backend/app/tests/test_predictive_route_service.py`
- `docs/api_contract.md`
- `docs/route_strategy_logic.md`
- `frontend/src/api/types.ts`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| A 同学：Agent / 后端 | 默认不配置高德 key 也能拿到稳定 mock_map 路段；后续可把 `PredictiveRouteService` 包成页面初始化或聊天前置推荐接口。 | 新用户预制路线不要调用 `ProfileService` 默认画像；需要传真实 `user_id/city/weather_scenario/start_lat/start_lng`。 |
| B 同学：POI / 路线策略 | POI 召回、mock 地图、mock 天气和预制路线形成完整闭环；路线策略文档已补齐。 | 当前只保证北京、上海数据质量；扩城市时需要同步 POI、mock_map、mock_weather。 |
| C 同学：前端 / UI | `RouteStop` 新增 `route_steps_from_previous`，路线卡片可展示地铁/公交/打车/步行步骤；预制路线响应复用现有 Route 结构。 | 前端类型已补字段；如接预制路线，只需要展示 `RoutePlanResponse.routes`，无需新增路线结构。 |

### 风险与注意事项

- mock 地图追求功能一致和体验可信，不代表真实导航精度。
- 地铁/公交线路参考真实城市结构，但站点、距离、耗时是简化近似。
- 预制路线当前是服务能力，尚未新增正式 API。
- 新用户预制路线不使用默认 fallback 画像，这是和普通聊天规划不同的逻辑。
- 目前 POI 主数据只覆盖北京、上海；其他城市会走 fallback，不适合当前 Demo 主场景。
- `route_steps_from_previous` 是给前端展示的分段说明，评分仍主要使用稳定数值字段：交通方式、耗时、距离。

### 验证结果

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest app/tests/test_predictive_route_service.py -q
# 7 passed
```

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest app/tests -q
# 115 passed
```

---

## 2026-06-04：标签体系按 Mock POI 字段重构

### 本次更新

- 后端新增统一标签分类层，把旧 `preferences` 拆成三类：
  - `interest_tags`：兴趣体验，例如美食、咖啡、拍照、citywalk、艺术展、自然风景、本地感、夜景、亲子、室内、安静。
  - `optimization_goals`：优化目标，例如少排队、省钱、少走路、高性价比、轻松、时间紧。
  - `avoid_tags`：避雷项，例如人流密集、排队久、太贵、需要预约、商业街、拍照打卡、步行多、辣。
- 保留旧 `preferences` 作为兼容入口：
  - 前端继续传 `preferences=["拍照","更省钱"]` 时，后端会拆成 `interest_tags=["拍照"]`、`optimization_goals=["省钱"]`。
  - 后端主逻辑逐步改用新字段，旧字段只做兼容和兜底。
- 预算、排队、步行不再主要依赖文本标签：
  - “人均 100 以内”只改 `budget_per_person=100`。
  - “更省钱/便宜点”进入 `optimization_goals=["省钱"]`。
  - “少排队/少走路”进入优化目标，参与评分权重和排序。
- 修复中文否定窗口：
  - “不想拍照”进入 `avoid_tags=["拍照打卡"]`。
  - “不要太累，安静一点”不会误删“安静”。
- Agent 思考过程和前端类型补充新字段中文展示。

### 涉及文件

- `backend/app/agent/tag_taxonomy.py`
- `backend/app/agent/intent_enhancer.py`
- `backend/app/agent/intent_context.py`
- `backend/app/agent/orchestrator.py`
- `backend/app/schemas/intent.py`
- `backend/app/schemas/user.py`
- `backend/app/schemas/chat.py`
- `backend/app/services/profile_service.py`
- `backend/app/services/poi_service.py`
- `backend/app/services/strategy_service.py`
- `backend/app/services/route_service.py`
- `backend/app/services/scoring_service.py`
- `backend/app/services/predictive_route_service.py`
- `backend/app/services/replan_service.py`
- `frontend/src/api/types.ts`
- `frontend/src/components/AgentTrace.tsx`

### 协作影响

| 角色 | 影响 | 需要关注 |
| --- | --- | --- |
| 星爻：后端 / Agent | 意图、画像、POI 召回和路线评分开始使用标签分层，避免“少排队/更省钱”被当作兴趣召回词。 | 后续新增标签时先补 `tag_taxonomy.py` 和 Mock POI 支撑字段，不要继续往 `preferences` 里堆。 |
| B 同学：POI / 路线策略 | POI 召回主要看兴趣标签，优化目标主要影响排序和权重。 | 预算优先看 `avg_price/budget_friendly`，排队看 `queue_minutes/risk_flags`，步行看 `walking_intensity`。 |
| 前端 / 交互 | 可继续传旧 `preferences`，也可以逐步展示 `interest_tags/optimization_goals/avoid_tags`。 | Agent 思考过程新增“兴趣”“优化目标”字段，展示时优先读新字段。 |

### 验证结果

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest app.tests.test_tag_taxonomy app.tests.test_intent_enhancer app.tests.test_profile_request_sync
# 22 passed
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest app.tests.test_intent_context app.tests.test_query_delta app.tests.test_tag_taxonomy app.tests.test_intent_enhancer app.tests.test_profile_request_sync
# 33 passed
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest app.tests.test_orchestrator_intent_flow
# 22 passed
```

```powershell
cd backend
# 手动执行 test_poi_service 和 test_route_plan 中的关键函数式用例
# POI 召回、少排队、省钱、少走路、餐饮、拍照、室内、多城市路线关键用例通过
```

```powershell
cd frontend
npx.cmd tsc --noEmit
# passed
```
