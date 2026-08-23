import { useState, useEffect, useRef } from "react";
import type { OnboardingProfile } from "./hooks/useOnboarding";
import { loadProfile } from "./hooks/useOnboarding";
import { setGpsCache, getGpsCache } from "./utils/gpsCache";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PlannerPage } from "./pages/PlannerPage";
import { HomePage } from "./pages/HomePage";
import { ProfilePage } from "./pages/ProfilePage";
import { Sidebar } from "./components/Sidebar";
import { GlobalInputBar } from "./components/GlobalInputBar";
import type { AppTab } from "./components/TabBar";
import type { Route, RouteStop } from "./api/types";
import type { ChatMessage, ChatSessionSnapshot } from "./hooks/useChat";
import type { ChatResponse } from "./api/types";

// ── iOS 风格状态栏图标 ──────────────────────────────────────
// 信号格：官方 SVG 原版
function IconCellular() {
  return (
    <svg width="17" height="11" viewBox="0 0 17 11" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M16 0H15C14.4477 0 14 0.447715 14 1V9.66667C14 10.219 14.4477 10.6667 15 10.6667H16C16.5523 10.6667 17 10.219 17 9.66667V1C17 0.447715 16.5523 0 16 0ZM10.3333 2.33333H11.3333C11.8856 2.33333 12.3333 2.78105 12.3333 3.33333V9.66667C12.3333 10.219 11.8856 10.6667 11.3333 10.6667H10.3333C9.78105 10.6667 9.33333 10.219 9.33333 9.66667V3.33333C9.33333 2.78105 9.78105 2.33333 10.3333 2.33333ZM6.66667 4.66667H5.66667C5.11438 4.66667 4.66667 5.11438 4.66667 5.66667V9.66667C4.66667 10.219 5.11438 10.6667 5.66667 10.6667H6.66667C7.21895 10.6667 7.66667 10.219 7.66667 9.66667V5.66667C7.66667 5.11438 7.21895 4.66667 6.66667 4.66667ZM2 6.66667H1C0.447715 6.66667 0 7.11438 0 7.66667V9.66667C0 10.219 0.447715 10.6667 1 10.6667H2C2.55228 10.6667 3 10.219 3 9.66667V7.66667C3 7.11438 2.55228 6.66667 2 6.66667Z" fill="currentColor"/>
    </svg>
  );
}

// WiFi：官方 SVG 原版
function IconWifi() {
  return (
    <svg width="16" height="11" viewBox="0 0 16 11" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M7.63661 2.27733C9.8525 2.27742 11.9837 3.12886 13.5896 4.65566C13.7105 4.77354 13.9038 4.77205 14.0229 4.65233L15.1789 3.48566C15.2392 3.42494 15.2729 3.34269 15.2724 3.25711C15.2719 3.17153 15.2373 3.08967 15.1763 3.02966C10.9612 -1.00989 4.31137 -1.00989 0.0962725 3.02966C0.0352139 3.08963 0.00057 3.17146 6.97078e-06 3.25704C-0.000556058 3.34262 0.0330082 3.42489 0.0932725 3.48566L1.24961 4.65233C1.36863 4.77223 1.56208 4.77372 1.68294 4.65566C3.28909 3.12876 5.4205 2.27732 7.63661 2.27733ZM7.63661 6.07299C8.8541 6.07292 10.0281 6.52545 10.9306 7.34266C11.0527 7.45864 11.245 7.45613 11.3639 7.33699L12.5186 6.17033C12.5794 6.10913 12.6132 6.02612 12.6123 5.93985C12.6114 5.85359 12.576 5.77127 12.5139 5.71133C9.76574 3.15494 5.5098 3.15494 2.76161 5.71133C2.69953 5.77127 2.66411 5.85363 2.6633 5.93992C2.66248 6.02621 2.69634 6.10922 2.75727 6.17033L3.91161 7.33699C4.03059 7.45613 4.22288 7.45864 4.34494 7.34266C5.24681 6.52599 6.41992 6.0735 7.63661 6.07299ZM9.9496 8.62681C9.95137 8.71332 9.91736 8.79672 9.85561 8.85733L7.85827 10.873C7.79972 10.9322 7.7199 10.9656 7.63661 10.9656C7.55332 10.9656 7.47349 10.9322 7.41494 10.873L5.41727 8.85733C5.35556 8.79668 5.32161 8.71325 5.32344 8.62674C5.32527 8.54023 5.36272 8.45831 5.42694 8.40033C6.70251 7.32144 8.5707 7.32144 9.84627 8.40033C9.91045 8.45836 9.94783 8.54031 9.9496 8.62681Z" fill="currentColor"/>
    </svg>
  );
}

