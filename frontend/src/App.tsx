import { useState } from "react";
import type { OnboardingProfile } from "./hooks/useOnboarding";
import { loadProfile } from "./hooks/useOnboarding";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PlannerPage } from "./pages/PlannerPage";
import { HomePage } from "./pages/HomePage";
import { ProfilePage } from "./pages/ProfilePage";
import { TabBar } from "./components/TabBar";
import type { AppTab, PlanAction } from "./components/TabBar";
import type { Route, RouteStop } from "./api/types";

// 从首页带过来的预设参数
interface PlannerPreset {
  goals?: string[];
  title?: string;
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
}

const HISTORY_KEY = "trip_history_v1";

function loadHistory(): HistoryTrip[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as HistoryTrip[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(list: HistoryTrip[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  } catch { /* ignore */ }
}

/** 从 Route 对象生成 HistoryTrip 记录 */
function routeToHistoryTrip(route: Route, avgScore: number): HistoryTrip {
  const stops = route.stops ?? [];
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
    id: `trip_${Date.now()}`,
    title: route.title,
    date: dateLabel,
    district,
    poi_count: stops.length,
    duration_label: durationLabel,
    rating: avgScore > 0 ? avgScore : undefined,
    goals: categories,
    emoji,
    stops,
    summary: route.summary,
    cost_per_person: route.total_cost_per_person,
  };
}

export default function App() {
  const [profile, setProfile] = useState<OnboardingProfile | null>(() => loadProfile());
  const [activeTab, setActiveTab] = useState<AppTab>("home");
  // 预设参数：首页点击路线/主题 → 跳规划页时携带
  const [plannerPreset, setPlannerPreset] = useState<PlannerPreset | null>(null);
  // 行程历史记录
  const [tripHistory, setTripHistory] = useState<HistoryTrip[]>(() => loadHistory());

  // ── Onboarding 未完成 ──
  if (!profile) {
    return <OnboardingPage onDone={(p) => setProfile(p)} />;
  }

  // ── 从首页发起规划 ──
  function handleStartPlanning(goals?: string[], title?: string) {
    setPlannerPreset({ goals, title });
    setActiveTab("plan");
  }

  // ── 切换 Tab ──
  function handleTabChange(tab: AppTab) {
    if (tab === "plan" && activeTab !== "plan") {
      setPlannerPreset(null);
    }
    setActiveTab(tab);
  }

  // ── 行程结束，保存记录并回首页 ──
  function handleTripFinished(route: Route, avgScore: number) {
    const record = routeToHistoryTrip(route, avgScore);
    setTripHistory((prev) => {
      const next = [record, ...prev];
      saveHistory(next);
      return next;
    });
    setActiveTab("home");
  }

  // ── 处理加号菜单动作 ──
  function handlePlanAction(action: PlanAction) {
    if (action === "new_trip") {
      setPlannerPreset(null);
      setActiveTab("plan");
    } else if (action === "import_route") {
      setActiveTab("home");
    }
  }

  // 规划页始终不显示 Tab Bar
  const showTabBar = activeTab !== "plan";

  return (
    <div className="app-root">
      {/* ── 页面内容区 ── */}
      <div className="app-pages">
        {/* 发现页 */}
        <div className={`app-page${activeTab === "home" ? " active" : ""}`}>
          <HomePage
            profile={profile}
            onStartPlanning={handleStartPlanning}
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
          />
        </div>

        {/* 我的页 */}
        <div className={`app-page${activeTab === "profile" ? " active" : ""}`}>
          <ProfilePage
            profile={profile}
            onResetProfile={() => setProfile(null)}
            onNewTrip={(goals) => handleStartPlanning(goals)}
            tripHistory={tripHistory}
          />
        </div>
      </div>

      {/* ── 底部 Tab Bar（规划页中隐藏）── */}
      {showTabBar && (
        <TabBar
          active={activeTab}
          onChange={handleTabChange}
          onPlanAction={handlePlanAction}
        />
      )}
    </div>
  );
}
