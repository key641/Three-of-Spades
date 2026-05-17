# AI 本地路线智能规划 Agent

这是一个 Hackathon 项目工程骨架，用于实现「真实 Agent + API + React 前端 + mock 数据」的本地路线规划系统。

项目目标：

```text
用户自然语言输入
-> Agent 理解意图并必要追问
-> 读取用户画像并生成策略权重
-> 调用 POI 召回工具
-> 调用路线规划与评分工具
-> 前端展示多条路线
-> 支持交互调整与动态重规划
-> 行程反馈更新用户画像
```

## 技术栈

| 层级 | 技术 | 负责人 |
| --- | --- | --- |
| 前端 | React + TypeScript + Vite | C 同学 |
| 后端 | Python + FastAPI | A 同学 |
| Agent | LLM tool calling / provider abstraction | A 同学 |
| 路线策略 | Python service tools | B 同学 |
| 数据 | SQLite + JSON seed mock data | B/A 同学 |

## 目录结构

```text
local-route-agent/
├── backend/       # FastAPI 后端、Agent 编排、路线工具
├── frontend/      # React 前端 Demo
├── data/          # mock POI、用户画像、动态事件
├── docs/          # 架构、分工、接口文档
├── scripts/       # 初始化与演示脚本
├── README.md
└── .env.example
```

## 快速启动

后端：

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认前端请求后端地址：`http://localhost:8000`。

## 每个人重点看哪些文件

### A 同学：Agent / 后端编排 / 用户画像

A 的核心任务是让系统真的像一个 Agent：能理解用户需求、管理多轮对话、调用工具、解释路线、处理反馈。

| 优先级 | 文件/目录 | 重点看什么 | 你负责产出什么 |
| --- | --- | --- | --- |
| 必看 | `backend/app/api/chat.py` | 前端主入口 `/api/chat` 怎么接收消息并返回结果 | 主对话 API |
| 必看 | `backend/app/agent/orchestrator.py` | Agent 主流程：解析意图、读画像、召回 POI、生成路线 | Agent 编排逻辑 |
| 必看 | `backend/app/agent/memory.py` | 当前路线和 session 状态怎么保存 | 多轮会话状态 |
| 必看 | `backend/app/agent/prompts.py` | 系统 prompt 和后续意图解析/解释 prompt 放哪里 | prompt 模板 |
| 必看 | `backend/app/agent/tool_registry.py` | Agent 可以调用哪些工具 | tool 列表和工具定义 |
| 必看 | `backend/app/llm/` | OpenAI/DeepSeek provider 怎么接入和切换 | 真实大模型调用 |
| 必看 | `backend/app/services/profile_service.py` | 用户画像、偏好权重、反馈更新逻辑 | 用户画像和策略权重 |
| 必看 | `backend/app/tools/intent_tool.py` | 用户自然语言转结构化约束 | 意图解析工具 |
| 必看 | `backend/app/tools/profile_tool.py` | 画像工具如何暴露给 Agent | 画像读取/权重工具 |
| 必看 | `backend/app/tools/feedback_tool.py` | 反馈如何更新画像 | 反馈闭环工具 |
| 必看 | `backend/app/schemas/intent.py` | 用户意图 JSON 字段 | Intent 契约 |
| 必看 | `backend/app/schemas/chat.py` | `/api/chat` 返回给前端的数据结构 | Chat Response 契约 |
| 建议看 | `docs/api_contract.md` | 前后端接口契约 | 和 C 对齐字段 |
| 建议看 | `data/seed/user_profiles.json` | mock 用户画像长什么样 | 用户画像 mock 数据 |

A 第一周最重要的改动：

```text
1. 把 orchestrator.py 里的 mock_parse_intent 替换成真实 LLM structured output
2. 把 llm/openai_client.py 或 deepseek_client.py 接成真实 API
3. 让 /api/chat 稳定返回 intent、routes、agent_trace
```

### B 同学：POI 数据 / 路线策略工具

B 的核心任务是让路线真的算得出来、评分有依据、动态情况能局部调整。重点不是复杂算法，而是可解释的策略规则。

| 优先级 | 文件/目录 | 重点看什么 | 你负责产出什么 |
| --- | --- | --- | --- |
| 必看 | `backend/app/services/poi_service.py` | POI 如何筛选、标签如何匹配 | POI 召回逻辑 |
| 必看 | `backend/app/services/route_service.py` | 多条路线如何生成，POI 如何排序 | 路线生成逻辑 |
| 必看 | `backend/app/services/scoring_service.py` | 路线评分如何计算 | 评分公式和分维度解释 |
| 必看 | `backend/app/services/replan_service.py` | 动态事件后如何重规划 | 局部替换和重规划 |
| 必看 | `backend/app/tools/poi_tool.py` | POI 搜索如何暴露给 Agent | POI tool |
| 必看 | `backend/app/tools/route_tool.py` | 路线规划如何暴露给 Agent | route planning tool |
| 必看 | `backend/app/tools/replan_tool.py` | 重规划如何暴露给 Agent | replan tool |
| 必看 | `backend/app/schemas/poi.py` | 每个 POI 应该有哪些字段 | POI 数据契约 |
| 必看 | `backend/app/schemas/route.py` | 路线、站点、评分字段长什么样 | Route JSON 契约 |
| 必看 | `data/seed/pois.json` | mock POI 数据样例 | 50-80 条 POI 数据 |
| 必看 | `data/seed/reviews.json` | UGC 标签和点评摘要如何模拟 | UGC mock 数据 |
| 必看 | `data/seed/demo_events.json` | 排队、堵车、下雨等事件 | 动态事件 mock 数据 |
| 建议看 | `backend/app/api/pois.py` | POI 调试接口 | 单独测试召回 |
| 建议看 | `backend/app/api/routes.py` | 路线和重规划调试接口 | 单独测试路线工具 |

