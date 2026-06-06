# Data

这里存放 mock 数据。数据可以是 mock 的，但必须通过后端 service/API 使用，前端不要直接读取。

| 文件 | 内容 | 负责人 |
| --- | --- | --- |
| `seed/pois.json` | POI 候选池 | B |
| `seed/interaction_events.json` | mock 用户-POI 交互事件，用于召回模型 | B |
| `seed/reviews.json` | UGC 标签与评论摘要 | B |
| `seed/user_profiles.json` | 用户画像样例 | A |
| `seed/demo_events.json` | 排队、堵车、下雨等动态事件 | A+B |
| `models/two_tower/*.json` | 双塔召回 user/poi embedding 和元信息 | B |
| `models/cf/item_similarity.json` | 协同过滤 POI 相似度表 | B |
| `models/fine_rank/*.joblib` | sklearn POI 精排模型，预测 click/like/skip | B |
| `models/fine_rank/model_metadata.json` | 精排训练样本、指标和特征版本元信息 | B |

`seed/pois.json` 当前覆盖上海、北京两城，共 1680 条 POI。召回相关 seed/model 文件可通过以下命令重建：

```bash
python3 scripts/build_recall_assets.py
```

精排模型可通过以下命令重训：

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/train_fine_rank_model.py
```
