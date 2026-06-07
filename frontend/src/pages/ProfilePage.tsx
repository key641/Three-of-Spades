import { useState, useMemo, useEffect, useRef } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Clock, Info, MapPin, Plus, Send, Settings, Star, Users, Wallet } from "lucide-react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import type { HistoryTrip } from "../App";
import { PhoneStatusBar } from "../App";
import { RouteCard } from "../components/RouteCard";
import type { Route, RouteStop } from "../api/types";
import logoSvg from "../assets/logo.svg";

// ── HistoryTrip → Route（供 RouteCard 使用） ─────────────────
function historyTripToRoute(trip: HistoryTrip): Route {
  const stops: RouteStop[] = (trip.stops ?? []).map((stop, i) => ({
    ...stop,
    // 保留原始 stop 的所有字段，补充缺失的展示字段
    transit_to_next: stop.transit_to_next ?? undefined,
  }));

  // 计算总时长（分钟）
  let totalMinutes = 0;
  if (stops.length >= 2) {
    const start = stops[0].start_time;
    const end   = stops[stops.length - 1].end_time;
    if (start && end) {
      const [sh, sm] = start.split(":").map(Number);
      const [eh, em] = end.split(":").map(Number);
      totalMinutes = (eh * 60 + em) - (sh * 60 + sm);
    }
  }

  const totalCost = trip.cost_per_person ?? stops.reduce((s, st) => s + (st.estimated_cost ?? 0), 0);

  return {
    route_id: trip.id,
    title: `${trip.emoji} ${trip.title}`,
    objective: trip.goals[0] ?? "citywalk",
    summary: trip.summary ?? "",
    total_duration_minutes: totalMinutes,
    total_cost_per_person: totalCost,
    total_queue_minutes: 0,
    score: trip.rating ?? 8.0,
    score_breakdown: { quality: 0.85, queue: 0.9, budget: 0.8, distance: 0.85, preference: 0.88 },
    stops,
    reasons: [],
  };
}

// 场景/偏好的 emoji 映射
const PREF_EMOJI: Record<string, string> = {
  citywalk:   "🚶",
  foodie:     "🍜",
  culture:    "🏛️",
  show_event: "🎭",
  landmark:   "📍",
  family:     "👨‍👩‍👧",
  nature:     "🌿",
  shopping:   "🛍️",
  freestyle:  "🎲",
  少排队:     "⚡",
  高评分:     "⭐",
  网红打卡:   "📸",
  亲子友好:   "👶",
  无障碍:     "♿",
  宠物友好:   "🐾",
  性价比:     "💰",
};

// 场景 key → 中文名称映射
const SCENARIO_LABEL: Record<string, string> = {
  citywalk:   "街头漫游",
  foodie:     "美食探店",
  culture:    "文化艺术",
  show_event: "演出活动",
  landmark:   "热门景点",
  family:     "亲子家庭",
  nature:     "自然放松",
  shopping:   "逛街购物",
  freestyle:  "随心而行",
};

const BUDGET_LABEL: Record<string, string> = {
  low:  "不特别计划",
  mid:  "小小计划",
  high: "大大计划",
  flex: "看心情",
};

// ── 历史行程详情覆盖页（与首页猜你喜欢同款样式） ────────────
function HistoryTripDetailOverlay({
  trip,
  onClose,
  onRestart,
}: {
  trip: HistoryTrip;
  onClose: () => void;
  onRestart: () => void;
}) {
  const routeData = historyTripToRoute(trip);

  return (
    <div className="preset-detail-overlay">
      {/* 状态栏 */}
      <PhoneStatusBar />

      {/* 顶部导航栏 */}
      <div className="preset-detail-topbar">
        <button type="button" className="preset-detail-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>
        <span className="preset-detail-topbar-title">{trip.title}</span>
        <div style={{ width: 36 }} />
      </div>

      {/* 滚动主体：RouteCard */}
      <div className="preset-detail-body">
        {/* 行程元信息 */}
        <div className="history-detail-meta">
          <span><MapPin size={11} />{trip.district || "未知区域"}</span>
          <span><Users size={11} />{trip.poi_count} 个地点</span>
          <span><Clock size={11} />{trip.duration_label}</span>
          {trip.cost_per_person != null && (
            <span><Wallet size={11} />人均¥{trip.cost_per_person}</span>
          )}
          {trip.rating && (
            <span><Star size={11} fill="#FACC15" stroke="#FACC15" />{trip.rating.toFixed(1)}</span>
          )}
        </div>

        <RouteCard
          route={routeData}
          selected={false}
          onSelect={onRestart}
        />
        {/* 底部提示 */}
        <p className="preset-detail-hint">可根据此方案重新规划</p>
        <div style={{ height: 32 }} />
      </div>
    </div>
  );
}

