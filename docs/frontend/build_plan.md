# 前端 React 实现计划

> 基于 React 19 + TypeScript + Vite，手机优先，分三阶段完成
> 参考设计方案：`docs/frontend/design.md`

---

## 一、现有骨架状态（起点）

项目已有完整的工程骨架，**不需要从零搭建**，在此基础上迭代改造：

| 已有 | 状态 |
|------|------|
| React 19 + TypeScript + Vite 工程 | ✅ 可用 |
| `frontend/src/api/types.ts` 类型定义 | ✅ 已对齐后端字段 |
| `frontend/src/api/chatApi.ts` 请求封装 | ✅ 可用 |
| `frontend/src/hooks/useChat.ts` 状态管理 | ✅ 可用 |
| 所有组件文件（骨架版） | ⚠️ 需要改造 |
| `globals.css` | ⚠️ 需要补充手机样式 |
| 手机端响应式 | ❌ 不完整 |
| 气泡对话流 | ❌ 待实现 |
| 路线卡片 swipe 切换 | ❌ 待实现 |

---

## 二、依赖包规划

### 需要新增的依赖

```bash
# 无需安装额外 UI 库，用现有 lucide-react 图标 + 原生 CSS 实现

# 可选：如果需要更丝滑的 swipe，可以加这个轻量库（< 5KB gzip）
npm install swiper
```

### 当前依赖（无需变更）

```
react@^19       ✅
react-dom@^19   ✅
lucide-react    ✅  图标库，已安装
vite + tsc      ✅  构建工具
```

**原则：不引入重型 UI 组件库（如 Ant Design / MUI），手机端优先用 CSS + 原生组件，保持包体积小。**

---

## 三、实现步骤（分三阶段）

---

### 阶段一：基础样式 & CSS 系统（优先级 P0，预估 1～2 小时）

**目标：** 建立颜色变量、字体规范、手机端基础布局，让所有现有骨架组件在手机上能正常显示。

#### Step 1.1 — 重写 `globals.css`，建立 CSS 变量系统

改造文件：`frontend/src/styles/globals.css`

主要改动：

```css
/* 1. 在 :root 中定义 CSS 变量 */
:root {
  --color-primary: #FF6600;      /* 美团橙 */
  --color-primary-bg: #FFF3EB;
  --color-ai-bg: #EEF6F3;        /* AI 消息背景 */
  --color-success: #12B76A;
  --color-warning: #F79009;
  --color-error: #B42318;
  --color-bg: #F6F7F9;
  --color-card: #FFFFFF;
  --color-border: #E0E4EA;
  --color-text: #20242a;
  --color-muted: #66707c;

  --font-title: 20px;
  --font-heading: 16px;
  --font-body: 14px;
  --font-small: 12px;

  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
}

/* 2. 禁止 iOS 字体自动缩放 */
html {
  -webkit-text-size-adjust: 100%;
  touch-action: manipulation;
}

/* 3. 手机端 app-shell 布局 */
/* mobile: 固定顶栏 + 滚动内容区 + 固定底部输入栏 */
```

#### Step 1.2 — 更新 `PlannerPage.tsx` 整体布局结构

改造文件：`frontend/src/pages/PlannerPage.tsx`

手机端结构：
```
<div class="app-shell">
  <header class="topbar">...</header>          ← position: fixed, top: 0
  <main class="scroll-area">                   ← padding-top: 56px, padding-bottom: 80px
    <ChatPanel />
    <AgentTrace />
    <RouteCompare />
    <ReplanPanel />
    <FeedbackPanel />
  </main>
  <footer class="input-bar">                   ← position: fixed, bottom: 0
    <!-- 输入框移到这里 -->
  </footer>
</div>
```

**验收标准：** `npm run dev` 启动，手机浏览器打开页面不错位，顶栏和底部输入栏固定，内容区可滚动。

---

### 阶段二：核心功能组件改造（优先级 P0/P1，预估 4～6 小时）

按优先级顺序逐一改造，每完成一个组件就在手机上验证一次。

---

#### Step 2.1 — `ChatPanel.tsx` → 气泡对话流 + 底部输入条

改造文件：`frontend/src/components/ChatPanel.tsx`

**数据变化：**

当前 `useChat` 只保存最后一条 response，需要在 ChatPanel 内部维护消息历史：

