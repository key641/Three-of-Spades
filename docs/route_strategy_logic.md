# 路线策略代码逻辑说明

本文档说明当前 B 侧路线策略的真实代码逻辑，覆盖三类场景：

- 规划路线：用户发起一次新的出行规划或追加约束后重新生成路线。
- 修改部分路线：用户希望替换 POI，或遇到排队、闭店、堵车、天气变化等事件后局部重规划。
- 预制路线：基于 mock 天气和用户画像，在用户正式交互前生成 3 条可直接展示的路线。

核心代码位置：

- `backend/app/services/poi_service.py`：POI 召回和 POI 初排。
- `backend/app/services/strategy_service.py`：策略标签识别、权重调整、路线目标打分。
- `backend/app/services/route_service.py`：多目标路线候选生成、路线排序、路线字段补全。
- `backend/app/services/scoring_service.py`：路线五维评分和硬惩罚。
- `backend/app/services/replan_service.py`：已生成路线的局部替换和动态重规划。
- `backend/app/services/predictive_route_service.py`：mock 天气 + 画像预制路线。
- `backend/app/services/amap_service.py`、`backend/app/services/mock_route_map_service.py`：两点之间路段耗时、距离、交通方式、polyline 和步骤。

## 1. 总体数据流

普通规划链路：

```text
用户消息
-> Orchestrator 解析 Intent、读取 UserProfile
-> StrategyService.infer_tags()
-> ProfileService.build_strategy_weights()
-> POIService.search()
-> RouteService.generate_routes()
-> ScoringService.score() / overall_score()
-> 返回 RoutePlanResponse(routes)
```

局部修改链路：

```text
已有 current_routes + selected_route_id + event_type/event_payload
-> ReplanService.replan()
-> 判断哪些未来 stop 受影响
-> 从本地 POI 或 mock map provider 找替代点
-> 重建后续 stops 时间线
-> 重新计算路线总计和评分
-> 返回更新后的 routes
```

预制路线链路：

```text
user_id + city + weather_scenario + 可选 user_profile
-> PredictiveRouteService 读取 mock_weather
-> 天气转偏好
-> 画像或 seed profile 转目标 objectives
-> POIService.search(limit=48)
-> RouteService.generate_routes_for_objectives(max_stops<=4, routes_per_objective=3)
-> 做路线差异过滤
-> 返回 1-3 条 Route
```

## 2. 策略标签和路线目标

`StrategyService` 把用户偏好、画像标签转成内部策略标签 `StrategyTag`。每个标签会影响两件事：

- 调整评分权重：例如 `少走路` 提高 distance 权重，`省钱` 提高 budget 权重，`拍照` 提高 preference 权重。
- 推动路线目标：例如 `吃好` 推动 `food_first`，`室内/雨天` 推动 `indoor_rainy`，`晚上/夜景` 推动 `night_friendly`。

当前支持的主要 objective：

| objective | 含义 | 主要偏向 |
| --- | --- | --- |
| `balanced` | 综合平衡 | 质量、排队、距离、预算、偏好均衡 |
| `budget` | 省钱路线 | 低人均、预算友好 |
| `low_walking` | 少走路路线 | 距离短、步行强度低、靠近交通 |
| `food_first` | 餐饮优先 | 正餐、咖啡、小吃等餐饮节点 |
| `photo_food` | 拍照餐饮 | 餐饮 + 拍照环境 |
| `nature_relax` | 自然放松 | 公园、自然、低强度休闲 |
| `photo_citywalk` | 拍照 citywalk | 街区、地标、拍照点 |
| `indoor_rainy` | 室内雨天 | 室内、雨天友好 |
| `night_friendly` | 夜间友好 | 夜景、晚间可玩 |

普通规划中，`RouteService._select_objectives()` 会：

1. 如果没有偏好和画像，默认生成 `photo_citywalk`、`food_first`、`balanced`。
2. 如果有偏好，调用 `StrategyService.objective_scores()` 给所有 objective 打分。
3. 取分数最高的非 `balanced` 目标前 2 个，再补 `balanced`。
4. 如果不足 3 个，用 `food_first`、`photo_citywalk`、`nature_relax`、`indoor_rainy`、`low_walking`、`budget`、`night_friendly` 兜底。

## 3. POI 召回逻辑

入口是 `POIService.search(intent, user_profile, limit=32, strategy_tags)`。

### 3.1 数据来源