// ── 行程记录汇总页（全屏 overlay） ───────────────────────────
function TripHistoryOverlay({
  trips,
  onClose,
  onView,
  onRestart,
  onNewTrip,
}: {
  trips: HistoryTrip[];
  onClose: () => void;
  onView: (trip: HistoryTrip) => void;
  onRestart: (trip: HistoryTrip) => void;
  onNewTrip: () => void;
}) {
  // 按日期分组（降序）
  const grouped = useMemo(() => {
    const sorted = [...trips].sort((a, b) => b.date.localeCompare(a.date));
    const map = new Map<string, HistoryTrip[]>();
    for (const trip of sorted) {
      const d = trip.date;
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(trip);
    }
    return Array.from(map.entries());
  }, [trips]);

  return (
    <div className="trip-history-overlay">
      {/* 状态栏 */}
      <PhoneStatusBar />

      {/* 顶栏 */}
      <div className="trip-history-topbar">
        <button type="button" className="trip-history-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>
        <h2 className="trip-history-heading">我的行程记录</h2>
        <span className="trip-history-count">{trips.length} 次</span>
      </div>

      {/* 列表 */}
      <div className="trip-history-scroll">
        {grouped.length === 0 ? (
          <div className="profile-trip-empty">
            <span>🗺️</span>
            <p>还没有行程记录</p>
          </div>
        ) : (
          grouped.map(([date, dateTrips]) => (
            <div key={date} className="trip-history-group">
              <div className="trip-history-date-label">{date}</div>
              {dateTrips.map((trip, i) => (
                <HistoryTripCard
                  key={trip.id}
                  trip={trip}
                  index={i}
                  onView={onView}
                  onRestart={onRestart}
                />
              ))}
            </div>
          ))
        )}
        <div style={{ height: 24 }} />
      </div>

      {/* 新建行程 */}
      <div className="trip-history-footer">
        <button
          type="button"
          className="profile-new-trip-btn"
          style={{ margin: 0, width: "100%" }}
          onClick={onNewTrip}
        >
          <Plus size={15} />
          新建行程
        </button>
      </div>
    </div>
  );
}

// category → 彩点颜色（与规划页方案卡片一致）
const HISTORY_CATEGORY_COLOR: Record<string, string> = {
  food: "#FF5A3C", restaurant: "#FF5A3C",
  culture: "#845EC2", museum: "#845EC2",
  nature: "#10B981", park: "#10B981",
  shopping: "#FF9800",
  landmark: "#4FA8E8",
  show: "#F59E0B",
  citywalk: "#4FA8E8",
  scenic: "#38c98a",
  rest: "#9CA3AF",
};

// 行程标签渐变（与规划页方案卡片一致）
const HISTORY_LABEL_GRADIENTS: [string, string][] = [
  ["#38c98a", "#1a9e68"],
  ["#845EC2", "#5c3d99"],
  ["#F59E0B", "#b45309"],
  ["#FF7A4D", "#cc3d1a"],
];

