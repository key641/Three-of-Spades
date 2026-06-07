import { AlertTriangle, BrainCircuit, CheckCircle, Loader } from "lucide-react";
import { useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { buildThinkingSummary, getLiveProgressLabel } from "../utils/agentThinking";
import { STEP_ICONS } from "../utils/traceIcons";

interface AgentTraceProps {
  steps: AgentTraceStep[];
  loading?: boolean;
}

export function AgentTrace({ steps, loading = false }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const hasIssue = issueCount > 0;
  const thinking = buildThinkingSummary(steps, loading);
  const liveProgressLabel = getLiveProgressLabel(steps);

  // 没有数据且不在加载时，不渲染
  if (!loading && steps.length === 0) return null;

  return (
    <div className="trace-panel">
      {/* 折叠切换按钮 */}
      <button
        className="trace-toggle"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        {loading ? (
          <>
            <Loader size={14} style={{ animation: "spin 1s linear infinite" }} />
            <span>{thinking.headline}</span>
            <span className="trace-summary-status">实时更新中</span>
          </>
        ) : (
          <>
            {hasIssue ? (
              <AlertTriangle size={14} style={{ color: "#92400E" }} />
            ) : (
              <CheckCircle size={14} style={{ color: "var(--color-success)" }} />
            )}
            <span>{thinking.headline}</span>
            <span className={hasIssue ? "trace-summary-status is-warning" : "trace-summary-status"}>
              {thinking.statusText}
            </span>
            <span style={{ marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
          </>
        )}
      </button>

      {(loading || expanded) && (
        <div className="trace-thinking">
          <div className="trace-thinking-title">
            <BrainCircuit size={15} />
            <span>{loading ? "正在组织路线思路" : thinking.statusText}</span>
          </div>
          <div className="trace-thinking-list">
            {thinking.items.map((item) => (
              <span className="trace-thinking-item" key={item}>
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 步骤列表 */}
      {(expanded || loading) && (
        <div className="trace-list">
          {steps.map((step, i) => (
            <div
              className="trace-item"
              key={step.step}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <span className="trace-icon">
                {STEP_ICONS[step.step] ?? "⚙️"}
              </span>
              <span className="trace-content">
                <span className="trace-label">{formatTraceLabel(step.label)}</span>
                <TraceDetails details={step.details} />
              </span>
              <span className={`trace-status status-${step.status}`}>
                {labelStatus(step.status)}
              </span>
            </div>
          ))}

          {/* loading 时末尾显示一个占位行 */}
          {loading && (
            <div className="trace-item" style={{ animationDelay: `${steps.length * 60}ms` }}>
              <span className="trace-icon">
                <Loader size={14} style={{ animation: "spin 1s linear infinite" }} />
              </span>
              <span className="trace-content">
                <span className="trace-label" style={{ color: "var(--color-muted)" }}>
                  {liveProgressLabel}
                </span>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TraceDetails({ details }: { details?: Record<string, unknown> }) {
  if (!details || Object.keys(details).length === 0) return null;

  const items = formatTraceDetails(details)
    .slice(0, 12);

  if (items.length === 0) return null;

  return (
    <div className="trace-detail-grid">
      {items.map((item) => (
        <span className="trace-detail-chip" key={`${item.key}:${item.value}`}>
          <span className="trace-detail-key">{item.label}</span>
          <span className="trace-detail-value">{item.value}</span>
        </span>
      ))}
    </div>
  );
}

interface DetailItem {
  key: string;
  label: string;
  value: string;
}

function formatTraceDetails(details: Record<string, unknown>): DetailItem[] {
  const hasLabelValue = new Set(Object.keys(details));
  const seen = new Set<string>();
  return flattenDetails(details)
    .filter((item) => isMeaningfulDetail(item.value))
    .filter((item) => !isDuplicateMachineField(item, hasLabelValue, details))
    .map((item) => ({
      key: item.key,
      label: labelDetailKey(item.key),
      value: item.value,
    }))
    .filter((item) => {
      const signature = `${item.label}:${item.value}`;
      if (seen.has(signature)) return false;
      seen.add(signature);
      return true;
    });
}

function flattenDetails(details: Record<string, unknown>, prefix = ""): Array<{ key: string; value: string }> {
  return Object.entries(details).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(value)) {
      return [{ key: nextKey, value: value.map((item) => formatDetailValue(item, nextKey)).join("、") }];
    }
    if (isRecord(value)) {
      if (Object.keys(value).length === 0) return [{ key: nextKey, value: "" }];
      if (isChangeObject(value)) {
        return [{ key: nextKey, value: formatChangeObject(value, nextKey) }];
      }
      const simpleEntries = Object.entries(value).filter(([, child]) => !isRecord(child) && !Array.isArray(child));
      if (simpleEntries.length === Object.keys(value).length) {
        return [
          {
            key: nextKey,
            value: simpleEntries
              .map(([childKey, child]) => `${labelDetailKey(childKey)}：${formatDetailValue(child, childKey)}`)
              .join("、"),
          },
        ];
      }
      return flattenDetails(value, nextKey);
    }
    return [{ key: nextKey, value: formatDetailValue(value, nextKey) }];
  });
}

function isMeaningfulDetail(value: string): boolean {
  const trimmed = value.trim();
  return trimmed !== "" && trimmed !== "[]" && trimmed !== "{}";
}

function isDuplicateMachineField(item: { key: string; value: string }, topLevelKeys: Set<string>, details: Record<string, unknown>): boolean {
  const key = item.key;
  if (key === "intent_type" && topLevelKeys.has("intent_type_label")) return true;
  if (key === "turn_type" && topLevelKeys.has("turn_type_label")) return true;
  if (key === "delta.target_route_ref" && topLevelKeys.has("target_route_ref")) return true;
  if (key === "delta.target_stop_ref" && topLevelKeys.has("target_stop_ref")) return true;
  if (key === "tags" && Array.isArray(details.preferences) && details.preferences.map(String).join("、") === item.value) return true;
  return false;
}

function isChangeObject(value: Record<string, unknown>): boolean {
  return Object.keys(value).length > 0 && Object.values(value).every((item) => isRecord(item) && ("from" in item || "to" in item));
}

function formatChangeObject(value: Record<string, unknown>, key: string): string {
  return Object.entries(value)
    .map(([field, change]) => {
      if (!isRecord(change)) return `${labelDetailKey(field)}：${formatDetailValue(change, field)}`;
      const from = formatDetailValue(change.from, field);
      const to = formatDetailValue(change.to, field);
      return `${labelDetailKey(field)}：${from || "未设置"}改为${to || "未设置"}`;
    })
    .join("、") || formatDetailValue(value, key);
}

function formatDetailValue(value: unknown, key = ""): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") {
    if (key.endsWith("confidence")) return `${Math.round(value * 100)}%`;
    return String(value);
  }
  if (typeof value === "string") return labelDetailValue(key, value);
  return JSON.stringify(value);
}

function labelDetailKey(key: string): string {
  const labels: Record<string, string> = {
    added_hard_constraints: "新增硬性条件",
    modified_hard_constraints: "修改硬性条件",
    removed_hard_constraints: "移除硬性条件",
    added_preferences: "新增偏好",
    removed_preferences: "移除偏好",
    interest_tags: "兴趣",
    optimization_goals: "优化目标",
    added_avoid_tags: "新增避开项",
    removed_avoid_tags: "移除避开项",
    added_implicit_needs: "新增隐含需求",
    removed_implicit_needs: "移除隐含需求",
    added_must_include: "新增必选安排",
    removed_must_include: "移除必选安排",
    intent_type: "意图类型",
    intent_type_label: "意图",
    turn_type: "本轮类型",
    turn_type_label: "本轮类型",
    planning_mode: "规划方式",
    candidate_planning_modes: "可能的规划方式",
    clarification_type: "澄清类型",
    missing_field: "缺少信息",
    priority: "优先级",
    question: "追问问题",
    can_continue_with_defaults: "能否默认继续",
    candidate_intents: "候选意图",
    inherit_previous: "继承上轮",
    preserve_scenario: "保留场景",
    references_previous_route: "引用路线",
    confidence: "置信度",
    raw_confidence: "原始置信度",
    confidence_source: "置信度来源",
    confidence_reasons: "置信度说明",
    reason: "判断理由",
    evidence: "依据原话",
    source: "来源",
    kept: "保留",
    added: "新增",
    changed: "修改",
    removed: "移除",
    preferences: "偏好",
    soft_preferences: "旧版偏好",
    avoid_tags: "避开",
    names: "候选点",
    count: "数量",
    route_titles: "路线",
    objectives: "目标",
    delta: "变更",
    city: "城市",
    people_count: "人数",
    start_time: "出发时间",
    duration_hours: "时长",
    budget_per_person: "人均预算",
    scenario: "出行场景",
    target_route_ref: "目标路线",
    target_stop_ref: "目标站点",
    question_type: "问题类型",
    event_type: "事件类型",
    event_label: "事件说明",
    current_poi_id: "当前地点",
    selected_route_id: "选中路线",
    route_id: "路线编号",
    user_id: "用户",
    tags: "画像标签",
    budget_sensitivity: "预算敏感度",
    walking_tolerance: "步行耐受",
    crowd_tolerance: "人群耐受",
    schedule_tightness: "节奏偏好",
    novelty_preference: "新鲜感偏好",
    comfort_preference: "舒适度偏好",
    category_preferences: "品类偏好",
    preferred_route_roles: "路线结构偏好",
    preferred_experience_tags: "体验偏好",
    preferred_time_slots: "时段偏好",
    preferred_transport_modes: "交通偏好",
    liked_poi_ids: "喜欢的地点",
    disliked_poi_ids: "不喜欢的地点",
    skipped_categories: "跳过的品类",
    common_adjust_actions: "常见调整",
    weights: "权重",
    quality: "品质",
    queue: "排队",
    budget: "预算",
    distance: "距离",
    preference: "偏好",
  };
  const parts = key.split(".");
  const lastKey = parts[parts.length - 1] ?? key;
  return labels[key] ?? labels[lastKey] ?? fallbackDetailLabel(lastKey);
}

function labelDetailValue(key: string, value: string): string {
  const valueLabels: Record<string, string> = {
    new_plan: "新规划",
    modify_plan: "修改已有路线",
    replan: "局部重规划",
    route_detail_question: "路线追问",
    general_chat: "普通聊天",
    add_constraint: "补充需求",
    modify_constraint: "修改条件",
    remove_constraint: "移除条件",
    route_detail: "路线追问",
    full_replan: "全量重规划",
    partial_replan: "局部重规划",
    missing_required_field: "缺少必要信息",
    intent_disambiguation: "确认意图",
    required: "必要信息",
    routing: "意图路由",
    "后端校准": "后端校准",
    "LLM 返回": "LLM 返回",
    "规则兜底": "规则兜底",
    current: "当前路线",
    llm_structured_delta: "LLM 结构化解析",
    rule_fallback_delta: "规则兜底解析",
    initial_intent_snapshot: "初始意图记录",
    amap: "高德地图",
    mock: "模拟数据",
    fallback: "兜底结果",
    route_modify: "路线修改",
    route_modify_place_replace: "替换路线中的一个地点",
    restaurant_alternative_short_wait: "等待时间短的餐厅替代方案",
    half_day_tour: "半日游",
    city_day_trip: "城市一日游",
    friends_citywalk: "朋友 Citywalk",
    foodie_tour: "美食路线",
    balanced: "综合平衡",
    low_queue: "少排队优先",
    budget_saver: "省钱优先",
    food_first: "美食优先",
    photo_citywalk: "拍照 Citywalk",
    indoor_rainy: "室内雨天",
    walk_light: "少走路",
    metro: "地铁",
    bus: "公交",
    taxi: "打车",
    walk: "步行",
    city: "城市",
    people_count: "人数",
    start_time: "出发时间",
    duration_hours: "时长",
    budget_per_person: "人均预算",
    scenario: "出行场景",
    route_titles: "路线标题",
    target_route_ref: "目标路线",
    target_stop_ref: "目标站点",
    meal_stop: "安排用餐",
    rest_stop: "安排休息",
    replace_poi: "替换地点",
    queue_spike: "排队变长",
    traffic_jam: "交通拥堵",
    weather_change: "天气变化",
    user_tired: "用户疲劳",
    poi_closed: "地点关闭",
  };

  if (key.endsWith("duration_hours") && /^\d+$/.test(value)) return `${value} 小时`;
  if (key.endsWith("budget_per_person") && /^\d+$/.test(value)) return `${value} 元/人`;
  if (key.endsWith("confidence")) return value === "0" ? "0%" : value;
  return valueLabels[value] ?? value;
}

function formatTraceLabel(label: string): string {
  const replacements: Record<string, string> = {
    intent_type: "意图类型",
    intent_type_label: "意图",
    turn_type: "本轮类型",
    turn_type_label: "本轮类型",
    planning_mode: "规划方式",
    candidate_planning_modes: "可能的规划方式",
    confidence_source: "置信度来源",
    confidence_reasons: "置信度说明",
    reason: "判断理由",
    evidence: "依据原话",
    city: "城市",
    people_count: "人数",
    start_time: "出发时间",
    duration_hours: "时长",
    budget_per_person: "人均预算",
    scenario: "出行场景",
    target_route_ref: "目标路线",
    target_stop_ref: "目标站点",
    meal_stop: "用餐安排",
    rest_stop: "休息安排",
    llm_structured_delta: "LLM 结构化解析",
    rule_fallback_delta: "规则兜底解析",
    initial_intent_snapshot: "初始意图记录",
  };
  return Object.entries(replacements).reduce(
    (result, [raw, translated]) => result.split(raw).join(translated),
    label,
  );
}

function fallbackDetailLabel(key: string): string {
  if (!/[A-Za-z_]/.test(key)) return key;
  return "补充信息";
}

function labelStatus(status: string): string {
  const labels: Record<string, string> = {
    done: "完成",
    fallback: "兜底",
    error: "异常",
  };
  return labels[status] ?? status;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
