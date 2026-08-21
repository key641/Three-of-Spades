# AI 出行规划 Agent V2 技术架构

> 文档状态：Draft for implementation
> 版本：2.0
> 更新日期：2026-08-18
> 适用范围：`backend/app/agent`、`backend/app/tools`、路线规划服务、会话状态、评测系统与前端 Agent Trace
> 设计目标：将当前固定长流水线升级为有边界、可恢复、可验证、可回归的出行规划 Agent，同时兼容现有 API 和 LYNN 优化。

## 1. 背景与结论

当前系统已经具备意图解析、用户画像、POI 召回、路线生成、多轮状态、Trace 和批量评测等能力，但端到端稳定性仍明显低于单模块表现。最近一轮 20 条基线评测中，意图理解维度约为 90%，最终通过率只有 50%；主要失败集中在路线不足、无有效规划结果、复合偏好丢失和起点来源错误。

根因不是某一个模型或某几条 Query，而是以下架构问题叠加：

1. 同一轮输入由消息路由、意图解析、Delta 解析、规则增强等多个模块重复理解，缺少唯一结果和字段级优先级。
2. `Intent`、`TripState`、`SessionState.last_intent` 和 `hard_constraints` 保存重复状态，转换时可能发生漂移。
3. 当前 Tool Registry 只列出工具名称，没有形成可供 Agent 观察和决策的工具协议。
4. 路线失败后的重试主要依赖扩大 POI 召回量，没有根据失败原因选择恢复动作。
5. 路线服务已经产生诊断，但失败链路没有完整向 Trace、Agent 和评测透传。
6. 编排器和路线服务承担过多职责，存在重复规划路径和演示特判，修改风险持续增加。
7. 评测能够看到过程步骤，但尚不能稳定回答“哪个约束、哪个状态更新、哪个工具调用导致失败”。

V2 不采用无限自治的通用 Agent，而采用 **确定性外壳 + 有边界的 Plan–Act–Observe 循环**：LLM 负责自然语言理解和受限决策，状态合并、约束执行、路线计算和结果验证保持确定性。

## 2. 产品能力目标

系统必须稳定完成以下能力：

- 将自然语言需求转成结构化、可追溯的旅行状态。
- 默认以用户明确指定地点为起点；未指定时使用当前 GPS；两者都没有时才使用城市级兜底。
- 正确处理追加、修改、删除、指代、局部重规划和新规划。
- 根据工具真实反馈调整计划，而不是按照固定次数机械重试。
- 三条路线凑不够时返回两条或一条；只有确实无解时才追问或解释无解原因。
- 不静默放宽用户明确表达的硬约束。
- 任何最终路线都经过确定性验证，回复不得编造路线事实。
- LLM、地图或下游服务异常时可降级、有明确错误分类，不向用户暴露内部异常和密钥。
- 每次变更都能通过自动化评测判断是否改善整体能力，而不是只修复单条 Query。

## 3. 设计原则

### 3.1 单一状态源

`TripStateV2` 是当前旅行目标的唯一权威状态。其他对象只能是输入、事件、只读投影或兼容输出，不得成为第二份可独立写入的状态。

### 3.2 结构化理解与确定性合并分离

LLM 只负责输出本轮理解和字段变更，不直接覆盖完整状态。状态变化由纯函数 Reducer 执行，并由可测试的优先级规则决定。

### 3.3 工具反馈驱动决策

每个工具必须返回统一状态、数据、诊断、是否可重试以及建议动作。Agent 必须基于 Observation 决定下一步，禁止无依据重复相同调用。

### 3.4 用户明确约束优先

用户本轮明确表达 > 历史明确表达 > GPS > 用户画像 > 模型推断 > 系统默认。只有可放宽约束允许自动降级；用户明确硬约束需要先获得确认。

### 3.5 最小自治和有界执行

每轮最多执行有限次数的工具循环，并限制总时长、LLM 调用次数和工具调用次数。Agent 不能无限尝试，也不能自由调用未注册能力。

### 3.6 先验证，再生成回答

路线对象是事实来源。自然语言回复只能基于通过验证的路线和诊断生成，不能在回复阶段重新发明站点、时间、价格或交通信息。

### 3.7 向后兼容和渐进迁移

保留现有 `/api/chat`、`ChatResponse`、前端路线卡片和 LYNN 排序/推荐优化。通过适配器逐步迁移，避免一次性重写路线算法。

## 4. 总体架构

