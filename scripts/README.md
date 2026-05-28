# Scripts

后续放置初始化和演示脚本。

建议脚本：

- `seed_db.py`: 读取 `data/seed/*.json` 初始化 SQLite
- `demo_chat.py`: 调用 `/api/chat` 验证端到端链路
- `demo_cases.py`: 直接调用后端 `AgentOrchestrator`，跑 A 侧固定 demo case，检查 intent、routes、agent_trace 和多轮上下文
- `check_contract.py`: 检查前后端 JSON 字段是否一致

## A 侧 demo case 检查

在项目根目录运行：

```bash
.\backend\.venv\Scripts\python.exe scripts\demo_cases.py
```

输出会显示每个 case 的城市识别、路线数量和 trace。需要看完整回复时：

```bash
.\backend\.venv\Scripts\python.exe scripts\demo_cases.py --verbose
```

如果需要查看 LLM/provider 的错误日志：

```bash
.\backend\.venv\Scripts\python.exe scripts\demo_cases.py --debug-logs
```

