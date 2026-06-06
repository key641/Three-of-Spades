# Scripts

后续放置初始化和演示脚本。

建议脚本：

- `seed_db.py`: 读取 `data/seed/*.json` 初始化 SQLite
- `demo_chat.py`: 调用 `/api/chat` 验证端到端链路
- `demo_cases.py`: 直接调用后端 `AgentOrchestrator`，跑 A 侧固定 demo case，检查 intent、routes、agent_trace 和多轮上下文
- `check_contract.py`: 检查前后端 JSON 字段是否一致
- `build_recall_assets.py`: 重建 B 侧召回资产，包括扩充 POI mock、生成 interaction events、协同过滤相似度和双塔 embedding
- `train_fine_rank_model.py`: 基于 interaction events 训练 sklearn 精排模型，生成 click/like/skip 三个模型产物

## B 侧召回资产重建

在项目根目录运行：

```bash
python3 scripts/build_recall_assets.py
```

脚本会更新：

- `data/seed/pois.json`
- `data/seed/interaction_events.json`
- `data/models/cf/item_similarity.json`
- `data/models/two_tower/*.json`

脚本是确定性的，重复运行会保持同一套 mock 数据规模：2240 条 POI、16000 条 interaction events、64 维双塔 embedding。

## B 侧精排模型训练

在项目根目录运行：

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/train_fine_rank_model.py
```

脚本会更新：

- `data/models/fine_rank/click_model.joblib`
- `data/models/fine_rank/like_model.joblib`
- `data/models/fine_rank/skip_model.joblib`
- `data/models/fine_rank/feature_schema.json`
- `data/models/fine_rank/model_metadata.json`

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
