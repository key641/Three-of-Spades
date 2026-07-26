# 当前路线规划规则文档

本文档整理当前代码库中已经落地的路线规划规则，覆盖三条链路：

- 主聊天路线规划
- 已生成路线的局部调整 / 动态重规划
- 预制路线生成

本文档按当前 `LYNN` 分支合并 `keyki` 后的代码编写。若历史方案文档和本文不一致，以当前代码为准。

## 1. 核心代码位置

主聊天编排：

- `backend/app/agent/orchestrator.py`
- `backend/app/agent/message_router.py`
- `backend/app/agent/clarification_policy.py`
- `backend/app/agent/intent_enhancer.py`
- `backend/app/agent/intent_context.py`

POI 与路线生成：

- `backend/app/services/poi_service.py`
- `backend/app/services/fine_rank_service.py`
- `backend/app/services/strategy_service.py`
- `backend/app/services/route_service.py`
- `backend/app/services/scoring_service.py`
- `backend/app/services/amap_service.py`
- `backend/app/services/mock_route_map_service.py`

路线调整：

- `backend/app/agent/replan_intent_parser.py`
- `backend/app/services/replan_service.py`

预制路线：

- `backend/app/services/predictive_route_service.py`
- `data/seed/mock_weather.json`

API 入口：

- `POST /api/chat`
- `POST /api/chat/stream`
- `POST /api/routes/plan`
- `POST /api/routes/replan`
- `POST /api/routes/evaluate`

## 2. 主要数据结构

### 2.1 Intent

位置：`backend/app/schemas/intent.py`

当前 `Intent` 字段：

- `city`：城市，默认 `上海`。
- `people_count`：人数，默认 `2`。
- `start_location_name`：起点名称，可为空。
- `start_lat` / `start_lng`：起点坐标，可为空。
- `start_time`：开始时间，默认 `14:00`。
- `duration_hours`：游玩时长，默认 `6`。
- `budget_per_person`：人均预算，默认 `300`。
- `preferences`：兼容字段，最终由兴趣标签、优化目标和未知偏好生成。
- `interest_tags`：体验偏好，例如 `美食`、`咖啡`、`拍照`、`citywalk`、`艺术展`、`自然风景`、`本地感`、`夜景`、`亲子`、`室内`、`安静`。
- `optimization_goals`：优化目标，例如 `少排队`、`省钱`、`少走路`、`高性价比`、`轻松`、`时间紧`。
- `avoid_tags`：避让标签，例如 `人流密集`、`排队久`、`太贵`、`需要预约`、`商业街`、`拍照打卡`、`辣`、`步行多`。
- `scenario`：场景，默认 `friends_citywalk`。
- `need_clarification`：是否需要追问。
- `city_from_message`：城市是否来自用户本轮显式表达。

`Intent.model_post_init()` 会对 `preferences` 做分层归一化：

- 体验类进入 `interest_tags`。
- 优化类进入 `optimization_goals`。
- 避雷类进入 `avoid_tags`。
- `preferences` 被重算为兼容字段。

当前 `Intent` 没有结构化 `target_district` 或 `target_business_area` 字段；区域主要通过 `city`、`start_location_name`、用户消息中的具体地点，以及 POI 搜索文本弱匹配体现。

### 2.2 POI

位置：`backend/app/schemas/poi.py`

POI 关键字段：

- 基础信息：`id`、`name`、`city`、`district`、`address`、`category`。
- 地图信息：`external_place_ids`、`source_provider`、`map_category`、`map_category_code`、`geohash`、`canonical_poi_id`。
- 类目结构：`primary_category`、`secondary_categories`。
- 路线结构：`route_roles`、`experience_tags`。
- 坐标：`lat`、`lng`。
- 价格：`avg_price`、`price_min`、`price_max`。
- 质量：`rating`、`review_count`、`popularity`。
- 人流排队：`crowd_level`、`queue_minutes`、`live_crowd_level`。
- 游玩时间：`visit_duration_minutes`、`open_time`、`close_time`、`last_entry_time`、`open_hours`、`need_booking`、`suitable_time_slots`。
- 标签：`tags`、`negative_tags`、`highlight_text_tags`。
- 适配分：`family_friendly`、`couple_friendly`、`friends_friendly`、`solo_friendly`、`elderly_friendly`、`rainy_day_score`、`budget_friendly`、`photo_friendly`、`food_nearby`、`night_activity`。
- 规划属性：`indoor`、`walking_intensity`、`recommended_transport`、`nearby_poi_ids`、`risk_flags`、`avoid_reasons`、`meal_type`、`transit_hub_nearby`、`parking_available`。
- 展示信息：`cover_image_url`、`highlight_text`、`ugc_tip`。

`POIService` 读取原始 `data/seed/pois.json` 时，会推断和补齐：

- `primary_category`
- `secondary_categories`
- `route_roles`
- `experience_tags`
- `search_text`
- `risk_text`

### 2.3 RouteStop

位置：`backend/app/schemas/route.py`

每个路线 stop 会包含 POI 信息、时间、费用、排队、标签、交通字段和解释字段：

