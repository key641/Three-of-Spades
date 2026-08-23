import type { AgentTraceStep } from "../api/types";

export interface AgentThinkingSummary {
  headline: string;
  statusText: string;
  items: string[];
  issueCount: number;
}

const STEP_SUMMARY: Record<string, string> = {
  route_message: "正在理解你的需求",
  clarify_intent: "有一项关键信息想和你确认",
  parse_intent: "正在整理这次出行的关键信息",
  apply_session_context: "已结合你前面提到的出行安排",
  apply_query_delta: "已更新这次出行的要求",
  get_user_profile: "正在参考你的游玩偏好",
  build_strategy_weights: "正在按你的偏好挑选方案",
  search_pois: "正在寻找合适的地点",
  generate_routes: "正在组合可行的游玩方案",
  summarize_routes: "正在整理推荐结果",
  direct_llm_chat: "正在为你准备回复",
};

const NEXT_STEP_HINTS: Record<string, string> = {
  route_message: "正在思考",
  parse_intent: "正在思考",
  apply_session_context: "正在思考",
  apply_query_delta: "正在思考",
  get_user_profile: "正在思考",
  build_strategy_weights: "正在思考",
  search_pois: "正在思考",
  generate_routes: "正在思考",
  summarize_routes: "正在思考",
  clarify_intent: "正在思考",
  direct_llm_chat: "正在思考",
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
    headline: "正在帮你规划",
    statusText: "正在理解你的需求",
    items: ["整理你的出行要求", "结合前面的安排给出合适建议"],
      issueCount: 0,
    };
  }

  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const items = steps
    .map((step) => summarizeStep(step))
    .filter((item, index, list) => item && list.indexOf(item) === index)
    .slice(0, 4);

  return {
    headline: "正在帮你规划",
    statusText: issueCount > 0 ? "规划时遇到一点问题，正在换一种方式处理" : "规划完成", 
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
  if (!last) return "正在思考";
  if (last.status === "fallback" || last.status === "error") return "正在整理结果…";
  return NEXT_STEP_HINTS[last.step] ?? "正在思考";
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

/**
 * 将 agent trace steps 串联成自然语言叙述句子数组，供前端逐行渲染。
 * 每个元素是一个思考步骤的自然语言描述。
 */
export function buildNarrativeSentences(steps: AgentTraceStep[], userInput?: string): string[] {
  const sentences: string[] = [];

  // 1. 用户输入开场
  if (userInput && userInput.trim()) {
    sentences.push(`用户说「${userInput.trim()}」`);
  }

  for (const step of steps) {
    const d = step.details ?? {};

    // ── 意图路由 ────────────────────────────────────────────
    if (step.step === "route_message") {
      const turnLabel = asText(d.turn_type_label) ?? asText(d.intent_type_label);
      const evidence = asText(d.evidence);
      const reason = asText(d.reason);

      const parts: string[] = [];
      if (reason) parts.push(reason);
      if (turnLabel) parts.push(`我会按「${turnLabel}」来帮你安排`);
      if (d.inherit_previous === true) parts.push("会结合你前面说过的安排");
      if (d.preserve_scenario === true) parts.push("保留原来的出行主题");
      if (!parts.length && evidence) parts.push("已理解你刚刚的需求");

      if (parts.length) sentences.push(parts.join("，"));
      continue;
    }

    // ── 意图解析 ────────────────────────────────────────────
    if (step.step === "parse_intent" || step.step === "apply_session_context") {
      const city = asText(d.city);
      const people = asNumber(d.people_count);
      const duration = asNumber(d.duration_hours);
      const budget = asNumber(d.budget_per_person);
      const startTime = asText(d.start_time);
      const explicitConditions: string[] = [];
      if (city) explicitConditions.push(city);
      if (people !== null) explicitConditions.push(`${people}人`);
      if (startTime) explicitConditions.push(`${startTime}出发`);
      if (duration !== null) explicitConditions.push(`${duration}小时`);
      if (budget !== null) explicitConditions.push(`人均${budget}元`);

      // 解析出的 scenario / preferences 既可能来自用户原话，也可能来自档案与默认策略；
      // 它们会在「用户偏好」步骤单独说明，避免误导为本轮明确输入。
      if (explicitConditions.length) {
        const prefix = step.step === "apply_session_context" ? "我会沿用这些出行条件" : "已确认这次的出行条件";
        sentences.push(`${prefix}：${explicitConditions.join(" · ")}`);
      }
      continue;
    }

    // ── 状态变更 ────────────────────────────────────────────
    if (step.step === "apply_query_delta") {
      const kept = asTextList(d.kept);
      const added = asTextList(d.added);
      const removed = asTextList(d.removed);
      const changed = isRecord(d.changed) ? Object.keys(d.changed) : [];

      const parts: string[] = [];
      if (kept.length) parts.push(`保留 ${kept.map(labelValue).join("、")}`);
      if (added.length) parts.push(`新增 ${added.map(labelValue).join("、")}`);
      if (changed.length) parts.push(`修改 ${changed.map(labelValue).join("、")}`);
      if (removed.length) parts.push(`移除 ${removed.map(labelValue).join("、")}`);

      if (parts.length) sentences.push(`我已按你的新想法调整：${parts.join("；")}`);
      continue;
    }

    // ── 用户画像 ────────────────────────────────────────────
    if (step.step === "get_user_profile") {
      const preferences = asTextList(d.preferences).map(labelValue).slice(0, 4);
      const avoidTags = asTextList(d.avoid_tags).map(labelValue).slice(0, 3);
      const parts: string[] = [];
      if (preferences.length) parts.push(`长期偏好：${preferences.join("、")}`);
      if (avoidTags.length) parts.push(`尽量避开：${avoidTags.join("、")}`);
      if (parts.length) sentences.push(`我会参考你的用户档案：${parts.join("；")}`);
      else sentences.push("你的用户档案中暂时没有额外偏好，本次会按当前需求推荐");
      continue;
    }

    // ── 策略权重 ────────────────────────────────────────────
    if (step.step === "build_strategy_weights") {
      sentences.push("正在按你的偏好挑选更合适的方案");
      continue;
    }

    // ── 召回 POI ────────────────────────────────────────────
    if (step.step === "search_pois") {
      const names = asTextList(d.names).slice(0, 4);
      const nameStr = names.length ? `（含 ${names.join("、")} 等）` : "";
      sentences.push(`正在挑选合适的地点${nameStr}`);
      continue;
    }

    // ── 生成路线 ────────────────────────────────────────────
    if (step.step === "generate_routes") {
      const titles = asTextList(d.route_titles).slice(0, 3);
      const titleStr = titles.length ? `：${titles.join("、")}` : "";
      sentences.push(`已整理出可选方案${titleStr}`);
      continue;
    }

    // ── 追问 ────────────────────────────────────────────────
    if (step.step === "clarify_intent") {
      const missing = asText(d.missing_field);
      const question = asText(d.question);
      if (missing) sentences.push(`还想确认一下${labelValue(missing)}，这样安排会更准确`);
      else if (question) sentences.push(`还想和你确认：${question}`);
      else sentences.push("还想确认一项出行信息，方便给你更合适的建议");
      continue;
    }

    // ── 直接回复 ────────────────────────────────────────────
    if (step.step === "direct_llm_chat") {
      sentences.push("正在为你准备回复");
      continue;
    }

    // ── 兜底：用 label（fallback/error 步骤静默，不展示内部错误）───────────
    if (step.status === "fallback" || step.status === "error") continue;
    if (step.label && step.label.trim()) {
      sentences.push(humanizeLabel(step.label));
    }
  }

  return sentences;
}

/**
 * 将 agent trace steps 串联成一段自然语言叙述，供用户阅读。
 * 格式例：用户说「…」→ 依据原话「…」，判定为新规划 → 出行状态：上海 · 2人 … → 筛选周边候选地点 → 生成候选路线。
 */
export function buildNarrativeText(steps: AgentTraceStep[], userInput?: string): string {
  return buildNarrativeSentences(steps, userInput).join(" → ");
}