当前 POI 来自 `data/seed/pois.json`，只覆盖上海和北京。读取时会把原始 JSON 转成统一的 `POI` 对象，并补充这些路线策略字段：

- `primary_category`：主类目，例如 `food`、`culture`、`landmark`、`nature`。
- `secondary_categories`：辅助标签，例如 `photo`、`indoor`、`night`、`rainy`、`budget`。
- `route_roles`：路线角色，例如 `main_activity`、`meal`、`coffee_break`、`photo_stop`、`rest_stop`、`transit_anchor`、`night_end`。
- `experience_tags`：体验标签，例如 `老字号`、`安静`、`文艺`、`夜景`、`雨天`。

这些字段会进入搜索文本，后续召回和评分不只依赖原始 `category`。

### 3.2 召回过滤

召回大致分三层：

1. 城市过滤：优先取 `poi.city == intent.city`。如果该城市没有数据，会用上海数据克隆成 fallback 候选，保证不空。
2. 严格匹配：要求命中用户偏好、避开 avoid_tags、价格不是极端超预算。
3. 放宽兜底：如果严格结果不足，会放宽为“不命中避开项 + 不是极端超预算”；仍不足则补低风险 POI。

预算过滤不是简单 `avg_price <= budget`，而是允许轻微超预算，但排除极端不匹配：

```text
poi.avg_price <= max(budget * 2, budget + 160)
```

### 3.3 POI 初排分数

`POIService._rank_score()` 会把每个 POI 打一个初排分。主要维度：

- 质量：评分、评论量、热度。
- 排队：排队时间、人流强度越低越好。
- 距离：如果有起点坐标，离起点越近越好。
- 预算：价格越贴合预算越好。
- 偏好：命中 `intent.preferences`、画像标签、策略标签越多越好。
- 场景：当前 `friends_citywalk` 会偏向朋友、拍照、citywalk、夜景、咖啡。
- 时间：营业时间、最晚入场、推荐时段是否匹配。

此外还有显式加分：

- 用户要 `少排队`，加排队分。
- 用户要 `吃好/咖啡/轻食/小吃`，加餐饮匹配分。
- 用户要 `citywalk`，加街区、拍照、地标分。
- 用户要 `室内/雨天`，加室内或雨天友好分。
- 用户要 `少走路/轻松`，加低步行强度分。
- 策略标签命中 POI 时，额外加 `StrategyService.tag_score()`。

### 3.4 召回结果多样性

初排后会做一次类目多样性处理：当 `limit >= 12` 时，每个 category 有一个上限，避免前几十个 POI 全是餐厅或咖啡。未入选的高分 POI 会放到后面作为补充。

## 4. 路线生成逻辑

入口是：

- 普通规划：`RouteService.generate_routes(request)`。
- 预制路线或指定目标生成：`RouteService.generate_routes_for_objectives(request, objectives, max_stops, routes_per_objective)`。

### 4.1 每个目标生成多条候选

对每个 objective，流程是：

1. 用 `_start_candidates()` 对所有 POI 按该 objective 的 POI 分数排序。
2. 取前若干高分 POI 作为 seed。
3. 从 seed 开始贪心扩展路线。
4. 每个 objective 最多生成 `CANDIDATES_PER_OBJECTIVE = 4` 条内部候选。
5. 对候选调用 `ScoringService` 打分。
6. 普通规划每个 objective 返回第一条 best；预制路线可以拿每个 objective 的多条候选做差异筛选。

### 4.2 stop 数量上下限

`RouteService._stop_bounds()` 根据时长决定默认 POI 数：

| 时长 | 默认 stop 数 |
| --- | --- |
| `duration_hours <= 3` | 2-3 个 |
| `duration_hours <= 6` | 3-4 个 |
| 更长 | 4-5 个 |

如果用户偏好 `轻松/少走路/老人/亲子`，会减少最大 stop 数。如果用户偏好 `多打卡/citywalk/拍照`，会增加最大 stop 数，最多 5 个。

预制路线会额外传 `max_stops`，默认最多 4 个；短时长、雨天、少走路、亲子、老人友好时最多 3 个。

### 4.3 单个 POI 在路线内的分数

`RouteService._poi_score()` 是路线生成阶段的局部打分，和最终路线评分不同。基础分包括：

- `quality`：质量。
- `queue`：排队少。
- `budget`：预算贴合。
- `preference`：偏好命中。
- `time_fit`：到达时间、营业、推荐时段。
- `distance`：离当前点近。
- `walking`：步行强度低。

