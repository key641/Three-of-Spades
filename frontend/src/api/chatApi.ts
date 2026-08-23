import { API_BASE_URL, postJson } from "./client";
import type { OnboardingProfile, TripConstraints } from "../hooks/useOnboarding";
import type { AgentTraceStep, ChatResponse, ChatStreamEvent, RouteStop } from "./types";

// 真实联调默认走后端；如需离线调试，可临时改为 true。
const USE_MOCK = false;
const SESSION_STORAGE_KEY = "tos_chat_session_id";


export function getChatSessionId() {
  if (typeof window === "undefined") return "session_demo";
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const generated = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  localStorage.setItem(SESSION_STORAGE_KEY, generated);
  return generated;
}

/** 切换到指定会话；恢复历史行程后，后续追问将继续写入同一会话。 */
export function setChatSessionId(sessionId: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

export function resetChatSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

// 模拟网络延迟
function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// 完整的 Mock 响应，覆盖所有 UI 字段
function buildMockResponse(message: string): ChatResponse {
  const isRoute = message.length > 15 || /路线|citywalk|吃|玩|去|逛|今晚|上海|北京|广州|深圳|杭州|成都|南京|武汉|西安|重庆|厦门|周末|半天|一天|规划|安排|推荐/.test(message);

  if (!isRoute) {
    // 普通对话模式
    return {
      session_id: "mock_session",
      message: `收到你的消息「${message}」！你可以试着发送「上海半天 citywalk，2人，预算200」，我会为你规划完整路线 🗺️`,
      need_clarification: false,
      routes: [],
      agent_trace: [
        { step: "direct_llm_chat", label: "直接 LLM 对话", status: "done" },
      ],
    };
  }

  // 路线规划模式
  return {
    session_id: "mock_session",
    message: `好的！根据你的需求「${message}」，我为你规划了 3 条路线，可以左右滑动查看哦 👇`,
    need_clarification: false,
    user_profile: {
      user_id: "user_demo",
      preferences: ["少排队", "吃好", "citywalk", "性价比"],
      avoid_tags: ["人多", "商业街"],
    },
    routes: [
      {
        route_id: "route_A",
        title: "798艺术区文艺路线",
        objective: "citywalk + 咖啡 + 艺术",
        summary: "798看展拍照一整个下午，傍晚去三里屯喝杯咖啡吃个饭，文艺又充实",
        total_duration_minutes: 240,
        total_cost_per_person: 158,
        total_queue_minutes: 15,
        score: 8.6,
        score_breakdown: { quality: 0.88, queue: 0.92, budget: 0.80, distance: 0.85, preference: 0.90 },
        reasons: ["文艺范十足", "全程不绕路", "拍照打卡圣地"],
        stops: [
          {
            poi_id: "p1",
            name: "798艺术区",
            category: "culture",
            district: "朝阳区·酒仙桥",
            lat: 39.9847,
            lng: 116.4969,
            start_time: "14:00",
            end_time: "15:30",
            estimated_cost: 0,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["网红打卡", "当代艺术"],
            cover_image_url: "https://images.unsplash.com/photo-1504618223053-559bdef9dd5a?w=400&q=75",
            rating: 4.7,
            review_count: 28600,
            distance_m: 1200,
            rank_label: "必游榜 Top 3",
            brief: "北京最具文艺气息的工业风创意园区，百家画廊与独立工作室聚集地",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 12,
              distance_m: 850,
              description: "沿酒仙桥路步行约 12 分钟",
            },
          },
          {
            poi_id: "p2",
            name: "木木美术馆",
            category: "culture",
            district: "朝阳区·798",
            lat: 39.9853,
            lng: 116.4945,
            start_time: "15:45",
            end_time: "16:30",
            estimated_cost: 36,
            queue_minutes: 10,
            queue_level: "low" as const,
            tags: ["当代艺术", "拍照出片"],
            cover_image_url: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&q=75",
            rating: 4.9,
            review_count: 15200,
            distance_m: 680,
            rank_label: "艺术必去榜 No.1",
            brief: "798园区内最受欢迎的美术馆，常设国际前沿艺术展",
            transit_to_next: {
              mode: "taxi" as const,
              duration_minutes: 15,
              distance_m: 6800,
              description: "打车约 15 分钟至三里屯",
            },
          },
          {
            poi_id: "p3",
            name: "三里屯太古里",
            category: "shopping",
            district: "朝阳区·三里屯",
            lat: 39.9353,
            lng: 116.4547,
            start_time: "17:00",
            end_time: "18:00",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["潮流地标", "拍照圣地"],
            cover_image_url: "https://images.unsplash.com/photo-1567521464027-f127ff144326?w=400&q=75",
            rating: 4.6,
            review_count: 41800,
            distance_m: 900,
            brief: "北京最潮的开放式购物中心，各国餐饮与独立品牌汇聚",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 5,
              distance_m: 400,
              description: "步行约 5 分钟至餐厅",
            },
          },
          {
            poi_id: "p4",
            name: "Shake Shack（三里屯店）",
            category: "restaurant",
            district: "朝阳区·三里屯",
            lat: 39.9342,
            lng: 116.4556,
            start_time: "18:15",
            end_time: "19:30",
            estimated_cost: 122,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["网红汉堡", "美式休闲"],
            cover_image_url: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&q=75",
            rating: 4.6,
            review_count: 3200,
            rank_label: "汉堡必吃榜 Top 5",
            brief: "纽约传奇汉堡三里屯门店，露天座位看人来人往超惬意",
          },
        ],
      },
      {
        route_id: "route_B",
        title: "朝阳公园自然漫步路线",
        objective: "自然 + 休闲 + 轻食",
        summary: "周末带着野餐垫去朝阳公园晒太阳，下午去望京小街喝个下午茶，是最松弛的一天",
        total_duration_minutes: 300,
        total_cost_per_person: 88,
        total_queue_minutes: 5,
        score: 7.9,
        score_breakdown: { quality: 0.85, queue: 0.68, budget: 0.75, distance: 0.78, preference: 0.82 },
        reasons: ["亲近自然", "适合放松散步", "全程人流适中不拥挤"],
        stops: [
          {
            poi_id: "p5",
            name: "朝阳公园",
            category: "nature",
            district: "朝阳区·朝阳公园",
            lat: 39.9372,
            lng: 116.4809,
            start_time: "10:00",
            end_time: "12:00",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["城市绿洲", "亲子友好"],
            cover_image_url: "https://images.unsplash.com/photo-1518020382113-a7e8fc38eac9?w=400&q=75",
            rating: 4.7,
            review_count: 89300,
            distance_m: 3400,
            rank_label: "公园必去榜 No.1",
            brief: "北京市四环内最大的城市公园，草坪、湖泊、游乐场应有尽有",
            transit_to_next: {
              mode: "taxi" as const,
              duration_minutes: 10,
              distance_m: 3200,
              description: "打车约 10 分钟至望京",
            },
          },
          {
            poi_id: "p6",
            name: "望京小街",
            category: "citywalk",
            district: "朝阳区·望京",
            lat: 39.9978,
            lng: 116.4726,
            start_time: "12:30",
            end_time: "13:30",
            estimated_cost: 65,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["户外美食街", "德式风情"],
            cover_image_url: "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400&q=75",
            rating: 4.5,
            review_count: 52100,
            distance_m: 2800,
            rank_label: "网红街区 Top 10",
            brief: "望京核心步行街，聚集各国料理与精酿啤酒，户外座位氛围超好",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 8,
              distance_m: 600,
              description: "沿望京街步行约 8 分钟",
            },
          },
          {
            poi_id: "p7",
            name: "臻选咖啡实验室",
            category: "rest",
            district: "朝阳区·望京",
            lat: 39.9930,
            lng: 116.4752,
            start_time: "13:45",
            end_time: "15:00",
            estimated_cost: 38,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["精品咖啡", "安静办公"],
            cover_image_url: "https://images.unsplash.com/photo-1557804506-669a67965ba0?w=400&q=75",
            rating: 4.8,
            review_count: 10350,
            distance_m: 3100,
            rank_label: "精品咖啡 No.1",
            brief: "望京最受欢迎的独立咖啡馆，手冲咖啡与甜品都在线",
            transit_to_next: {
              mode: "metro" as const,
              duration_minutes: 18,
              distance_m: 4200,
              description: "地铁 14 号线望京南→国贸站，约 18 分钟",
            },
          },
          {
            poi_id: "p8",
            name: "郎园Vintage",
            category: "culture",
            district: "朝阳区·CBD",
            lat: 39.9078,
            lng: 116.4617,
            start_time: "15:30",
            end_time: "16:30",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["文创园区", "工业遗存"],
            cover_image_url: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=400&q=75",
            rating: 4.5,
            review_count: 8900,
            distance_m: 200,
            rank_label: "文创地标 Top 3",
            brief: "通惠河畔的工业遗存文创园区，读书会、展览、精品店混搭",
          },
        ],
      },
      {
        route_id: "route_C",
        title: "国贸CBD精致路线",
        objective: "午餐 + 艺术 + 逛街",
        summary: "国贸吃顿精致午餐，然后去今日美术馆看个展，再逛SKP，citywalk感拉满",
        total_duration_minutes: 270,
        total_cost_per_person: 220,
        total_queue_minutes: 10,
        score: 8.2,
        score_breakdown: { quality: 0.90, queue: 0.85, budget: 0.82, distance: 0.88, preference: 0.78 },
        reasons: ["精致体验", "步行友好", "艺术+购物双享"],
        stops: [
          {
            poi_id: "p9",
            name: "国贸大酒店·红馆",
            category: "restaurant",
            district: "朝阳区·国贸",
            lat: 39.9106,
            lng: 116.4587,
            start_time: "12:00",
            end_time: "13:30",
            estimated_cost: 180,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["商务午餐", "精致中餐"],
            cover_image_url: "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=400&q=75",
            rating: 4.8,
            review_count: 6320,
            distance_m: 2900,
            rank_label: "必吃榜 No.1",
            brief: "国贸核心地段的商务宴请名菜，精致粤菜搭配落地窗城景",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 12,
              distance_m: 800,
              description: "沿东三环步行约 12 分钟",
            },
          },
          {
            poi_id: "p10",
            name: "今日美术馆",
            category: "museum",
            district: "朝阳区·CBD",
            lat: 39.9053,
            lng: 116.4647,
            start_time: "14:00",
            end_time: "15:30",
            estimated_cost: 30,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["当代艺术", "策展人推荐"],
            cover_image_url: "https://images.unsplash.com/photo-1483728642387-6c3bdd6c93e5?w=400&q=75",
            rating: 4.7,
            review_count: 31400,
            distance_m: 400,
            brief: "中国首家民营非企业公益性美术馆，常设国际前沿展览",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 8,
              distance_m: 600,
              description: "沿百子湾路步行约 8 分钟",
            },
          },
          {
            poi_id: "p11",
            name: "SKP商场",
            category: "shopping",
            district: "朝阳区·大望路",
            lat: 39.9087,
            lng: 116.4725,
            start_time: "15:45",
            end_time: "17:00",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["奢侈品", "室内综合体"],
            cover_image_url: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&q=75",
            rating: 4.5,
            review_count: 7600,
            distance_m: 1800,
            rank_label: "商场高端榜 No.2",
            brief: "中国最顶级百货商场，国际一线品牌最全，逛吃一体化",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 10,
              distance_m: 500,
              description: "沿光华路步行约 10 分钟",
            },
          },
          {
            poi_id: "p12",
            name: "那家小馆（SKP店）",
            category: "restaurant",
            district: "朝阳区·大望路",
            lat: 39.9074,
            lng: 116.4735,
            start_time: "17:15",
            end_time: "18:30",
            estimated_cost: 150,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["宫廷菜", "精致京味"],
            cover_image_url: "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=400&q=75",
            rating: 4.8,
            review_count: 12300,
            distance_m: 500,
            rank_label: "京菜必吃榜 Top 3",
            brief: "那家小馆 SKP 分店，宫廷风味环境雅致，皇坛子是一绝",
          },
        ],
      },
    ],
    agent_trace: [
      { step: "parse_intent",           label: "解析出行意图",     status: "done" },
      { step: "get_user_profile",       label: "读取用户画像",     status: "done" },
      { step: "build_strategy_weights", label: "计算策略权重",     status: "done" },
      { step: "search_pois",            label: "召回候选 POI",     status: "done" },
      { step: "generate_routes",        label: "生成 3 条路线",    status: "done" },
      { step: "summarize_routes",       label: "LLM 总结推荐语",   status: "done" },
    ],
  };
}