// 电池：官方 SVG 原版（满电）
function IconBattery() {
  return (
    <svg width="25" height="12" viewBox="0 0 25 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect opacity="0.35" x="0.5" y="0.5" width="21" height="10.3333" rx="2.16667" stroke="currentColor"/>
      <path opacity="0.4" d="M23 3.66663V7.66663C23.8047 7.32785 24.328 6.53976 24.328 5.66663C24.328 4.79349 23.8047 4.0054 23 3.66663Z" fill="currentColor"/>
      <rect x="2" y="2" width="18" height="7.33333" rx="1.33333" fill="currentColor"/>
    </svg>
  );
}

// ── 手机状态栏（全局） ──────────────────────────────────────
export function PhoneStatusBar() {
  const [time, setTime] = useState(() => {
    const now = new Date();
    return now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0");
  });

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0"));
    };
    const ms = (60 - new Date().getSeconds()) * 1000;
    const t = setTimeout(() => {
      tick();
      const interval = setInterval(tick, 60_000);
      return () => clearInterval(interval);
    }, ms);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="phone-status-bar">
      <span className="phone-status-time">{time}</span>
      <div className="phone-status-icons">
        <IconCellular />
        <IconWifi />
        <IconBattery />
      </div>
    </div>
  );
}

// 从首页带过来的预设参数
interface PlannerPreset {
  goals?: string[];
  title?: string;
  initialMsg?: string; // 首页输入框直接发送的消息
  directBoard?: boolean; // 从侧边栏进入时直接跳看板
  /** 已完成的会话快照；用于历史记录恢复，不触发重新规划。 */
  conversation?: ChatSessionSnapshot;
  /** 历史记录选择的路线 ID。 */
  routeId?: string;
}

// ── 历史行程记录 ──────────────────────────────────────────
export interface HistoryTrip {
  id: string;
  title: string;
  date: string;
  district: string;
  poi_count: number;
  duration_label: string;
  rating?: number;
  goals: string[];
  emoji: string;
  /** 行程站点列表，用于详情页展示 */
  stops?: RouteStop[];
  /** 路线摘要 */
  summary?: string;
  /** 人均花费 */
  cost_per_person?: number;
  /** 用户反馈文字 */
  feedback?: string;
  /** 历史对话快照：页面刷新后仍可恢复完整对话和最终路线。 */
  conversation?: ChatSessionSnapshot;
  /** 历史记录对应的精确路线标识，避免仅用标题匹配时回退到第一条路线。 */
  route_id?: string;
}

const HISTORY_KEY = "trip_history_v1";

function loadHistory(): HistoryTrip[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const history = raw ? (JSON.parse(raw) as HistoryTrip[]) : [];
    const migratedHistory = history.map(migrateHistoryRouteReference);
    // 旧记录没有 route_id 时，在首次读取后立即回写迁移结果，后续恢复可精确定位路线。
    if (raw && JSON.stringify(history) !== JSON.stringify(migratedHistory)) {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(migratedHistory));
    }
    return migratedHistory;
  } catch {
    return [];
  }
}

