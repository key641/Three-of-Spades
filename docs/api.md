# Drifto 前后端接口文档

## 基本信息

| 项目 | 说明 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 前端框架 | React + TypeScript |
| Base URL | `VITE_API_BASE_URL`（默认 `http://localhost:8000`） |
| Content-Type | `application/json` |
| 健康检查 | `GET /health` → `{ "status": "ok" }` |

---

## 1. 对话接口

### 1.1 普通对话（同步）

```
POST /api/chat
```

#### 请求体 `ChatRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | 否 | 会话 ID，前端自动生成并存 localStorage（格式 `session_{ts}_{random}`）；默认 `"session_demo"` |
| `user_id` | string | 否 | 用户 ID，来自 `OnboardingProfile.user_id`；默认 `"user_demo"` |
| `message` | string | **是** | 用户输入的自然语言消息 |
| `event_type` | string | 否 | 固定为 `"user_message"` |
| `city` | string | 否 | 来自本次出行约束 `trip.city` |
| `scenarios` | string[] | 否 | 出行场景标签数组，来自用户画像 |
| `scenario` | string | 否 | 兼容字段，取 `scenarios[0]` |
| `preferences` | string[] | 否 | 偏好标签，如 `["少排队", "吃好"]` |
| `avoid_tags` | string[] | 否 | 避开标签，如 `["人多", "商业街"]` |
| `budget_level` | string | 否 | 预算档位：`"low"` / `"mid"` / `"high"` / `"flex"` |
| `preference_weights` | object | 否 | 策略权重（见附录 StrategyWeights） |
| `trip_city` | string | 否 | 本次出行城市（来自 `TripConstraints`，每次请求都带） |
| `trip_people` | number | 否 | 本次出行人数 |
| `trip_duration_hours` | number | 否 | 本次出行时长（小时） |
| `trip_budget_per_person` | number \| null | 否 | 本次人均预算（元），`null` 表示不限 |

> **说明**：画像字段（`city` / `scenarios` / `preferences` / `avoid_tags` / `budget_level` / `preference_weights`）通常只在会话**首轮**发送，后续由后端 session memory 接管。`trip_*` 出行约束字段**每次请求都发送**。

#### 请求示例

```json
{
  "session_id": "session_1748700000_abc123",
  "user_id": "user_1748700000",
  "message": "上海半天 citywalk，2人，预算200",
  "event_type": "user_message",
  "city": "上海",
  "scenarios": ["朋友出游", "citywalk"],
  "scenario": "朋友出游",
  "preferences": ["少排队", "吃好", "性价比"],
  "avoid_tags": ["人多", "商业街"],
  "budget_level": "mid",
  "preference_weights": {
    "quality": 0.28,
    "queue": 0.35,
    "distance": 0.2,
    "budget": 0.15,
    "preference": 0.1
  },
  "trip_city": "上海",
  "trip_people": 2,
  "trip_duration_hours": 4,
  "trip_budget_per_person": 200
}
```

#### 响应体 `ChatResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 服务端分配/确认的会话 ID |
| `message` | string | AI 回复文本，直接渲染到聊天气泡 |
| `need_clarification` | boolean | 是否需要追问用户补充信息 |
| `clarifying_question` | string \| null | 追问问题内容（`need_clarification=true` 时有值） |
| `intent` | Intent \| null | 解析出的出行意图（见附录 Intent 结构） |
| `user_profile` | UserProfile \| null | 后端记录的用户画像快照 |
| `routes` | Route[] | 规划路线数组，通常 0–3 条 |
| `agent_trace` | AgentTraceStep[] | Agent 推理链路步骤，供前端"思考过程"面板展示 |

#### 响应示例

```json
{
  "session_id": "session_1748700000_abc123",
  "message": "好的！根据你的需求，我为你规划了3条路线，可以左右滑动查看。",
  "need_clarification": false,
  "clarifying_question": null,
  "intent": {
    "city": "上海",
    "people_count": 2,
    "duration_hours": 4,
    "budget_per_person": 200,
    "scenario": "friends_citywalk"
  },
  "user_profile": {
    "user_id": "user_1748700000",
    "preferences": ["少排队", "吃好"],
    "avoid_tags": ["人多"]
  },
  "routes": [ ... ],
  "agent_trace": [
    { "step": "parse_intent", "label": "解析出行意图", "status": "done", "details": {} },
    { "step": "search_pois",  "label": "召回候选 POI", "status": "done", "details": { "count": 12 } },
    { "step": "generate_routes", "label": "生成 3 条路线", "status": "done", "details": {} }
  ]
}
```

