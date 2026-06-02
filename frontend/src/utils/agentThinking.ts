import type { AgentTraceStep } from "../api/types";

export interface AgentThinkingSummary {
  headline: string;
  statusText: string;
  items: string[];
  issueCount: number;
}

const STEP_SUMMARY: Record<string, string> = {
  route_message: "正在判断这句话属于新规划、补充需求还是路线追问",
  clarify_intent: "发现需求还不够清晰，正在准备一个轻量追问",
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

const NEXT_STEP_HINTS: Record<string, string> = {
  route_message: "等待后端解析结构化出行需求",
  parse_intent: "等待后端合并上一轮上下文",
  apply_session_context: "等待后端确认本轮状态变化",
  apply_query_delta: "等待后端读取用户画像",
  get_user_profile: "等待后端生成偏好权重",
  build_strategy_weights: "等待后端召回候选地点",
  search_pois: "等待后端生成候选路线",
  generate_routes: "等待后端总结路线方案",
  summarize_routes: "等待最终回复返回",
  clarify_intent: "等待澄清问题返回",
  direct_llm_chat: "等待最终回复返回",
};

const FIELD_LABELS: Record<string, string> = {
  city: "城市",
  people_count: "人数",
  start_time: "出发时间",
  duration_hours: "时长",
  budget_per_person: "人均预算",
  scenario: "出行场景",
  target_route_ref: "目标路线",
  target_stop_ref: "目标站点",
  intent_type: "意图类型",
  turn_type: "本轮类型",
  planning_mode: "规划方式",
  candidate_planning_modes: "可能的规划方式",
  raw_confidence: "原始置信度",
  confidence_source: "置信度来源",
  confidence_reasons: "置信度说明",
  reason: "判断理由",
  evidence: "依据原话",
  clarification_type: "澄清类型",
  missing_field: "缺少信息",
  priority: "优先级",
  question: "追问问题",
  can_continue_with_defaults: "能否默认继续",
  candidate_intents: "候选意图",
  meal_stop: "用餐安排",
  rest_stop: "休息安排",
  llm_structured_delta: "LLM 结构化解析",
  rule_fallback_delta: "规则兜底解析",
  initial_intent_snapshot: "初始意图记录",
  quality: "品质",
  queue: "排队",
  budget: "预算",
  distance: "距离",
  preference: "偏好",
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
    current: "当前路线",
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
  };
  return FIELD_LABELS[value] ?? valueLabels[value] ?? value;
}

export function getLiveProgressLabel(steps: AgentTraceStep[]): string {
  const last = steps[steps.length - 1];
  if (!last) return "正在等待后端开始处理";
  if (last.status === "fallback") return "后端正在使用兜底逻辑继续处理";
  if (last.status === "error") return "后端处理遇到异常，正在收尾";
  return NEXT_STEP_HINTS[last.step] ?? "等待后端返回下一步进度";
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