/** 用旧记录的站点序列反查会话内路线，为早期历史数据补齐 route_id。 */
function migrateHistoryRouteReference(trip: HistoryTrip): HistoryTrip {
  const hydratedTrip = trip.conversation ? trip : { ...trip, conversation: createLegacyConversationSnapshot(trip) };
  if (hydratedTrip.route_id || !hydratedTrip.conversation?.response?.routes?.length) return hydratedTrip;
  const routes = hydratedTrip.conversation.response.routes;
  const historyPoiIds = hydratedTrip.stops?.map((stop) => stop.poi_id).filter(Boolean) ?? [];
  const historyNames = hydratedTrip.stops?.map((stop) => stop.name).filter(Boolean) ?? [];
  const matchedRoute = routes
    .map((route) => ({
      route,
      score: route.stops.reduce((score, stop) => score
        + (historyPoiIds.includes(stop.poi_id) ? 3 : 0)
        + (historyNames.includes(stop.name) ? 1 : 0), 0),
    }))
    .sort((left, right) => right.score - left.score)[0]?.route;

  return matchedRoute ? { ...hydratedTrip, route_id: matchedRoute.route_id } : hydratedTrip;
}

/**
 * 老版本只保存了路线摘要，缺少逐轮消息；将既有内容转为只读的本地历史快照。
 * 这样打开历史不会再请求接口或显示流式思考，同时不会伪造不存在的完整对话。
 */
function createLegacyConversationSnapshot(trip: HistoryTrip): ChatSessionSnapshot {
  const route: Route = {
    route_id: trip.route_id ?? `legacy_${trip.id}`,
    title: trip.title,
    objective: trip.goals.join(" · ") || "历史行程",
    summary: trip.summary ?? "已保存的历史路线",
    total_duration_minutes: parseDurationMinutes(trip.duration_label),
    total_cost_per_person: trip.cost_per_person ?? 0,
    total_queue_minutes: 0,
    score: trip.rating ?? 0,
    score_breakdown: { quality: 0, queue: 0, budget: 0, distance: 0, preference: 0 },
    stops: trip.stops ?? [],
    reasons: [],
  };
  const response: ChatResponse = {
    session_id: `legacy_${trip.id}`,
    message: trip.summary ?? `这是你保存的「${trip.title}」历史行程。`,
    need_clarification: false,
    routes: [route],
    agent_trace: [],
  };
  const messages: ChatMessage[] = [
    {
      role: "assistant",
      content: `这是你保存的「${trip.title}」历史行程。${trip.summary ? `\n${trip.summary}` : ""}`,
      timestamp: Date.now(),
    },
  ];
  return { sessionId: response.session_id, messages, response };
}

function parseDurationMinutes(label: string): number {
  const hours = Number(label.match(/(\d+)小时/)?.[1] ?? 0);
  const minutes = Number(label.match(/(\d+)分钟/)?.[1] ?? 0);
  return hours * 60 + minutes;
}

function saveHistory(list: HistoryTrip[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  } catch { /* ignore */ }
}

function getConversationTitle(conversation?: ChatSessionSnapshot): string | null {
  const firstUserMessage = conversation?.messages.find((message) => message.role === "user")?.content.trim();
  return firstUserMessage ? firstUserMessage.slice(0, 24) : null;
}

