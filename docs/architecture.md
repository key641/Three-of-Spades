# 工程架构说明

## 目标

本项目采用真实 Agent + API + 工具调用架构。mock 的只是 POI/UGC/用户画像数据，不 mock 系统链路。

## 总体链路

```text
React Frontend
  -> FastAPI /api/chat
  -> Agent Orchestrator
  -> LLM Provider
  -> Tool Layer
  -> Services
  -> SQLite / JSON seed
```

## 模块分工

| 模块 | 目录 | 负责人 | 说明 |
| --- | --- | --- | --- |
| 前端体验 | `frontend/src` | C | 聊天、路线卡片、动态事件、反馈 |
| API 主入口 | `backend/app/api` | A | `/api/chat` 和调试接口 |
| Agent 编排 | `backend/app/agent` | A | 意图、画像、工具调用、多轮状态 |
| LLM Provider | `backend/app/llm` | A | OpenAI/DeepSeek 切换 |
| Agent Tools | `backend/app/tools` | A+B | 对 Agent 暴露可调用工具 |
| POI/路线服务 | `backend/app/services/*route*`, `*poi*` | B | 召回、评分、规划、重规划 |
| 画像服务 | `backend/app/services/profile_service.py` | A | 用户画像、权重、反馈 |
| 数据 | `data/seed` | A+B | mock POI、UGC、画像、动态事件 |

## 接口契约

三人协作优先围绕以下 JSON：

- `Intent JSON`: A 负责
- `User Profile JSON`: A 负责
- `POI JSON`: B 负责
- `Route JSON`: B 负责，C 参与展示字段
- `Chat Response JSON`: A 负责，C 使用

## 第一阶段验收

输入：

```text
我们三个人周六下午在上海 citywalk，想吃好但别排队，人均300以内
```

输出：

```text
前端展示 3 条路线，并显示 Agent trace。
```

