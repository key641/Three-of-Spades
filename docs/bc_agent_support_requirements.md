# B/C 侧 Agent 支持需求说明

更新时间：2026-05-23

## 背景

A 侧正在把 Agent 从“只保存上一轮 `Intent`”推进到“显式保存 `QueryUnderstanding`、`IntentDelta`、`TripState`”。这一步先在后端内部兼容落地，不要求 B 侧路线策略和 C 侧前端马上改动。

通俗理解：A 侧会先把用户的话整理成一张更清楚的“旅行状态表”。现在路线生成仍然按旧 `Intent` 跑；等 B/C 准备好后，再逐步消费这张状态表。

## 当前不需要 B/C 立即做的事

- B 侧暂时不需要修改 `RouteService`。
- C 侧暂时不需要修改 `AgentTrace` 或路线卡片。
- 现有 `/api/chat` 返回结构暂时不变。
- 现有 demo 和前端流程暂时按旧字段继续工作。

## 未来需要 B 侧支持

### 1. 消费明确的路线需求字段

未来 route planner request 需要支持：

```json
{
  "soft_preferences": ["拍照", "吃好"],
  "implicit_needs": ["rest_stop"],
  "must_include": ["meal_stop"]
}
```

B 侧需要把这些字段作为结构化输入，而不是只从 `preferences` 关键词里猜。

### 2. 支持节点语义

需要识别以下节点类型：

- `meal_stop`：餐厅、小吃、咖啡、轻食等可满足用餐或休息的点。
- `rest_stop`：咖啡、室内空间、公园休息点、低强度街区等可降低疲劳的点。

验收标准：

- `must_include` 中有 `meal_stop` 时，至少一条主推路线要包含餐饮/休息节点。
- `implicit_needs` 中有 `rest_stop` 时，路线应优先加入休息节点；无法满足时要说明原因。
- 拍照一日游追加吃饭后，路线不能变成“餐厅 -> 餐厅 -> 餐厅”。

### 3. 暴露未满足原因

当路线工具无法满足 `must_include` 时，需要返回机器可读原因，例如：

```json
{
  "unmet_requirements": [
    {
      "type": "meal_stop",
      "reason": "候选 POI 中没有营业时间合适的餐饮点"
    }
  ]
}
```

A 侧会把这类信息写入 trace 和用户回复，避免 LLM 编造路线已经满足。

## 未来需要 C 侧支持

### 1. 展示分层 Trace

未来 trace 会按层级输出：

- `understanding`：用户这句话被理解成什么。
- `state_merge`：保留、新增、修改、删除了哪些状态。
- `planning_policy`：为什么重规划或不重规划。
- `tool_result`：POI 和路线工具执行结果。
- `response_composer`：回复是否使用 LLM，是否 fallback。

C 侧可以先保持当前折叠展示，后续再按层级加标签。

### 2. 展示状态变化摘要

建议前端能展示类似文案：

```text
保留：上海、2人、一日游、拍照
新增：meal_stop
修改：城市 上海 -> 杭州
```

这能让用户理解 Agent 为什么没有“忘记上一轮”。

### 3. 展示 fallback/error

如果 LLM 总结不可用、路线工具未满足 `meal_stop`，前端需要让用户看见系统状态，而不是只显示一段正常回复。

## 建议协作顺序

1. A 侧先完成 `TripState` 内部落地，保持旧 API 兼容。
2. A+B 约定 route planner request 中 `soft_preferences / implicit_needs / must_include` 的最终字段名。
3. B 侧支持 `meal_stop / rest_stop` 结构化规划。
4. A 侧把未满足原因接入 trace。
5. C 侧升级 trace 展示和状态变化摘要。

## 对齐问题

- B 侧 POI 数据里是否已有足够字段判断餐饮、休息、拍照、低强度？
- `meal_stop` 是否只代表正餐，还是也允许咖啡/轻食兜底？
- C 侧 trace 是继续使用当前列表样式，还是后续改成按层级分组？
- 如果 `must_include` 无法满足，前端希望展示为警告、提示条，还是 trace 详情？
