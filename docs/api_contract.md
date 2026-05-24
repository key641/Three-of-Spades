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

### Request

在用户已经选择某条路线并开始行进后，前端或 Agent 可把当前路线、已完成点位和实时事件传给后端。`current_routes` 仍兼容现有 `Route` 结构。

```json
{
  "session_id": "session_demo",
  "selected_route_id": "route_balanced_best",
  "event_type": "queue_spike",
  "event_label": "餐厅排队 90 分钟",
  "current_routes": [],
  "completed_poi_ids": ["poi_001"],
  "locked_poi_ids": ["poi_003"],
  "current_poi_id": "poi_001",
  "current_lat": 31.2304,
  "current_lng": 121.4737,
  "current_time": "15:20",
  "event_payload": {
    "affected_poi_id": "poi_002",
    "queue_minutes": 90,
    "traffic_multiplier": 1.6,
    "allow_external_candidates": false
  }
}
```

说明：

- `event_type` 当前支持 `queue_spike`、`poi_closed`、`traffic_jam`、`user_tired`、`weather_change`。
- `completed_poi_ids` 会被固定保留，不参与替换。
- `locked_poi_ids` 默认保留，除非实时状态是 `closed / unavailable / sold_out`。
- `event_payload` 是地图 API / mock provider 的扩展载体，后续接高德、百度、Google 或 Mapbox 时统一映射到内部 live status。

### Response Additions

每条路线除原有字段外，会额外返回：

```json
{
  "replan_reason": "已根据「餐厅排队 90 分钟」替换受影响的后续点位，并重新计算时间、排队和交通。",
  "changed_stops": [
    {
      "change_type": "replace",
      "from_poi_id": "poi_002",
      "from_name": "原餐厅",
      "to_poi_id": "poi_008",
      "to_name": "替代餐厅",
      "reason": "原 POI 实时排队过长"
    }
  ],
  "live_warnings": ["原餐厅 实时排队约 90 分钟，已换成 替代餐厅。"],
  "data_sources": ["local", "mock"]
}
```

说明：

- `changed_stops` 用于前端展示“替换/删除/调整”的差异。
- `live_warnings` 用于提示排队、闭店、交通拥堵等风险。
- `data_sources` 当前可能是 `local/mock`，后续真实地图 API 接入后可出现 `amap/baidu/google/mapbox`。

## POST /api/feedback

行程评分和画像更新使用。