---

### 1.2 流式对话（推荐）

```
POST /api/chat/stream
```

**请求体**：与 `POST /api/chat` 完全相同。

**响应**：`Content-Type: application/x-ndjson`，每行一个 JSON 事件（Newline-Delimited JSON）。

#### 事件类型

| 事件 type | 结构 | 触发时机 |
|-----------|------|----------|
| `progress` | `{ "type": "progress", "step": AgentTraceStep }` | Agent 每完成一个推理步骤后推送 |
| `final` | `{ "type": "final", "response": ChatResponse }` | 全部步骤完成，返回最终结果 |
| `error` | `{ "type": "error", "message": "错误描述" }` | 发生异常时推送 |

#### 流式事件示例

```
{"type":"progress","step":{"step":"parse_intent","label":"解析出行意图","status":"done","details":{}}}
{"type":"progress","step":{"step":"search_pois","label":"召回候选 POI","status":"done","details":{"count":12}}}
{"type":"progress","step":{"step":"generate_routes","label":"生成 3 条路线","status":"done","details":{}}}
{"type":"final","response":{ ... ChatResponse ... }}
```

#### 前端处理逻辑

1. `progress` 事件 → 更新 AgentTrace 进度面板（逐步出现的步骤）
2. `final` 事件 → 渲染路线卡片、聊天气泡
3. `error` 事件 → 展示错误提示 Toast

---

## 2. 路线相关接口

### 2.1 直接规划路线

```
POST /api/routes/plan
```

> 通常由后端 Agent 内部调用，前端一般不直接使用，通过 `/api/chat` 触发。

#### 请求体 `RoutePlanRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `intent` | Intent | **是** | 出行意图（见附录 Intent 结构） |
| `user_profile` | UserProfile | **是** | 用户画像 |
| `strategy_weights` | StrategyWeights | 否 | 策略权重，有默认值 |
| `candidate_pois` | POI[] | 否 | 候选 POI 列表 |

#### 响应体 `RoutePlanResponse`

```json
{
  "routes": [ Route, Route, Route ]
}
```

---

### 2.2 中途重新规划

```
POST /api/routes/replan
```

用于用户已出发、中途临时改变需求时触发重规划。

#### 请求体 `ReplanRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | **是** | 会话 ID |
| `event_type` | string | **是** | 触发事件类型，如 `"skip_poi"` / `"change_preference"` |
| `event_label` | string | **是** | 事件描述文字，如 `"用户跳过了田子坊"` |
| `current_routes` | Route[] | **是** | 当前已有路线 |
| `completed_poi_ids` | string[] | 否 | 已完成（已游览）的 POI ID 列表 |

#### 响应体

同 `RoutePlanResponse`。

---

## 3. POI 搜索接口

```
POST /api/pois/search
```

> 通常由后端 Agent 内部调用，前端一般不直接使用。

#### 请求体

直接传入 `Intent` 结构（见附录）。

#### 响应体

`POI[]` 数组（见附录 POI 结构）。

---

## 4. 用户反馈接口

```
POST /api/feedback
```

用户对路线进行评分后调用，后端会据此更新用户偏好画像。

#### 请求体 `FeedbackRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | **是** | 用户 ID |
| `session_id` | string | **是** | 会话 ID |
| `route_id` | string | **是** | 被评价的路线 ID |
| `route_score` | int | **是** | 路线整体评分（1–5） |
| `restaurant_score` | int | **是** | 餐厅满意度评分（1–5） |
| `queue_score` | int | **是** | 排队体验评分（1–5） |
| `budget_score` | int | **是** | 预算契合度评分（1–5） |
| `comment` | string | 否 | 文字反馈 |