不同 objective 会加额外偏置：

- `budget`：加大 budget。
- `low_walking`：加大距离近、低步行、交通枢纽。
- `food_first`：加餐饮分。
- `photo_food`：加拍照餐饮分。
- `nature_relax`：加自然分。
- `photo_citywalk`：加拍照 citywalk 分。
- `indoor_rainy`：加室内、雨天友好。
- `night_friendly`：加夜间活动和晚间时段。

### 4.4 贪心扩展和结构约束

路线从 seed 开始，不断选下一个 POI。每次扩展会检查：

- 加上交通时间、排队时间、游玩时间后不能超过总时长。
- 不能重复已选 POI。
- 如果路线需要餐饮，优先补餐饮点。
- 默认不混合“正餐”和“咖啡”作为多个餐饮节点，除非用户明确同时想要。
- 默认不重复多家咖啡或多家正餐，除非用户明确要咖啡探店或美食扫街。

选下一个 POI 时，除了 POI 局部分，还会叠加：

- `nearby_bonus`：和已选点互为 nearby 时加分。
- `distance_penalty`：离当前点越远扣分。
- `diversity_penalty`：连续同主类目、重复 route_roles、多次咖啡或正餐会扣分。
- `missing_role_bonus`：路线缺主活动、餐饮、拍照、休息等角色时，对能补角色的 POI 加分。

这也是当前路线比“高分 POI 列表”更像行程的主要原因。

## 5. 交通路段逻辑

每个 `RouteStop` 都会写入从上一个位置到当前 POI 的路段字段：

- `travel_minutes_from_previous`
- `distance_km_from_previous`
- `transport_mode_from_previous`
- `polyline_from_previous`
- `route_leg_source_from_previous`
- `route_steps_from_previous`

`RouteService._best_route_leg()` 会按距离和偏好枚举候选交通方式：

- 短距离且不偏好少走路：`walk`、`taxi`。
- 一般距离：`walk`、`taxi`、`metro`，再加 POI 推荐交通。
- 超过 8 公里：去掉 `walk`。

然后调用 `AmapService.route_leg()`。当前默认 `MAP_ROUTE_PROVIDER=mock`，所以会走 `MockRouteMapService`：

- `walk`：返回步行耗时、距离、一步说明。
- `taxi`：返回打车距离、耗时、折线。
- `metro`：优先匹配附近地铁站，支持同线直达和一次换乘，失败则 fallback 到 taxi。
- `bus`：匹配附近公交线，失败则 fallback 到 taxi。

耗时不是纯直线估算，会按交通方式加入绕路系数、等待时间、进出站时间、高峰倍率。`route_steps_from_previous` 会包含类似“乘坐地铁2号线 3站至 XXX站”的分段说明。

## 6. 路线最终评分和排序

路线候选生成后，会进入 `ScoringService`。

### 6.1 五维评分

每条路线都有 `score_breakdown`：

| 维度 | 逻辑 |
| --- | --- |
| `quality` | POI 评分、评论量、热度，按游玩时长加权；有风险或需预约会扣分 |
| `queue` | 总排队时间、实时人流、拥挤程度越低越好 |
| `budget` | 总人均是否在预算内，POI budget_friendly 加一点 |
| `distance` | 总路程、总交通时间、步行强度、连续同类目；靠近交通加分 |
| `preference` | 用户偏好命中、objective 适配度、路线结构完整度 |

最终分数是加权和减去硬惩罚，范围 0-100。

### 6.2 objective 权重

不同 objective 的五维权重不同。例如：

- `balanced`：质量 0.30、排队 0.25、距离 0.20、预算 0.15、偏好 0.10。
- `budget`：预算权重 0.45。
- `low_walking`：距离权重 0.45。
- `food_first`：偏好权重 0.35。
- `photo_food`：偏好权重 0.40。
- `indoor_rainy`：偏好权重 0.40。

如果 objective 没有固定权重，会使用 request 中的 `strategy_weights` 归一化结果。

### 6.3 硬惩罚

`ScoringService.hard_penalty()` 会扣分：

- 总时长超过 `duration_hours`。
- 总费用超过预算，超过 1.5 倍预算继续重扣。
- 到达时 POI 未营业。
- 命中 avoid_tags 或画像 avoid_tags。
- objective 必需元素缺失，例如：
  - `food_first` 没有餐饮。
  - `photo_food` 没有拍照餐饮。
  - `nature_relax` 没有自然点。
  - `indoor_rainy` 没有室内点。
