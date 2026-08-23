# AI 出行规划 Agent V2：测试架构、能力优势与版本改进

> 文档状态：Implemented and verified
> 适用分支：`codex/agent-v2-optimization` → `keykii`
> 更新日期：2026-08-21
> 关联设计：[Agent V2 技术架构](./agent_architecture_v2.md)
> 关联评测：[评测使用说明](./evaluation.md)

## 1. 版本结论

本版本不是对若干失败 Query 做逐条特判，而是把 Agent 的理解、状态、决策、工具、恢复、验证、回复和评测重新划分为可独立验证的工程层。

核心变化是：系统从“多个模块重复理解、固定流水线执行、失败后机械扩大召回”，升级为“一个权威理解结果、一个权威旅行状态、诊断驱动的有界执行、确定性结果验证”。

当前版本保留既有 LYNN 召回与排序优化、多目标 Fine Rank、路线算法、POI 服务、地图服务、`/api/chat`、流式接口和前端展示，不以重写成熟模块为代价。

截至本文更新时：

- 原有测试基线已恢复并扩展，合并前完整回归为 `276 passed`。
- 前端 TypeScript 检查和生产构建通过。
- V2 实际烟测能够返回 3 条合法路线，并包含 `planning_outcome`、`state_version` 和 `trace_id`。
- “上午 10 点开始玩 4 小时”能够识别午餐需求，实际返回的 3 条路线均包含正餐节点。

## 2. 用户此前反馈的问题与本次对应改进

| 之前的问题 | 根因 | 本版本改进 |
| --- | --- | --- |
| 明明有当前位置，仍然追问城市或起点 | 地点字段分散在请求、Intent 和 Session 中，来源优先级不统一 | `TripStateV2` 统一保存地点及来源，严格执行“用户明确地点 > 历史明确地点 > GPS > 画像 > 推断 > 默认值” |
| 用户指定“从国贸出发”后又被 GPS 覆盖 | 名称和坐标分别更新，后写入字段覆盖前值 | `LocationRef` 将名称、坐标、城市和精度合并；明确新起点会整体替换旧地点 |
| 凑不够 3 条路线时直接返回空 | 编排器把“目标 3 条”错误等同于“少于 3 条不可用” | 1～2 条经过验证的路线正常返回，并标记 `partial` |
| POI 很多但三站无解，只会扩大召回 | 没有利用路线失败原因决定恢复动作 | 诊断区分候选不足、最少站点、营业时间、预算和时长；只有候选不足才扩大召回 |
| 用户明确约束被静默放宽 | 约束没有来源和可放宽属性 | 每个字段保存 `source/confidence/relaxability/evidence`；明确预算、城市、时间和必含站点放宽前必须询问 |
| 多轮修改导致城市、人数或起点丢失 | 每轮重建完整 Intent，多个理解模块竞争写状态 | 单轮 `TurnUnderstanding` 只输出增量 Patch，纯函数 Reducer 只修改明确字段 |
| `NoneType.confidence`、`ConnectError` 暴露给用户 | 下游异常缺少统一安全映射 | 工具协议统一错误分类；回复只暴露安全信息，LLM 总结失败时使用模板结果 |
| LLM 挂掉后整条路线不可用 | 路线数据和自然语言总结耦合 | 路线计算、验证与回复分离；总结不可用时仍返回已验证路线 |
| 推荐结果无法整体判断好坏 | 评测只看最终文字或少量 Case | Eval V3 同时检查 Golden Patch、Golden State、工具选择、恢复动作、最终路线和稳定性 |
| 不知道中间哪一步出问题 | Trace 只有步骤名，失败诊断未贯穿 | Trace 展示结构化理解、状态变化、工具结果、错误码和约束拒绝统计，不展示隐藏推理 |
| 覆盖饭点却没有安排吃饭 | 饭点属于隐含需求，旧理解只提取显式偏好 | Prompt 和确定性兜底共同推断 `implicit_needs: meal`，再投影为路线必需角色；明确不吃饭时移除 |

## 3. 当前 Agent 运行架构

