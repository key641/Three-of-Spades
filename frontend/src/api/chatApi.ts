import { API_BASE_URL, postJson } from "./client";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import type { AgentTraceStep, ChatResponse, ChatStreamEvent } from "./types";

// ============================================================
// Mock 开关：后端未启动时设为 true，可直接预览所有 UI 流程
// ============================================================
const USE_MOCK = import.meta.env.VITE_USE_MOCK_CHAT !== "false";

// 模拟网络延迟
function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// 完整的 Mock 响应，覆盖所有 UI 字段
function buildMockResponse(message: string): ChatResponse {
  const isRoute = /路线|citywalk|吃|玩|去|逛|今晚|上海|北京|周末|半天|一天/.test(message);

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
        title: "🌿 文艺下午茶路线",
        objective: "citywalk + 咖啡 + 轻食",
        summary: "田子坊→网红咖啡馆→新天地步行街，全程约 4 公里，轻松惬意",
        total_duration_minutes: 240,
        total_cost_per_person: 138,
        total_queue_minutes: 15,
        score: 8.6,
        score_breakdown: { quality: 0.88, queue: 0.92, budget: 0.80, distance: 0.85, preference: 0.90 },
        reasons: ["排队少", "环境好", "打卡热门", "性价比高"],
        stops: [
          {
            poi_id: "p1",
            name: "田子坊",
            category: "citywalk",
            start_time: "14:00",
            end_time: "15:30",
            estimated_cost: 0,
            queue_minutes: 5,
            tags: ["网红打卡", "文艺", "弄堂"],
          },
          {
            poi_id: "p2",
            name: "Manner 咖啡（永康路店）",
            category: "cafe",
            start_time: "15:45",
            end_time: "16:30",
            estimated_cost: 36,
            queue_minutes: 10,
            tags: ["精品咖啡", "排队少"],
            travel_minutes_from_previous: 12,
            distance_km_from_previous: 1.3,
            transport_mode_from_previous: "walk/metro",
          },
          {
            poi_id: "p3",
            name: "新天地广场",
            category: "citywalk",
            start_time: "16:45",
            end_time: "18:00",
            estimated_cost: 0,
            queue_minutes: 0,
            tags: ["步行街", "拍照"],
            travel_minutes_from_previous: 10,
            distance_km_from_previous: 0.8,
            transport_mode_from_previous: "walk",
          },
          {
            poi_id: "p4",
            name: "VEDAS 素食餐厅",
            category: "restaurant",
            start_time: "18:30",
            end_time: "20:00",
            estimated_cost: 102,
            queue_minutes: 0,
            tags: ["素食", "环境好", "特色"],
            travel_minutes_from_previous: 18,
            distance_km_from_previous: 2.4,
            transport_mode_from_previous: "metro/taxi",
          },
        ],
      },
      {
        route_id: "route_B",
        title: "🍜 市井烟火美食路线",
        objective: "本地小吃 + 市集 + 网红餐厅",
        summary: "南京路步行街→城隍庙小吃→外滩夜景，体验最地道上海风味",
        total_duration_minutes: 300,
        total_cost_per_person: 165,
        total_queue_minutes: 40,
        score: 7.9,
        score_breakdown: { quality: 0.85, queue: 0.68, budget: 0.75, distance: 0.78, preference: 0.82 },
        reasons: ["美食丰富", "经典上海", "夜景绝美"],
        stops: [
          {
            poi_id: "p5",
            name: "南京路步行街",
            category: "shopping",
            start_time: "14:00",
            end_time: "15:00",
            estimated_cost: 0,
            queue_minutes: 0,
            tags: ["步行街", "繁华"],
          },
          {
            poi_id: "p6",
            name: "城隍庙小吃街",
            category: "snack",
            start_time: "15:15",
            end_time: "16:30",
            estimated_cost: 65,
            queue_minutes: 30,
            tags: ["本地小吃", "人气高"],
          },
          {
            poi_id: "p7",
            name: "外滩观景台",
            category: "scenic",
            start_time: "17:30",
            end_time: "19:00",
            estimated_cost: 0,
            queue_minutes: 10,
            tags: ["夜景", "必打卡"],
          },
          {
            poi_id: "p8",
            name: "小南国（外滩店）",
            category: "restaurant",
            start_time: "19:15",
            end_time: "21:00",
            estimated_cost: 100,
            queue_minutes: 0,
            tags: ["本帮菜", "正餐"],
          },
        ],
      },
      {
        route_id: "route_C",
        title: "🏛️ 博物馆亲子路线",
        objective: "博物馆 + 科普 + 轻松步行",
        summary: "上海博物馆→人民公园→和平饭店下午茶，适合带娃的文化半日游",
        total_duration_minutes: 270,
        total_cost_per_person: 120,
        total_queue_minutes: 20,
        score: 8.2,
        score_breakdown: { quality: 0.90, queue: 0.85, budget: 0.82, distance: 0.88, preference: 0.78 },
        reasons: ["亲子友好", "文化体验", "少排队", "预约制"],
        stops: [
          {
            poi_id: "p9",
            name: "上海博物馆（人民广场）",
            category: "museum",
            start_time: "10:00",
            end_time: "12:00",
            estimated_cost: 0,
            queue_minutes: 15,
            tags: ["免费", "亲子", "需预约"],
          },
          {
            poi_id: "p10",
            name: "人民公园",
            category: "park",
            start_time: "12:15",
            end_time: "13:15",
            estimated_cost: 0,
            queue_minutes: 0,
            tags: ["公园", "休闲", "遛娃"],
          },
          {
            poi_id: "p11",
            name: "和平饭店下午茶",
            category: "cafe",
            start_time: "14:00",
            end_time: "15:30",
            estimated_cost: 120,
            queue_minutes: 5,
            tags: ["百年老店", "下午茶", "氛围感"],
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
  sessionId = createChatSessionId(profile?.user_id),
): Promise<ChatResponse> {
  if (USE_MOCK) {
    await delay(1200); // 模拟 1.2s 延迟，让 loading 动效可见
    return { ...buildMockResponse(message), session_id: sessionId };
  }

  const profilePayload = includeProfile
    ? {
        city:         profile?.city,
        scenarios:    profile?.scenarios ?? [],
        preferences:  profile?.preferences ?? [],
        avoid_tags:   profile?.avoid_tags ?? [],
        budget_level: profile?.budget_level ?? "mid",
        preference_weights: profile?.preference_weights,
      }
    : {};

  return postJson<ChatResponse>("/api/chat", {
    session_id: sessionId,
    user_id:    profile?.user_id ?? "user_demo",
    message,
    event_type: "user_message",
    // 完整画像字段只在会话首轮发送，后续由后端 session memory 接管当前上下文。
    ...profilePayload,
  });
}

export async function sendChatMessageStream(
  message: string,
  profile?: OnboardingProfile,
  includeProfile = true,
  onProgress?: (step: AgentTraceStep) => void,
  sessionId = createChatSessionId(profile?.user_id),
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
    }
    await delay(250);
    return { ...buildMockResponse(message), session_id: sessionId };
  }

  const profilePayload = includeProfile
    ? {
        city:         profile?.city,
        scenarios:    profile?.scenarios ?? [],
        preferences:  profile?.preferences ?? [],
        avoid_tags:   profile?.avoid_tags ?? [],
        budget_level: profile?.budget_level ?? "mid",
        preference_weights: profile?.preference_weights,
      }
    : {};

  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_id:    profile?.user_id ?? "user_demo",
      message,
      event_type: "user_message",
      ...profilePayload,
    }),
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
      } else if (event.type === "final") {
        finalResponse = event.response;
      } else if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }

  const remainingEvent = parseStreamEvent(buffer);
  if (remainingEvent?.type === "progress") {
    onProgress?.(remainingEvent.step);
  } else if (remainingEvent?.type === "final") {
    finalResponse = remainingEvent.response;
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

export function createChatSessionId(userId = "user_demo"): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}_${Math.random().toString(36).slice(2)}`;
  return `session_${userId}_${random}`;
}