- 路线结构不合理，例如没有主活动、重复咖啡、重复正餐、连续同类目、重复 route_roles。

### 6.4 候选排序

`RouteService._route_rank_key()` 不是只看最终 `score`。排序 key 是：

```text
(route.score,
 objective_fit,
 stop_fit,
 time_fit,
 -total_distance_km,
 preference_fit)
```

含义：

- 先看综合分。
- 再看是否更贴合当前 objective。
- 再看 stop 数是否接近理想数量。
- 再看总时长是否接近时长窗口的 85%。
- 再偏向距离更短。
- 最后看用户偏好命中率。

## 7. 普通规划路线

普通规划由 `Orchestrator` 触发，核心代码在 `backend/app/agent/orchestrator.py`。

它会：

1. 解析用户消息为 `Intent`。
2. 应用多轮上下文，比如“再少走路一点”会继承上一轮城市、时长、偏好，再叠加新约束。
3. 读取用户画像。
4. 生成策略标签和权重。
5. 召回 POI。
6. 调 `RouteService.generate_routes()` 生成 1-3 条不同 objective 的路线。
7. 保存到 session memory，便于后续追问或修改。

普通规划的路线数主要由 objective 数决定，通常最多 3 条：两个画像/偏好目标 + `balanced`。

## 8. 修改部分路线

局部修改入口是：

- API：`POST /api/routes/replan`。
- Agent 内部：当 `ChatRequest.event_type` 属于 `replace_poi`、`avoid_poi`、`queue_spike`、`traffic_jam`、`user_tired`、`weather_change` 时，走 `_handle_structured_replan()`。

### 8.1 修改范围

`ReplanService` 不会默认整条路线推倒重来。它会：

1. 找到 `selected_route_id` 对应路线。
2. 保留 `completed_poi_ids` 中已经完成的 stops。
3. 只检查后续 future stops。
4. `locked_poi_ids` 和 `preserve_poi_ids` 默认不替换，除非闭店、不可达、售罄等强不可用。

### 8.2 触发替换的条件

某个未来 stop 会被替换，当：

- 地图状态是 `closed`、`unavailable`、`sold_out`。
- `replace_poi` 或 `avoid_poi` 命中目标点。
- `avoid_poi` 命中用户传入的 `avoid_tags`。
- `queue_spike` 后排队时间超过 `QUEUE_REPLACE_THRESHOLD = 45`。
- `user_tired` 且该 stop 是高步行强度。
- `weather_change` 且该 stop 不是室内。
- `preference_change` 命中受影响点、避开标签，或新偏好要求少走路/室内。

如果 `event_payload.warning_only = true`，则只给 warning，不替换。

### 8.3 替代 POI 召回

替代点优先从本地 POI 中找：

- 同城市。
- 不在已选、已完成、锁定、保留、不可用集合中。
- 不命中 `avoid_tags`。
- 如果传了 `replacement_category`，必须匹配替代类目。
- 和原 POI 有角色重叠、主类目相同或餐饮类型相同。
- 实时状态不是关闭或不可用。

如果本地没有可用替代点，才会调用 `map_provider.search_nearby_pois()` 找外部候选。当前 mock provider 默认不返回外部候选，除非 `event_payload.allow_external_candidates = true`。

### 8.4 替代点排序

`_replacement_score()` 会综合：

- 和原 POI 的角色、主类目、餐饮类型相似度。
- 排队越短越好。
- 从当前点过去越快越好。
- 评分越高越好。
- 命中 `prefer_tags` 加分。
- 命中 `avoid_tags` 扣分。
- 超预算扣分。
- 匹配当前 route objective 加分。
- `user_tired` 时低步行、室内加分。
- `weather_change` 或雨天偏好时室内加分，非室内扣分。
- 关闭、不可用、售罄大幅扣分。

### 8.5 重建和重新评分

替换完成后：

1. 已完成 stops 原样保留。
2. 后续 POI 重新按当前时间和当前位置计算 start/end time。
3. 用 `map_provider.get_live_travel_time()` 补交通时间和距离。
4. 重新计算路线总费用、总排队、总交通、总距离、总时长。
5. 复用 `ScoringService` 重新打分。
6. 输出：
   - `changed_stops`
   - `live_warnings`
   - `data_sources`
   - `replan_reason`