```text
Frontend / POST /api/chat
        |
        v
Chat API Adapter
        |
        v
Agent Runtime
  1. Load Session Snapshot
  2. Understand Turn
  3. Reduce State
  4. Decide: Answer / Clarify / Plan / Replan
  5. Bounded Plan-Act-Observe Loop
  6. Verify Outcome
  7. Compose Grounded Response
  8. Commit State + Events + Trace
        |
        +--------------------+
        |                    |
        v                    v
Tool Gateway           Observability
  - resolve_location     - structured trace
  - search_pois          - metrics / timing
  - generate_routes      - failure taxonomy
  - diagnose_failure     - evaluation records
  - relax_constraints
  - replan_route
        |
        v
Existing Services
  - POI / Recall
  - Route Planner
  - AMap
  - Profile / Ranking / LYNN
```

核心执行流：

```text
Understand -> Reduce -> Decide
                    |
                    v
               Plan Action
                    |
                    v
               Execute Tool
                    |
                    v
                 Observe
                    |
            +-------+-------+
            |               |
        recoverable      completed
            |               |
            +---- loop ------+-> Verify -> Respond
```

## 5. 模块划分

建议新增以下目录和模块；迁移期间保留现有 `orchestrator.py` 作为 V1 入口。

```text
backend/app/agent/v2/
  runtime.py                  # 单轮执行入口与生命周期
  models.py                   # V2 核心 Schema
  understanding.py            # 单次结构化理解
  reducer.py                  # 纯状态合并
  policy.py                   # Answer/Clarify/Plan/Replan 决策
  executor.py                 # 有界 Plan-Act-Observe 循环
  recovery.py                 # 约束降级阶梯与恢复策略
  verifier.py                 # 结果验证
  response_composer.py        # 基于事实生成回复
  compatibility.py            # Intent/TripState/ChatResponse 适配
  trace.py                    # 结构化 Trace 构建

backend/app/tools/v2/
  base.py                     # ToolSpec、ToolResult、错误语义
  registry.py                 # 工具注册和发现
  resolve_location.py
  search_pois.py
  generate_routes.py
  diagnose_infeasibility.py
  relax_constraints.py
  replan_route.py

backend/app/state/
  repository.py               # 状态仓储接口
  in_memory.py                # 本地兼容实现
  event_store.py              # 状态事件与回放
```

职责边界：

| 模块 | 负责 | 不负责 |
| --- | --- | --- |
| Understanding | 解释本轮话语，生成字段 Patch | 写会话状态、调用路线工具 |
| Reducer | 按优先级合并状态，生成变更摘要 | 调用 LLM、判断路线可行性 |
| Policy | 选择 Answer/Clarify/Plan/Replan | 直接计算路线 |
| Executor | 执行有限循环、控制预算和停止条件 | 私自修改 TripState |
| Tool Gateway | 校验参数、执行工具、统一错误 | 决定是否放宽用户约束 |
| Route Service | 确定性生成与诊断路线 | 修改请求 Intent、生成聊天文案 |
| Verifier | 验证路线和回复依据 | 优化排序策略 |
| Response Composer | 根据已验证事实生成用户回复 | 创建不存在的路线事实 |
| State Repository | 原子保存状态、版本和事件 | 解释自然语言 |

## 6. 核心数据模型

### 6.1 字段值与来源

所有可能发生覆盖或放宽的字段使用统一包装：

```python
class ConstraintSource(str, Enum):
    USER_EXPLICIT = "user_explicit"
    HISTORY_EXPLICIT = "history_explicit"
    GPS = "gps"
    PROFILE = "profile"
    INFERRED = "inferred"
    DEFAULT = "default"

class Relaxability(str, Enum):
    HARD = "hard"
    ASK_BEFORE_RELAX = "ask_before_relax"
    SOFT = "soft"

class ConstraintValue(BaseModel, Generic[T]):
    value: T
    source: ConstraintSource
    confidence: float = Field(ge=0, le=1)
    turn_id: str
    relaxability: Relaxability
    evidence: str | None = None
```

要求：

- `USER_EXPLICIT` 默认是 `HARD` 或 `ASK_BEFORE_RELAX`。
- `GPS` 只在没有明确起点时生效。
- `INFERRED` 和 `DEFAULT` 默认允许自动放宽。
- `evidence` 只保留短证据片段，不保存或展示模型内部推理。

### 6.2 TripStateV2