// ============================================================
// 主入口
// ============================================================
export async function sendChatMessage(
  message: string,
  profile?: OnboardingProfile,
  includeProfile = true,
  trip?: TripConstraints,
  options: Record<string, unknown> = {},
): Promise<ChatResponse> {
  if (USE_MOCK) {
    await delay(1200); // 模拟 1.2s 延迟，让 loading 动效可见
    return buildMockResponse(message);
  }

  const profilePayload = includeProfile
    ? {
        city:         trip?.city,
        scenarios:    profile?.scenarios ?? [],
        scenario:     profile?.scenario,
        preferences:  profile?.preferences ?? [],
        avoid_tags:   profile?.avoid_tags ?? [],
        budget_level: profile?.budget_level ?? "mid",
        preference_weights: profile?.preference_weights,
      }
    : {};

  // 本次出行约束（每次请求都带上，不受 includeProfile 开关限制）
  // trip_city 仅在用户明确填写了城市时才发送，空值不传，让后端走追问逻辑
  const tripPayload = trip
    ? {
        ...(trip.city ? { trip_city: trip.city } : {}),
        trip_people:             trip.people,
        trip_duration_hours:     trip.duration,
        trip_budget_per_person:  trip.budget_per_person,
      }
    : {};

  const payload = {
    session_id: getChatSessionId(),
    user_id:    profile?.user_id ?? "user_demo",
    message,
    event_type: "user_message",
    // 完整画像字段只在会话首轮发送，后续由后端 session memory 接管当前上下文。
    ...profilePayload,
    // 本次出行约束每次都发送
    ...tripPayload,
    ...options,
  };
  const res = await postJson<ChatResponse>("/api/chat", payload);
  return normalizeResponse(res);
}