#### 响应体 `FeedbackResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | string | 用户 ID |
| `updated_tags` | string[] | 本次反馈后更新的偏好标签 |
| `message` | string | 提示文字，如 `"已更新你的偏好"` |

#### 请求示例

```json
{
  "user_id": "user_1748700000",
  "session_id": "session_1748700000_abc123",
  "route_id": "route_A",
  "route_score": 5,
  "restaurant_score": 4,
  "queue_score": 5,
  "budget_score": 4,
  "comment": "路线很棒，排队确实少"
}
```

---

## 附录：核心数据结构

### Intent（出行意图）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `city` | string | `"上海"` | 目标城市 |
| `people_count` | int | `2` | 出行人数 |
| `start_location_name` | string \| null | — | 出发地名称 |
| `start_lat` | float \| null | — | 出发地纬度 |
| `start_lng` | float \| null | — | 出发地经度 |
| `start_time` | string | `"14:00"` | 出发时间（`HH:MM` 格式） |
| `duration_hours` | int | `6` | 计划时长（小时） |
| `budget_per_person` | int | `300` | 人均预算（元） |
| `preferences` | string[] | `[]` | 偏好标签 |
| `avoid_tags` | string[] | `[]` | 避开标签 |
| `scenario` | string | `"friends_citywalk"` | 场景类型 |
| `need_clarification` | bool | `false` | 是否需要追问 |
| `city_from_message` | bool | `false` | 城市是否从消息中提取 |

---

### Route（路线）

| 字段 | 类型 | 说明 |
|------|------|------|
| `route_id` | string | 路线唯一 ID，如 `"route_A"` |
| `title` | string | 路线标题，如 `"文艺下午茶路线"` |
| `objective` | string | 路线目标描述，如 `"citywalk + 咖啡 + 轻食"` |
| `summary` | string | 一句话摘要 |
| `total_duration_minutes` | int | 总时长（分钟） |
| `total_cost_per_person` | int | 人均总费用（元） |
| `total_queue_minutes` | int | 总排队时间（分钟） |
| `total_travel_minutes` | int | 总交通耗时（分钟） |
| `total_distance_km` | float | 总距离（公里） |
| `score` | int | 综合评分（0–100） |
| `score_breakdown` | RouteScoreBreakdown | 各维度分项评分 |
| `stops` | RouteStop[] | 站点列表（按游览顺序） |
| `reasons` | string[] | 推荐理由标签，如 `["性价比超高", "排队极少"]` |
| `replan_reason` | string \| null | 重规划原因（仅重规划时有值） |

#### RouteScoreBreakdown（分项评分）

| 字段 | 类型 | 说明 |
|------|------|------|
| `quality` | number | 质量评分（0–1） |
| `queue` | number | 排队友好度（0–1） |
| `budget` | number | 预算匹配度（0–1） |
| `distance` | number | 距离合理度（0–1） |
| `preference` | number | 偏好匹配度（0–1） |

---

### RouteStop（路线站点）

| 字段 | 类型 | 说明 |
|------|------|------|
| `poi_id` | string | POI 唯一 ID |
| `name` | string | 地点名称 |
| `category` | string | 类别：`restaurant` / `cafe` / `museum` / `park` / `citywalk` / `snack` / `scenic` / `shopping` 等 |
| `district` | string | 所在区域，如 `"卢湾·打浦桥"` |
| `address` | string | 详细地址 |
| `lat` / `lng` | float \| null | 坐标 |
| `start_time` / `end_time` | string | 游览时间段，格式 `"HH:MM"` |
| `estimated_cost` | int | 预计花费（元） |
| `queue_minutes` | int | 预计排队分钟数 |
| `queue_level` | enum | 排队程度：`"none"` / `"low"` / `"medium"` / `"high"` / `"very_high"` |
| `tags` | string[] | 标签，如 `["网红打卡", "文艺弄堂"]` |
| `rating` | float | 评分（如 4.8） |
| `review_count` | int | 评论总数 |
| `rank_label` | string | 榜单标签，如 `"必吃榜 Top 5"` |
| `brief` | string | 一句话简介 / 编辑推荐语 |
| `cover_image_url` | string | 封面图 URL |
| `distance_m` | int | 距用户出发点距离（米） |
| `transit_to_next` | TransitSegment \| null | 到下一站的交通信息（最后一站无此字段） |
| `booking_required` | bool | 是否需要预约 |
| `booking_url` | string | 预约链接 |
| `booking_phone` | string | 预约电话 |
| `booking_note` | string | 预约备注，如 `"建议提前1天预约"` |
| `indoor` | bool | 是否室内场所 |
| `walking_intensity` | string | 步行强度：`"low"` / `"medium"` / `"high"` |