```python
class TripStateV2(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    session_id: str
    state_version: int

    city: ConstraintValue[str] | None = None
    people_count: ConstraintValue[int] | None = None
    start_location: ConstraintValue[LocationRef] | None = None
    start_time: ConstraintValue[str] | None = None
    duration_minutes: ConstraintValue[int] | None = None
    budget_per_person: ConstraintValue[int] | None = None
    target_area: ConstraintValue[AreaRef] | None = None

    scenario: ConstraintValue[str] | None = None
    preferences: list[PreferenceConstraint] = []
    avoidances: list[PreferenceConstraint] = []
    must_include: list[RequiredStop] = []
    implicit_needs: list[SuggestedNeed] = []

    active_route_id: str | None = None
    current_route_ids: list[str] = []
    locked_stop_ids: list[str] = []
    last_outcome: PlanningOutcome | None = None
```

约束：

- 不再同时保存一份散装 `hard_constraints` 字典。
- `last_intent` 降级为兼容投影，禁止业务模块直接写入。
- 坐标和地点名称放在同一个 `LocationRef`，避免更换名称后保留旧坐标。
- 列表字段必须使用 `Field(default_factory=list)`，示例中的 `[]` 仅用于简写。

### 6.3 TurnUnderstanding

每轮只允许一个权威理解结果：

```json
{
  "turn_type": "new_plan | add | modify | remove | route_question | replan | select | chat",
  "state_patch": [
    {
      "op": "replace",
      "path": "/budget_per_person",
      "value": 200,
      "source": "user_explicit",
      "confidence": 0.99,
      "evidence": "降到人均 200"
    }
  ],
  "references": {
    "route_id": null,
    "stop_id": null,
    "scope": "current_trip"
  },
  "ambiguities": [],
  "confidence": 0.96
}
```

Schema 校验失败时最多自动修复一次；仍失败则使用确定性 fallback，且 Trace 必须标记 `understanding_mode=fallback`。

### 6.4 状态事件

每次状态更新同时写入事件：

```json
{
  "event_id": "evt_xxx",
  "session_id": "session_xxx",
  "turn_id": "turn_xxx",
  "base_version": 7,
  "new_version": 8,
  "type": "budget_changed",
  "patch": [{"op": "replace", "path": "/budget_per_person", "value": 200}],
  "source": "user_explicit",
  "timestamp": "2026-08-18T10:00:00+08:00"
}
```

事件用于调试、回放和评测，不要求第一阶段立即引入数据库；可以先由内存仓储实现接口。

## 7. 状态合并规则

Reducer 必须是纯函数：

```python
new_state, events, change_summary = reduce_state(old_state, understanding, request_context)
```

### 7.1 字段优先级

| 优先级 | 来源 | 示例 |
| --- | --- | --- |
| 1 | 本轮用户明确表达 | “从国贸出发” |
| 2 | 历史用户明确表达 | 上一轮指定静安寺，本轮只改预算 |
| 3 | 当前 GPS | 用户说“附近”，且没有明确起点 |
| 4 | 用户画像/前端配置 | 常驻城市、长期偏好 |
| 5 | 模型推断 | “我俩”推断人数为 2 |
| 6 | 系统默认 | 默认开始时间、默认时长 |

### 7.2 起点规则

1. 本轮出现明确地点时，写入完整 `LocationRef`，清除旧 GPS 坐标，随后由 `resolve_location` 解析新坐标。
2. 本轮未出现明确地点但存在历史明确起点时，继承历史起点。
3. 没有明确起点且请求包含 GPS 时，使用 GPS，并通过逆地理编码补全城市。
4. 仅有城市时，允许使用城市兜底起点，但必须标记 `source=default`，用户界面不得称为“当前位置”。
5. 用户明确目的城市与 GPS 城市不同，不得用 GPS 覆盖目的城市。

### 7.3 多轮规则

- `add`：只追加 Patch 中出现的字段或列表项。
- `modify`：只替换明确修改字段，未出现字段保持原值和来源。
- `remove`：只删除明确目标；删除起点时可以重新回退到当前 GPS。
- `new_plan`：创建新的旅行状态版本，旧状态进入历史，不继承路线和锁定站点。
- `route_question`：只读当前路线，不触发重新召回或规划。
- `replan`：继承旅行状态，仅按指定范围修改路线。

### 7.4 并发与幂等

- 每个请求携带 `turn_id` 和可选 `request_id`。
- 状态写入使用 `expected_state_version` 做乐观锁。
- 同一 `request_id` 重试必须返回相同结果，不能重复写事件或画像反馈。
- 同一 session 默认串行执行；不同 session 可以并行。

## 8. 决策策略

Policy 输出以下有限动作之一：