/** 从 Route 对象生成 HistoryTrip 记录。标题始终优先使用用户的第一句话。 */
function routeToHistoryTrip(route: Route, avgScore: number, conversation?: ChatSessionSnapshot, id?: string): HistoryTrip {
  const selectedRoute = conversation?.response?.routes.find((candidate) => candidate.route_id === route.route_id);
  const resolvedRoute = selectedRoute ?? route;
  const stops = resolvedRoute.stops ?? [];
  const h = Math.floor(route.total_duration_minutes / 60);
  const m = route.total_duration_minutes % 60;
  const durationLabel = h > 0 ? (m > 0 ? `${h}小时${m}分钟` : `${h}小时`) : `${m}分钟`;

  const district = stops[0]?.district ?? "";

  // 根据路线类别推断 emoji
  const categories = [...new Set(stops.map((s) => s.category))];
  const emojiMap: Record<string, string> = {
    food: "🍜", restaurant: "🍜", culture: "🏛️", museum: "🏛️",
    nature: "🌿", park: "🌿", shopping: "🛍️", landmark: "📍",
    show: "🎭", citywalk: "🚶", scenic: "🌄",
  };
  const emoji = emojiMap[categories[0]] ?? "🗺️";

  // 格式化日期
  const now = new Date();
  const dateLabel = `${now.getMonth() + 1}月${now.getDate()}日`;

  return {
    id: id ?? `trip_${Date.now()}`,
    title: getConversationTitle(conversation) ?? "未命名行程",
    date: dateLabel,
    district,
    poi_count: stops.length,
    duration_label: durationLabel,
    rating: avgScore > 0 ? avgScore : undefined,
    goals: categories,
    emoji,
    stops,
    summary: resolvedRoute.summary,
    cost_per_person: resolvedRoute.total_cost_per_person,
    conversation,
    route_id: resolvedRoute.route_id,
  };
}

