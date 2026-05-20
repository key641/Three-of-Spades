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