```python
class DecisionType(str, Enum):
    ANSWER_FROM_STATE = "answer_from_state"
    CLARIFY = "clarify"
    PLAN = "plan"
    REPLAN = "replan"
    REJECT = "reject"
```

### 8.1 追问条件

只有缺失信息会阻断下一步时才追问：

- 无法确定目的城市，且没有 GPS/历史城市可用。
- 用户明确条件互相冲突，系统不能安全选择。
- 必须放宽用户明确硬约束才能得到结果。
- 用户指代的路线或站点存在多个可能目标。

非阻断字段采用有来源的默认值，并在结果中透明展示。禁止使用全局“一次追问后永不追问”的粗粒度计数；应按未决字段记录追问状态并防止同一问题循环。

### 8.2 追问输出

```json
{
  "decision": "clarify",
  "blocking_fields": ["city"],
  "question": "你想在哪个城市安排这次行程？",
  "options": [],
  "state_preserved": true
}
```

追问前必须先提交当前可确认的状态 Patch，确保下一轮不会丢失已知信息。

## 9. 工具协议

### 9.1 ToolSpec

```python
class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    timeout_ms: int
    side_effect: Literal["none", "idempotent", "mutating"]
    max_attempts: int = 1
```

### 9.2 ToolResult

```python
class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    INFEASIBLE = "infeasible"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"
    INVALID_INPUT = "invalid_input"

class ToolResult(BaseModel, Generic[T]):
    call_id: str
    tool_name: str
    status: ToolStatus
    data: T | None = None
    diagnostics: dict = Field(default_factory=dict)
    retryable: bool = False
    suggested_next_actions: list[str] = Field(default_factory=list)
    duration_ms: int
    error_code: str | None = None
    safe_message: str | None = None
```

所有异常必须在 Tool Gateway 转成 `ToolResult`。业务代码不得依赖捕获裸 `AttributeError`、`ConnectError` 或解析异常判断流程。

### 9.3 必需工具

| 工具 | 输入 | 成功输出 | 失败诊断重点 |
| --- | --- | --- | --- |
| `resolve_location` | 地点名/GPS/城市 | 标准地点和坐标 | 未找到、跨城冲突、精度 |
| `search_pois` | 状态投影、召回策略 | POI 列表和覆盖统计 | 候选数、类别缺口、过滤原因 |
| `generate_routes` | 约束快照、POI、策略 | 0～3 条路线 | 硬约束拒绝直方图、预算、时长 |
| `diagnose_infeasibility` | 规划诊断 | 主因和可恢复动作 | 可放宽等级、预估收益 |
| `relax_constraints` | 状态快照、降级等级 | 临时规划约束 | 被放宽字段及来源 |
| `replan_route` | 活跃路线和局部变更 | 新路线 | 锁定站点冲突、替换失败 |

## 10. 有边界的 Plan–Act–Observe 执行器

### 10.1 执行预算

默认限制：

- 理解 LLM：每轮最多 1 次，Schema 修复最多额外 1 次。
- 决策 LLM：优先确定性 Policy；需要模型选择恢复动作时最多 1 次。
- 工具步骤：最多 5 步。
- 路线生成：最多 3 次，且后一次参数必须与前一次存在有解释的变化。
- 单轮软超时：12 秒；硬超时：20 秒。
- 达到预算后返回已验证的部分结果或精准追问，不能继续后台无限执行。

超时数值必须通过配置管理，并依据实际 P95 数据调整。

### 10.2 状态机

```text
READY
  -> UNDERSTOOD
  -> STATE_REDUCED
  -> DECIDED
  -> TOOL_RUNNING
  -> OBSERVING
       -> TOOL_RUNNING       可恢复且预算充足
       -> CLARIFICATION      需放宽显式硬约束
       -> VERIFYING          有候选结果
       -> DEGRADED_RESULT    只有部分结果
       -> FAILED             不可恢复
  -> COMPLETED
```

### 10.3 停止条件

满足任一条件必须停止循环：

- 得到至少一条通过验证的路线。
- 得到可直接回答的路线问题结果。
- 需要用户确认才能继续。
- 发生不可恢复错误。
- 达到工具步骤、时间或调用次数上限。
- 连续两次 Observation 没有产生新信息或新候选。

## 11. 路线规划与恢复策略

### 11.1 路线服务纯函数化

目标接口：

```python
RoutePlanResult generate_routes(RoutePlanInput input)
```

要求：

