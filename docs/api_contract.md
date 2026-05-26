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

## POST /api/routes/evaluate

A 同学调试路线点评大模型使用。该接口不重新生成路线，只接收已经由 `/api/routes/plan` 或 `/api/chat` 产出的 routes，并返回每条路线的简要评分、亮点、风险和推荐语。

### 给 A 同学的接入说明

这个接口需要接在“路线已生成”之后、“前端展示路线概览”之前：

```text
用户输入
-> intent 解析
-> POI 召回
-> /api/routes/plan 或 /api/chat 生成 1-3 条 Route
-> /api/routes/evaluate 调用大模型逐条点评 Route
-> 前端把 Route + evaluation 一起展示
```

这一部分的作用是把 B 同学的规则算法结果翻译成更像用户能读懂的路线评语。算法已经给出了 `score`、`score_breakdown`、`summary`、`reasons` 等结构化分数和原因；A 同学需要在这里调用大模型，让模型基于这些已有字段生成每条路线的短评、亮点、风险和推荐语。注意：这个接口只做“点评和解释”，不负责重新选 POI、不重新排序路线，也不要让模型编造新的地点、价格或时间。

后续如果要调 prompt 或切换模型，主要改 `backend/app/services/route_evaluation_service.py` 里的 LLM prompt、输入裁剪和 JSON 解析逻辑；接口路径和响应结构尽量保持稳定，方便前端联调。

### Request

```json
{
  "intent": {
    "city": "北京",
    "people_count": 2,
    "start_time": "14:00",
    "duration_hours": 6,
    "budget_per_person": 300,
    "preferences": ["拍照", "咖啡"],
    "avoid_tags": [],
    "scenario": "friends_citywalk"
  },
  "user_profile": null,
  "routes": []
}
```

说明：

- `routes` 使用现有 `Route` 结构，通常直接复用 `/api/routes/plan` 或 `/api/chat` 返回值。
- 后端会优先调用 LLM provider；LLM 不可用时返回 `source: "fallback"` 的稳定结果，方便前端和 A 同学先联调接口。

### Response

```json
{
  "evaluations": [
    {
      "route_id": "route_balanced_best",
      "score": 91,
      "summary": "节奏均衡，适合首次游玩。",
      "highlights": ["点位集中", "预算稳定"],
      "risks": ["热门点位可能略拥挤"],
      "recommendation": "推荐作为首选方案。",
      "source": "llm"
    }
  ]
}
```

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

- `event_type` 当前支持 `replace_poi`、`avoid_poi`、`preference_change`、`queue_spike`、`poi_closed`、`traffic_jam`、`user_tired`、`weather_change`。
- `completed_poi_ids` 会被固定保留，不参与替换。
- `locked_poi_ids` 默认保留，除非实时状态是 `closed / unavailable / sold_out`。
- `event_payload` 是地图 API / mock provider 的扩展载体，后续接高德、百度、Google 或 Mapbox 时统一映射到内部 live status。
- A 同学负责把用户自然语言解析成 `event_type + event_payload`；B 的路线调整工具只执行结构化策略，不做自然语言理解。

### Replan Event Payload 约定

用户主动调整：

```json
{
  "event_type": "replace_poi",
  "event_label": "用户不想去第二个点，换一个",
  "event_payload": {
    "affected_poi_id": "poi_002",
    "preserve_poi_ids": ["poi_001", "poi_003"],
    "replacement_category": "咖啡馆",
    "prefer_tags": ["安静", "咖啡"],
    "avoid_tags": ["商业化", "人多"],
    "force_replace": true
  }
}
```

动态风险提醒：

```json
{
  "event_type": "queue_spike",
  "event_label": "餐厅排队变长",
  "event_payload": {
    "affected_poi_id": "poi_002",
    "queue_minutes": 25,
    "warning_only": true
  }
}
```

字段说明：

- `affected_poi_id` / `affected_poi_ids`：需要替换或提醒的 POI。
- `preserve_poi_ids`：用户明确要求保留的 POI，优先级高于普通替换；闭店、不可达、售罄除外。
- `avoid_tags`：本次调整额外避开的标签，例如“商业化”“人多”“太贵”。
- `prefer_tags`：本次调整额外偏好的标签，例如“安静”“咖啡”“室内”。
- `replacement_category`：用户指定替代类型，例如“咖啡馆”“餐厅”“室内展览”。
- `force_replace`：用户明确说“换掉”时设为 `true`。
- `warning_only`：只做实时复核和提醒，不替换可用 POI。

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