- POI 字段：`poi_id`、`name`、`category`、`primary_category`、`secondary_categories`、`route_roles`、`experience_tags`、`district`、`address`、`lat`、`lng`。
- 时间字段：`start_time`、`end_time`。
- 费用与排队：`estimated_cost`、`queue_minutes`。
- 标签与体验：`tags`、`meal_type`、`open_hours`、`last_entry_time`、`walking_intensity`、`cover_image_url`、`highlight_text`、`ugc_tip`、`indoor`、`recommended_transport`。
- 交通字段：
  - `travel_minutes_from_previous`
  - `distance_km_from_previous`
  - `transport_mode_from_previous`
  - `polyline_from_previous`
  - `amap_distance_meters_from_previous`
  - `amap_duration_minutes_from_previous`
  - `route_leg_source_from_previous`
  - `route_steps_from_previous`
- 解释字段：`reason`

### 2.4 Route

路线字段：

- `route_id`
- `title`
- `objective`
- `summary`
- `total_duration_minutes`
- `total_cost_per_person`
- `total_queue_minutes`
- `total_travel_minutes`
- `total_distance_km`
- `score`
- `score_breakdown`
- `stops`
- `reasons`
- `replan_reason`
- `changed_stops`
- `live_warnings`
- `data_sources`

## 3. 主聊天路线规划

### 3.1 总体流程

入口：`AgentOrchestrator.handle_message()`

流程：

```text
用户消息
-> MessageRouter.classify()
-> ClarificationPolicy.evaluate()
-> 路线追问 / 普通聊天 / 局部重规划分流
-> _parse_intent()
-> enhance_intent_from_message()
-> apply_session_context()
-> ProfileService.merge_request_into_intent()
-> _parse_query_delta()
-> apply_query_delta()
-> _apply_default_city_start()
-> ClarificationPolicy.evaluate()
-> ProfileService 获取并更新用户画像
-> StrategyService.infer_tags()
-> ProfileService.build_strategy_weights()
-> POIService.search()
-> FineRankService.score_map()
-> RouteService.generate_routes()
-> _summarize_route_result()
-> SessionMemory.save_turn_result()
```

### 3.2 消息路由规则

位置：`backend/app/agent/message_router.py`

`MessageRouter` 先尝试 LLM 分类，失败则走规则 fallback。

路由输出：

- `intent_type`
  - `new_plan`
  - `modify_plan`
  - `replan`
  - `route_detail_question`
  - `general_chat`
- `turn_type`
  - `new_plan`
  - `add_constraint`
  - `modify_constraint`
  - `remove_constraint`
  - `route_detail`
  - `general_chat`
- `planning_mode`
  - `new_plan`
  - `full_replan`
  - `partial_replan`
  - `route_detail`
  - `general_chat`

规则 fallback 判断：

- 问交通细节：包含 `怎么过去`、`怎么去`、`两地`、`交通` 等，并引用 `刚刚`、`这条路线`、`两个地点` 等上一轮内容，进入 `route_detail_question`。
- 追加约束：已有上一轮 intent，且包含 `还要`、`也想`、`加一个`、`顺便` 等，同时出现 `吃饭`、`咖啡`、`拍照`、`省钱` 等约束，进入 `modify_plan + full_replan`，并继承上一轮。
- 局部重规划：已有上一轮 intent，且包含 `换一家`、`第二站`、`排队90分钟`、`下雨`、`堵车`、`关门`、`太累` 等，进入 `replan + partial_replan`。
- 模糊重规划：例如 `换个便宜点的`，可能是整条重规划也可能局部替换，会输出候选模式，低置信度时触发追问。
- 全量重规划：例如 `重新生成路线`、`更省钱`、`少排队`、`少走路`、`整体不满意`，进入 `modify_plan + full_replan`。
- 普通路线相关：已有上一轮则当作修改；没有上一轮则当作新规划。
- 其他内容进入普通聊天。

### 3.3 追问规则

位置：`backend/app/agent/clarification_policy.py`

当前追问策略：

- 每个 session 最多追问 1 轮。
- 单轮最多合并 3 个问题。
- 低置信度且存在多个候选规划模式时，优先问用户是全量重规划还是局部替换。
- 对需要路线生成的消息，判断是否缺地点。
- 新规划过于泛化时，追问目标：景点、美食、轻松 citywalk。

地点信息被视为足够的条件：

- 消息里包含具体地点，例如区、县、新区、路、街、巷、弄、大道、步行街、老街等。
- 请求里有具体 `start_location_name`。
- LLM 解析出的城市字段本身是具体地点。
- 修改 / 重规划场景能继承上一轮地点。

地点追问文案：

- 有 GPS 和城市：`你想在哪个区域逛？`
- 有 GPS 但无城市：`你想在附近逛，还是去某个特定区域？`
- 无城市：`你想在哪个城市逛？`
- 只有城市：`你想在哪个区域逛？`

### 3.4 Intent 解析和上下文继承

Intent 解析：

- 首选 LLM 解析，prompt 位于 `AgentOrchestrator._llm_parse_intent()`。
- LLM 失败走 `_mock_parse_intent()`。
- 随后调用 `enhance_intent_from_message()` 用规则补强城市、人数、时间、时长、预算、偏好、避雷等。

多轮继承：

- `apply_session_context()` 判断用户是否是调整上一轮。
- 当消息包含 `预算低`、`便宜`、`省钱`、`少排队`、`换一家`、`换成`、`再`、`继续` 等，或路由标记 `inherit_previous=true` 时，会继承上一轮。
- 继承时保留上一轮城市、时长、预算、场景等，再合并本轮显式字段。
- 如果本轮显式说了城市，`city_from_message=true`，会覆盖上一轮城市。