```typescript
// ChatPanel 内部新增状态
const [messages, setMessages] = useState<ChatMessage[]>([]);

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}
```

**UI 结构：**

```tsx
// 消息列表区（在 scroll-area 内）
<div className="message-list">
  {messages.map(msg => (
    <div className={`bubble bubble-${msg.role}`}>
      {msg.content}
    </div>
  ))}
  {loading && <div className="bubble bubble-assistant typing-dots">...</div>}
</div>

// 快捷 Chips（在消息列表下方，只在没有路线时显示）
<div className="chips">
  <button onClick={() => setInput('上海半天 citywalk 2人')}>
    上海半天 citywalk 2人
  </button>
  ...
</div>

// 底部输入条（fixed，移到 PlannerPage 的 footer 里）
<div className="input-bar">
  <textarea ... />
  <button className="send-btn" type="submit">
    <Send size={20} />
  </button>
</div>
```

**CSS 关键样式：**

```css
.bubble { border-radius: 16px; padding: 10px 14px; max-width: 80%; }
.bubble-user { background: var(--color-primary); color: #fff; align-self: flex-end; }
.bubble-assistant { background: var(--color-ai-bg); align-self: flex-start; }
.typing-dots::after { content: '●●●'; animation: blink 1s infinite; }

.input-bar {
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 8px 16px env(safe-area-inset-bottom);
  background: #fff; border-top: 1px solid var(--color-border);
  display: flex; gap: 8px; align-items: flex-end;
}

.send-btn {
  background: var(--color-primary); color: #fff;
  border: none; border-radius: 50%;
  width: 44px; height: 44px; min-height: 44px;
}
```

**验收标准：** 输入消息发送后，出现用户气泡和 AI 回复气泡，loading 时有打字动效。

---

#### Step 2.2 — `AgentTrace.tsx` → 折叠面板 + 状态图标

改造文件：`frontend/src/components/AgentTrace.tsx`

**新增状态：**
```typescript
const [expanded, setExpanded] = useState(false);
```

**UI 结构：**

```tsx
<div className="trace-panel">
  {/* 折叠按钮（手机默认折叠，桌面默认展开） */}
  <button className="trace-toggle" onClick={() => setExpanded(!expanded)}>
    {loading
      ? <><Loader size={14} spin /> Agent 处理中...</>
      : <><CheckCircle size={14} /> 已完成 {steps.length} 步  {expanded ? '▲' : '▼'}</>
    }
  </button>

  {expanded && (
    <div className="trace-list">
      {steps.map((step, i) => (
        <div className="trace-item" style={{ animationDelay: `${i * 80}ms` }}>
          <span className="trace-icon">{STEP_ICONS[step.step] ?? '⚙️'}</span>
          <span className="trace-label">{step.label}</span>
          <span className={`trace-status status-${step.status}`}>{step.status}</span>
        </div>
      ))}
    </div>
  )}
</div>
```

**步骤图标映射（单独的 constants 文件）：**

```typescript
// frontend/src/utils/traceIcons.ts
export const STEP_ICONS: Record<string, string> = {
  parse_intent:           '🧠',
  get_user_profile:       '👤',
  build_strategy_weights: '⚖️',
  search_pois:            '📍',
  generate_routes:        '🗺️',
  summarize_routes:       '✍️',
  direct_llm_chat:        '💬',
};
```

**CSS 关键样式：**

```css
.trace-item { animation: fadeInUp 0.3s ease both; }
.status-done     { color: var(--color-success); }
.status-fallback { color: var(--color-warning); }
.status-error    { color: var(--color-error); }

/* 桌面端默认展开 */
@media (min-width: 1024px) {
  .trace-list { display: block !important; }
}
```

**验收标准：** 手机上默认折叠，点击展开，步骤逐个淡入；桌面上常驻展开。

---

#### Step 2.3 — `RouteCompare.tsx` + `RouteCard.tsx` → 手机 swipe 卡片

这是改动最大的部分，分两步：

**Step 2.3a — `RouteCompare.tsx`：实现横向 swipe 容器**

