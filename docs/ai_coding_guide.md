# AI Coding 协作与执行指南

这份文档给三位同学使用 AI coding 时统一规则。目标是：减少互相覆盖、减少字段不一致、减少“看起来能跑但联调失败”的代码。

## 总原则

1. 每次只让 AI 完成一个明确小任务，不要一次让它重构大半个项目。
2. 先说明自己负责的模块，再说明允许修改的文件范围。
3. 不要让 AI 随意改接口字段。`schemas` 和 `frontend/src/api/types.ts` 变更必须同步通知其他人。
4. 每次改完都跑对应验证命令。
5. AI 生成代码后必须人工快速审一遍：看数据结构、边界情况、错误处理、是否写死。

## 三人文件 ownership

| 同学 | 主要可改文件 | 改动前需要告知他人的文件 |
| --- | --- | --- |
| A | `backend/app/api/chat.py`、`backend/app/agent/`、`backend/app/llm/`、`backend/app/services/profile_service.py`、`backend/app/tools/intent_tool.py`、`backend/app/tools/profile_tool.py`、`backend/app/tools/feedback_tool.py` | `backend/app/schemas/`、`docs/api_contract.md` |
| B | `backend/app/services/poi_service.py`、`backend/app/services/route_service.py`、`backend/app/services/scoring_service.py`、`backend/app/services/replan_service.py`、`backend/app/tools/poi_tool.py`、`backend/app/tools/route_tool.py`、`backend/app/tools/replan_tool.py`、`data/seed/` | `backend/app/schemas/poi.py`、`backend/app/schemas/route.py` |
| C | `frontend/src/pages/`、`frontend/src/components/`、`frontend/src/hooks/`、`frontend/src/styles/`、`frontend/src/api/` | `frontend/src/api/types.ts`、任何依赖后端字段的组件 |

## 禁止 AI 随意做的事

- 不要让 AI 一次性“优化整个项目”。
- 不要让 AI 删除别人负责的文件。
- 不要让 AI 改完后不跑验证。
- 不要让 AI 发明新的 JSON 字段而不更新 schema 和文档。
- 不要让 AI 把 mock 数据直接写死在前端。
- 不要让 AI 把路线规划全部交给 LLM 文案生成。
- 不要让 AI 为了修一个 bug 大范围重命名文件、函数、字段。
- 不要把 API key 写进代码，统一放 `.env`。

## 每次 AI coding 的推荐流程

```text
1. 先读相关文件
2. 明确这次任务的文件范围
3. 让 AI 给出小计划
4. 让 AI 修改代码
5. 跑验证命令
6. 人工检查关键逻辑
7. 更新 README/docs 中受影响的说明
```

## 推荐 prompt 模板

### 通用模板

```text
你现在只负责本项目中的【模块名】。

背景：
- 项目是 AI 本地路线规划 Agent
- 技术栈是 FastAPI + React + mock POI 数据
- 请遵守 docs/ai_coding_guide.md 中的协作规则

本次任务：
- [写清楚一个具体目标]

允许修改的文件：
- [列出文件]

不要修改：
- [列出不希望碰的文件]

验收标准：
- [列出命令或接口返回要求]

请先阅读相关文件，再做最小必要修改。
```

### A 同学 prompt 示例

```text
你负责 Agent 编排。

本次任务：
把 backend/app/agent/orchestrator.py 中的 mock_parse_intent 替换为基于 LLM 的结构化意图解析。

允许修改：
- backend/app/agent/orchestrator.py
- backend/app/llm/openai_client.py
- backend/app/agent/prompts.py
- backend/app/tools/intent_tool.py

不要修改：
- backend/app/services/route_service.py
- frontend/src

验收标准：
- POST /api/chat 后仍返回 routes 和 agent_trace
- intent 字段包含 city、people_count、budget_per_person、preferences
- LLM 失败时有 fallback，不影响 demo
```

### B 同学 prompt 示例