状态 delta：

- `_parse_query_delta()` 尝试让 LLM 输出本轮对 `TripState` 的增量。
- LLM 失败时使用 `_build_intent_delta()` 规则兜底。
- 支持硬约束变更：`city`、`people_count`、`start_time`、`duration_hours`、`budget_per_person`、`scenario`。
- 支持新增/移除偏好、避让项、隐式需求和必须包含项。
- 相对预算表达会被保护：如果用户说“预算低一点”但没有明确金额，不把它解析成新的 `budget_per_person`，而是加 `省钱` 偏好。

### 3.5 默认起点

如果用户没有起点坐标，且城市是上海或北京，会设置默认起点：

- 上海：`静安寺站`，`31.2231, 121.4466`
- 北京：`西单站`，`39.9072, 116.3740`

`RouteService.generate_routes()` 内部也会在没有起点坐标时设置城市中心：

- 上海：`31.2304, 121.4737`
- 北京：`39.9042, 116.4074`

通常主聊天链路会先使用 Orchestrator 的默认站点。

## 4. POI 召回规则

入口：`POIService.search(intent, user_profile, limit=60, strategy_tags=None, relax_preferences=False)`

### 4.1 数据来源

当前 POI 从 `data/seed/pois.json` 加载。

当前实现只使用目标城市本地种子数据。城市本身没有 POI 数据时，`POIService.search()` 返回空列表，不再从上海或其他城市克隆 fallback POI。

主聊天链路会在城市无数据时直接中止规划并提示：

```text
当前城市暂无可用 POI 数据，可以先选择北京或上海的路线。
```

### 4.2 搜索文本和风险文本

`POIService` 为每个 POI 生成：

- `search_text`：名称、区、地址、类目、主类目、亮点、UGC、餐型、步行强度、辅助类目、路线角色、体验标签、推荐时段、推荐交通、标签等。
- `risk_text`：负面标签、风险标记、避让原因等。

偏好匹配和避让匹配都通过别名映射对这些文本做包含判断。

### 4.3 过滤顺序

POI 搜索流程：

1. 按城市过滤。
2. 城市无数据则返回空，不跨城兜底。
3. 首轮召回默认 `limit=60`，严格匹配：
   - 命中 `intent.interest_tags`。
   - 不命中 `intent.avoid_tags`。
   - 不是极端预算不匹配。
4. 如果候选不足，上层 Orchestrator 会按 `90 -> 120` 扩召回，并传入 `relax_preferences=True` 放宽偏好 strict match。
5. 放宽召回只放宽偏好匹配，不放宽城市过滤、避让标签和极端预算过滤：
   - 不命中避让标签。
   - 不是极端预算不匹配。
6. 通过多路召回和 `CoarseRankService` 粗排，返回前 `limit` 个 POI。

预算极端不匹配阈值：

```text
poi.avg_price <= max(intent.budget_per_person * 2, intent.budget_per_person + 160)
```

### 4.4 POI 排序维度

`POIService._rank_score()` 融合：

- 质量：评分、热度、评论量。
- 排队：排队越短、人流越低越好。
- 距离：有起点坐标时离起点越近越好。
- 预算：越贴近预算越好；预算内会参考 `budget_friendly`。
- 偏好：用户本轮兴趣标签命中。
- 画像：用户历史偏好、类目、路线角色、体验标签、时段、交通偏好。
- 场景：`friends_citywalk` 偏朋友、拍照、citywalk、夜景、咖啡。
- 时间：营业时间、最晚入场、推荐时段。
- 策略标签：`StrategyService.tag_score()`。
- liked / disliked POI 与 skipped category。

优化目标加分：

- `少排队`：提高 queue_score。
- `省钱`：提高 budget_score。
- `高性价比`：预算 + 质量。
- `美食` / `咖啡` / `轻食` / `小吃`：提高餐饮匹配。
- `citywalk`：提高街区、拍照、地标匹配。
- `室内` / `雨天`：提高室内或雨天友好。
- `少走路` / `轻松`：提高低步行强度。

### 4.5 POI 多样性

当 `limit >= 12` 时，`_diversify_ranked_candidates()` 会控制单个 `category` 数量：

```text
category_cap = max(4, min(10, limit // 3))
```

被跳过的高分 POI 会在后续回填，避免因多样性导致候选不足。

当前该多样性是召回结果层面的软约束，不等于最终路线内部类目硬约束。

## 5. 策略标签和路线目标

入口：`StrategyService.infer_tags()`、`StrategyService.objective_scores()`

### 5.1 策略标签

当前规则标签：

- `photo`
- `photo_food`
- `food_first`
- `nature`
- `quiet`
- `low_walking`
- `budget`
- `indoor_rainy`
- `night_view`
- `local_vibe`
- `family`
- `elderly`
- `low_queue`
- `cafe`
- `art_exhibition`

每个标签包含：

- aliases：触发词。
- multipliers：对评分权重的乘法调整。
- objectives：对路线目标的偏好分。

例如：

- `photo`：提高 `preference` 和 `quality`，推动 `photo_citywalk`。
- `food_first`：提高 `preference` 和 `quality`，推动 `food_first`。
- `low_walking`：提高 `distance` 和 `queue`，推动 `low_walking`。
- `budget`：提高 `budget`，轻微降低 `quality`，推动 `budget`。
- `indoor_rainy`：提高 `preference` 和 `distance`，推动 `indoor_rainy`。

