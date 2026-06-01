import { useState, useMemo } from "react";
import { ArrowLeft, ChevronRight, Clock, Eye, Info, MapPin, Plus, RefreshCw, Settings, Star, Users, Wallet } from "lucide-react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import type { HistoryTrip } from "../App";
import { RouteDetailOverlay, QUEUE_META, TRANSPORT_EMOJI } from "../components/RouteDetailOverlay";
import type { RouteDetailData } from "../components/RouteDetailOverlay";

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
  少排队:     "⚡",
  高评分:     "⭐",
  网红打卡:   "📸",
  亲子友好:   "👶",
  无障碍:     "♿",
  宠物友好:   "🐾",
  性价比:     "💰",
};

const BUDGET_LABEL: Record<string, string> = {
  low:  "不特别计划",
  mid:  "小小计划",
  high: "大大计划",
  flex: "看心情",
};

// ── HistoryTrip → 通用格式适配 ───────────────────────────────
const GOAL_COLOR: Record<string, string> = {
  food: "#FF6B6B", restaurant: "#FF6B6B", culture: "#845EC2", museum: "#845EC2",
  nature: "#4CAF50", park: "#4CAF50", shopping: "#FF9800",
  show: "#1677FF", citywalk: "#1677FF", scenic: "#1677FF",
};