B 第一周最重要的改动：

```text
1. 扩充 data/seed/pois.json 到 50-80 条
2. 让 poi_service.py 从 JSON/SQLite 读取数据，而不是使用写死样例
3. 完善 route_service.py，让三条路线真的有差异
4. 在 scoring_service.py 中补充质量、排队、预算、距离、偏好五个维度的可解释评分
```

### C 同学：React 前端 / UI / 体验

C 的核心任务是让评委和用户能直接看懂 Agent 做了什么、路线为什么合理、用户如何继续调整。

| 优先级 | 文件/目录 | 重点看什么 | 你负责产出什么 |
| --- | --- | --- | --- |
| 必看 | `frontend/src/pages/PlannerPage.tsx` | 主页面结构如何组织 | Demo 主页面 |
| 必看 | `frontend/src/api/client.ts` | 前端如何请求后端 | API 请求封装 |
| 必看 | `frontend/src/api/chatApi.ts` | `/api/chat` 怎么调用 | 聊天请求 |
| 必看 | `frontend/src/api/types.ts` | 前端使用的 Route/Trace 类型 | 前端类型契约 |
| 必看 | `frontend/src/hooks/useChat.ts` | 聊天请求、loading、error 状态 | 对话状态 |
| 必看 | `frontend/src/components/ChatPanel.tsx` | 用户输入和 Agent 回复展示 | 聊天输入组件 |
| 必看 | `frontend/src/components/AgentTrace.tsx` | Agent 调用过程怎么展示 | Agent trace 展示 |
| 必看 | `frontend/src/components/RouteCompare.tsx` | 多条路线如何布局 | 多方案对比 |
| 必看 | `frontend/src/components/RouteCard.tsx` | 单条路线展示哪些核心信息 | 路线卡片 |
| 必看 | `frontend/src/components/RouteTimeline.tsx` | POI 时间线如何展示 | 行程时间线 |
| 必看 | `frontend/src/components/ActionBar.tsx` | 换一家、更省钱、少排队等按钮 | 交互按钮 |
| 必看 | `frontend/src/components/ReplanPanel.tsx` | 动态事件如何模拟 | 重规划演示入口 |
| 必看 | `frontend/src/components/FeedbackPanel.tsx` | 行程评分如何收集 | 反馈组件 |
| 必看 | `frontend/src/styles/globals.css` | 页面整体视觉和响应式布局 | UI 样式 |
| 建议看 | `docs/api_contract.md` | 后端返回字段 | 和 A/B 对齐展示字段 |

C 第一周最重要的改动：

```text
1. 保证输入一句话后能展示路线卡片和 Agent trace
2. 优化 RouteCard 和 RouteTimeline，让路线一眼能看懂
3. 和 A 对齐 Chat Response 字段，和 B 对齐 Route JSON 字段
4. 不要先做复杂视觉，先保证演示闭环稳定
```

## 协作边界

| 同学 | 主要负责 | 不主要负责 |
| --- | --- | --- |
| A | 用户说什么、Agent 怎么理解、怎么调工具、怎么解释 | 不负责具体路线怎么算 |
| B | POI 怎么筛、路线怎么排、分数怎么算、突发情况怎么替换 | 不负责大模型对话体验 |
| C | 用户怎么看、怎么点、怎么理解路线变化和 Agent 过程 | 不负责后端策略和算法 |

## 关键接口流向

```text
frontend/src/components/ChatPanel.tsx
-> frontend/src/api/chatApi.ts
-> backend/app/api/chat.py
-> backend/app/agent/orchestrator.py
-> backend/app/services/profile_service.py
-> backend/app/services/poi_service.py
-> backend/app/services/route_service.py
-> backend/app/services/scoring_service.py
-> frontend/src/components/RouteCompare.tsx
```

## 当前骨架状态

这个版本先完成工程边界和接口样例，后续三位同学按 `docs/team_plan.md` 的节奏补齐真实逻辑。

当前已经验证：

- 后端 `/health` 可以返回 `ok`
- 后端 `/api/chat` 可以返回 3 条路线和 5 个 Agent trace 步骤
- 前端 `npm run build` 可以通过

## 相关文档

| 文档 | 用途 |
| --- | --- |
| `docs/architecture.md` | 工程架构说明 |
| `docs/team_plan.md` | 三人分工和三周计划 |
| `docs/ai_coding_guide.md` | AI coding 协作与执行指南 |
| `docs/api_contract.md` | API 契约 |
| `backend/README.md` | 后端说明 |
| `frontend/README.md` | 前端说明 |
| `data/README.md` | mock 数据说明 |