### 5.2 路线目标

当前 `RouteService.OBJECTIVE_TITLES` 支持：

| objective | 标题 | 主要含义 |
| --- | --- | --- |
| `balanced` | 综合候选路线 | 综合平衡 |
| `budget` | 省钱候选路线 | 控制人均 |
| `low_walking` | 少走路候选路线 | 距离短、步行低 |
| `food_first` | 吃好优先候选路线 | 餐饮优先 |
| `photo_food` | 拍照餐饮候选路线 | 餐饮 + 拍照 |
| `nature_relax` | 自然风景候选路线 | 公园、自然、低强度 |
| `photo_citywalk` | 拍照 Citywalk 候选路线 | 街区、地标、拍照 |
| `indoor_rainy` | 室内雨天候选路线 | 室内、雨天友好 |
| `night_friendly` | 夜间友好候选路线 | 夜景、晚间活动 |

目标选择规则：

- 如果没有用户偏好和画像，默认目标为：
  - `photo_citywalk`
  - `food_first`
  - `balanced`
- 如果有偏好：
  - 先用 `StrategyService.objective_scores()` 打分。
  - 取分数最高的非 `balanced` 目标前 2 个。
  - 加入 `balanced`。
  - 不足 3 个时，用 `food_first`、`photo_citywalk`、`nature_relax`、`indoor_rainy`、`low_walking`、`budget`、`night_friendly` 兜底。

普通主聊天路线默认每个 objective 只返回 1 条最佳路线，因此通常输出 3 条路线。

## 6. 路线生成规则

入口：`RouteService.generate_routes()`

### 6.1 总体流程

```text
candidate_pois
-> 补默认城市中心坐标（上海/北京）
-> 选择 objectives
-> 对每个 objective 构建候选
-> ScoringService 打分
-> 每个 objective 选最高分路线
-> finalize route 标题、summary、reasons
-> 返回 RoutePlanResponse
```

### 6.2 stop 数量规则

`_stop_bounds()` 根据时长计算：

| 时长 | min_stops | max_stops |
| --- | ---: | ---: |
| `<= 3h` | 3；简单路线为 2 | 3 |
| `<= 6h` | 3 | 4 |
| `> 6h` | 4 | 5 |

偏好调整：

- 如果有 `轻松`、`少走路`、`老人`、`亲子`，降低 `max_stops` 1 个，但不低于 `min_stops`。
- 如果有 `多打卡`、`citywalk`、`拍照`，`max_stops` 最多提高到 5。

当前代码已删除 `min_stops=1` fallback。默认最终路线每条至少 3 个 POI；只有用户明确表达“简单点、别太复杂、少安排、不要太满、轻松少安排”等简单路线意图时，最低可放宽到 2 个 POI。初始主路线不允许返回 1 个 POI。

### 6.3 候选生成

对每个 objective：

1. `time_limit = max(60, duration_hours * 60)`。
2. 根据 `_stop_bounds()` 得到 `min_stops` 和 `max_stops`。
3. `_start_candidates()` 按 `_poi_score()` 对全部候选 POI 排序。
4. `_diverse_start_seeds()` 扩大 seed 覆盖，当前 `INTERNAL_CANDIDATES_PER_OBJECTIVE = 16`。
5. 每个 seed 调 `_build_candidate()` 贪心扩展路线。
6. 如果生成路线数不足 16，会继续用后续 seed 尝试，但不再降低到 `min_stops=1`。
7. 对候选调用 `ScoringService` 打分并排序。
8. 主聊天收集多 objective、多候选后进入最终强筛选；只有筛满 3 条才返回。

### 6.4 单条路线扩展规则

`_build_candidate()`：

1. 从 seed POI 开始。
2. 每次调用 `_next_poi()` 选择下一个 POI。
3. 不允许同一条路线内重复 `poi.id`。
4. 用 `_append_if_feasible()` 判断时间是否可行。
5. 若目标或用户意图需要餐饮，且路线中没有餐饮节点，尝试 `_food_replacement()` 追加一个餐饮 POI。

时间可行性：

```text
travel_minutes + poi.queue_minutes + poi.visit_duration_minutes
```

如果加入该 POI 后超过总时长，则跳过。

早停条件：

```text
len(stops) >= min_stops 且 elapsed_minutes >= time_limit * 0.82
```

### 6.5 下一个 POI 选择

`_next_poi()`：

候选条件：

- 未被当前路线选过。
- 通过餐饮组合规则。
- 加入后不超时。

如果当前 objective 或用户需求要求餐饮，且当前路线还没有餐饮节点，会优先在食物类 POI 中选。

最终用以下分数取最大：

```text
_poi_score()
+ nearby_bonus
- distance_penalty
- diversity_penalty
+ missing_role_bonus
+ must_extend_bonus
```

其中：

- `nearby_bonus`：命中彼此 `nearby_poi_ids` 加分。
- `distance_penalty`：距离越远扣分。
- `diversity_penalty`：咖啡/正餐重复、连续主类目重复、路线角色重复等扣分。
- `missing_role_bonus`：缺主活动、餐饮、拍照、休息、交通锚点等角色时加分。
- `must_extend_bonus`：当前还没达到 `min_stops` 时加一点分。