```text
Chat API / Stream API
        │
        ▼
AgentRuntimeRouter ── v1 / shadow / v2
        │
        ▼
TurnUnderstanding（每轮唯一理解结果）
        │  StatePatch + evidence + confidence
        ▼
State Reducer（来源优先级、增量合并）
        │
        ▼
TripStateV2 ── SQLite Snapshot + Event Log + Idempotency
        │
        ▼
Deterministic Policy
 answer / clarify / plan / replan / reject
        │
        ▼
Bounded Plan–Act–Observe Executor
        │
        ├─ resolve_location
        ├─ search_pois
        ├─ generate_routes（保留 LYNN + Fine Rank）
        ├─ diagnose_infeasibility
        ├─ relax_constraints
        ├─ replan_route
        └─ answer_route_question
        │
        ▼
OutcomeVerifier
        │
        ▼
Response Composer（LLM 或确定性模板）
```

### 3.1 唯一理解结果

`TurnUnderstanding` 在一次结构化输出中描述：

- 本轮类型：新规划、追加、修改、删除、路线问答、局部重规划等。
- 增量状态 Patch，而不是重新生成整份 Intent。
- 指代目标、歧义、字段证据和置信度。
- 饭点等少量可解释隐含需求。

规则层只负责城市、人数、金额、单位、时间和标签 taxonomy 校验，并提供 LLM 不可用时的确定性 fallback，不再与 LLM 竞争写完整状态。

### 3.2 唯一权威状态

`TripStateV2` 是 V2 内部唯一可写旅行状态。每个约束都保存：

- `value`：字段值。
- `source`：用户明确、历史明确、GPS、画像、推断或默认值。
- `confidence`：理解置信度。
- `turn_id`：来源轮次。
- `relaxability`：硬约束、询问后可放宽或软约束。
- `evidence`：支持该字段的原始证据。

SQLite 同时保存当前快照、状态事件和请求幂等结果，支持进程重启恢复、乐观锁冲突检测和事件回放。

### 3.3 有边界的工具执行

V2 不采用无限自治循环：

- 单轮最多 5 个工具步骤。
- 路线生成最多 3 次。
- 相同参数不得重复调用。
- 后续调用必须由新诊断或参数变化驱动。
- 达到预算时返回已验证的部分结果或精准追问。

工具返回统一 `ToolResult`：`success/partial/infeasible/retryable_error/fatal_error/invalid_input`，并携带诊断、耗时、错误码、重试属性和建议动作。

### 3.4 先验证，再回复

`OutcomeVerifier` 会在路线进入响应前检查：

- POI 存在性、坐标和重复节点。
- 时间顺序、总时长、预算和营业约束。
- 必含站点、必需角色和饭点角色。
- 交通腿字段完整性。

验证失败的路线不会返回给用户。自然语言回复只能读取已验证路线、未满足偏好、降级步骤和安全提示。

## 4. 测试与评测架构

### 4.1 测试金字塔

| 层级 | 验证目标 | 代表性内容 |
| --- | --- | --- |
| 单元测试 | 单个规则与纯函数正确 | 来源优先级、Reducer、Policy、Recovery、Verifier、饭点推断 |
| 契约测试 | 模块边界稳定 | 工具 Schema、SQLite Repository、V1/V2 适配、ChatResponse、流式事件 |
| 集成测试 | 主链路完整 | 理解 → 状态 → 工具 → 恢复 → 验证 → 回复 |
| 故障测试 | 依赖异常可控 | LLM 非法 JSON/超时、工具异常、SQLite 版本冲突、Case 超时 |
| 前端验证 | 新旧响应都可展示 | TypeScript、生产构建、1～3 条路线、追问、降级和错误状态 |
| 批量评测 | 产品效果可比较 | Golden Patch/State、pass@1、stable-pass@3、问题步骤和版本元数据 |

### 4.2 Eval V3 的判定链

每条评测 Case 不只判断“最后有没有路线”，而是依次观察：

