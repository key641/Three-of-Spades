export interface AgentTraceStep {
  step: string;
  label: string;
  status: string;
}

export interface RouteStop {
  poi_id: string;
  name: string;
  category: string;
  district?: string;
  address?: string;
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
  reason?: string | null;
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
  preferences?: string[];
  avoid_tags?: string[];
  [key: string]: unknown;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  need_clarification: boolean;
  clarifying_question?: string | null;
  intent?: Record<string, unknown> | null;
  user_profile?: UserProfile | null;
  routes: Route[];
  agent_trace: AgentTraceStep[];
}