### 6.6 POI 分数

`_poi_score()` 基础分：

```text
quality * 0.22
+ queue * 0.14
+ budget * 0.12
+ preference * 0.18
+ time_fit * 0.14
+ distance * 0.12
+ walking * 0.08
```

objective 加成：

- `budget`：预算友好额外加权。
- `low_walking`：距离、步行、交通锚点加权。
- `food_first`：餐饮分加权。
- `photo_food`：拍照餐饮 + 餐饮加权。
- `nature_relax`：自然分 + 低步行加权。
- `photo_citywalk`：拍照 citywalk 分加权。
- `indoor_rainy`：室内 + 雨天友好加权。
- `night_friendly`：夜间活跃度 + 晚间时段加权。

### 6.7 餐饮组合规则

当前会识别三类 meal group：

- `coffee`
- `meal`
- `snack`

规则：

- 默认不鼓励同一条路线出现多个咖啡节点。
- 默认不鼓励同一条路线出现多个正餐节点。
- 默认不允许咖啡和正餐混排，除非用户同时表达想要咖啡和正餐。
- 用户明确 `咖啡探店`、`咖啡路线`、`多家咖啡`、`咖啡馆` 时允许重复咖啡。
- 用户明确 `美食路线`、`扫街`、`吃很多家`、`小吃街`、`多家餐厅` 时允许重复正餐。

### 6.8 路线交通规则

每个 stop 都会尝试生成从上一位置到当前 POI 的交通信息。

交通来源：

- `AmapService.route_leg()`
- 如果配置为 mock 或没有高德 key，会走 `MockRouteMapService`

候选交通模式：

- 距离 `<= 0.8km` 且用户没有少走路偏好：`walk`、`metro`、`bus`、`taxi`。
- 距离 `> 8km`：`metro`、`bus`、`taxi`。
- 其他距离：`metro`、`bus`、`taxi`、`walk`。
- POI 的 `recommended_transport` 会插入候选模式。

交通选择：

- 优先考虑公共交通，即 `metro` 或 `bus`。
- 若公共交通比打车慢不超过一定阈值，则选择公共交通：
  - 普通：公共交通耗时 `<= taxi + 30min` 或 `<= taxi * 3.0`。
  - 少走路：公共交通耗时 `<= taxi + 20min` 或 `<= taxi * 2.5`。
- 打车会有额外 score penalty。
- 长距离不优先纯步行。
- 少走路场景下，大于 1km 的步行会强烈扣分。

输出字段：

- `transport_mode_from_previous`
- `travel_minutes_from_previous`
- `distance_km_from_previous`
- `polyline_from_previous`
- `route_steps_from_previous`
- `route_leg_source_from_previous`

### 6.9 路线评分

位置：`ScoringService`

五维评分：

- `quality`
- `queue`
- `budget`
- `distance`
- `preference`

每个 objective 有不同权重：

| objective | 质量 | 排队 | 距离 | 预算 | 偏好 |
| --- | ---: | ---: | ---: | ---: | ---: |
| balanced | 0.30 | 0.25 | 0.20 | 0.15 | 0.10 |
| budget | 0.20 | 0.15 | 0.10 | 0.45 | 0.10 |
| low_walking | 0.15 | 0.20 | 0.45 | 0.10 | 0.10 |
| food_first | 0.30 | 0.15 | 0.10 | 0.10 | 0.35 |
| photo_food | 0.30 | 0.12 | 0.10 | 0.08 | 0.40 |
| nature_relax | 0.22 | 0.14 | 0.24 | 0.10 | 0.30 |
| photo_citywalk | 0.20 | 0.15 | 0.20 | 0.10 | 0.35 |
| indoor_rainy | 0.15 | 0.15 | 0.20 | 0.10 | 0.40 |
| night_friendly | 0.25 | 0.15 | 0.15 | 0.10 | 0.35 |

硬惩罚：

- 总时长超出用户时长。
- 总费用超预算。
- 到达时 POI 不营业或超过最晚入场。
- 命中 avoid_tags。
- objective 必备结构缺失，例如：
  - `food_first` 没有餐饮。
  - `photo_food` 没有拍照餐饮。
  - `nature_relax` 没有自然点。
  - `indoor_rainy` 没有室内点。
- 路线结构不合理，例如没有主活动、咖啡过多、正餐过多、连续同主类目、连续同角色。
- 常识惩罚，例如：
  - 晚上安排咖啡且用户没有明确咖啡需求。
  - 下午安排正餐且用户没有明确想吃。
  - 雨天/高温还安排高强度户外。
  - 亲子/老人/轻松/少走路场景安排高步行强度。
  - 连续两个高步行强度 stop。

最终分：

```text
overall_score = weighted_score - hard_penalty
```

分数裁剪到 `0-100`。

### 6.10 路线输出解释

`RouteService._finalize_route()` 会补：

- `route_id`
  - 第一条：`route_{objective}_best`
  - 其他候选：`route_{objective}_candidate_{index}`
- `title`
- `summary`
- `reasons`

`summary` 包含：

- objective 文案
- 综合评分
- stop 数
- 人均费用
- 排队时间
- 路上时间
- 该路线优势

`reasons` 最多取 4 条，包括：

- objective 胜出
- 五维中最强维度
- 包含餐饮或休息节点
- 包含室内点位
- 排队压力较低
- 预算可控
- 点位相对集中

