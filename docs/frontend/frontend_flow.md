# 前端完整功能链路

> 基于 React + TypeScript + Vite，当前 `USE_MOCK = true`（后端未接入）

---

## 整体架构

```
App.tsx
├── loadProfile()：检查 localStorage
│   ├─ 有画像 → PlannerPage
│   └─ 无画像 → OnboardingPage → 完成后进入 PlannerPage
```

---

## 一、Onboarding 流程（首次进入 / 重置画像）

**文件**：`pages/OnboardingPage.tsx`、`hooks/useOnboarding.ts`

### 三步引导

| 步骤 | 内容 | 进入下一步条件 |
|------|------|--------------|
| Step 1 | 选出行场景（多选：朋友 citywalk / 家庭出行 / 独自探索 / 约会 / 美食打卡 / 文化艺术 6 种） | 至少选 1 个 |
| Step 2 | 偏好标签（9 种"我喜欢"）+ 避开标签（5 种） | 偏好至少选 1 个 |
| Step 3 | 预算档位（省钱/舒适/享受）+ 城市（9 个）+ 昵称（可选） | 无强制 |

### 完成逻辑

```
handleFinish()
  → saveProfile(partial)
    → 生成 user_id（时间戳）
    → buildWeights(preferences, budget_level)  // 动态计算 preference_weights
    → localStorage.setItem("tos_onboarding_profile", ...)
  → onDone(profile) → App.tsx 切换至 PlannerPage
```

### preference_weights 计算规则

| 偏好 / 预算 | 效果 |
|------------|------|
| 偏好含"少排队" | `queue` 权重 +0.1 |
| `budget_level = "low"` | `budget` 权重 +0.1 |
| 基准 | quality 0.3 / queue 0.25 / distance 0.2 / budget 0.15 / preference 0.1 |

---

## 二、PlannerPage 主界面

**文件**：`pages/PlannerPage.tsx`

### 布局结构

```
┌──────────────────────────────┐
│  Topbar（固定顶部）            │
│  标题 + UserProfileBadge      │
├──────────────────────────────┤
│  主内容区（可滚动）             │
│  ├─ 快捷 Chips（无消息时显示）  │
│  ├─ ChatPanel（消息气泡列表）   │
│  ├─ AgentTrace（AI 推理步骤）  │
│  ├─ RouteCompare（路线卡片组） │
│  ├─ ReplanPanel（突发事件面板）│
│  └─ FeedbackPanel（行程评分） │
├──────────────────────────────┤
│  底部输入栏（固定）             │
└──────────────────────────────┘
```

### 快捷 Chips

根据用户画像动态生成（最多 4 个），点击后自动填入输入框：

- 始终包含：`${city} 半天 citywalk，2人`
- 偏好含"少排队" → 少排队路线，避开人流
- 偏好含"吃好" → `${city}今天吃什么`
- 偏好含"亲子友好" → 带小孩，亲子友好路线
- 预算 low → 预算100以内，高性价比
- 偏好含"网红打卡" → 网红打卡路线推荐

### 首次进入欢迎语

```
useEffect (welcomeSentRef 防重)
  → inject("assistant", `你好 ${nickname}！我已了解你的偏好…`)
  // 本地注入，不走网络请求
```

---

## 三、对话 & 路线规划核心链路

**文件**：`hooks/useChat.ts`、`api/chatApi.ts`、`api/client.ts`

```
用户输入 / 快捷Chip点击
  → handleSubmit()
    → useChat.send(msg)
      → setMessages（追加用户气泡）
      → sendChatMessage(msg, profile)
          ├─ USE_MOCK=true：
          │   delay(1200ms) → buildMockResponse(msg)
          │   ├─ 含路线关键词 → 返回 3 条路线 + 6 步 agent_trace
          │   └─ 普通消息   → 返回引导语
          └─ USE_MOCK=false：
              POST /api/chat（VITE_API_BASE_URL，默认 localhost:8000）
              Body: { session_id, user_id, message, city, scenarios,
                      preferences, avoid_tags, budget_level, preference_weights }
      ← ChatResponse
      → setResponse（更新路线/trace）
      → setMessages（追加 AI 气泡）
```