```tsx
// 使用 CSS scroll-snap 实现 swipe，无需额外依赖
<section className="route-section">
  <h2>规划方案 ({routes.length} 条)</h2>

  {/* 手机：横向滑动 */}
  <div className="route-swiper">
    {routes.map(route => (
      <div className="route-slide" key={route.route_id}>
        <RouteCard route={route} />
      </div>
    ))}
  </div>

  {/* 小圆点指示器 */}
  <div className="swiper-dots">
    {routes.map((_, i) => (
      <span key={i} className={`dot ${i === activeIndex ? 'active' : ''}`} />
    ))}
  </div>
</section>
```

```css
/* 手机端：横向 scroll-snap */
@media (max-width: 767px) {
  .route-swiper {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;        /* 隐藏滚动条 */
    gap: 12px;
    padding: 0 16px 12px;
  }
  .route-slide {
    scroll-snap-align: start;
    flex: 0 0 calc(100% - 32px);  /* 每张卡占满屏宽 */
  }
}

/* 桌面：三列并排 */
@media (min-width: 1024px) {
  .route-swiper { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
  .swiper-dots  { display: none; }
}
```

**Step 2.3b — `RouteCard.tsx`：完善卡片内容展示**

```tsx
<article className="route-card">
  {/* 头部：标题 + 评分 */}
  <div className="route-card-header">
    <div>
      <h3>{route.title}</h3>
      <p className="muted">{route.summary}</p>
    </div>
    <div className="score">{route.score.toFixed(1)}</div>
  </div>

  {/* 核心指标 */}
  <div className="metrics">
    <span><Clock size={14} />{route.total_duration_minutes} 分钟</span>
    <span><Coins size={14} />人均 ¥{route.total_cost_per_person}</span>
    <span><Timer size={14} />排队 {route.total_queue_minutes} 分钟</span>
  </div>

  {/* 评分维度进度条 */}
  <ScoreBreakdown breakdown={route.score_breakdown} />

  {/* 行程时间线 */}
  <RouteTimeline stops={route.stops} />

  {/* 推荐原因标签 */}
  <div className="reason-list">
    {route.reasons.map(r => <span key={r} className="tag">{r}</span>)}
  </div>

  {/* 重规划说明（有时才显示） */}
  {route.replan_reason && (
    <div className="replan-notice">⚠️ {route.replan_reason}</div>
  )}

  {/* 操作按钮 */}
  <ActionBar routeId={route.route_id} />
</article>
```

**新增子组件 `ScoreBreakdown.tsx`：**

```tsx
// frontend/src/components/ScoreBreakdown.tsx
const LABELS = { quality: '品质', queue: '排队少', budget: '预算', distance: '距离', preference: '偏好匹配' };

export function ScoreBreakdown({ breakdown }: { breakdown: RouteScoreBreakdown }) {
  return (
    <div className="score-breakdown">
      {Object.entries(LABELS).map(([key, label]) => (
        <div className="score-row" key={key}>
          <span className="score-label">{label}</span>
          <div className="score-bar-bg">
            <div className="score-bar-fill"
              style={{ width: `${(breakdown[key as keyof RouteScoreBreakdown] / 10) * 100}%` }} />
          </div>
          <span className="score-val">{breakdown[key as keyof RouteScoreBreakdown]}</span>
        </div>
      ))}
    </div>
  );
}
```

**验收标准：** 手机上路线卡片可以左右滑动，每张卡占满屏宽，评分维度进度条可见；桌面上三列并排显示。

---

#### Step 2.4 — `RouteTimeline.tsx` → 视觉优化

改造文件：`frontend/src/components/RouteTimeline.tsx`

主要改动：时间线左侧竖线 + 圆点，时间/地点/类别分层显示，排队时间标红。

```tsx
<ol className="timeline">
  {stops.map((stop) => (
    <li key={stop.poi_id}>
      <div className="timeline-dot" />        {/* 圆点 */}
      <time>{stop.start_time}</time>
      <div className="timeline-content">
        <strong>{stop.name}</strong>
        <p>
          <span className="tag-small">{CATEGORY_LABELS[stop.category] ?? stop.category}</span>
          {stop.estimated_cost > 0 && <span>¥{stop.estimated_cost}</span>}
          {stop.queue_minutes > 0 && (
            <span className={stop.queue_minutes >= 30 ? 'text-warning' : ''}>
              排队 {stop.queue_minutes} 分
            </span>
          )}
        </p>
      </div>
    </li>
  ))}
</ol>
```

