# Backend

FastAPI 后端负责：

- `/api/chat` 主对话入口
- Agent 编排与 LLM provider 切换
- 用户意图、画像、策略权重
- POI 召回、路线生成、评分、动态重规划工具
- SQLite/mock 数据访问

## 负责人边界

| 目录 | 作用 | 负责人 |
| --- | --- | --- |
| `app/api` | 对外 API | A 主导 |
| `app/agent` | Agent 编排、prompt、memory | A |
| `app/llm` | OpenAI/DeepSeek provider | A |
| `app/tools` | Agent 可调用工具封装 | A+B |
| `app/services/poi_service.py` | POI 召回 | B |
| `app/services/route_service.py` | 路线生成 | B |
| `app/services/scoring_service.py` | 路线评分 | B |
| `app/services/replan_service.py` | 动态重规划 | B |
| `app/services/profile_service.py` | 用户画像 | A |
| `app/schemas` | 前后端契约 | A+B+C 共同维护 |

## 本地启动

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

也可以不激活虚拟环境，直接运行：

```bash
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## 虚拟环境说明

后端统一使用项目内虚拟环境：

```text
backend/.venv
```

推荐 Python 版本：

```text
Python 3.12.x
```

VS Code 里请选择：

```text
backend\.venv\Scripts\python.exe
```

不要使用全局 Python 环境直接开发后端，避免和本机其他项目的依赖版本冲突。