- 不修改传入的 `Intent`、`TripState` 或 POI。
- 相同输入和随机种子产生相同结果。
- 0 条路线也是正常业务结果，必须包含完整诊断。
- 返回所有可执行路线，最多截取 3 条；不足 3 条时不得清空已有路线。
- LYNN 的召回、排序或权重优化作为内部策略保留，通过 `strategy_version` 标识。

### 11.2 失败诊断

最少返回：

```json
{
  "candidate_poi_count": 51,
  "feasible_route_count": 0,
  "hard_constraint_rejections": {
    "outside_city": 0,
    "closed_at_arrival": 18,
    "duration_exceeded": 22,
    "budget_exceeded": 4,
    "required_stop_missing": 7,
    "minimum_stops_not_met": 31
  },
  "coverage": {
    "meal_stop": 8,
    "rest_stop": 14
  },
  "degradation_steps": [],
  "dominant_failure": "minimum_stops_not_met"
}
```

### 11.3 自动降级阶梯

| 等级 | 允许变化 | 是否需要询问 |
| --- | --- | --- |
| L0 | 严格执行全部约束 | 否 |
| L1 | 降低路线间多样性、允许更多站点重合 | 否 |
| L2 | 最少站点 3 → 2 → 1，返回部分路线 | 否，但结果需说明 |
| L3 | 放宽 `DEFAULT`/`INFERRED` 的时间缓冲、隐式需求 | 否，需记录 Trace |
| L4 | 放宽画像偏好或普通软偏好 | 否，需说明未完全满足 |
| L5 | 放宽用户明确预算、时间、城市、必含站点 | 必须询问 |

恢复动作必须针对主导失败原因：

- 候选数不足或类别覆盖不足：扩大/改变 POI 召回。
- 已有足够候选但最少站点不足：启用两站或单站回退。
- 营业时间冲突：调整可放宽的开始时间，或询问用户。
- 时长不足：减少站点或交通范围，不应继续扩大召回。
- 预算超限：先重排低成本 POI；只有仍无解时询问是否提高预算。

禁止仅因为路线为 0 就依次将召回量从 60 增加到 260。

## 12. 结果验证

`OutcomeVerifier` 在回复前执行，输出 `VerificationReport`。

### 12.1 硬验证

- 路线城市与状态城市一致。
- 第一段路线使用正确起点来源。
- 所有站点有合法 ID、名称和坐标。
- 时间单调递增，停留和交通时间非负。
- 到达时间处于营业时间内。
- 总时长不超过不可放宽上限。
- 总预算不超过不可放宽上限。
- 用户明确 `must_include` 在至少一条主路线中满足。
- 路线中没有重复 POI 或明显回环。
- 交通腿与前后站点一致。

任一硬验证失败，该路线不得返回用户。

### 12.2 软验证

- 偏好覆盖程度。
- 步行、排队、服务、热门度等目标得分。
- 三条路线之间是否有可理解的差异。
- 是否存在更优但被过滤的候选。

软验证不阻断返回，但进入 `warnings` 和评测指标。

### 12.3 回复忠实度

回复生成器只接收：

- 已验证路线的只读投影。
- 未满足偏好列表。
- 实际使用的降级步骤。
- 面向用户的安全提示。

禁止向回复模型提供未选择候选、内部异常堆栈、密钥或完整内部诊断。

## 13. 可观测性与错误语义

### 13.1 Trace 结构

```json
{
  "trace_id": "trace_xxx",
  "turn_id": "turn_xxx",
  "step_id": "step_04",
  "phase": "act",
  "name": "generate_routes",
  "status": "infeasible",
  "started_at": "...",
  "duration_ms": 842,
  "input_summary": {"poi_count": 51, "degradation_level": 0},
  "output_summary": {"route_count": 0},
  "diagnostics": {"dominant_failure": "minimum_stops_not_met"},
  "error_code": null,
  "parent_step_id": "step_03"
}
```

前端默认展示摘要；详细诊断仅在测评和调试模式展开。不得展示隐藏推理过程，只展示可验证的决策依据、输入摘要和工具结果。

### 13.2 错误分类

| 类别 | 示例 | 系统行为 |
| --- | --- | --- |
| `invalid_input` | 坐标非法、Schema 不匹配 | 校验失败，不调用下游 |
| `understanding_failed` | LLM 超时、JSON 无法修复 | 使用 fallback 或安全追问 |
| `location_unresolved` | 地点重名、无法解析 | 精准追问 |
| `planning_infeasible` | 约束组合无解 | 诊断并按等级恢复 |
| `dependency_unavailable` | 地图/LLM ConnectError | 有缓存则降级，否则安全提示 |
| `timeout` | 单工具超时 | 有界重试或返回部分结果 |
| `internal_error` | 未预期异常 | 记录 trace_id，返回安全文案 |

