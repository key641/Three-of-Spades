# API Contract

## POST /api/chat

前端主入口。

### 前端联调配置

前端默认可以使用 mock chat 预览 UI。需要连接真实后端时，在 `frontend/.env` 中设置：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_CHAT=false
```

如果 `VITE_USE_MOCK_CHAT` 未配置，或值不是 `false`，前端会使用 mock 响应，不会请求后端。

### Request

```json
{
  "session_id": "session_demo",
  "user_id": "user_demo",
  "message": "我们三个人周六下午在上海 citywalk，想吃好但别排队，人均300以内",
  "event_type": "user_message",
  "city": "上海",
  "scenarios": ["friends_citywalk"],
  "scenario": "friends_citywalk",
  "preferences": ["少排队", "吃好", "citywalk"],
  "avoid_tags": ["人多", "商业街"],
  "budget_level": "mid",
  "preference_weights": {
    "quality": 0.3,
    "queue": 0.25,
    "distance": 0.2,
    "budget": 0.15,
    "preference": 0.1
  }
}
```

说明：

- `message` 是必填字段。
- `city`、`scenarios`、`preferences`、`avoid_tags`、`budget_level`、`preference_weights` 来自前端 onboarding，可选。
- 后端会把 onboarding 字段合并进 LLM 解析出的 `Intent` 和 `UserProfile`。
- `budget_level` 当前映射为：`low -> 100`、`mid -> 300`、`high -> 600`。

### Response

```json
{
  "session_id": "session_demo",
  "message": "我先按你们的需求生成了几条可执行路线。",
  "need_clarification": false,
  "clarifying_question": null,
  "intent": {
    "city": "上海",
    "people_count": 3,
    "start_location_name": "人民广场",
    "start_lat": 31.2304,
    "start_lng": 121.4737,
    "start_time": "14:00",
    "duration_hours": 6,
    "budget_per_person": 300,
    "preferences": ["少排队", "吃好"],
    "avoid_tags": ["人多"],
    "scenario": "friends_citywalk",
    "need_clarification": false
  },
  "user_profile": {
    "user_id": "user_demo",
    "tags": ["少排队", "吃好"],
    "preferences": ["少排队", "吃好"],
    "avoid_tags": ["人多"],
    "preference_weights": {
      "quality": 0.3,
      "queue": 0.25,
      "distance": 0.2,
      "budget": 0.15,
      "preference": 0.1
    }
  },
  "routes": [
    {
      "route_id": "route_balanced",
      "title": "综合最优路线",
      "objective": "balanced",
      "summary": "综合平衡评分、预算、排队和距离，预计人均 200 元，排队 20 分钟，路上约 30 分钟。",
      "total_duration_minutes": 300,
      "total_cost_per_person": 200,
      "total_queue_minutes": 20,
      "total_travel_minutes": 30,
      "total_distance_km": 5.6,
      "score": 86,
      "score_breakdown": {
        "quality": 88,
        "queue": 82,
        "budget": 90,
        "distance": 80,
        "preference": 86
      },
      "stops": [
        {
          "poi_id": "poi_001",
          "name": "武康路街区",
          "category": "citywalk",
          "start_time": "14:10",
          "end_time": "15:30",
          "estimated_cost": 0,
          "queue_minutes": 0,
          "tags": ["拍照", "citywalk"],
          "travel_minutes_from_previous": 10,
          "distance_km_from_previous": 1.2,
          "transport_mode_from_previous": "walk",
          "reason": "适合拍照和 citywalk 体验"
        }
      ],
      "reasons": ["预算可控", "点位集中，少绕路"],
      "replan_reason": null
    }
  ],
  "agent_trace": [
    { "step": "parse_intent", "label": "LLM 解析用户意图", "status": "done" }
  ]
}
```

评分约定：

- `score` 使用 0-100 整数。
- `score_breakdown` 使用 0-100 整数。
- 前端如果展示为 10 分制，应自行除以 10；如果展示进度条，应直接按百分比使用。

## POST /api/pois/search

B 同学调试 POI 召回使用。

## POST /api/routes/plan

B 同学调试路线规划使用。

## POST /api/routes/replan

动态事件重规划使用。

## POST /api/feedback

行程评分和画像更新使用。