// ── 历史行程卡片（复用规划页 route-summary-card 样式） ───────
function HistoryTripCard({
  trip,
  index,
  onView,
  onRestart,
}: {
  trip: HistoryTrip;
  index: number;
  onView: (trip: HistoryTrip) => void;
  onRestart: (trip: HistoryTrip) => void;
}) {
  const stops = trip.stops ?? [];
  const imgStops = stops.filter((s) => s.cover_image_url);
  const [imgIndex, setImgIndex] = useState(0);

  const startTime = stops[0]?.start_time ?? "";
  const endTime   = stops[stops.length - 1]?.end_time ?? "";
  const timeRange = startTime && endTime ? `${startTime} → ${endTime}` : "";

  const gradient = HISTORY_LABEL_GRADIENTS[index % HISTORY_LABEL_GRADIENTS.length];

  // 各站点时长（用于进度条）
  const durations = stops.map((s) => {
    const [sh, sm] = (s.start_time ?? "00:00").split(":").map(Number);
    const [eh, em] = (s.end_time ?? "00:00").split(":").map(Number);
    return Math.max((eh * 60 + em) - (sh * 60 + sm), 5);
  });
  const totalDur = durations.reduce((a, b) => a + b, 0) || 1;

  // ── 图片横滑逻辑（与 RouteSummaryCard 一致） ────────────
  const imgWrapRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; locked: boolean | null } | null>(null);

  // 拦截原生 touchmove，横滑时阻止外层滚动和卡片点击
  useEffect(() => {
    const el = imgWrapRef.current;
    if (!el || imgStops.length <= 1) return;
    function onTouchMove(e: TouchEvent) {
      if (!dragRef.current) return;
      const dx = Math.abs(e.touches[0].clientX - dragRef.current.startX);
      const dy = Math.abs(e.touches[0].clientY - dragRef.current.startY);
      if (dragRef.current.locked === null) dragRef.current.locked = dx > dy;
      if (dragRef.current.locked) { e.preventDefault(); e.stopPropagation(); }
    }
    el.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => el.removeEventListener("touchmove", onTouchMove);
  }, [imgStops.length]);

  function handleTouchStart(e: React.TouchEvent) {
    dragRef.current = { startX: e.touches[0].clientX, startY: e.touches[0].clientY, locked: null };
  }

  function handleTouchEnd(e: React.TouchEvent) {
    if (!dragRef.current?.locked) { dragRef.current = null; return; }
    const dx = e.changedTouches[0].clientX - dragRef.current.startX;
    dragRef.current = null;
    if (Math.abs(dx) < 30) return;
    if (dx < 0) setImgIndex((i) => Math.min(i + 1, imgStops.length - 1));
    else         setImgIndex((i) => Math.max(i - 1, 0));
  }

  return (
    <div
      className="route-summary-card"
      style={{ cursor: "pointer" }}
      onClick={() => onView(trip)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onView(trip)}
    >
      {/* 左侧图片区 */}
      <div className="rsc-left">
        <div
          ref={imgWrapRef}
          className="rsc-img-wrap"
          style={imgStops.length === 0 ? {
            background: `linear-gradient(135deg, ${gradient[0]} 0%, ${gradient[1]} 100%)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 32,
          } : undefined}
          onTouchStart={imgStops.length > 1 ? handleTouchStart : undefined}
          onTouchEnd={imgStops.length > 1 ? handleTouchEnd : undefined}
          onClick={(e) => { if (dragRef.current?.locked) e.stopPropagation(); }}
        >
          {imgStops.length === 0 && (
            <span>{trip.emoji}</span>
          )}
          {imgStops.length > 0 && (
            <div
              className="rsc-img-track"
              style={{ transform: `translateX(${-imgIndex * 100}%)` }}
            >
              {imgStops.map((s) => (
                <img
                  key={s.poi_id}
                  className="rsc-img"
                  src={s.cover_image_url}
                  alt={s.name}
                />
              ))}
            </div>
          )}
          {/* 多图圆点 */}
          {imgStops.length > 1 && (
            <div className="rsc-dots">
              {imgStops.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`rsc-dot${i === imgIndex ? " rsc-dot--active" : ""}`}
                  onClick={(e) => { e.stopPropagation(); setImgIndex(i); }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 右侧文字区 */}
      <div className="rsc-body">
        {/* 标题 + 评分 */}
        <div className="rsc-top">
          <span className="rsc-title">{trip.title}</span>
          {trip.rating != null && (
            <span className="rsc-score" style={{ fontSize: 13 }}>
              <Star size={11} fill="#FACC15" stroke="#FACC15" style={{ verticalAlign: "middle", marginRight: 2 }} />
              {trip.rating.toFixed(1)}
            </span>
          )}
        </div>

        {/* 地点流（有 stops 时显示） */}
        {stops.length > 0 ? (
          <div className="rsc-poi-line">
            {stops.map((s, i) => (
              <span key={s.poi_id} className="rsc-poi-inline">
                <span
                  className="rsc-poi-dot"
                  style={{ background: HISTORY_CATEGORY_COLOR[s.category] ?? "#9CA3AF" }}
                />
                <span className="rsc-poi-name">{s.name}</span>
                {i < stops.length - 1 && <span className="rsc-poi-sep">›</span>}
              </span>
            ))}
          </div>
        ) : (
          <div className="rsc-reason-line">
            <MapPin size={10} style={{ display: "inline", marginRight: 2 }} />
            {trip.district} · {trip.poi_count} 个地点 · {trip.duration_label}
          </div>
        )}

        {/* 时间 + 费用行 */}
        <div className="rsc-meta-row">
          <Clock size={9} strokeWidth={2} />
          <span>{timeRange || trip.duration_label}</span>
          {trip.cost_per_person != null && (
            <>
              <span className="rsc-meta-dot">·</span>
              <Wallet size={9} strokeWidth={2} />
              <span>¥{trip.cost_per_person}/人</span>
            </>
          )}
        </div>

        {/* 进度条（有 stops 时显示） */}
        {stops.length > 0 && (
          <div className="rsc-timeline-bar">
            {stops.map((s, i) => (
              <div
                key={s.poi_id}
                className="rsc-timeline-seg"
                style={{
                  width: `${(durations[i] / totalDur) * 100}%`,
                  background: HISTORY_CATEGORY_COLOR[s.category] ?? "#9CA3AF",
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 右箭头 */}
      <ChevronRight size={15} className="rsc-chevron" />
    </div>
  );
}

// ── 意见反馈覆盖页 ───────────────────────────────────────────
function FeedbackOverlay({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit() {
    if (!text.trim()) return;
    setSubmitted(true);
    setTimeout(onClose, 1400);
  }

  return (
    <div className="preset-detail-overlay">
      <PhoneStatusBar />
      <div className="preset-detail-topbar">
        <button type="button" className="preset-detail-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>
        <span className="preset-detail-topbar-title">意见反馈</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="feedback-body">
        {submitted ? (
          <div className="feedback-success">
            <span className="feedback-success-icon">🎉</span>
            <p className="feedback-success-title">感谢你的反馈！</p>
            <p className="feedback-success-desc">我们会认真阅读每一条建议，持续改进 Drifto。</p>
          </div>
        ) : (
          <>
            <p className="feedback-hint">遇到了问题，或者有什么想对我们说的？<br />每一条反馈我们都会认真对待。</p>
            <textarea
              className="feedback-textarea"
              placeholder="写下你的想法或建议……"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              autoFocus
            />
            <div className="feedback-actions">
              <button
                type="button"
                className="feedback-cancel"
                onClick={onClose}
              >
                取消
              </button>
              <button
                type="button"
                className="feedback-submit"
                disabled={!text.trim()}
                onClick={handleSubmit}
              >
                <Send size={13} />
                提交反馈
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── 关于 Drifto 覆盖页 ────────────────────────────────────────
function AboutOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div className="preset-detail-overlay">
      <PhoneStatusBar />
      <div className="preset-detail-topbar">
        <button type="button" className="preset-detail-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>
        <span className="preset-detail-topbar-title">关于「Drifto」</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="about-body">
        <div className="about-hero">
          <div className="about-logo-wrap">
            <img src={logoSvg} alt="Drifto" className="about-logo-img" />
          </div>
          <p className="about-tagline">随漂流动，随心而行</p>
        </div>

        <div className="about-content">
          <p className="about-para">
            城市从来不缺好去处，<br />
            缺的是一个懂你的人，陪你找到它。
          </p>

          <p className="about-para">
            Drifto 是一款由 AI 驱动的出行规划助手。<br />
            你只需要告诉它此刻的心情、口袋里的预算，<br />
            或者仅仅是一句"我想出去走走"——<br />
            它就会为你生成一条专属于此刻的路线。
          </p>

          <p className="about-para">
            不是千篇一律的攻略，<br />
            不是别人拍过无数次的打卡清单。<br />
            是今天的你，在这座城市里，<br />
            独一无二的一段漫游。
          </p>

          <div className="about-divider" />

          <div className="about-feature-list">
            <div className="about-feature-item">
              <span className="about-feature-icon">🗺️</span>
              <div>
                <p className="about-feature-title">智能路线规划</p>
                <p className="about-feature-desc">根据偏好、时间、预算，实时生成多条个性化方案</p>
              </div>
            </div>
            <div className="about-feature-item">
              <span className="about-feature-icon">⚡</span>
              <div>
                <p className="about-feature-title">排队预测</p>
                <p className="about-feature-desc">提前感知人流，把等待时间从行程里抹掉</p>
              </div>
            </div>
            <div className="about-feature-item">
              <span className="about-feature-icon">✏️</span>
              <div>
                <p className="about-feature-title">边走边改</p>
                <p className="about-feature-desc">临时换地点、延长停留、插入休息，一句话搞定</p>
              </div>
            </div>
            <div className="about-feature-item">
              <span className="about-feature-icon">📖</span>
              <div>
                <p className="about-feature-title">行程记忆</p>
                <p className="about-feature-desc">每一次出行都被记住，下次规划时更懂你</p>
              </div>
            </div>
          </div>

          <div className="about-divider" />

          <p className="about-footer-text">
            Drifto 由美团黑客松团队「三张黑桃」打造<br />
            <span className="about-footer-sub">愿每一次出发，都刚刚好</span>
          </p>
        </div>
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────
export interface ProfilePageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
  onNewTrip: (goals?: string[], initialMsg?: string) => void;
  tripHistory?: HistoryTrip[];
  onBack?: () => void;
}

export function ProfilePage({ profile, onResetProfile, onNewTrip, tripHistory = [], onBack }: ProfilePageProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [viewTrip, setViewTrip] = useState<HistoryTrip | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  return (
    <div className="profile-shell">
      {/* ── 顶部用户卡 ── */}
      <header className="profile-header">
        {/* 第一行：返回 */}
        <div className="profile-header-topbar">
          {onBack ? (
            <button
              type="button"
              className="profile-back-btn"
              onClick={onBack}
              aria-label="返回"
            >
              <ChevronLeft size={20} strokeWidth={2.5} />
            </button>
          ) : <span />}
        </div>
        {/* 第二行：头像 + 用户信息 */}
        <div className="profile-header-user">
          <div className="profile-avatar">
            <span className="profile-avatar-emoji">
              {profile.scenarios[0] === "citywalk" ? "🚶"
                : profile.scenarios[0] === "foodie" ? "🍜"
                : profile.scenarios[0] === "culture" ? "🎨"
                : "🗺️"}
            </span>
          </div>
          <div className="profile-header-info">
            <p className="profile-name">{profile.nickname || "旅行者"}</p>
            <p className="profile-budget-tag">ID：{profile.user_id}</p>
          </div>
        </div>
      </header>

      <div className="profile-scroll">
        {/* ── 我的偏好标签 ── */}
        <section className="profile-section">
          <div className="profile-section-header">
            <h2 className="profile-section-title">🎯 我的出行偏好</h2>
            <button
              type="button"
              className="profile-settings-btn"
              onClick={() => setShowResetConfirm(true)}
              title="重置偏好"
            >
              <Settings size={16} />
            </button>
          </div>
          {/* 常去场景 */}
          {profile.scenarios?.length > 0 && (
            <div className="profile-pref-group">
              <p className="profile-pref-group-title">常去场景</p>
              <div className="profile-pref-tags">
                {profile.scenarios.map((s) => (
                  <span key={s} className="profile-pref-tag">
                    {PREF_EMOJI[s] ?? "🗺️"} {SCENARIO_LABEL[s] ?? s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 出行偏好 */}
          {(profile.preferences ?? []).length > 0 && (
            <div className="profile-pref-group">
              <p className="profile-pref-group-title">出行偏好</p>
              <div className="profile-pref-tags">
                {(profile.preferences ?? []).map((s) => (
                  <span key={s} className="profile-pref-tag profile-pref-tag--pref">
                    {PREF_EMOJI[s] ?? "✨"} {SCENARIO_LABEL[s] ?? s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 避开场景 */}
          {profile.avoid_tags?.length > 0 && (
            <div className="profile-pref-group">
              <p className="profile-pref-group-title">避开场景</p>
              <div className="profile-pref-tags">
                {profile.avoid_tags.map((t) => (
                  <span key={t} className="profile-pref-tag profile-pref-tag--avoid">
                    ✗ {t}
                  </span>
                ))}
              </div>
            </div>
          )}

        </section>

        {/* ── 功能菜单（行程记录 + 设置项） ── */}
        <section className="profile-section">
          <div className="profile-menu-list">
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => setShowHistory(true)}
            >
              <span className="profile-menu-icon">📋</span>
              <span className="profile-menu-label">我的行程记录</span>
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => setShowFeedback(true)}
            >
              <span className="profile-menu-icon">💬</span>
              <span className="profile-menu-label">意见反馈</span>
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => setShowAbout(true)}
            >
              <span className="profile-menu-icon"><Info size={14} /></span>
              <span className="profile-menu-label">关于「Drifto」</span>
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
          </div>
        </section>

        <div style={{ height: 24 }} />
      </div>

      {/* ── 重置确认弹窗 ── */}
      {showResetConfirm && (
        <div className="profile-reset-mask">
          <div className="profile-reset-dialog">
            <p className="profile-reset-title">重置出行偏好？</p>
            <p className="profile-reset-desc">将清除已保存的偏好设置，重新完成初始配置。</p>
            <div className="profile-reset-actions">
              <button
                type="button"
                className="profile-reset-cancel"
                onClick={() => setShowResetConfirm(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="profile-reset-confirm"
                onClick={() => { setShowResetConfirm(false); onResetProfile(); }}
              >
                确认重置
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 行程记录汇总页 ── */}
      {showHistory && (
        <TripHistoryOverlay
          trips={tripHistory}
          onClose={() => setShowHistory(false)}
          onView={(t) => setViewTrip(t)}
          onRestart={(t) => {
            setShowHistory(false);
            // 构建包含历史路线信息的提示词，通过聊天框启动新规划
            const stops = t.stops ?? [];
            const poisStr = stops.map((s) => s.name).join("、");
            const msg = poisStr
              ? `我上次走过「${t.title}」这条路线（经过${poisStr}），想参考它重新规划一次行程`
              : `我上次走过「${t.title}」，想参考它重新规划一次行程`;
            onNewTrip(t.goals, msg);
          }}
          onNewTrip={() => { setShowHistory(false); onNewTrip(); }}
        />
      )}

      {/* ── 历史行程详情覆盖页（同款样式） ── */}
      {viewTrip && (
        <HistoryTripDetailOverlay
          trip={viewTrip}
          onClose={() => setViewTrip(null)}
          onRestart={() => {
            if (!viewTrip) return;
            setViewTrip(null);
            // 构建包含历史路线信息的提示词，通过聊天框启动新规划
            const stops = viewTrip.stops ?? [];
            const poisStr = stops.map((s) => s.name).join("、");
            const msg = poisStr
              ? `我上次走过「${viewTrip.title}」这条路线（经过${poisStr}），想参考它重新规划一次行程`
              : `我上次走过「${viewTrip.title}」，想参考它重新规划一次行程`;
            onNewTrip(viewTrip.goals, msg);
          }}
        />
      )}

      {/* ── 意见反馈 ── */}
      {showFeedback && (
        <FeedbackOverlay onClose={() => setShowFeedback(false)} />
      )}

      {/* ── 关于 Drifto ── */}
      {showAbout && (
        <AboutOverlay onClose={() => setShowAbout(false)} />
      )}
    </div>
  );
}