### 13.3 指标

至少采集：

- `agent_turn_total{decision,outcome}`
- `agent_turn_latency_ms`
- `understanding_latency_ms`
- `tool_call_total{tool,status,error_code}`
- `tool_call_latency_ms{tool}`
- `route_count`
- `route_infeasible_total{dominant_failure}`
- `recovery_attempt_total{level,result}`
- `verification_failure_total{code}`
- `llm_call_total{purpose,model,status}`
- `llm_tokens_total{purpose,model}`
- `state_conflict_total`

日志必须包含 `trace_id/session_id/turn_id/request_id/model_version/prompt_version/strategy_version`，并对用户文本和位置数据执行脱敏策略。

## 14. 稳定性设计

### 14.1 超时、重试与熔断

- LLM、地图和外部服务分别配置连接超时和总超时。
- 仅对明确的临时错误重试，使用指数退避和随机抖动。
- 参数错误、鉴权错误和业务无解不得重试。
- 同一依赖连续失败达到阈值时短时熔断，避免拖垮整批评测。
- 重试必须保持 `request_id`，确保幂等。

### 14.2 降级

- 总结 LLM 不可用：使用模板总结已验证路线，路线本身仍可返回。
- 意图 LLM 不可用：规则 fallback 只提取高置信字段；不能确定的阻断字段进行追问。
- 地图不可用：仅在已有可信缓存或 mock 明确开启时返回，并标注数据来源；生产模式不得将 mock 冒充实时地图。
- 路线只生成 1～2 条：正常返回并说明数量，不视为系统异常。
- 全部路线无解：返回主因和一个最小化追问，不返回空白或内部异常。

### 14.3 状态持久化

第一阶段可继续使用内存实现，但必须通过 `StateRepository` 接口访问。生产实现应支持：

- 带版本的原子读写。
- TTL 和显式会话结束。
- 最近状态快照与事件回放。
- 进程重启后恢复。
- 按用户和会话隔离。

### 14.4 配置与密钥

- API Key 只从环境变量或密钥管理服务读取。
- 不写入代码、Trace、评测结果和前端响应。
- 启动时验证必需配置，并输出脱敏后的 Provider/Model/Base URL 状态。
- 模型切换必须通过配置和版本记录完成，不能在业务逻辑中写死。

## 15. API 兼容策略

### 15.1 保持现有接口

V2 初期继续使用：

```text
POST /api/chat
POST /api/evaluation/run
```

`ChatRequest` 保持兼容。`ChatResponse` 中原有字段继续存在，并可追加：

```json
{
  "planning_outcome": "complete | partial | clarification | infeasible | degraded",
  "state_version": 8,
  "trace_id": "trace_xxx",
  "warnings": [],
  "degradation": {
    "level": 2,
    "changes": ["minimum_stops: 3 -> 2"]
  }
}
```

### 15.2 兼容适配器

- `TripStateV2 -> Intent`：只用于调用尚未迁移的旧服务。
- `RoutePlanResponse -> ToolResult`：保留 routes，并完整封装 diagnostics。
- `V2 Trace -> AgentTraceStep`：前端未升级前映射为现有格式。
- `ChatResponseV2 -> ChatResponse`：新增字段保持可选，旧前端可以忽略。

兼容适配器必须单向使用。旧 `Intent` 的变化不得反向静默覆盖 `TripStateV2`。

### 15.3 灰度开关

```text
AGENT_RUNTIME_VERSION=v1|v2|shadow
```

- `v1`：现有链路。
- `shadow`：V1 正常响应，V2 同请求后台执行并比较，不影响用户。
- `v2`：V2 主链路，必要时可快速切回 V1。

Shadow 模式禁止重复写画像反馈、曝光事件等副作用。

## 16. 评测体系 V3

### 16.1 分层指标

| 层级 | 指标 |
| --- | --- |
| Understanding | 字段 Precision/Recall/F1、复合偏好召回、指代正确率 |
| State | Patch 正确率、状态转移正确率、来源优先级、跨轮保留率 |
| Policy | 追问准确率、工具选择准确率、无效行动率 |
| Tool | 参数正确率、错误分类准确率、诊断完整率 |
| Planning | 可执行路线率、部分结果率、零结果恢复率、硬约束满足率 |
| Verification | 违规检出率、误杀率、回复忠实度 |
| Stability | pass@1、stable-pass@3、异常率、状态冲突率 |
| Efficiency | P50/P95 延迟、LLM/工具调用次数、Token 和成本 |