注意：局部修改目前主要是“替换后续受影响点”，不是重新生成三条全新路线。

## 9. 预制路线

预制路线入口是 `PredictiveRouteService.generate()`，当前没有正式 API，供 C/A 后续包装成页面初始化或聊天前置推荐接口。

### 9.1 mock 天气

天气数据来自 `data/seed/mock_weather.json`，覆盖上海、北京，每城有：

- `sunny`
- `rainy`
- `hot`
- `cloudy`
- `night`

字段包括：

- `condition`
- `temperature_c`
- `rain_probability`
- `wind_level`
- `comfort_level`
- `suggested_preferences`

天气会转成偏好：

- 雨天、大风：`室内`、`雨天`、`少走路`。
- 高温：`室内`、`少走路`、`咖啡`。
- 晴天、阴天且舒适：`citywalk`、`拍照`、`自然风景`。
- 夜间：`晚上`、`夜景`。

### 9.2 有画像用户

“有画像”定义为：

- 请求显式传入非空 `user_profile`；或
- seed profile 中存在该 `user_id`。

不会把 `ProfileService` 的默认 fallback 画像当成真实画像。

有画像时：

1. 天气偏好 + 画像偏好合成 Intent。
2. 召回 48 个 POI。
3. 用画像偏好调用 `StrategyService.objective_scores()`。
4. 选出前两个非 `balanced` objective。
5. 如果画像只能推出 1 个有效目标，用天气 objective 补。
6. 最终 objectives 固定为：

```text
[profile_objective_1, profile_objective_2, "balanced"]
```

然后每个 objective 生成多条候选，最后做差异筛选，返回最多 3 条。

### 9.3 新用户

“新用户”定义为：

- 没有传入 `user_profile`；并且
- seed profile 中也没有该 `user_id`。

新用户不会强制包含 `balanced`。流程是：

1. 用天气偏好构造 Intent。
2. 对全部 objective 生成候选：

```text
photo_food, food_first, nature_relax, photo_citywalk,
indoor_rainy, night_friendly, low_walking, budget, balanced
```

3. 按路线 `score` 从高到低选 3 条。
4. 选的过程中仍要求 objective 不重复、POI 组合不同、路线差异尽量大。

### 9.4 预制路线差异规则

`PredictiveRouteService` 会用 POI id 集合做差异过滤：

- objective 不能重复。
- POI 组合不能完全相同。
- 两条路线 POI 重合率默认不能超过 50%。
- 如果路线只有 2 个 POI，最多允许重合 1 个。
- 如果不足 3 条，放宽到 70%。
- 最后仍不足，才进一步放宽，但仍不能完全相同。

重合率计算：

```text
overlap / min(len(route_a), len(route_b))
```

### 9.5 预制路线 POI 数

`PredictiveRouteRequest.duration_hours` 默认是 5 小时，目标是默认半日推荐更容易生成 3-4 个点。

预制路线会额外限制：

- 每条最多 4 个 POI。
- `duration_hours <= 3` 时最多 3 个。
- 雨天、室内、少走路、亲子、老人友好时最多 3 个。

这只影响预制路线，不影响普通聊天路线规划。

## 10. 当前实现边界

- POI 召回和路线生成是规则系统，不是全局最优路径算法。
- 普通规划的路线顺序是“按 objective 选点并评分”，不是旅行商问题求解。
- mock 地图会尽量模拟真实地图字段，但距离和线路不是精确导航数据。
- 局部修改以替换受影响后续点为主，不会自动把整条路线彻底重排。
- 预制路线当前是后端服务能力，还没有正式接口。
- 天气、地图、POI 都是 mock，本阶段目标是体验可信和稳定演示。

## 11. 调试建议

常用检查点：

1. 看 `agent_trace.search_pois.details`：确认召回城市、候选数、前几个 POI、策略标签。
2. 看每条 `route.objective`：确认是不是期望的路线目标。
3. 看 `route.score_breakdown`：判断低分来自质量、排队、预算、距离还是偏好。
4. 看每个 `stop.reason` 和 `route_roles`：判断路线结构是否合理。
5. 看 `route_steps_from_previous` 和 `route_leg_source_from_previous`：确认地图路段是否来自 mock_map，交通方式和步骤是否可展示。
6. 局部修改时看 `changed_stops`、`live_warnings`、`replan_reason`。
7. 预制路线时看三条路线的 POI id 重合率，避免只是标题不同。