### ChatResponse 数据结构

```typescript
{
  session_id: string
  message: string                    // AI 文字回复
  need_clarification: boolean        // 是否需要追问
  clarifying_question?: string       // 追问内容
  user_profile?: UserProfile         // 后端返回的画像（可覆盖本地显示）
  routes: Route[]                    // 路线数组（最多 3 条）
  agent_trace: AgentTraceStep[]      // AI 推理步骤
}
```

### Route 数据结构

```typescript
{
  route_id, title, objective, summary
  total_duration_minutes, total_cost_per_person, total_queue_minutes
  score: number                      // 综合评分
  score_breakdown: {                 // 5 维度分项（0-1）
    quality, queue, budget, distance, preference
  }
  stops: RouteStop[]                 // 行程站点
  reasons: string[]                  // 推荐原因标签
  replan_reason?: string             // 重规划时的说明
}
```

---

## 四、路线展示链路

**文件**：`components/RouteCompare.tsx`、`RouteCard.tsx`、`RouteTimeline.tsx`、`ScoreBreakdown.tsx`、`ActionBar.tsx`

```
RouteCompare（横向 swiper，底部 dot 指示器）
└── RouteCard（每条路线）
    ├─ 重规划提示（replan_reason，有则显示）
    ├─ 标题 + 综合评分气泡
    ├─ 核心指标（时长 / 人均费用 / 排队时间）
    ├─ ScoreBreakdown（5 维度进度条：品质/排队少/预算/距离/偏好）
    ├─ RouteTimeline（时间线列表）
    │   └─ 每个 Stop：开始时间 / 名称 / 分类标签 / 费用 / 排队时间 / 标签
    ├─ 推荐原因标签组
    └─ ActionBar（快捷操作）
```

### ActionBar 操作 → 触发重新规划

| 按钮 | 发送文本模板 |
|------|------------|
| 换一家 | 帮我替换路线 `{routeId}` 中的一个地点 |
| 更省钱 | 对路线 `{routeId}` 重新规划，降低人均消费 |
| 少排队 | 对路线 `{routeId}` 重新规划，避开需要排队的地点 |
| 亲子友好 | 对路线 `{routeId}` 加入亲子友好筛选条件 |

> 操作经 `PlannerPage.handleAction()` → `useChat.send()` → 走普通对话链路

---

## 五、突发事件重规划链路

**文件**：`components/ReplanPanel.tsx`

```
ReplanPanel（悬浮 FAB 按钮，仅有路线时可点击）
  → 点击 → 手机端：底部抽屉 / 桌面端：内联按钮组
    → 选择事件
        ├─ 🍽️ 餐厅排队 90 分钟 (queue90)
        ├─ 🚗 交通堵车了    (traffic)
        └─ 😴 我们有点累了  (tired)
    → handleReplan(eventKey)
      → buildReplanMessage(key, currentRouteId)
        // 拼接自然语言，携带当前路线 ID
      → useChat.send(文本)
      → 走普通对话链路 → 返回新路线（含 replan_reason）
```

---

## 六、反馈 & 画像自动更新链路

**文件**：`components/FeedbackPanel.tsx`、`hooks/useOnboarding.ts`

```
FeedbackPanel（有路线时在页面底部显示）
  → 5 个维度星级评分（1-5 星）
      ├─ 📍 路线合理性
      ├─ 🍽️ 餐厅满意度
      ├─ ⏱️ 时间安排
      ├─ 💰 预算控制
      └─ 🤖 AI 准确度
  → 提交
    → deriveWeightPatch(scores)
        ├─ 预算分 < 3 → budget 权重提升至 0.3
        ├─ 时间分 < 3 → queue 权重提升至 0.35
        └─ 路线 & 餐厅分 ≥ 4 → quality 权重提升至 0.35
    → updateProfile(weightPatch) → 写回 localStorage
    → onProfileUpdated(updated) → 更新 PlannerPage.localProfile
    → 显示"偏好档案已更新"感谢语
```

