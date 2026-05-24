import type { AgentTraceStep } from "../api/types";

export interface AgentThinkingSummary {
  headline: string;
  statusText: string;
  items: string[];
  issueCount: number;
}

const STEP_SUMMARY: Record<string, string> = {
  route_message: "正在判断这句话属于新规划、补充需求还是路线追问",
  parse_intent: "正在把自然语言整理成路线规划意图",
  apply_session_context: "正在继承上一轮的城市、人数、时长和主场景",
  apply_query_delta: "正在合并本轮新增或修改的旅行状态",
  get_user_profile: "正在读取你的偏好画像",
  build_strategy_weights: "正在把偏好转换成路线排序权重",
  search_pois: "正在召回可选地点",
  generate_routes: "正在生成候选路线",
  summarize_routes: "正在根据结构化路线生成回复",
  direct_llm_chat: "识别为非路线问题并直接回复",
};

const FIELD_LABELS: Record<string, string> = {
  city: "城市",
  people_count: "人数",
  start_time: "开始时间",
  duration_hours: "时长",
  budget_per_person: "预算",
  scenario: "场景",
  meal_stop: "吃饭节点",
  rest_stop: "休息节点",
};

export function buildThinkingSummary(steps: AgentTraceStep[], loading = false): AgentThinkingSummary {
  if (loading && steps.length === 0) {
    return {
      headline: "Agent 思考过程",
      statusText: "正在理解需求",
      items: ["先判断你的需求类型", "再结合已有出行状态决定是否重规划"],
      issueCount: 0,
    };
  }

  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const items = steps
    .map((step) => summarizeStep(step))
    .filter((item, index, list) => item && list.indexOf(item) === index)
    .slice(0, 4);

  return {
    headline: "Agent 思考过程",
    statusText: issueCount > 0 ? `${issueCount} 项需要关注` : `已记录 ${steps.length} 个处理步骤`,
    items,
    issueCount,
  };
}

function summarizeStep(step: AgentTraceStep): string {
  const detailed = summarizeDetails(step);
  if (detailed) return detailed;

  if (step.step === "apply_query_delta" || step.step === "apply_session_context") {
    return humanizeLabel(step.label);
  }
  return STEP_SUMMARY[step.step] ?? humanizeLabel(step.label);
}

function summarizeDetails(step: AgentTraceStep): string | null {
  const details = step.details;
  if (!details) return null;

  if (step.step === "route_message") {
    const turnType = asText(details.turn_type_label) || asText(details.intent_type_label);
    const parts = turnType ? [`判定为：${turnType}`] : [humanizeLabel(step.label)];
    if (details.inherit_previous === true) parts.push("继承上一轮出行上下文");
    if (details.preserve_scenario === true) parts.push("保留原来的出行场景");
    if (details.references_previous_route === true) parts.push("会基于上一轮路线回答");
    const confidence = asNumber(details.confidence);
    if (confidence !== null) parts.push(`置信度 ${Math.round(confidence * 100)}%`);
    return parts.join("，");
  }

  if (step.step === "parse_intent" || step.step === "apply_session_context") {
    return formatIntentDetails(details, step.step === "apply_session_context" ? "继承后状态" : "理解结果");
  }

  if (step.step === "apply_query_delta") {
    const parts: string[] = [];
    const kept = asTextList(details.kept).map(labelValue);
    const added = asTextList(details.added).map(labelValue);
    const removed = asTextList(details.removed).map(labelValue);
    const changed = formatChanged(details.changed);
    if (kept.length) parts.push(`保留：${kept.join("、")}`);
    if (added.length) parts.push(`新增：${added.join("、")}`);
    if (changed.length) parts.push(`修改：${changed.join("、")}`);
    if (removed.length) parts.push(`移除：${removed.join("、")}`);
    return parts.join("；") || humanizeLabel(step.label);
  }

  if (step.step === "get_user_profile") {
    const preferences = asTextList(details.preferences);
    const avoidTags = asTextList(details.avoid_tags);
    const parts: string[] = [];
    if (preferences.length) parts.push(`画像偏好：${preferences.slice(0, 4).join("、")}`);
    if (avoidTags.length) parts.push(`避开：${avoidTags.slice(0, 3).join("、")}`);
    return parts.join("；") || "没有额外画像偏好";
  }

  if (step.step === "build_strategy_weights") {
    const weights = isRecord(details.weights) ? details.weights : details;
    const topWeights = Object.entries(weights)
      .filter(([, value]) => typeof value === "number")
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 2)
      .map(([key]) => labelValue(key));
    return topWeights.length ? `本轮优先考虑：${topWeights.join("、")}` : null;
  }

  if (step.step === "search_pois") {
    const count = asNumber(details.count);
    const names = asTextList(details.names).slice(0, 3);
    if (count !== null && names.length) return `召回 ${count} 个候选点：${names.join("、")}`;
    if (count !== null) return `召回 ${count} 个候选点`;
  }

  if (step.step === "generate_routes") {
    const count = asNumber(details.count);
    const titles = asTextList(details.route_titles).slice(0, 2);
    if (count !== null && titles.length) return `生成 ${count} 条候选路线：${titles.join("、")}`;
    if (count !== null) return `生成 ${count} 条候选路线`;
  }

  return null;
}

function formatIntentDetails(details: Record<string, unknown>, prefix: string): string {
  const city = asText(details.city);
  const people = asNumber(details.people_count);
  const duration = asNumber(details.duration_hours);
  const preferences = asTextList(details.preferences).slice(0, 3);
  const parts: string[] = [];
  if (city) parts.push(city);
  if (people !== null) parts.push(`${people}人`);
  if (duration !== null) parts.push(`${duration}小时`);
  if (preferences.length) parts.push(`偏好${preferences.join("、")}`);
  return parts.length ? `${prefix}：${parts.join("、")}` : prefix;
}

function formatChanged(value: unknown): string[] {
  if (!isRecord(value)) return [];
  return Object.entries(value).map(([field, change]) => {
    if (!isRecord(change)) return labelValue(field);
    return `${labelValue(field)} ${String(change.from ?? "")} -> ${String(change.to ?? "")}`;
  });
}

function humanizeLabel(label: string): string {
  let result = label;
  for (const [key, value] of Object.entries(FIELD_LABELS)) {
    result = result.split(key).join(value);
  }
  return result;
}

function labelValue(value: string): string {
  return FIELD_LABELS[value] ?? value;
}

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