function historyTripToDetailData(trip: HistoryTrip): RouteDetailData {
  const themeColor = GOAL_COLOR[trip.goals[0]] ?? "#6366F1";
  const stops = trip.stops ?? [];

  return {
    title: trip.title,
    emoji: trip.emoji,
    subtitle: trip.summary,
    themeColor,
    rating: trip.rating,
    dateLabel: trip.date,
    feedback: trip.feedback,
    stats: [
      { icon: <MapPin size={13} />,  text: trip.district || "未知区域" },
      { icon: <Users size={13} />,   text: `${trip.poi_count} 个地点` },
      { icon: <Clock size={13} />,   text: trip.duration_label },
      ...(trip.cost_per_person != null
        ? [{ icon: <Wallet size={13} />, text: `人均¥${trip.cost_per_person}` }]
        : []),
    ],
    stops: stops.map((stop) => {
      const qMeta = stop.queue_level ? QUEUE_META[stop.queue_level] : undefined;
      const transit = stop.transit_to_next
        ? `${TRANSPORT_EMOJI[stop.transit_to_next.mode] ?? "🚗"} ${stop.transit_to_next.description || stop.transit_to_next.mode} · 约 ${stop.transit_to_next.duration_minutes} 分钟`
        : undefined;
      return {
        key: stop.poi_id || stop.name,
        name: stop.name,
        img: stop.cover_image_url,
        timeLabel: `${stop.start_time} – ${stop.end_time}`,
        costLabel: `¥${stop.estimated_cost}`,
        brief: stop.brief,
        highlight: stop.highlight_text,
        tip: stop.ugc_tip,
        tags: stop.tags,
        queue: qMeta && qMeta.text ? qMeta : undefined,
        transitToNext: transit,
      };
    }),
    footerHint: "复制此路线，AI 将根据你现在的偏好重新优化",
    copyBtnText: "复制同款路线，重新规划",
  };
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
              {dateTrips.map((trip) => (
                <HistoryTripCard
                  key={trip.id}
                  trip={trip}
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

// ── 历史行程卡片 ──────────────────────────────────────────────
function HistoryTripCard({
  trip,
  onView,
  onRestart,
}: {
  trip: HistoryTrip;
  onView: (trip: HistoryTrip) => void;
  onRestart: (trip: HistoryTrip) => void;
}) {
  return (
    <div className="profile-trip-card">
      <div className="profile-trip-emoji">{trip.emoji}</div>
      <div className="profile-trip-info">
        <div className="profile-trip-title-row">
          <span className="profile-trip-title">{trip.title}</span>
          {trip.rating && (
            <span className="profile-trip-rating">
              <Star size={10} fill="#FACC15" stroke="#FACC15" />
              {trip.rating.toFixed(1)}
            </span>
          )}
        </div>
        <div className="profile-trip-meta">
          <span><MapPin size={10} />{trip.district}</span>
          <span><Users size={10} />{trip.poi_count} 个地点</span>
          <span><Clock size={10} />{trip.duration_label}</span>
        </div>
        <span className="profile-trip-date">{trip.date}</span>
      </div>
      <div className="profile-trip-actions">
        <button
          type="button"
          className="profile-trip-view"
          onClick={() => onView(trip)}
          title="查看详情"
        >
          <Eye size={13} />
        </button>
        <button
          type="button"
          className="profile-trip-restart"
          onClick={() => onRestart(trip)}
          title="重新规划"
        >
          <RefreshCw size={13} />
        </button>
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────
export interface ProfilePageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
  onNewTrip: (goals?: string[]) => void;
  tripHistory?: HistoryTrip[];
}

export function ProfilePage({ profile, onResetProfile, onNewTrip, tripHistory = [] }: ProfilePageProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [viewTrip, setViewTrip] = useState<HistoryTrip | null>(null);

  const allScenarios = [
    ...profile.scenarios,
    ...(profile.preferences ?? []),
  ].filter((v, i, arr) => arr.indexOf(v) === i); // 去重

  return (
    <div className="profile-shell">
      {/* ── 顶部用户卡 ── */}
      <header className="profile-header">
        <div className="profile-avatar">
          <span className="profile-avatar-emoji">
            {profile.scenarios[0] === "citywalk" ? "🚶"
              : profile.scenarios[0] === "foodie" ? "🍜"
              : profile.scenarios[0] === "culture" ? "🎨"
              : "🗺️"}
          </span>
        </div>
        <div className="profile-header-info">
          <p className="profile-name">旅行者</p>
          <p className="profile-budget-tag">出行风格：{BUDGET_LABEL[profile.budget_level] ?? "随心"}</p>
        </div>
        <button
          type="button"
          className="profile-settings-btn"
          onClick={() => setShowResetConfirm(true)}
          title="重置偏好"
        >
          <Settings size={16} />
        </button>
      </header>

      <div className="profile-scroll">
        {/* ── 我的偏好标签 ── */}
        <section className="profile-section">
          <div className="profile-section-header">
            <h2 className="profile-section-title">🎯 我的出行偏好</h2>
            <button
              type="button"
              className="profile-section-edit"
              onClick={() => onResetProfile()}
            >
              重新设置
            </button>
          </div>
          <div className="profile-pref-tags">
            {allScenarios.map((s) => (
              <span key={s} className="profile-pref-tag">
                {PREF_EMOJI[s] ?? "🏷️"} {s}
              </span>
            ))}
            {profile.avoid_tags?.length > 0 && (
              <>
                <span className="profile-pref-divider">避开</span>
                {profile.avoid_tags.map((t) => (
                  <span key={t} className="profile-pref-tag profile-pref-tag--avoid">
                    ✗ {t}
                  </span>
                ))}
              </>
            )}
          </div>

          {/* 偏好权重简要展示 */}
          <div className="profile-weights">
            {Object.entries(profile.preference_weights).map(([key, val]) => {
              const labels: Record<string, string> = {
                quality: "品质", queue: "少排队", distance: "距离", budget: "预算", preference: "偏好匹配"
              };
              const pct = Math.round(val * 100);
              return (
                <div key={key} className="profile-weight-row">
                  <span className="profile-weight-label">{labels[key] ?? key}</span>
                  <div className="profile-weight-bar-bg">
                    <div
                      className="profile-weight-bar-fill"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="profile-weight-pct">{pct}%</span>
                </div>
              );
            })}
          </div>
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
              {tripHistory.length > 0 && (
                <span className="profile-history-entry-badge">{tripHistory.length} 次</span>
              )}
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => onResetProfile()}
            >
              <span className="profile-menu-icon">🎯</span>
              <span className="profile-menu-label">重新设置出行偏好</span>
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => {/* 反馈 */}}
            >
              <span className="profile-menu-icon">💬</span>
              <span className="profile-menu-label">意见反馈</span>
              <ChevronRight size={14} className="profile-menu-arrow" />
            </button>
            <button
              type="button"
              className="profile-menu-item"
              onClick={() => {/* 关于 */}}
            >
              <span className="profile-menu-icon"><Info size={14} /></span>
              <span className="profile-menu-label">关于「现在就出发」</span>
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
          onRestart={(t) => { setShowHistory(false); onNewTrip(t.goals); }}
          onNewTrip={() => { setShowHistory(false); onNewTrip(); }}
        />
      )}

      {/* ── 历史行程详情覆盖页（使用通用 RouteDetailOverlay） ── */}
      {viewTrip && (
        <RouteDetailOverlay
          data={historyTripToDetailData(viewTrip)}
          onClose={() => setViewTrip(null)}
          onCopy={() => {
            setViewTrip(null);
            onNewTrip(viewTrip.goals);
          }}
        />
      )}
    </div>
  );
}