---

#### Step 2.5 — `ActionBar.tsx` → 传入路线 ID，手机端 2×2 布局

改造文件：`frontend/src/components/ActionBar.tsx`

```tsx
// 新增 props：传入路线 ID 和 onAction 回调
interface ActionBarProps {
  routeId: string;
  onAction?: (action: string, routeId: string) => void;
}

// 手机端 2×2 网格布局
// 按钮点击后触发 onAction，由父组件决定是否发 chat 请求
```

```css
.action-bar {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 16px;
}
.action-bar button {
  min-height: 44px;
  border-radius: var(--radius-sm);
}
```

---

### 阶段三：进阶功能（优先级 P2，预估 2～3 小时）

完成阶段一、二后，演示闭环已稳定，可按时间情况选择性做。

---

#### Step 3.1 — `ReplanPanel.tsx` → 底部抽屉 Drawer

```tsx
// 新增状态：抽屉是否打开
const [open, setOpen] = useState(false);

// 触发入口（悬浮按钮或底部 Tab）
<button className="fab-replan" onClick={() => setOpen(true)}>
  ⚡ 模拟突发事件
</button>

// 抽屉
{open && (
  <div className="drawer-overlay" onClick={() => setOpen(false)}>
    <div className="drawer" onClick={e => e.stopPropagation()}>
      <div className="drawer-handle" />
      <h3>模拟突发情况</h3>
      <button>🍽️ 餐厅排队 90 分钟</button>
      <button>🚗 交通堵车</button>
      <button>😴 有点累了</button>
    </div>
  </div>
)}
```

```css
.drawer-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 100; }
.drawer {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: #fff; border-radius: 16px 16px 0 0;
  padding: 16px 16px env(safe-area-inset-bottom);
  animation: slideUp 0.25s ease;
}
```

---

#### Step 3.2 — `FeedbackPanel.tsx` → 星级评分 UI

将现有 `input[type=range]` 改为 5 颗可点击的星星图标。

```tsx
function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="star-rating">
      {[1,2,3,4,5].map(star => (
        <Star
          key={star}
          size={24}
          className={star <= value ? 'star-filled' : 'star-empty'}
          onClick={() => onChange(star)}
        />
      ))}
    </div>
  );
}
```

---

#### Step 3.3 — `UserProfileBadge.tsx` → 手机端画像抽屉

手机端：顶部栏右侧显示头像 icon，点击后从右侧滑出抽屉，显示用户偏好标签。

---

#### Step 3.4 — Skeleton 骨架屏

在路线卡片 loading 期间显示骨架屏，代替 spinner：

```tsx
function RouteCardSkeleton() {
  return (
    <div className="route-card skeleton">
      <div className="sk-line sk-title" />
      <div className="sk-line sk-short" />
      <div className="sk-metrics">
        <div className="sk-chip" /><div className="sk-chip" /><div className="sk-chip" />
      </div>
      <div className="sk-timeline">
        {[1,2,3].map(i => <div key={i} className="sk-stop" />)}
      </div>
    </div>
  );
}
```

```css
.sk-line, .sk-chip, .sk-stop {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}
@keyframes shimmer { to { background-position: -200% 0; } }
```

---

## 四、新增文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/utils/traceIcons.ts` | 新增 | Agent 步骤图标映射 |
| `src/utils/categoryLabels.ts` | 新增 | POI 类别中文标签映射 |
| `src/components/ScoreBreakdown.tsx` | 新增 | 评分维度进度条 |

---

## 五、改造文件清单

| 文件 | 改动量 | 主要改动 |
|------|--------|---------|
| `src/styles/globals.css` | 大 | CSS 变量系统 + 手机端布局 + 所有组件新样式 |
| `src/pages/PlannerPage.tsx` | 中 | 固定顶栏 + 固定底部输入条 + 主内容滚动区 |
| `src/components/ChatPanel.tsx` | 大 | 气泡对话流 + chips + 输入栏分离 |
| `src/components/AgentTrace.tsx` | 中 | 折叠面板 + 图标 + 状态颜色 |
| `src/components/RouteCompare.tsx` | 中 | swipe 容器 + 圆点指示器 |
| `src/components/RouteCard.tsx` | 中 | 补充 ScoreBreakdown + 重规划提示 |
| `src/components/RouteTimeline.tsx` | 小 | 圆点 + 类别标签 + 排队标红 |
| `src/components/ActionBar.tsx` | 小 | 2×2 布局 + 传 routeId |
| `src/components/ReplanPanel.tsx` | 中 | 底部抽屉 |
| `src/components/FeedbackPanel.tsx` | 中 | 星级评分 |

