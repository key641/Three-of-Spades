# API Contract

## POST /api/chat

前端主入口。

### Request

```json
{
  "session_id": "session_demo",
  "user_id": "user_demo",
  "message": "我们三个人周六下午在上海 citywalk，想吃好但别排队，人均300以内",
  "event_type": "user_message"
}
```

### Response

```json
{
  "session_id": "session_demo",
  "message": "我先按你们的需求生成了几条可执行路线。",
  "need_clarification": false,
  "clarifying_question": null,
  "intent": {},
  "user_profile": {},
  "routes": [],
  "agent_trace": []
}
```

## POST /api/pois/search

B 同学调试 POI 召回使用。

## POST /api/routes/plan

B 同学调试路线规划使用。

## POST /api/routes/replan

动态事件重规划使用。

## POST /api/feedback

行程评分和画像更新使用。