### 16.2 数据集切片

- 首轮完整需求。
- 首轮信息不足。
- 明确起点、GPS 起点、历史起点、异地目的城市。
- 多轮追加、修改、删除、指代和“其他不变”。
- 复合偏好和相互冲突偏好。
- 无 POI、POI 足够但路线无解、只有 1～2 条路线。
- 营业时间、预算、时长、必含站点导致的无解。
- LLM 超时、地图超时、错误响应和部分依赖不可用。
- 口语、错别字、中英文混合、长输入和重复输入。
- 脱敏真实用户日志及其人工标注结果。

### 16.3 评测方式

- 状态层使用 Golden Patch 和 Golden State，不比较自然语言文案。
- 路线层允许多个正确答案，比较硬约束、可执行性和质量下界。
- 每条非确定性用例至少运行 3 次，报告 `pass@1` 和 `stable-pass@3`。
- 固定代码版本、数据版本、模型、Prompt、策略版本和随机种子。
- 单条超时或异常不得中断整批运行。
- 批次支持并发上限、实时进度、单 Case 超时和结果持久化。

### 16.4 发布门禁

| 指标 | 合并门槛 | V2 全量门槛 |
| --- | ---: | ---: |
| P0 主链路通过率 | 100% | 100% |
| 起点来源优先级 | 100% | 100% |
| 明确硬约束保留率 | 100% | 100% |
| Understanding 字段 F1 | >= 95% | >= 97% |
| 零路线恢复率 | >= 90% | >= 95% |
| Stable pass@3 | >= 85% | >= 90% |
| 未捕获异常率 | 0 | 0 |
| 失败诊断完整率 | >= 95% | 100% |

延迟门槛在收集真实基线后确定。功能正确性和状态一致性不得为了降低延迟而降级。

## 17. 测试策略

### 17.1 单元测试

- Reducer：覆盖全部来源优先级和 Patch 操作。
- Policy：覆盖追问、规划、重规划和只读问答。
- Recovery：每个失败主因映射到正确动作。
- Verifier：每条硬验证规则包含正反例。
- Tool Gateway：异常映射、超时、幂等和 Schema 校验。

### 17.2 契约测试

- 所有工具输入输出必须通过 Pydantic Schema。
- 旧 Route Service 到 V2 ToolResult 的 diagnostics 不得丢字段。
- V2 到现有 `ChatResponse` 的前端兼容快照。
- Provider Mock 覆盖超时、限流、鉴权、空响应和非法 JSON。

### 17.3 集成测试

- 完整 `Understand -> Reduce -> Plan -> Verify -> Respond`。
- 指定起点覆盖 GPS。
- 无指定起点使用 GPS。
- 51 个 POI 但三站无解时回退两站。
- 明确预算导致无解时追问，不静默提高预算。
- 总结 LLM 挂掉仍返回路线。
- 重复 `request_id` 不产生重复副作用。

### 17.4 故障注入

- LLM 连接失败、超时、429、返回非法 JSON。
- 地图服务超时、部分交通腿失败。
- 状态版本冲突。
- POI 服务返回空列表或脏数据。
- 路线服务抛出未预期异常。
- 批量评测中单条 Case 卡住。

### 17.5 属性与不变量测试

以下不变量适合属性测试：

- Reducer 不修改旧状态对象。
- 未出现在 Patch 中的显式字段保持不变。
- 明确起点永远不会被 GPS 覆盖。
- 任何返回路线都通过硬验证。
- 降级等级增加时，不得放宽高于该等级的约束。
- 同一输入、状态、策略版本和随机种子产生相同规划结果。

## 18. 迁移计划

### Phase 0：建立可靠基线（1～2 天）

- 将 `route_service.last_diagnostics` 在成功和失败路径都完整透传。
- 合并 `orchestrator.py` 中重复的 `build_routes` 流程。
- 启用不足三条时的 2/1 站回退。
- 重试前根据诊断判断是否需要扩大召回。
- Trace 增加模型、Prompt、策略版本、耗时和错误码。
- 固化当前 20 条用例结果，新增“51 个 POI 但零路线”回归用例。

验收：任何 `no_feasible_routes` 都能定位主导拒绝原因；已有一条合法路线时不返回空结果。

### Phase 1：统一状态（3～5 天）

- 引入 `TripStateV2`、ConstraintValue 和 Reducer。
- 写全状态优先级单元测试。
- 通过兼容适配器继续调用现有路线服务。
- `last_intent` 改为只读兼容投影。
- SessionMemory 抽象为 StateRepository。