## 7. 当前主路线规划的强约束

这些是当前代码真实状态：

1. 城市无数据时直接提示“当前城市暂无可用 POI 数据，可以先选择北京或上海的路线”，不跨城克隆 POI。
2. 主聊天首轮召回 60 个 POI；如果筛不满 3 条合规路线，按 90、120 扩召回并放宽偏好 strict match。
3. 放宽召回不放宽城市过滤、避让标签、极端预算过滤、跨路线去重和交通完整性。
4. `RouteService.generate_routes()` 会扩展 objective 覆盖，并为每个 objective 生成多条内部候选。
5. 最终选择层默认必须选满 3 条路线；每条初始路线之间 POI ID 零重叠。
6. 默认每条路线至少 3 个 POI；明确简单路线意图时可降到 2 个 POI；不允许 1 个 POI 路线。
7. 最终入选路线的每个 stop 必须具备交通方式、耗时、距离、polyline 和可读 steps。
8. 最终选择会按 objective 优先级先保留用户意图相关路线，再用剩余高分候选补齐 3 条。
9. 中长距离交通优先选择 `metro` / `bus`，短距离可步行；高德不可用时使用 `mock_map` 生成可读交通步骤。
10. 目前没有结构化 `target_district` / `target_business_area` 硬过滤字段。
11. `RouteRerankService` 当前存在独立实现，但主聊天 `RouteService.generate_routes()` 没有调用它。
12. `FineRankService.score_map()` 在主聊天中会生成 POI 相关分，但当前 `RouteService._poi_score()` 没有直接读取 `poi_relevance_scores`，路线候选生成主要仍是规则分。

## 8. 路线调整 / 局部重规划

### 8.1 两类入口

自然语言局部调整：

```text
用户消息
-> MessageRouter 判断 partial_replan
-> ReplanIntentParser.parse()
-> AgentOrchestrator._handle_partial_replan()
-> ReplanService.replan()
```

结构化事件调整：

```text
POST /api/chat
event_type in {"replace_poi", "avoid_poi", "queue_spike", "traffic_jam", "user_tired", "weather_change"}
且 session_state.current_routes 存在
-> AgentOrchestrator._handle_structured_replan()
-> ReplanService.replan()
```

或者直接：

```text
POST /api/routes/replan
-> ReplanService.replan()
```

### 8.2 自然语言事件解析

位置：`ReplanIntentParser`

支持事件：

- `queue_spike`
  - 触发：`排队 X 分钟`
  - payload：`queue_minutes`、`avoid_tags=["排队久"]`、`prefer_tags=["少排队"]`
  - 如果目标是餐饮 stop，会带 `replacement_category`
- `weather_change`
  - 触发：`下雨`、`雨天`、`暴雨`
  - payload：`prefer_tags=["室内"]`、`avoid_tags=["步行多"]`
- `traffic_jam`
  - 触发：`堵车`、`交通堵`、`路上堵`、`临时堵`
  - payload：`traffic_multiplier=1.6`
- `poi_closed`
  - 触发：`关门`、`闭店`、`临时关闭`、`不开门`
  - payload：`status="closed"`、`force_replace=True`
- `user_tired`
  - 触发：`太累`、`累了`、`走不动`、`少走`
  - payload：`prefer_tags=["少走路","室内休息"]`、`avoid_tags=["步行多"]`
- `replace_poi`
  - 触发：`换一家`、`换个店`、`换一个`、`换掉`、`替换`、`不喜欢这家`、`不想去`
  - 如果包含 `太贵`、`贵了`、`预算`，加 `avoid_tags=["太贵"]`、`prefer_tags=["更省钱"]`

目标 route：

- 如果消息里包含 `route_id`，使用对应路线。
- 否则默认当前 routes 的第一条。

目标 stop：

- 如果消息里包含 `第X站`，按站序匹配。
- 如果消息里包含 stop 名称，直接匹配。
- 如果消息像是在说 `这家`、`店`、`餐厅`、`咖啡`、`吃`，优先选择路线中的食物 stop。
- 否则默认第一站。

### 8.3 ReplanService 总体规则

入口：`ReplanService.replan(request)`

流程：

1. 如果 `current_routes` 为空，返回空。
2. 只调整 `selected_route_id` 对应路线；其他路线原样保留。
3. 对目标路线 deep copy。
4. 区分：
   - `completed_stops`：已经完成的 POI。
   - `future_stops`：后续未完成 POI。
5. 已完成 stop 固定保留，不重建。
6. 对未来 stop 获取实时状态。
7. 判断是否需要替换。
8. 如需替换，从本地同城候选或外部 mock map provider 找替代。
9. 用替换后的 POI 重建未来 stop 时间线。
10. 刷新路线总费用、排队、交通、距离、时长和评分。
11. 生成 `changed_stops`、`live_warnings`、`data_sources`、`replan_reason`、`summary`。

### 8.4 什么情况下替换 POI

`_should_replace()` 会判断：

强制替换：

- 实时状态是 `closed`、`unavailable`、`sold_out`。
- `is_open=false`。
- `is_accessible=false`。

事件替换：