1. 输入 Query 与多轮补充。
2. 本轮 Golden Patch 是否正确。
3. 合并后的 Golden State 是否只改变了应该改变的字段。
4. Policy 是否选择正确动作。
5. 工具选择和恢复动作是否符合诊断。
6. 最终路线是否通过确定性约束验证。
7. 输出、降级和 Trace 是否完整。
8. 同一 Case 重复三次是否稳定通过。

评测支持：

- 单 Case 超时，不阻塞整个批次。
- `repeat_count=1..3`。
- `pass@1` 和 `stable-pass@3`。
- 模型、Prompt、数据集、策略和代码版本记录。
- 输入、输出、中间步骤、失败码和问题步骤回放。

### 4.3 重点回归场景

- 明确起点覆盖 GPS；未明确起点使用 GPS。
- 用户在后续轮次只修改预算，城市、人数和起点保持不变。
- 缺少城市时只追问阻断字段，并先保存已确认信息。
- 51 个 POI 但三站无解时回退为两站。
- 只有 1～2 条合法路线时返回已有结果。
- 需要放宽明确预算时先追问。
- LLM 总结失败仍返回路线。
- 饭点覆盖时每条路线包含正餐；用户明确不吃饭时不强制餐饮。

## 5. 相对旧版的工程优势

### 5.1 可解释

失败能够定位到字段 Patch、状态版本、决策、工具调用或具体硬约束，而不是只能看到“没有路线”。

### 5.2 可恢复

恢复动作由失败原因决定，不再用无限扩大 POI 数量掩盖营业时间、预算或站点数问题。

### 5.3 可降级

LLM、地图或部分交通腿失败不会自动等于整个规划失败；系统优先保留已经验证的结果。

### 5.4 可回归

每项架构规则都有对应测试，批量评测能够记录模型、Prompt、数据和代码版本，使优化结果可以纵向比较。

### 5.5 可灰度

运行模式由 `AGENT_RUNTIME_VERSION` 控制：

- `v1`：继续使用旧运行时，默认安全回退。
- `shadow`：V1 返回用户结果，V2 只读执行并记录对比，不产生重复副作用。
- `v2`：使用新运行时返回结果。

这使 Agent 可以按 Shadow → 小流量 → 全量的顺序上线，并在任何门禁失败时快速回切。

### 5.6 兼容既有优化

LYNN、POI 召回、路线 Beam Search、多目标 Fine Rank、画像权重和地图能力继续作为路线工具内部策略。V2 改造的是控制面、状态面和验证面，而不是删除已经有效的算法资产。

## 6. 运行与验证

### 6.1 启动 V2

```powershell
cd backend
$env:AGENT_RUNTIME_VERSION="v2"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

### 6.2 启动 Shadow

```powershell
$env:AGENT_RUNTIME_VERSION="shadow"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

### 6.3 全量测试

```powershell
cd "D:\Document\New project"
$env:PYTHONPATH="backend;."
.\backend\.venv\Scripts\python.exe -m pytest -q
```

### 6.4 前端检查

```powershell
cd frontend
.\node_modules\.bin\tsc.cmd --noEmit
npm.cmd run build
```

## 7. 后续优化建议

1. 先使用 Shadow 评测真实 Query 分布，再决定灰度比例。
2. 将饭点、亲子、无障碍、雨天等隐含需求统一收敛为可解释 taxonomy，避免散落在 Prompt 和路线代码中。
3. 为地图部分失败增加更细的交通腿修复测试。
4. 将 Eval V3 结果接入持续集成，P0、起点优先级、硬约束保留率和未捕获异常率作为阻断门禁。
5. 定期复核模板回复和前端 Trace，保证诊断对开发可见、内部异常对用户不可见。

## 8. 合并说明

- 本版本已从 `codex/agent-v2-optimization` 合并回 `keykii`。
- 默认配置仍为 `v1`，不会因为合并自动全量开启 V2。
- 当前本地验证服务可用环境变量临时启用 V2。
- 合并保留 LYNN 及当前工作区已有优化，不执行 reset 或覆盖式 checkout。