验收：起点、城市、人数、预算在多轮修改中没有非预期变化；状态转移测试 100% 通过。

### Phase 2：统一理解与工具协议（5～7 天）

- 合并 MessageRouter、Intent Parse 和 Query Delta 的权威输出。
- 保留确定性规则作为校验和 fallback。
- 实现 ToolSpec、ToolResult、Registry 和 Tool Gateway。
- 将 POI、路线、定位服务包装为 V2 工具。

验收：每轮只有一个权威 TurnUnderstanding；所有工具失败都有标准错误码和建议动作。

### Phase 3：有界执行器与恢复（5～7 天）

- 实现 Policy 和 Plan–Act–Observe 状态机。
- 引入诊断驱动的恢复策略和降级阶梯。
- 加入循环预算、停止条件、幂等和超时。
- 路线服务移除对输入 Intent 的修改。

验收：零路线恢复率达到 90% 以上；同参数机械重试为 0；显式硬约束没有静默放宽。

### Phase 4：验证器与 Eval V3（3～5 天）

- 实现路线硬验证和回复忠实度检查。
- 加入 Golden State、工具决策、故障注入和稳定性用例。
- 评测支持 `stable-pass@3`、进度、超时和版本记录。
- Shadow 对比 V1/V2。

验收：P0 100%，未捕获异常为 0，失败诊断完整率 100%，Shadow 指标达到全量门槛。

### Phase 5：灰度与清理

- 按 5% → 20% → 50% → 100% 灰度。
- 每级至少覆盖一个完整业务周期，并观察错误率、恢复率和延迟。
- 达到全量门槛后删除 V1 重复状态写入、Demo 特判和重复编排代码。
- 将生产问题自动沉淀为脱敏回归 Case。

## 19. 发布与回滚

发布前必须满足：

- 全量单元、契约、集成和 P0 评测通过。
- 模型、Prompt、数据和策略版本可追溯。
- V2 Shadow 无状态副作用。
- 已验证 V1 快速切回开关。
- 数据结构变更向前兼容；旧客户端可以忽略新增字段。
- 仪表盘能够按错误码、恢复等级和模型版本切分。

触发自动回滚的建议条件：

- P0 在线成功率下降超过 2 个百分点。
- 错误城市或错误起点来源出现任一确认案例。
- 未捕获异常率超过 0.1%。
- P95 延迟连续 10 分钟超过基线 1.5 倍。
- 状态版本冲突或重复副作用超过阈值。

## 20. 关键架构决策记录

### ADR-001：不采用完全自治 Agent

出行规划具有明确业务约束和真实世界可执行性要求。选择确定性 Policy 与有限 ReAct 循环，在需要环境反馈的失败恢复环节使用 Agent 决策。

### ADR-002：TripStateV2 为唯一状态源

避免 `Intent`、`TripState` 和字典约束重复写入。旧对象仅作为兼容投影。

### ADR-003：路线算法继续作为确定性工具

保留现有路线规划、排序和 LYNN 优化，先修正输入输出协议和诊断，不进行高风险重写。

### ADR-004：不保存和展示模型隐藏推理

Trace 保存结构化理解、动作、工具输入摘要、Observation 和可验证决策依据，不保存长篇内部推理。

### ADR-005：部分结果优于空结果

只要存在一条通过硬验证的路线，就应返回该路线。路线数量不足属于部分成功，不属于系统失败。

## 21. Definition of Done

V2 只有同时满足以下条件才算完成：

1. 每轮只有一个权威理解结果和一个权威旅行状态。
2. 状态字段具备来源、置信度、轮次和可放宽等级。
3. 所有工具使用统一协议，并对错误和业务无解做明确区分。
4. 路线失败可以定位到具体硬约束，并驱动下一步恢复动作。
5. Agent 循环具备步骤、时间、成本和停止边界。
6. 不足三条路线时返回已有合法路线。
7. 所有用户可见路线通过确定性验证。
8. LLM 总结不可用时仍能返回模板化路线结果。
9. 多轮起点、城市和显式约束不会被默认值或 GPS 覆盖。
10. P0、故障注入、稳定性和 Shadow 发布门禁全部通过。

## 22. 参考资料

- [Anthropic：Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic：Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- 仓库现有行为规格：`docs/agent_roadmap.md`
- 仓库现有评测条例：`docs/evaluation.md`
- 仓库现有 API 契约：`docs/api_contract.md`