export default function App() {
  const [profile, setProfile] = useState<OnboardingProfile | null>(() => loadProfile());
  const [activeTab, setActiveTab] = useState<AppTab>("home");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  // 预设参数：首页点击路线/主题 → 跳规划页时携带
  const [plannerPreset, setPlannerPreset] = useState<PlannerPreset | null>(null);
  // 行程历史记录
  const [tripHistory, setTripHistory] = useState<HistoryTrip[]>(() => loadHistory());
  // 当前进行中的行程独立于对话生命周期，确保新建行程回首页后仍可查看。
  const [activeTrip, setActiveTrip] = useState<Route | null>(null);

  // ── 全局输入栏状态 ──
  const [globalInputText, setGlobalInputText] = useState("");
  // PlannerPage 通过回调上报的禁用状态和发送函数
  const planSendRef = useRef<((msg: string) => void) | null>(null);
  const [planInputDisabled, setPlanInputDisabled] = useState(false);
  // PlannerPage 视图模式：board 时隐藏输入栏，chat 时显示
  const [plannerViewMode, setPlannerViewMode] = useState<"chat" | "board">("chat");

  // ── 应用启动时立即发起 GPS 请求（最早时机，给用户最长等待时间）──
  useEffect(() => {
    if ("geolocation" in navigator && !getGpsCache()) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setGpsCache(pos.coords.latitude, pos.coords.longitude),
        () => { /* GPS 拒绝/不可用，忽略 */ },
        { enableHighAccuracy: false, maximumAge: 300000, timeout: 10000 },
      );
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Onboarding 未完成 ──
  if (!profile) {
    return (
      <OnboardingPage
        onDone={(p) => {
          setActiveTab("home");
          setProfile(p);
        }}
      />
    );
  }

  // ── 从首页发起规划 ──
  function handleStartPlanning(goals?: string[], title?: string, initialMsg?: string) {
    setPlannerPreset({ goals, title, initialMsg });
    setActiveTab("plan");
  }

  function handleViewActiveTrip() {
    if (!activeTrip) return;
    setPlannerPreset({ title: activeTrip.title, directBoard: true });
    setActiveTab("plan");
  }

  // ── 全局输入栏发送 ──
  function handleGlobalSend(msg: string) {
    if (activeTab === "home") {
      handleStartPlanning(undefined, undefined, msg);
    } else if (activeTab === "plan") {
      planSendRef.current?.(msg);
    }
  }

  // ── 切换 Tab ──
  function handleTabChange(tab: AppTab) {
    if (tab === "plan" && activeTab !== "plan") {
      setPlannerPreset(null);
    }
    setActiveTab(tab);
  }

  // ── 首条消息发出即创建草稿，确保对话尚未产出路线时也能出现在侧边栏。 ──
  function handleConversationStart(message: string): string {
    const now = new Date();
    const record: HistoryTrip = {
      id: `trip_${Date.now()}`,
      title: message.trim().slice(0, 24) || "未命名行程",
      date: `${now.getMonth() + 1}月${now.getDate()}日`,
      district: "",
      poi_count: 0,
      duration_label: "规划中",
      goals: [],
      emoji: "🗺️",
      summary: "对话进行中…",
    };
    setTripHistory((prev) => {
      const next = [record, ...prev];
      saveHistory(next);
      return next;
    });
    return record.id;
  }

  function upsertTrip(route: Route, avgScore: number, conversation: ChatSessionSnapshot | undefined, tripId?: string) {
    const record = routeToHistoryTrip(route, avgScore, conversation, tripId);
    setTripHistory((prev) => {
      const exists = tripId && prev.some((trip) => trip.id === tripId);
      const next = exists
        // 草稿在首条消息写入时已经确定标题，后续无论选择哪条方案都不能覆盖它。
        ? prev.map((trip) => trip.id === tripId ? { ...record, title: trip.title } : trip)
        : [record, ...prev];
      saveHistory(next);
      return next;
    });
  }

  // ── 行程结束，更新已有草稿并回首页 ──
  function handleTripFinished(route: Route, avgScore: number, conversation?: ChatSessionSnapshot, tripId?: string) {
    upsertTrip(route, avgScore, conversation, tripId);
    setActiveTab("home");
  }

  // ── 新建行程前保存当前会话，优先更新首条消息创建的草稿。 ──
  function handleSaveTrip(route: Route, conversation?: ChatSessionSnapshot, tripId?: string) {
    upsertTrip(route, 0, conversation, tripId);
  }

  // ── 行程重命名 ──
  function handleRenameTrip(tripId: string, newTitle: string) {
    setTripHistory((prev) => {
      const next = prev.map((t) => (t.id === tripId ? { ...t, title: newTitle } : t));
      saveHistory(next);
      return next;
    });
  }

  // ── 行程删除 ──
  function handleDeleteTrip(tripId: string) {
    setTripHistory((prev) => {
      const next = prev.filter((t) => t.id !== tripId);
      saveHistory(next);
      return next;
    });
  }

  // ── 从侧边栏点击历史行程：优先恢复原会话，旧数据才退化为重新规划 ──
  function handleSelectTrip(trip: HistoryTrip) {
    // 即使页面未刷新，旧记录也在点击时即时补齐快照，确保绝不触发重新规划。
    const restoredTrip = migrateHistoryRouteReference(trip);
    if (restoredTrip !== trip) {
      setTripHistory((prev) => {
        const next = prev.map((item) => item.id === trip.id ? restoredTrip : item);
        saveHistory(next);
        return next;
      });
    }
    setPlannerPreset({
      goals: restoredTrip.goals,
      title: restoredTrip.title,
      directBoard: true,
      conversation: restoredTrip.conversation,
      routeId: restoredTrip.route_id,
    });
    setActiveTab("plan");
  }

  return (
    <div className={`app-root${isSidebarOpen ? " sidebar-open" : ""}`}>
      {/* ── 全局物理纸张微粒噪点层 ── */}
      <div className="grain-overlay" />

      {/* ── 弥散呼吸光斑系统 ── */}
      <div className="ambient-blobs-layer">
        <div className="ambient-blob ambient-blob-sage" />
        <div className="ambient-blob ambient-blob-coral" />
        <div className="ambient-blob ambient-blob-lavender" />
      </div>

      {/* ── 侧边栏抽屉（始终渲染在左侧） ── */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        profile={profile}
        trips={tripHistory}
        onNewTrip={() => {
          setIsSidebarOpen(false);
          setActiveTab("home");
          setPlannerPreset(null);
        }}
        onSelectTrip={(trip) => {
          setIsSidebarOpen(false);
          handleSelectTrip(trip);
        }}
        onOpenSettings={() => {
          setIsSidebarOpen(false);
          setActiveTab("profile");
        }}
        onRenameTrip={handleRenameTrip}
        onDeleteTrip={handleDeleteTrip}
      />

      {/* ── 手机状态栏（全局固定顶部） ── */}
      <PhoneStatusBar />

      {/* ── 主内容区（可整体平移 + 手势关闭侧边栏） ── */}
      <div className="app-pages-wrapper">
        {/* 侧边栏打开时的点击/滑动关闭层 */}
        {isSidebarOpen && (
          <div
            className="sidebar-dismiss-overlay"
            onClick={() => setIsSidebarOpen(false)}
            onTouchStart={(e) => {
              const touch = e.touches[0];
              e.currentTarget.dataset.touchX = String(touch.clientX);
            }}
            onTouchEnd={(e) => {
              const rawStartX = e.currentTarget.dataset.touchX;
              const startX = rawStartX === undefined ? undefined : Number(rawStartX);
              if (startX === undefined) return;
              const endX = e.changedTouches[0].clientX;
              if (startX - endX > 60) {
                setIsSidebarOpen(false);
              }
              delete e.currentTarget.dataset.touchX;
            }}
          />
        )}

        {/* ── 页面内容区 ── */}
        <div className="app-pages">
          {/* 极简首页 */}
          <div className={`app-page${activeTab === "home" ? " active" : ""}`}>
            <HomePage
              profile={profile}
              activeTrip={activeTrip}
              onViewActiveTrip={handleViewActiveTrip}
              onOpenSidebar={() => setIsSidebarOpen(true)}
              onTagClick={(text) => {
                setGlobalInputText((prev) => {
                  const trimmed = prev.trim();
                  return !trimmed ? text : `${trimmed}，${text}`;
                });
              }}
            />
          </div>

          {/* 规划页（全屏，无 Tab Bar） */}
          <div className={`app-page${activeTab === "plan" ? " active" : ""}`}>
            <PlannerPage
              profile={profile}
              onResetProfile={() => setProfile(null)}
              preset={plannerPreset}
              onPresetConsumed={() => setPlannerPreset(null)}
              onBackToHome={() => setActiveTab("home")}
              onTripFinished={handleTripFinished}
              onConversationStart={handleConversationStart}
              onNewTrip={() => {
                setPlannerPreset(null);
                setGlobalInputText("");
                setActiveTab("home");
              }}
              onActiveTripChange={setActiveTrip}
              activeTrip={activeTrip}
              onSaveTrip={handleSaveTrip}
              initialMsg={plannerPreset?.initialMsg}
              onOpenSidebar={() => setIsSidebarOpen(true)}
              onSendReady={(sendFn) => { planSendRef.current = sendFn; }}
              onInjectText={(text) => setGlobalInputText(text)}
              onDisabledChange={setPlanInputDisabled}
              onViewModeChange={setPlannerViewMode}
            />
          </div>

          {/* 个人偏好与设置页 */}
          <div className={`app-page${activeTab === "profile" ? " active" : ""}`}>
            <ProfilePage
              profile={profile}
              onResetProfile={() => setProfile(null)}
              onBack={() => setActiveTab("home")}
            />
          </div>
        </div>

        {/* ── 全局底部输入栏（不随页面切换卸载，跟随侧边栏平移） ── */}
        {activeTab !== "profile" && !(activeTab === "plan" && plannerViewMode === "board") && (
          <GlobalInputBar
            mode={activeTab === "plan" ? "plan" : "home"}
            value={globalInputText}
            onChange={setGlobalInputText}
            onSend={handleGlobalSend}
            disabled={activeTab === "plan" ? planInputDisabled : false}
            placeholder={activeTab === "plan" ? "输入调整想法" : "去哪玩、怎么逛，问我就行…"}
          />
        )}
      </div>
    </div>
  );
}