---

### TransitSegment（站点间交通段）

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | enum | 交通方式：`"walk"` / `"metro"` / `"bus"` / `"taxi"` / `"bike"` |
| `duration_minutes` | int | 耗时（分钟） |
| `distance_m` | int | 距离（米） |
| `description` | string | 路线描述，如 `"地铁 10 号线新天地站→老西门站"` |

---

### AgentTraceStep（推理步骤）

| 字段 | 类型 | 说明 |
|------|------|------|
| `step` | string | 步骤 key |
| `label` | string | 前端展示文字 |
| `status` | string | `"running"` / `"done"` / `"error"` |
| `details` | object | 附加调试信息（可选） |

常见 step 枚举：

| step key | 说明 |
|----------|------|
| `parse_intent` | 解析出行意图 |
| `get_user_profile` | 读取用户画像 |
| `build_strategy_weights` | 计算策略权重 |
| `search_pois` | 召回候选 POI |
| `generate_routes` | 生成路线 |
| `summarize_routes` | LLM 总结推荐语 |
| `route_message` | 判定消息类型（新规划/修改） |
| `apply_query_delta` | 合并本轮意图变更 |

---

### UserProfile（用户画像）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | string | 用户 ID |
| `preferences` | string[] | 偏好标签 |
| `avoid_tags` | string[] | 避开标签 |
| `preference_weights` | object | 策略权重（key → float） |

---

### StrategyWeights（策略权重）

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `quality` | 0.3 | 质量优先权重 |
| `queue` | 0.25 | 排队友好权重 |
| `distance` | 0.2 | 距离合理权重 |
| `budget` | 0.15 | 预算匹配权重 |
| `preference` | 0.1 | 偏好匹配权重 |

> 所有权重之和应为 1.0。前端根据用户的 `preferences` 和 `budget_level` 动态计算（详见 `buildWeights()` 函数）。

---

## 前后端字段差异待对齐

> 以下字段前端已使用，但后端 schema 尚未定义，需协商对齐：

| 前端发送字段 | 后端现状 | 建议处理方式 |
|---|---|---|
| `trip_city` | 后端 `ChatRequest` 无此字段 | 后端添加 `trip_city: str \| None = None` 或统一复用 `city` 字段 |
| `trip_people` | 后端 `ChatRequest` 无此字段 | 后端添加 `trip_people: int \| None = None` |
| `trip_duration_hours` | 后端 `ChatRequest` 无此字段 | 后端添加 `trip_duration_hours: float \| None = None` |
| `trip_budget_per_person` | 后端 `ChatRequest` 无此字段 | 后端添加 `trip_budget_per_person: int \| None = None` |
| `RouteStop.rating` | 后端 `RouteStop` 无此字段 | 后端补充 `rating: float \| None = None` |
| `RouteStop.review_count` | 后端 `RouteStop` 无此字段 | 后端补充 `review_count: int \| None = None` |
| `RouteStop.rank_label` | 后端 `RouteStop` 无此字段 | 后端补充 `rank_label: str = ""` |
| `RouteStop.brief` | 后端 `RouteStop` 无此字段 | 后端补充 `brief: str = ""` |
| `RouteStop.distance_m` | 后端 `RouteStop` 无此字段 | 后端补充 `distance_m: int \| None = None` |
| `RouteStop.queue_level` | 后端 `RouteStop` 无此字段 | 后端补充 `queue_level: str = "none"` |
| `RouteStop.transit_to_next` | 后端 `RouteStop` 无此字段 | 后端补充 `transit_to_next: TransitSegment \| None = None` |