```text
你负责路线策略工具。

本次任务：
让 POIService 从 data/seed/pois.json 读取 POI，并根据 intent.preferences、budget_per_person、avoid_tags 进行打分排序。

允许修改：
- backend/app/services/poi_service.py
- data/seed/pois.json
- backend/app/tests/test_poi_search.py

不要修改：
- backend/app/agent/orchestrator.py
- frontend/src

验收标准：
- /api/pois/search 能返回按匹配分排序的 POI
- 不改变 POI schema 字段名
- python -m compileall backend/app 通过
```

### C 同学 prompt 示例

```text
你负责 React 前端体验。

本次任务：
优化 RouteCard，让三条路线能清楚展示总时长、人均预算、排队时间、评分维度和 POI 时间线。

允许修改：
- frontend/src/components/RouteCard.tsx
- frontend/src/components/RouteTimeline.tsx
- frontend/src/styles/globals.css

不要修改：
- backend
- frontend/src/api/types.ts

验收标准：
- npm run build 通过
- 页面在 1280px 和 390px 宽度下不出现明显文字重叠
- 不新增后端字段依赖
```

## 接口字段变更规则

接口字段是三个人最容易冲突的地方。任何字段变更必须遵守：

1. 后端 schema 先改：`backend/app/schemas/`
2. 前端类型同步改：`frontend/src/api/types.ts`
3. API 文档同步改：`docs/api_contract.md`
4. 和相关同学说清楚字段变化

字段变更记录建议写成：

```text
变更字段：Route.total_walk_minutes
原因：前端需要展示步行压力
影响文件：
- backend/app/schemas/route.py
- frontend/src/api/types.ts
- frontend/src/components/RouteCard.tsx
兼容处理：
- 如果缺失则前端展示“待估算”
```

## 每个人的每日最小验证

后端同学统一使用虚拟环境执行命令。第一次拉取项目后先运行：

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

之后每次开发前激活：

```bash
cd backend
.\.venv\Scripts\activate
```

也可以直接用：

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

### A 验证

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

然后请求：

```http
POST http://127.0.0.1:8000/api/chat
```

必须确认：

- 有 `message`
- 有 `routes`
- 有 `agent_trace`
- LLM 失败时 demo 不崩

### B 验证

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

重点确认：

- POI 搜索不返回空列表
- 三条路线 objective 不同
- 分数不全相同
- 动态重规划能保留已完成 POI

### C 验证

```bash
cd frontend
npm run build
```

重点确认：

- 没有 TypeScript 报错
- 空 routes 时页面不崩
- 后端请求失败时有错误提示
- 手机宽度下卡片不重叠

## 联调前检查清单

每天结束前至少做一次：

```text
1. 后端能启动
2. 前端能启动
3. /api/chat 返回 3 条路线
4. 页面能展示路线卡片
5. Agent trace 能展示完整步骤
6. 没有新增未说明字段
```

## 减少 bug 的策略

| 风险 | 预防方式 |
| --- | --- |
| 字段对不上 | 先改 schema，再改前端 type，再改组件 |
| AI 大范围乱改 | prompt 中明确“只允许修改这些文件” |
| 路线结果很假 | B 用 5-8 个固定 demo case 调参 |
| LLM 调用不稳定 | A 必须保留 fallback 逻辑 |
| 前端空数据崩溃 | C 对 routes、trace、profile 做空状态 |
| mock 数据格式乱 | B 每次扩数据后保持和 `POI` schema 一致 |
| 动态重规划说不清 | B 返回结构化 replan_reason，A 负责润色 |

## 推荐开发节奏

```text
上午：每人完成自己小任务
下午早段：各自跑验证
下午晚段：合一次端到端
晚上：只修 bug 和补文档，不大改接口
```

第 3 周后半尤其重要：不再让 AI 加大功能，只让它修 bug、补边界、优化文案和 UI。

## Code Review 要看什么

每次 AI 生成代码后，至少人工检查 5 点：

1. 是否改了不该改的文件。
2. 是否新增了没有文档说明的字段。
3. 是否把异常情况考虑进去。
4. 是否有明显写死到 demo case 的逻辑。
5. 是否还能通过对应验证命令。