---

## 六、各阶段验收标准

### 阶段一验收

```
□ npm run dev 不报错
□ 手机浏览器打开 localhost:5173，顶栏固定不滚动
□ 底部输入栏固定，不被软键盘遮挡
□ CSS 变量生效（主色 #FF6600 可见）
```

### 阶段二验收

```
□ 输入一句话 → 出现用户气泡 → 出现 AI 气泡
□ loading 期间气泡区显示打字动效
□ Agent Trace 在手机上默认折叠，点击可展开
□ 路线卡片在手机上可以左右滑动，每张占满屏宽
□ 评分维度进度条可见
□ 时间线圆点和颜色正常显示
□ 操作按钮 2×2 布局，可点击
```

### 阶段三验收

```
□ 点击"模拟突发事件"，底部抽屉从下弹出
□ 反馈面板显示 5 颗可点击星星
□ loading 时显示骨架屏而非 spinner
```

---

## 七、与 A/B 同学的对齐点

### 和 A 同学对齐（接口字段）

| 前端依赖字段 | 来源 | 状态 |
|------------|------|------|
| `ChatResponse.message` | A | ✅ 已有 |
| `ChatResponse.agent_trace[]` | A | ✅ 已有 |
| `ChatResponse.routes[]` | A 调 B 产出 | ✅ 已有 |
| `ChatResponse.need_clarification` | A | ✅ 已有，待前端使用 |

**待对齐**：`need_clarification=true` 时，前端需要展示追问气泡而不是路线卡片。

### 和 B 同学对齐（路线字段）

| 前端依赖字段 | 来源 | 状态 |
|------------|------|------|
| `route.score_breakdown` | B | ✅ 类型已定义 |
| `route.stops[].queue_minutes` | B | ✅ 已有 |
| `route.replan_reason` | B | ✅ 类型已定义，需确认非空时格式 |

**待对齐**：确认 `score_breakdown` 各维度的值域（0-10 还是 0-1），影响进度条宽度计算。

---

## 八、快速开始

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖（第一次）
npm install

# 3. 启动开发服务器（局域网 IP 可手机访问）
npm run dev

# 手机访问：打开手机浏览器，输入 Mac 的局域网 IP:5173
# Mac IP 查询：ifconfig | grep "inet 192"
```

> `package.json` 中 `vite --host 0.0.0.0` 已配置，局域网内手机可直接访问。

---

## 九、文件目录（改造后的最终结构）

```
frontend/src/
├── api/
│   ├── chatApi.ts          ✅ 不变
│   ├── client.ts           ✅ 不变
│   └── types.ts            ✅ 不变
├── components/
│   ├── ActionBar.tsx       ⚠️ 改造
│   ├── AgentTrace.tsx      ⚠️ 改造
│   ├── ChatPanel.tsx       ⚠️ 改造（最大）
│   ├── FeedbackPanel.tsx   ⚠️ 改造
│   ├── ReplanPanel.tsx     ⚠️ 改造
│   ├── RouteCard.tsx       ⚠️ 改造
│   ├── RouteCompare.tsx    ⚠️ 改造
│   ├── RouteTimeline.tsx   ⚠️ 改造
│   ├── ScoreBreakdown.tsx  🆕 新增
│   └── UserProfileBadge.tsx ⚠️ 改造
├── hooks/
│   ├── useChat.ts          ✅ 不变
│   ├── useDemoEvents.ts    ✅ 不变
│   └── useRoutes.ts        ✅ 不变
├── pages/
│   └── PlannerPage.tsx     ⚠️ 改造
├── styles/
│   └── globals.css         ⚠️ 改造（最大）
└── utils/
    ├── formatTime.ts       ✅ 不变
    ├── routeDisplay.ts     ✅ 不变
    ├── traceIcons.ts       🆕 新增
    └── categoryLabels.ts   🆕 新增
```