---

## 七、用户画像管理

**文件**：`components/UserProfileBadge.tsx`

```
UserProfileBadge（顶部右侧）
  ├─ 桌面：行内展示当前偏好标签（前 3 个）
  └─ 手机：点击图标 → 底部抽屉
       ├─ 显示昵称
       ├─ ✅ 喜欢标签列表
       ├─ 🚫 避开标签列表
       └─ "重新填写偏好"按钮
            → clearProfile()（清除 localStorage）
            → App.onResetProfile()
            → useChat.reset()（清空消息历史）
            → 返回 OnboardingPage
```

---

## 八、追问（Clarification）链路

**文件**：`components/ChatPanel.tsx`

```
后端返回 need_clarification = true 时
  → ChatPanel 在消息列表末尾渲染追问卡片
    ├─ 显示 clarifying_question 文字
    └─ 快捷回答 Chips（按问题关键词自动匹配）
        ├─ 含"几个人/人数" → ["1人","2人","3人","4人以上"]
        ├─ 含"预算/多少钱" → ["100以内","100~200","200~400","400以上"]
        ├─ 含"时间/几点"  → ["上午","下午","晚上","全天"]
        └─ 默认           → ["1人","2人","3人及以上","不确定"]
  → 用户点击 Chip / 手动输入
    → onClarify(answer) → useChat.send(answer) → 走普通对话链路
```

---

## 九、Mock 开关 & 接入真实后端

**文件**：`api/chatApi.ts`

| 配置项 | 说明 |
|--------|------|
| `USE_MOCK = true` | 本地 Mock，含 1.2s 模拟延迟，**当前状态** |
| `USE_MOCK = false` | 接入真实后端 |
| `VITE_API_BASE_URL` | 环境变量，默认 `http://localhost:8000` |

Mock 判断逻辑：消息含 `/路线|citywalk|吃|玩|去|逛|今晚|上海|北京|周末|半天|一天/` → 返回完整路线数据，否则返回引导语。

---

## 十、文件结构速查

```
frontend/src/
├── App.tsx                    # 根组件，控制 Onboarding / Planner 路由
├── main.tsx                   # 应用入口
├── api/
│   ├── chatApi.ts             # sendChatMessage，Mock 开关在此
│   ├── client.ts              # postJson 封装，读取 VITE_API_BASE_URL
│   └── types.ts               # ChatResponse / Route / RouteStop 等类型定义
├── hooks/
│   ├── useChat.ts             # 消息状态管理（send / inject / reset）
│   ├── useOnboarding.ts       # 画像读写（loadProfile / saveProfile / updateProfile）
│   ├── useRoutes.ts           # 路线 hook（当前为 passthrough）
│   └── useDemoEvents.ts       # 演示事件 hook（当前为空实现）
├── pages/
│   ├── OnboardingPage.tsx     # 3 步引导页
│   └── PlannerPage.tsx        # 主规划页，组合所有组件
├── components/
│   ├── ChatPanel.tsx          # 消息气泡列表 + 追问卡片
│   ├── AgentTrace.tsx         # AI 推理步骤折叠面板
│   ├── RouteCompare.tsx       # 路线横向 swiper 容器
│   ├── RouteCard.tsx          # 单条路线卡片
│   ├── RouteTimeline.tsx      # 行程时间线
│   ├── ScoreBreakdown.tsx     # 5 维度评分进度条
│   ├── ActionBar.tsx          # 路线操作按钮组
│   ├── ReplanPanel.tsx        # 突发事件重规划面板
│   ├── FeedbackPanel.tsx      # 行程评分反馈
│   └── UserProfileBadge.tsx   # 用户画像展示 & 重置
└── utils/
    ├── categoryLabels.ts      # POI 分类中文标签
    ├── formatTime.ts          # 时间格式化
    ├── routeDisplay.ts        # 路线展示工具
    └── traceIcons.ts          # Agent 步骤图标映射
```