- `replace_poi`：目标 stop 被命中且 `force_replace` 或受影响。
- `avoid_poi`：目标 stop 被命中，或匹配 avoid_tags。
- `preference_change`：目标 stop 被命中，匹配 avoid_tags，或偏好变成少走路/室内而当前 stop 不符合。
- `queue_spike`：排队时间大于等于 `QUEUE_REPLACE_THRESHOLD = 45`。
- `user_tired`：当前 stop 步行强度为 `high`。
- `weather_change`：当前 stop 非室内。

保护规则：

- `completed_poi_ids` 不替换。
- `locked_poi_ids` 默认不替换，除非 closed/unavailable/sold_out。
- `preserve_poi_ids` 默认不替换，除非 closed/unavailable/sold_out。
- `warning_only=true` 时只提示，不替换。

### 8.5 替代 POI 选择

候选来源：

1. 本地同城 POI：`POIService.all_pois(city=route_city)`。
2. 如果本地没有可用候选，调用 `map_provider.search_nearby_pois()` 生成外部候选。

本地候选过滤：

- 不在已选、已完成、锁定、保留、不可用集合内。
- 不命中 `event_payload.avoid_tags`。
- 匹配 `replacement_category`，如果指定了替换类目。
- 与原 POI 在 route_roles、primary_category 或 meal_type 上有一定重合。
- 实时状态不是 closed/unavailable/sold_out。

替代评分：

```text
role/category/meal 相似度 * 3
+ 排队短 * 2
+ 交通近 * 1.5
+ rating 加分
+ prefer_tags 命中 * 1.8
- avoid_tags 命中 * 3.0
- 超预算惩罚 * 1.2
+ objective_bonus * 0.8
+ 事件特殊加分/扣分
- 关闭/不可用重罚
```

事件特殊加分：

- `user_tired`：低步行、室内加分。
- `weather_change` 或偏好含 `室内/雨天/下雨`：室内加分，非室内扣分。
- `少排队`：排队小于等于 15 分钟加分。
- `少走路/轻松`：低步行加分。
- `美食/吃好/咖啡`：餐饮节点加分。

### 8.6 重建时间线

未来 stop 会按替换后的 POI 重新计算：

- 起点来自当前坐标、当前 POI、已完成最后一个 stop，或第一个未来 POI。
- 每段交通来自 `map_provider.get_live_travel_time()`。
- 新 start/end：

```text
start = current_minutes + leg.travel_minutes
end = start + poi.queue_minutes + poi.visit_duration_minutes
```

刷新路线指标：

- `total_cost_per_person`
- `total_queue_minutes`
- `total_travel_minutes`
- `total_distance_km`
- `total_duration_minutes`
- `score_breakdown`
- `score`

若事件是 `traffic_jam`，`total_travel_minutes` 至少不低于原路线，避免“堵车后反而变短”的展示问题。

### 8.7 调整结果解释

返回字段：

- `route.changed_stops`：替换列表。
- `route.live_warnings`：实时提醒。
- `route.data_sources`：数据来源，例如 `local`、`mock_map`。
- `route.replan_reason`：本次调整原因。
- `route.summary`：调整后路线摘要。

Orchestrator 给用户的消息：

- 如果有替换：说明原点位换成新点位。
- 如果没有替换但有 warning：说明已复核路线。
- 如果没有可调整路线：提示需要先生成路线。

## 9. 路线详情追问

入口：`RouteDetailHandler`

当用户问“刚刚这条路线两个地点之间怎么去”等问题时：

- 读取 session 中的 `current_routes[0]`。
- 遍历连续 stops。
- 从每个 stop 的交通字段生成用户可读说明：
  - 交通方式
  - 耗时
  - 距离
  - 分段 steps

如果当前路线没有足够连续地点，则提示无法说明两点之间怎么过去。

## 10. 预制路线生成

入口：`PredictiveRouteService.generate()`

当前预制路线不直接挂在 FastAPI router 上，主要由服务和测试调用。请求结构是 `PredictiveRouteRequest`。

### 10.1 请求字段

`PredictiveRouteRequest`：

- `user_id`：默认 `user_demo`。
- `city`：默认 `上海`。
- `weather_scenario`：天气场景，可为空。
- `start_time`：默认 `10:00`。
- `duration_hours`：默认 `5`。
- `start_lat` / `start_lng`：可选起点坐标。
- `user_profile`：可选用户画像。

### 10.2 天气数据

预制路线读取：

```text
data/seed/mock_weather.json
```

`weather_for(city, scenario)`：

- 优先取指定城市。
- 城市无天气数据时 fallback 到上海。
- 如果指定 `scenario` 存在，取该 scenario。
- 否则取 `sunny`。
- 如果没有 sunny，取城市天气里的第一个。

### 10.3 天气转偏好

`preferences_from_weather()`：

- 先读取天气配置里的 `suggested_preferences`。
- 如果降雨概率 `>= 0.55`，或 condition 包含 `rain`，或风力 `>= 5`：
  - 加 `室内`
  - 加 `雨天`
  - 加 `少走路`
- 如果温度 `>= 32`：
  - 加 `室内`
  - 加 `少走路`
  - 加 `咖啡`
- 如果晴天/多云、降雨概率 `< 0.35`、温度 `< 32`：
  - 加 `citywalk`
  - 加 `拍照`
  - 加 `自然风景`
- 如果 condition 包含 `night`：
  - 加 `晚上`
  - 加 `夜景`

最终去重。

### 10.4 画像选择

`_profile_for_request()`：