export async function sendChatMessageStream(
  message: string,
  profile?: OnboardingProfile,
  includeProfile = true,
  onProgress?: (step: AgentTraceStep) => void,
  trip?: TripConstraints,
  options: Record<string, unknown> = {},
  onRoutes?: (routes: ChatResponse["routes"]) => void,
): Promise<ChatResponse> {
  if (USE_MOCK) {
    const mockSteps: AgentTraceStep[] = [
      {
        step: "route_message",
        label: "判定为：补充需求，继承上一轮出行上下文",
        status: "done",
        details: {
          intent_type: "modify_plan",
          intent_type_label: "修改已有路线",
          turn_type: "add_constraint",
          turn_type_label: "补充需求",
          inherit_previous: true,
          preserve_scenario: true,
          confidence: 0.86,
        },
      },
      {
        step: "parse_intent",
        label: "LLM 解析用户意图",
        status: "done",
        details: {
          city: "上海",
          people_count: 2,
          duration_hours: 8,
          preferences: ["拍照", "吃好"],
        },
      },
      {
        step: "apply_query_delta",
        label: "保留 city、people_count、duration_hours；新增 meal_stop",
        status: "done",
        details: {
          kept: ["city", "people_count", "duration_hours"],
          added: ["meal_stop"],
          changed: {},
          removed: [],
        },
      },
      {
        step: "search_pois",
        label: "召回候选 POI",
        status: "done",
        details: { count: 12, city: "上海", names: ["外滩观景平台", "新天地广场", "Manner 咖啡"] },
      },
      {
        step: "generate_routes",
        label: "生成 3 条路线",
        status: "done",
        details: { count: 3, route_titles: ["综合候选路线 1", "吃好优先候选路线 1"] },
      },
    ];
    for (const step of mockSteps) {
      await delay(220);
      onProgress?.(step);
      if (step.step === "generate_routes") {
        onRoutes?.(buildMockResponse(message).routes.slice(0, 1));
      }
    }
    await delay(250);
    return buildMockResponse(message);
  }

  const profilePayload = includeProfile
    ? {
        city:         trip?.city,
        scenarios:    profile?.scenarios ?? [],
        scenario:     profile?.scenario,
        preferences:  profile?.preferences ?? [],
        avoid_tags:   profile?.avoid_tags ?? [],
        budget_level: profile?.budget_level ?? "mid",
        preference_weights: profile?.preference_weights,
      }
    : {};

  // 本次出行约束（每次请求都带上，不受 includeProfile 开关限制）
  // trip_city 仅在用户明确填写了城市时才发送，空值不传，让后端走追问逻辑
  const tripPayload = trip
    ? {
        ...(trip.city ? { trip_city: trip.city } : {}),
        trip_people:             trip.people,
        trip_duration_hours:     trip.duration,
        trip_budget_per_person:  trip.budget_per_person,
      }
    : {};

  const streamPayload = {
    session_id: getChatSessionId(),
    user_id:    profile?.user_id ?? "user_demo",
    message,
    event_type: "user_message",
    ...profilePayload,
    ...tripPayload,
    ...options,
  };
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(streamPayload),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseStreamEvent(line);
      if (!event) continue;
      if (event.type === "progress") {
        onProgress?.(event.step);
      } else if (event.type === "routes") {
        onRoutes?.(normalizeRoutes(event.routes));
      } else if (event.type === "final") {
        finalResponse = normalizeResponse(event.response);
      } else if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }

  const remainingEvent = parseStreamEvent(buffer);
  if (remainingEvent?.type === "progress") {
    onProgress?.(remainingEvent.step);
  } else if (remainingEvent?.type === "routes") {
    onRoutes?.(normalizeRoutes(remainingEvent.routes));
  } else if (remainingEvent?.type === "final") {
    finalResponse = normalizeResponse(remainingEvent.response);
  } else if (remainingEvent?.type === "error") {
    throw new Error(remainingEvent.message);
  }

  if (!finalResponse) {
    throw new Error("流式响应缺少最终结果");
  }
  return finalResponse;
}

