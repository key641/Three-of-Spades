export interface AgentTraceStep {
  step: string;
  label: string;
  status: string;
  details?: Record<string, unknown>;
}

export interface ClarificationOption {
  id: string;
  label: string;
  value?: Record<string, unknown>;
}

export interface ClarificationGroup {
  id: string;
  title: string;
  required: boolean;
  options: ClarificationOption[];
}

export interface RouteStop {
  poi_id: string;
  name: string;
  category: string;
  district?: string;
  business_area?: string;
  address?: string;
  lat?: number | null;
  lng?: number | null;
  start_time: string;
  end_time: string;
  estimated_cost: number;
  queue_minutes: number;
  tags: string[];
  meal_type?: string;
  open_hours?: string;
  last_entry_time?: string;
  walking_intensity?: string;
  cover_image_url?: string;
  highlight_text?: string;
  ugc_tip?: string;
  indoor?: boolean;
  recommended_transport?: string[];
  travel_minutes_from_previous?: number | null;
  distance_km_from_previous?: number | null;
  transport_mode_from_previous?: string | null;
  polyline_from_previous?: string;
  amap_distance_meters_from_previous?: number | null;
  amap_duration_minutes_from_previous?: number | null;
  route_leg_source_from_previous?: string | null;
  route_steps_from_previous?: string[];
  reason?: string | null;

  // ── POI 卡片展示字段 ────────────────────────────────
  /** 美团综合评分，如 4.8 */
  rating?: number;
  /** 评论总数，如 3200 */
  review_count?: number;
  /** 榜单标签，如 "必吃榜 Top 5"、"必玩榜 No.3" */
  rank_label?: string;
  /** 一句话简介 / 编辑推荐语 */
  brief?: string;
  /** 距离（米），相对于用户出发点 */
  distance_m?: number;

  // ── 实时/预测排队 ────────────────────────────────
  /**
   * 排队程度（枚举）：
   * "none"   = 无需排队
   * "low"    = 较少（＜15 分钟）
   * "medium" = 一般（15–30 分钟）
   * "high"   = 较多（30–60 分钟）
   * "very_high" = 非常多（＞60 分钟）
   */
  queue_level?: "none" | "low" | "medium" | "high" | "very_high";

  // ── 到下一站的交通段 ─────────────────────────────
  /** 到下一个站点的交通信息（最后一站无此字段） */
  transit_to_next?: TransitSegment;

  // ── 预约信息 ─────────────────────────────────
  /** 是否需要预约 */
  booking_required?: boolean;
  /** 小程序/网页预约链接（有则展示跳转按钮） */
  booking_url?: string;
  /** 电话预约号码 */
  booking_phone?: string;
  /** 预约备注，如"建议提前1天预约" */
  booking_note?: string;
}

/** 两站之间的交通连接信息 */
export interface TransitSegment {
  /** 交通方式：walk / metro / bus / taxi / bike */
  mode: "walk" | "metro" | "bus" | "taxi" | "bike";
  /** 预计耗时（分钟） */
  duration_minutes: number;
  /** 距离（米） */
  distance_m: number;
  /** 路线简述，如 "地铁 1 号线→2 号线换乘" */
  description?: string;
}

export interface RouteScoreBreakdown {
  quality: number;
  queue: number;
  budget: number;
  distance: number;
  preference: number;
}

export interface Route {
  route_id: string;
  title: string;
  objective: string;
  summary: string;
  total_duration_minutes: number;
  total_cost_per_person: number;
  total_queue_minutes: number;
  total_travel_minutes?: number;
  total_distance_km?: number;
  score: number;
  score_breakdown: RouteScoreBreakdown;
  stops: RouteStop[];
  reasons: string[];
  replan_reason?: string | null;
  changed_stops?: Array<{
    change_type: string;
    from_poi_id?: string | null;
    from_name?: string | null;
    to_poi_id?: string | null;
    to_name?: string | null;
    reason: string;
  }>;
  live_warnings?: string[];
  data_sources?: string[];
}

export interface UserProfile {
  user_id?: string;
  tags?: string[];
  preferences?: string[];
  interest_tags?: string[];
  optimization_goals?: string[];
  avoid_tags?: string[];
  preference_weights?: Record<string, number>;
  budget_sensitivity?: number;
  walking_tolerance?: number;
  crowd_tolerance?: number;
  schedule_tightness?: number;
  novelty_preference?: number;
  comfort_preference?: number;
  category_preferences?: Record<string, number>;
  preferred_route_roles?: string[];
  preferred_experience_tags?: string[];
  preferred_time_slots?: string[];
  preferred_transport_modes?: string[];
  liked_poi_ids?: string[];
  disliked_poi_ids?: string[];
  skipped_categories?: string[];
  common_adjust_actions?: string[];
  [key: string]: unknown;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  need_clarification: boolean;
  clarifying_question?: string | null;
  clarification_type?: string | null;
  clarification_groups?: ClarificationGroup[];
  inferred_context?: Record<string, unknown>;
  intent?: Record<string, unknown> | null;
  user_profile?: UserProfile | null;
  routes: Route[];
  agent_trace: AgentTraceStep[];
}

export type ChatStreamEvent =
  | { type: "progress"; step: AgentTraceStep }
  | { type: "routes"; routes: Route[] }
  | { type: "final"; response: ChatResponse }
  | { type: "error"; message: string };