- 如果请求传入 `user_profile` 且包含 tags/preferences/preference_weights，使用它。
- 否则从 seed profile 读取 `user_id` 对应画像。
- 如果没有画像，走无画像逻辑。

规划 profile：

- 有画像：使用画像。
- 无画像：创建默认 `UserProfile`，使用默认权重。

### 10.5 Intent 构造

`_intent_for_request()` 会合并：

- 天气偏好。
- 用户画像偏好、标签、兴趣、优化目标。
- 用户画像避让项。
- 请求城市、开始时间、时长、起点坐标。
- 默认预算 `300`。
- 默认场景 `friends_citywalk`。

### 10.6 预制路线目标选择

如果有用户画像：

1. 根据画像偏好生成 profile intent。
2. 用 `StrategyService.infer_tags()` 和 `objective_scores()` 计算目标分。
3. 取前 2 个非 `balanced` objective。
4. 不足时用天气目标补充。
5. 仍不足时用 fallback 目标补充。
6. 最后加 `balanced`。

天气目标映射：

- `室内` / `雨天` -> `indoor_rainy`
- `少走路` / `亲子友好` / `老人友好` -> `low_walking`
- `citywalk` / `拍照` -> `photo_citywalk`
- `自然风景` -> `nature_relax`
- `晚上` / `夜景` -> `night_friendly`
- `吃好` / `咖啡` -> `food_first`

如果没有画像：

- 使用所有目标：
  - `photo_food`
  - `food_first`
  - `nature_relax`
  - `photo_citywalk`
  - `indoor_rainy`
  - `night_friendly`
  - `low_walking`
  - `budget`
  - `balanced`

### 10.7 预制路线生成参数

预制路线召回：

```text
POIService.search(limit=60)
不足 3 条合规路线时按 90、120 扩召回
```

每个 objective 生成：

```text
routes_per_objective = RouteService.INTERNAL_CANDIDATES_PER_OBJECTIVE
enforce_constraints = True
```

最大 stop：

- 如果时长 `<= 3h`，或偏好包含 `少走路`、`亲子友好`、`老人友好`、`室内`，或降雨概率 `>= 0.55`：
  - `max_stops = 3`
- 否则：
  - `max_stops = 4`

### 10.8 预制路线最终选择

预制路线现在复用 `RouteService` 的强筛选：

- 最终默认必须 3 条路线。
- 初始路线之间 POI 零重叠。
- 默认每条至少 3 个 POI；简单路线最低 2 个 POI。
- 每个 stop 必须有交通字段和可读 steps。
- 城市无数据时返回空路线列表，不跨城克隆。
- 120 扩召回后仍不足 3 条时返回空路线列表，不返回半成品。

## 11. 路线评价

入口：`RouteEvaluationService.evaluate()`

用途：

- 不重新规划。
- 不重新选 POI。
- 只基于已经生成的路线做点评和解释。

流程：

- 优先调用 LLM。
- LLM 失败时 fallback。

LLM 输出：

- `route_id`
- `score`
- `summary`
- `highlights`
- `risks`
- `recommendation`
- `source="llm"`

Fallback 风险：

- `total_queue_minutes >= 45`：排队时间偏长。
- `total_cost_per_person >= 350`：预算压力较高。
- `total_distance_km >= 8`：路程跨度较大。

## 12. 当前需要特别注意的行为边界

以下是当前实现里可能影响产品效果的边界：

1. 候选不足时不会返回少于 3 条或不合规路线；城市有数据但 120 扩召回后仍不足，会返回明确失败说明。
2. 城市完全无 POI 数据时是唯一不保证 3 条路线的场景；系统会提示用户选择北京或上海。
3. 初始主路线之间 POI 必须零重叠；局部重规划 / 替换某一家 POI 不套用这条跨路线零重叠规则。
4. 默认每条路线至少 3 个 POI；简单路线最低 2 个 POI；不允许 1 个 POI。
5. 区/商圈目前不是结构化硬过滤字段。
6. 路线内部类目多样性主要靠候选惩罚、角色补位和多 objective 组合，不是独立的最终硬校验。
7. `RouteRerankService` 当前没有接入主聊天路线生成链路。
8. `FineRankService` 当前主要输出 relevance map 和 trace details，主路线候选生成的 POI 选择仍主要依赖 `RouteService._poi_score()` 规则。
9. 预制路线已复用强筛选；不足 3 条时同样按 90/120 扩召回，仍不足则返回空路线列表。
10. 局部重规划允许使用外部 mock map provider 补候选，可能产生 `external_...` POI。

## 13. 建议前端展示优先级

路线卡片：

- `title`
- `summary`
- `score`
- `score_breakdown`
- `total_duration_minutes`
- `total_cost_per_person`
- `total_queue_minutes`
- `total_travel_minutes`
- `total_distance_km`
- `reasons`

路线时间线 stop：

- `name`
- `category` / `primary_category`
- `start_time` / `end_time`
- `estimated_cost`
- `queue_minutes`
- `highlight_text`
- `ugc_tip`
- `reason`
- `walking_intensity`
- `indoor`
- `tags`

交通展示：

- `transport_mode_from_previous`
- `travel_minutes_from_previous`
- `distance_km_from_previous`
- `route_steps_from_previous`

局部调整展示：

- `replan_reason`
- `changed_stops`
- `live_warnings`
- `data_sources`