function parseStreamEvent(line: string): ChatStreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  return JSON.parse(trimmed) as ChatStreamEvent;
}

// ============================================================
// 后端数据适配层
// 把后端返回的 *_from_previous 扁平字段转成前端 RouteTimeline
// 所需的 transit_to_next 嵌套结构，以及 queue_minutes → queue_level。
// ============================================================
type RawStop = Record<string, unknown>;

/** 根据 queue_minutes 推断 queue_level */
function inferQueueLevel(minutes: number | undefined): RouteStop["queue_level"] {
  if (minutes == null || minutes <= 0) return "none";
  if (minutes < 15) return "low";
  if (minutes < 30) return "medium";
  if (minutes < 60) return "high";
  return "very_high";
}

/** 把后端 Route[] 归一化为前端可直接渲染的 Route[] */
export function normalizeRoutes(routes: ChatResponse["routes"]): ChatResponse["routes"] {
  return routes.map((route) => {
    // ── 把 stops[i] 的 *_from_previous 拼装成 stops[i-1].transit_to_next ──
    const rawStops = route.stops as unknown as RawStop[];
    const normalized = rawStops.map((stop, idx): RouteStop => {
      // queue_level 如果后端没传，从 queue_minutes 推断
      const queueMinutes = (stop.queue_minutes as number) ?? 0;
      const queue_level = (stop.queue_level as RouteStop["queue_level"]) ?? inferQueueLevel(queueMinutes);

      // 把当前站的 *_from_previous 转换为前一站的 transit_to_next（idx > 0 时处理）
      // 这里先原样保留，下面统一处理
      return { ...(stop as unknown as RouteStop), queue_level };
    });

    // 第二轮：用 stops[i]._from_previous 填充 stops[i-1].transit_to_next
    for (let i = 1; i < normalized.length; i++) {
      const cur = normalized[i] as RawStop & RouteStop;
      const mode = (cur.transport_mode_from_previous as string) ?? "walk";
      const duration = (cur.travel_minutes_from_previous as number) ?? 0;
      // amap_distance_meters_from_previous 精度更高，优先用；否则用 km 字段换算
      const distanceM =
        (cur.amap_distance_meters_from_previous as number) ??
        ((cur.distance_km_from_previous as number) != null
          ? Math.round((cur.distance_km_from_previous as number) * 1000)
          : 0);
      // description 用第一条 route_step（人可读文案）
      const steps = cur.route_steps_from_previous as string[] | undefined;
      const description = steps && steps.length > 0 ? steps[0] : undefined;

      // 只有在有意义的交通信息时才填
      if (duration > 0 || distanceM > 0) {
        normalized[i - 1] = {
          ...normalized[i - 1],
          transit_to_next: {
            mode: (mode as RouteStop["transit_to_next"] extends { mode: infer M } | undefined ? M : "walk"),
            duration_minutes: duration,
            distance_m: distanceM,
            description,
          },
        };
      }
    }

    return { ...route, stops: normalized };
  });
}

/** 对完整 ChatResponse 做归一化 */
function normalizeResponse(res: ChatResponse): ChatResponse {
  return { ...res, routes: normalizeRoutes(res.routes) };
}
