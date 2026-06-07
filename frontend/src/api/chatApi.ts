import { API_BASE_URL, postJson } from "./client";
import type { OnboardingProfile, TripConstraints } from "../hooks/useOnboarding";
import type { AgentTraceStep, ChatResponse, ChatStreamEvent, RouteStop } from "./types";

// ============================================================
// Mock 开关：默认走真实后端，只有显式设为 true 才使用前端本地 mock。
// ============================================================
const USE_MOCK = import.meta.env.VITE_USE_MOCK_CHAT === "true";
const SESSION_STORAGE_KEY = "tos_chat_session_id";


function getSessionId() {
  if (typeof window === "undefined") return "session_demo";
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const generated = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  localStorage.setItem(SESSION_STORAGE_KEY, generated);
  return generated;
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
        title: "文艺下午茶路线",
        objective: "citywalk + 咖啡 + 轻食",
        summary: "弄堂里随手一拍就出片，咖啡香气飘出来就走不动道了，完全不赶时间的那种下午",
        total_duration_minutes: 240,
        total_cost_per_person: 138,
        total_queue_minutes: 15,
        score: 8.6,
        score_breakdown: { quality: 0.88, queue: 0.92, budget: 0.80, distance: 0.85, preference: 0.90 },
        reasons: ["性价比超高", "全程排队不超过15分钟，节省大量等待时间", "文艺弄堂气息十足，适合拍照打卡"],
        stops: [
          {
            poi_id: "p1",
            name: "田子坊",
            category: "citywalk",
            district: "卢湾·打浦桥",
            start_time: "14:00",
            end_time: "15:30",
            estimated_cost: 0,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["网红打卡", "文艺弄堂"],
            cover_image_url: "https://images.unsplash.com/photo-1504618223053-559bdef9dd5a?w=400&q=75",
            rating: 4.7,
            review_count: 28600,
            distance_m: 1200,
            rank_label: "必游榜 Top 3",
            brief: "上海最具文艺气息的石库门创意街区，藏着百家独立小店与手工艺摊位",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 12,
              distance_m: 850,
              description: "沿泰康路步行约 12 分钟",
            },
          },
          {
            poi_id: "p2",
            name: "Manner Coffee（永康路店）",
            category: "cafe",
            district: "卢湾·永康路",
            start_time: "15:45",
            end_time: "16:30",
            estimated_cost: 36,
            queue_minutes: 10,
            queue_level: "low" as const,
            tags: ["精品咖啡", "性价比高"],
            cover_image_url: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&q=75",
            rating: 4.9,
            review_count: 15200,
            distance_m: 680,
            rank_label: "咖啡必喝榜 No.1",
            brief: "国民精品咖啡，永康路梧桐树下的慢时光，人均35元喝到精品意式",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 10,
              distance_m: 700,
              description: "沿淡水路向北步行约 10 分钟",
            },
          },
          {
            poi_id: "p3",
            name: "新天地广场",
            category: "citywalk",
            district: "卢湾·新天地",
            start_time: "16:45",
            end_time: "17:45",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["拍照圣地", "步行友好"],
            cover_image_url: "https://images.unsplash.com/photo-1567521464027-f127ff144326?w=400&q=75",
            rating: 4.6,
            review_count: 41800,
            distance_m: 900,
            brief: "中西融合的石库门改造街区，时尚餐饮与精品零售汇聚，傍晚氛围绝佳",
            transit_to_next: {
              mode: "metro" as const,
              duration_minutes: 18,
              distance_m: 4200,
              description: "地铁 10 号线新天地站→老西门站，步行至餐厅约 5 分钟",
            },
          },
          {
            poi_id: "p3b",
            name: "思南公馆",
            category: "citywalk",
            district: "卢湾·思南路",
            start_time: "18:15",
            end_time: "19:00",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["历史建筑", "花园洋房", "文艺"],
            cover_image_url: "https://images.unsplash.com/photo-1519120944692-1a8d8cfc107f?w=400&q=75",
            rating: 4.7,
            review_count: 18500,
            distance_m: 1100,
            rank_label: "网红打卡地 Top 10",
            brief: "51幢花园洋房环绕中央广场，法租界历史风貌保存最完好的街区，适合散步拍照",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 8,
              distance_m: 600,
              description: "沿复兴中路向西步行约 8 分钟",
            },
          },
          {
            poi_id: "p4",
            name: "VEDAS 印度素食餐厅",
            category: "restaurant",
            district: "卢湾·复兴路",
            start_time: "19:15",
            end_time: "20:30",
            estimated_cost: 102,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["素食特色", "环境精致"],
            cover_image_url: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&q=75",
            rating: 4.8,
            review_count: 3200,
            rank_label: "素食必吃榜 Top 5",
            brief: "上海顶级印度素食，花园洋房改造，咖喱香料混搭东南亚食材，小众宝藏",
          },
        ],
      },
      {
        route_id: "route_B",
        title: "市井烟火美食路线",
        objective: "本地小吃 + 市集 + 网红餐厅",
        summary: "城隍庙那家生煎真的绝，外滩夜色一点都不输网上的照片，吃饱了再溜达消食刚好",
        total_duration_minutes: 300,
        total_cost_per_person: 165,
        total_queue_minutes: 40,
        score: 7.9,
        score_breakdown: { quality: 0.85, queue: 0.68, budget: 0.75, distance: 0.78, preference: 0.82 },
        reasons: ["夜景绝美", "城隍庙小吃一条街超划算，品类齐全", "最地道市井烟火气，沉浸感极强"],
        stops: [
          {
            poi_id: "p5",
            name: "南京路步行街",
            category: "shopping",
            district: "黄浦·南京路",
            start_time: "14:00",
            end_time: "15:00",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["百年商圈", "人气地标"],
            cover_image_url: "https://images.unsplash.com/photo-1483728642387-6c3bdd6c93e5?w=400&q=75",
            rating: 4.5,
            review_count: 89300,
            distance_m: 3400,
            rank_label: "必游榜 No.1",
            brief: "上海最繁华的百年商业步行街，云集国际品牌与老字号，感受大都市的脉搏",
            transit_to_next: {
              mode: "taxi" as const,
              duration_minutes: 12,
              distance_m: 2800,
              description: "打车约 12 分钟，避开人流高峰的步行",
            },
          },
          {
            poi_id: "p6",
            name: "城隍庙豫园小吃街",
            category: "snack",
            district: "黄浦·豫园",
            start_time: "15:15",
            end_time: "16:30",
            estimated_cost: 65,
            queue_minutes: 30,
            queue_level: "high" as const,
            tags: ["上海小吃", "市井烟火"],
            cover_image_url: "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400&q=75",
            rating: 4.4,
            review_count: 52100,
            distance_m: 2800,
            rank_label: "小吃必吃榜 Top 10",
            brief: "汇聚南翔小笼、生煎馒头、梨膏糖等百年老字号，地道上海市井味道",
            transit_to_next: {
              mode: "bus" as const,
              duration_minutes: 14,
              distance_m: 1800,
              description: "乘 11 路公交外滩中山东二路站，约 14 分钟",
            },
          },
          {
            poi_id: "p7",
            name: "外滩观景平台",
            category: "scenic",
            district: "黄浦·外滩",
            start_time: "17:30",
            end_time: "19:00",
            estimated_cost: 0,
            queue_minutes: 10,
            queue_level: "low" as const,
            tags: ["夜景绝美", "免费开放"],
            cover_image_url: "https://images.unsplash.com/photo-1557804506-669a67965ba0?w=400&q=75",
            rating: 4.9,
            review_count: 103500,
            distance_m: 3100,
            rank_label: "上海必打卡 No.1",
            brief: "隔江对望陆家嘴三件套，万国建筑博览群与东方明珠交相辉映，夜景无可替代",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 5,
              distance_m: 350,
              description: "沿外滩步行约 5 分钟至餐厅",
            },
          },
          {
            poi_id: "p8",
            name: "小南国（外滩旗舰店）",
            category: "restaurant",
            district: "黄浦·外滩",
            start_time: "19:15",
            end_time: "21:00",
            estimated_cost: 100,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["本帮菜", "精致正餐"],
            cover_image_url: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=400&q=75",
            rating: 4.7,
            review_count: 8900,
            distance_m: 200,
            rank_label: "本帮菜必吃榜 Top 3",
            brief: "沪上本帮菜标杆品牌，红烧肉、葱油拌面是招牌，老上海家宴氛围感拉满",
          },
        ],
      },
      {
        route_id: "route_C",
        title: "博物馆亲子路线",
        objective: "博物馆 + 科普 + 轻松步行",
        summary: "孩子在博物馆问了一路问题都没停，公园喂完鸽子又不肯走，比刷手机充实多了",
        total_duration_minutes: 270,
        total_cost_per_person: 120,
        total_queue_minutes: 20,
        score: 8.2,
        score_breakdown: { quality: 0.90, queue: 0.85, budget: 0.82, distance: 0.88, preference: 0.78 },
        reasons: ["亲子友好", "孩子体验感极佳，互动展区丰富有趣", "一票多用，三大文化地标一日贯通"],
        stops: [
          {
            poi_id: "p9",
            name: "上海博物馆（人民广场）",
            category: "museum",
            district: "黄浦·人民广场",
            start_time: "10:00",
            end_time: "12:00",
            estimated_cost: 0,
            queue_minutes: 15,
            queue_level: "medium" as const,
            tags: ["免费参观", "需提前预约"],
            cover_image_url: "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=400&q=75",
            rating: 4.8,
            review_count: 63200,
            distance_m: 2900,
            rank_label: "文化必游榜 No.1",
            brief: "中国古代艺术文物宝库，馆藏逾百万件，青铜器、陶瓷、书画精华尽在其中",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 5,
              distance_m: 380,
              description: "步行穿过人民大道，约 5 分钟",
            },
          },
          {
            poi_id: "p10",
            name: "人民公园",
            category: "park",
            district: "黄浦·人民广场",
            start_time: "12:15",
            end_time: "13:15",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["免费公园", "亲子友好"],
            cover_image_url: "https://images.unsplash.com/photo-1518020382113-a7e8fc38eac9?w=400&q=75",
            rating: 4.5,
            review_count: 31400,
            distance_m: 400,
            brief: "闹市中心的绿洲，樱花季赏花胜地，玫瑰园、相亲角各有趣味，遛娃必去",
            transit_to_next: {
              mode: "bike" as const,
              duration_minutes: 15,
              distance_m: 2800,
              description: "扫码美团单车骑行，沿南京路→外滩，全程约 15 分钟",
            },
          },
          {
            poi_id: "p11",
            name: "和平饭店下午茶（华尔道夫）",
            category: "cafe",
            district: "黄浦·外滩",
            start_time: "13:35",
            end_time: "15:00",
            estimated_cost: 120,
            queue_minutes: 5,
            queue_level: "low" as const,
            tags: ["百年地标", "氛围感满分"],
            cover_image_url: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&q=75",
            rating: 4.9,
            review_count: 7600,
            distance_m: 1800,
            rank_label: "下午茶必喝榜 No.2",
            brief: "1929年开业的传奇老店，Art Deco 建筑内享用英式下午茶，听爵士乐队现场演奏",
            transit_to_next: {
              mode: "walk" as const,
              duration_minutes: 5,
              distance_m: 400,
              description: "沿中山东一路向北步行约 5 分钟",
            },
          },
          {
            poi_id: "p12",
            name: "外滩源（圆明园路历史风貌区）",
            category: "citywalk",
            district: "黄浦·外滩",
            start_time: "15:10",
            end_time: "16:30",
            estimated_cost: 0,
            queue_minutes: 0,
            queue_level: "none" as const,
            tags: ["历史建筑群", "亲子科普", "免费开放"],
            cover_image_url: "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=400&q=75",
            rating: 4.7,
            review_count: 12300,
            distance_m: 500,
            brief: "上海近代建筑博览地，6幢百年领事馆建筑并排而立，教堂、花园洋房交相辉映",
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
    session_id: getSessionId(),
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
    session_id: getSessionId(),
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
