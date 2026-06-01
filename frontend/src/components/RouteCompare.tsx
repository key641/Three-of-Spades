import { useEffect, useRef, useState, useCallback } from "react";
import {
  MapPin, ChevronDown, ChevronRight, CheckCircle2, Clock, Wallet, X, Star,
  MessageSquare, SkipForward, CheckCheck, Navigation,
  Footprints, Train, Bus, CarTaxiFront, Bike,
  MoreHorizontal, ArrowUp, ArrowDown, RefreshCw, PlusCircle,
  Timer, Coffee, Undo2, Phone, ExternalLink, CalendarCheck, CalendarX,
} from "lucide-react";
import type { Route, RouteStop, TransitSegment } from "../api/types";
import { RouteCard } from "./RouteCard";
import { RouteTimeline, type PoiAction } from "./RouteTimeline";
import { RouteOptimizeBar } from "./ActionBar";
import { TripSummaryOverlay } from "./TripSummaryOverlay";

export interface RouteCompareProps {
  routes: Route[];
  loading?: boolean;
  /** 从 RouteOptimizeBar 冒泡上来的路线级操作 */
  onAction?: (actionKey: string, routeId: string) => void;
  /** 从 PoiCard 冒泡上来的 POI 级操作 */
  onPoiAction?: (action: PoiAction, routeId: string) => void;
  /** 注入聊天框文本（用于增加节点等操作） */
  onInjectChat?: (text: string) => void;
  /** 行程完结并关闭总结页时回调（保存记录+回首页） */
  onTripFinished?: (route: Route, avgScore: number) => void;
}

// ── 骨架屏 ──────────────────────────────────────────────────
function RouteCardSkeleton() {
  return (
    <div className="route-card skeleton">
      <div className="route-card-header" style={{ marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div className="sk-line sk-title" />
          <div className="sk-line sk-short" />
        </div>
        <div style={{ width: 44, height: 44, borderRadius: 8, background: "#eee" }} />
      </div>
      <div className="sk-metrics">
        <div className="sk-chip" /><div className="sk-chip" /><div className="sk-chip" />
      </div>
      <div style={{ marginTop: 12 }}>
        <div className="sk-stop" />
        <div className="sk-stop" />
        <div className="sk-stop" />
      </div>
    </div>
  );
}

// ── 判断当前进行中的站点 ────────────────────────────────────
function getCurrentStopIndex(stops: RouteStop[]): number {
  const now = new Date();
  const hh = now.getHours();
  const mm = now.getMinutes();
  const nowMin = hh * 60 + mm;

  function parseTime(t: string): number {
    const [h, m] = t.split(":").map(Number);
    return h * 60 + (m || 0);
  }

  for (let i = 0; i < stops.length; i++) {
    const start = parseTime(stops[i].start_time);
    const end = parseTime(stops[i].end_time);
    if (nowMin >= start && nowMin < end) return i;
    if (i === 0 && nowMin < start) return 0; // 还没开始，显示第一站
  }
  return stops.length - 1; // 已结束，显示最后一站
}

// ── 已选方案置顶条 ─────────────────────────────────────────
interface ActiveTripBarProps {
  route: Route;
  onUnselect: () => void;
  onAction?: (actionKey: string, routeId: string) => void;
  onPoiAction?: (action: PoiAction, routeId: string) => void;
  onInjectChat?: (text: string) => void;
  onTripFinished?: (route: Route, avgScore: number) => void;
}

// ── 行程结束后的轻量评价卡片 ─────────────────────────────────
const FEEDBACK_ITEMS = [
  { key: "route",  emoji: "📍", label: "路线合理" },
  { key: "time",   emoji: "⏱️", label: "时间安排" },
  { key: "budget", emoji: "💰", label: "预算控制" },
  { key: "ai",     emoji: "🤖", label: "AI 准确度" },
];

function TripEndFeedback({
  scores,
  setScores,
  comment,
  setComment,
  onSubmit,
  onSkip,
}: {
  scores: Record<string, number>;
  setScores: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  comment: string;
  setComment: React.Dispatch<React.SetStateAction<string>>;
  onSubmit: () => void;
  onSkip: () => void;
}) {
  const allFive = Object.values(scores).every((v) => v === 5);

  function handleFullScore() {
    setScores({ route: 5, time: 5, budget: 5, ai: 5 });
  }

  return (
    <div className="trip-end-feedback">
      <p className="trip-end-title">🏁 行程结束，今天玩得怎么样？</p>

      {/* 一键满分 */}
      <button
        type="button"
        className={`trip-end-fullscore${allFive ? " active" : ""}`}
        onClick={handleFullScore}
      >
        ⭐ 一键满分
      </button>
      <p className="trip-end-hint">您的反馈有助于我们为您更好地推荐行程</p>

      <div className="trip-end-rows">
        {FEEDBACK_ITEMS.map(({ key, emoji, label }) => (
          <div key={key} className="trip-end-row">
            <span className="trip-end-row-label">{emoji} {label}</span>
            <div className="trip-end-stars">
              {[1, 2, 3, 4, 5].map((s) => (
                <Star
                  key={s}
                  size={20}
                  fill={s <= (scores[key] ?? 0) ? "#FACC15" : "none"}
                  stroke={s <= (scores[key] ?? 0) ? "#FACC15" : "#D1D5DB"}
                  strokeWidth={1.5}
                  style={{ cursor: "pointer" }}
                  onClick={() => setScores((prev) => ({ ...prev, [key]: s }))}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 意见输入框 */}
      <textarea
        className="trip-end-comment"
        placeholder="有其他意见或建议？告诉我们（选填）"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
      />

      <div className="trip-end-footer">
        <button type="button" className="trip-end-skip" onClick={onSkip}>跳过</button>
        <button
          type="button"
          className="trip-end-submit"
          disabled={Object.values(scores).every((v) => v === 0)}
          onClick={onSubmit}
        >
          提交反馈
        </button>
      </div>
    </div>
  );
}

// ── 交通段图标映射 ──────────────────────────────────────────
const TRANSIT_ICON: Record<TransitSegment["mode"], React.ReactNode> = {
  walk:  <Footprints size={11} />,
  metro: <Train size={11} />,
  bus:   <Bus size={11} />,
  taxi:  <CarTaxiFront size={11} />,
  bike:  <Bike size={11} />,
};
const TRANSIT_LABEL: Record<TransitSegment["mode"], string> = {
  walk: "步行", metro: "地铁", bus: "公交", taxi: "打车", bike: "骑行",
};
const TRANSIT_COLOR: Record<TransitSegment["mode"], string> = {
  walk: "#52C41A", metro: "#1677FF", bus: "#722ED1", taxi: "#FA8C16", bike: "#13C2C2",
};

function formatDist(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${m}m`;
}

// ─────────────────────────────────────────────────────────────
// 时间工具
// ─────────────────────────────────────────────────────────────
function parseMin(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + (m || 0);
}
function fmtMin(totalMin: number): string {
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** 从 fromIdx 开始重算后续所有站点的 start_time / end_time */
function recalcTimes(stops: RouteStop[], fromIdx = 1): RouteStop[] {
  const result = stops.map((s) => ({ ...s }));
  for (let i = Math.max(fromIdx, 1); i < result.length; i++) {
    const prev = result[i - 1];
    let startMin = parseMin(prev.end_time);
    if (prev.transit_to_next) startMin += prev.transit_to_next.duration_minutes;
    const dur = parseMin(result[i].end_time) - parseMin(result[i].start_time);
    const endMin = startMin + Math.max(dur, 30);
    result[i] = {
      ...result[i],
      start_time: fmtMin(startMin),
      end_time:   fmtMin(endMin),
    };
  }
  return result;
}

/** 默认的「休息」transit segment（在原地，步行0距离） */
function restTransit(dur: number): TransitSegment {
  return { mode: "walk", duration_minutes: 0, distance_m: 0, description: `原地休息 ${dur} 分钟` };
}

/** 生成一个休息占位节点 */
function makeRestStop(after: RouteStop, restMin: number): RouteStop {
  const startMin = parseMin(after.end_time) + (after.transit_to_next?.duration_minutes ?? 0);
  return {
    poi_id:         `rest_${Date.now()}`,
    name:           "☕ 休息一下",
    category:       "rest",
    district:       after.district,
    start_time:     fmtMin(startMin),
    end_time:       fmtMin(startMin + restMin),
    estimated_cost: 0,
    queue_minutes:  0,
    tags:           ["休息"],
    brief:          "稍作休息，恢复体力",
    transit_to_next: after.transit_to_next
      ? { ...after.transit_to_next }
      : undefined,
  };
}

// ── 延长时间选项 ─────────────────────────────────────────────
const EXTEND_OPTIONS = [15, 30, 45, 60] as const;

// ── 停留时长展示 ─────────────────────────────────────────────
function durLabel(start: string, end: string): string {
  const d = parseMin(end) - parseMin(start);
  if (d <= 0) return "";
  if (d < 60) return `${d}分钟`;
  const h = Math.floor(d / 60);
  const m = d % 60;
  return m === 0 ? `${h}h` : `${h}h${m}m`;
}

function ActiveTripBar({ route, onUnselect, onAction, onInjectChat, onTripFinished }: ActiveTripBarProps) {
  // 本地可编辑 stops 列表
  const [stops, setStops] = useState<RouteStop[]>(route.stops);
  // 当前所在节点
  const [activeIdx, setActiveIdx] = useState(0);
  // 行程结束评价
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackScores, setFeedbackScores] = useState<Record<string, number>>({ route: 0, time: 0, budget: 0, ai: 0 });
  const [feedbackComment, setFeedbackComment] = useState("");
  const [showSummary, setShowSummary] = useState(false);
  // 当前展开菜单的节点 idx（null = 全部收起）
  const [menuIdx, setMenuIdx] = useState<number | null>(null);
  // 延长时间选择面板（null = 收起）
  const [extendIdx, setExtendIdx] = useState<number | null>(null);
  // 休息面板
  const [restIdx, setRestIdx] = useState<number | null>(null);
  // 撤销栈（保存上一次 stops 快照）
  const [undoStack, setUndoStack] = useState<RouteStop[][]>([]);
  // 已预约的 POI id 集合（默认将所有 booking_required 的 POI 标记为已预约）
  const [bookedIds, setBookedIds] = useState<Set<string>>(
    () => new Set(route.stops.filter((s) => s.booking_required).map((s) => s.poi_id))
  );

  const lastIdx = stops.length - 1;
  const currentStop = stops[activeIdx];
  const nextStop = stops[activeIdx + 1];

  // 点击其他地方关闭菜单
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest(".vtl-menu-wrap")) {
        setMenuIdx(null);
        setExtendIdx(null);
        setRestIdx(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ── 通用快照保存 ──────────────────────────────────────────
  const saveSnapshot = useCallback((prev: RouteStop[]) => {
    setUndoStack((stack) => [...stack.slice(-4), prev]);
  }, []);

  function applyStops(newStops: RouteStop[], fromIdx = 0) {
    saveSnapshot(stops);
    setStops(recalcTimes(newStops, fromIdx));
  }

  // ── 标记到达 ─────────────────────────────────────────────
  function handleArrived(idx: number) {
    if (idx === activeIdx && idx !== stops.length - 1) return;
    setActiveIdx(idx);
    if (idx === stops.length - 1 && activeIdx !== stops.length - 1) {
      setShowFeedback(true);
    }
  }

  // ── 跳过某站 ─────────────────────────────────────────────
  function handleSkip(idx: number) {
    const arr = stops.map((s) => ({ ...s }));
    if (idx > 0 && arr[idx].transit_to_next && arr[idx - 1].transit_to_next) {
      const pt = arr[idx - 1].transit_to_next!;
      const st = arr[idx].transit_to_next!;
      arr[idx - 1] = {
        ...arr[idx - 1],
        transit_to_next: {
          ...pt,
          duration_minutes: pt.duration_minutes + st.duration_minutes,
          distance_m: pt.distance_m + st.distance_m,
          description: `${pt.description ?? ""} → 跳过${arr[idx].name}`,
        },
      };
    } else if (idx > 0 && arr[idx].transit_to_next) {
      arr[idx - 1] = { ...arr[idx - 1], transit_to_next: arr[idx].transit_to_next };
    }
    const next = [...arr.slice(0, idx), ...arr.slice(idx + 1)];
    applyStops(next, idx - 1);
    setActiveIdx((prev) => Math.min(prev, next.length - 1));
    setMenuIdx(null);
  }

  // ── 延长当前站停留 ────────────────────────────────────────
  function handleExtend(idx: number, minutes: number) {
    const arr = stops.map((s) => ({ ...s }));
    const newEndMin = parseMin(arr[idx].end_time) + minutes;
    arr[idx] = { ...arr[idx], end_time: fmtMin(newEndMin) };
    applyStops(arr, idx);
    setExtendIdx(null);
    setMenuIdx(null);
  }

  // ── 缩短当前站（提前离开） ────────────────────────────────
  function handleShorten(idx: number, minutes: number) {
    const arr = stops.map((s) => ({ ...s }));
    const newEndMin = Math.max(parseMin(arr[idx].start_time) + 10, parseMin(arr[idx].end_time) - minutes);
    arr[idx] = { ...arr[idx], end_time: fmtMin(newEndMin) };
    applyStops(arr, idx);
    setExtendIdx(null);
    setMenuIdx(null);
  }

  // ── 上移节点（与前一站交换） ──────────────────────────────
  function handleMoveUp(idx: number) {
    if (idx <= activeIdx + 1) return; // 不允许移到已完成站之前
    const arr = stops.map((s) => ({ ...s }));
    // 交换 idx-1 和 idx 的内容，但 transit_to_next 保持原位（是路段，不随内容走）
    const prevTrans = arr[idx - 2]?.transit_to_next;
    const curTrans = arr[idx - 1].transit_to_next;
    const nextTrans = arr[idx].transit_to_next;

    const tmp = { ...arr[idx - 1], transit_to_next: curTrans };
    arr[idx - 1] = { ...arr[idx], transit_to_next: curTrans };
    arr[idx] = { ...tmp, transit_to_next: nextTrans };
    applyStops(arr, idx - 1);
    setMenuIdx(null);
  }

  // ── 下移节点（与后一站交换） ──────────────────────────────
  function handleMoveDown(idx: number) {
    if (idx >= lastIdx) return;
    const arr = stops.map((s) => ({ ...s }));
    const curTrans = arr[idx].transit_to_next;
    const nextTrans = arr[idx + 1].transit_to_next;
    arr[idx] = { ...arr[idx + 1], transit_to_next: curTrans };
    arr[idx + 1] = { ...arr[idx - 1 >= 0 ? idx : idx], transit_to_next: nextTrans };
    // 直接 swap content 保留 transit
    const aContent = { ...stops[idx], transit_to_next: stops[idx].transit_to_next };
    const bContent = { ...stops[idx + 1], transit_to_next: stops[idx + 1].transit_to_next };
    arr[idx] = { ...bContent, transit_to_next: aContent.transit_to_next };
    arr[idx + 1] = { ...aContent, transit_to_next: bContent.transit_to_next };
    applyStops(arr, idx);
    setMenuIdx(null);
  }

  // ── 插入休息节点 ──────────────────────────────────────────
  function handleInsertRest(idx: number, restMin: number) {
    const arr = stops.map((s) => ({ ...s }));
    const rest = makeRestStop(arr[idx], restMin);
    // 原站的 transit 转给休息节点，原站 transit 清空
    rest.transit_to_next = arr[idx].transit_to_next;
    arr[idx] = { ...arr[idx], transit_to_next: restTransit(restMin) };
    const next = [...arr.slice(0, idx + 1), rest, ...arr.slice(idx + 1)];
    applyStops(next, idx);
    setRestIdx(null);
    setMenuIdx(null);
  }

  // ── 撤销 ──────────────────────────────────────────────────
  function handleUndo() {
    if (undoStack.length === 0) return;
    const prev = undoStack[undoStack.length - 1];
    setStops(prev);
    setUndoStack((s) => s.slice(0, -1));
    setActiveIdx((idx) => Math.min(idx, prev.length - 1));
  }

  // ── 跟 AI 说（注入聊天框） ────────────────────────────────
  function handleTalkAI(idx: number) {
    const s = stops[idx];
    const hint = `我在出行中，想修改「${s.name}」这个节点，`;
    onInjectChat?.(hint);
    setMenuIdx(null);
  }

  // ── 删除节点（本地直接删除 + 重算时间） ──────────────────
  function handleDeleteStop(idx: number) {
    const arr = stops.map((s) => ({ ...s }));
    // 合并前后 transit：被删节点的 transit_to_next 接给前驱节点
    if (idx > 0 && arr[idx].transit_to_next) {
      const prevTrans = arr[idx - 1].transit_to_next;
      const curTrans  = arr[idx].transit_to_next!;
      arr[idx - 1] = {
        ...arr[idx - 1],
        transit_to_next: prevTrans
          ? {
              mode: curTrans.mode,
              duration_minutes: prevTrans.duration_minutes + curTrans.duration_minutes,
              distance_m: prevTrans.distance_m + curTrans.distance_m,
              description: undefined,
            }
          : { ...curTrans },
      };
    } else if (idx > 0) {
      arr[idx - 1] = { ...arr[idx - 1], transit_to_next: undefined };
    }
    const newStops = [...arr.slice(0, idx), ...arr.slice(idx + 1)];
    applyStops(newStops, Math.max(idx - 1, 1));
    setActiveIdx((prev) => Math.min(prev, newStops.length - 1));
    setMenuIdx(null);
  }

  // ── 渲染节点操作菜单（简化为两项） ───────────────────────
  function renderMenu(idx: number, state: "done" | "current" | "upcoming") {
    if (menuIdx !== idx) return null;

    return (
      <div className="vtl-menu">
        {/* 跟 AI 说想怎么修改路线 */}
        <button
          className="vtl-menu-item vtl-menu-item--ai"
          onClick={() => handleTalkAI(idx)}
        >
          <MessageSquare size={13} />
          跟 AI 说想怎么修改路线
        </button>

        <div className="vtl-menu-divider" />

        {/* 删除当前节点 */}
        <button
          className="vtl-menu-item vtl-menu-item--danger"
          onClick={() => handleDeleteStop(idx)}
        >
          <X size={13} />
          删除当前节点
        </button>
      </div>
    );
  }

  return (
    <>
      {/* ── 置顶条 ── */}
      <div className="active-trip-bar">
        <div className="active-trip-info">
          <div className="active-trip-badge">
            <CheckCircle2 size={13} />
            出行中
          </div>
          <p className="active-trip-title">{route.title}</p>
          <div className="active-trip-progress">
            <span className="active-stop active-stop--current">
              <Navigation size={11} />
              {currentStop.start_time} {currentStop.name}
            </span>
            {nextStop && (
              <>
                <ChevronRight size={11} className="active-progress-arrow" />
                <span className="active-stop active-stop--next">
                  <Clock size={11} />
                  {nextStop.start_time} {nextStop.name}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="active-trip-actions">
          {/* 撤销按钮 */}
          {undoStack.length > 0 && (
            <button
              type="button"
              className="active-trip-btn active-trip-btn--undo"
              onClick={handleUndo}
              title="撤销上一步操作"
            >
              <Undo2 size={13} />
            </button>
          )}
          <button
            type="button"
            className="active-trip-btn active-trip-btn--unselect"
            onClick={onUnselect}
          >
            取消行程
          </button>
        </div>
      </div>

      {/* ── 竖向节点进度轨道 ── */}
      <div className="vtl-list">
        {stops.map((stop, idx) => {
          const state: "done" | "current" | "upcoming" =
            idx < activeIdx ? "done" : idx === activeIdx ? "current" : "upcoming";
          const isLast = idx === lastIdx;
          const trans = stop.transit_to_next;
          const dur = durLabel(stop.start_time, stop.end_time);

          return (
            <div key={stop.poi_id} className={`vtl-item ${state}`}>
              {/* ── 站点行 ── */}
              <div className="vtl-row">
                {/* 左侧脊柱：圆点 + 竖线 */}
                <div className="vtl-spine">
                  <button
                    type="button"
                    className={`vtl-dot ${state}`}
                    onClick={() => handleArrived(idx)}
                    title={state === "current" ? "当前位置" : `标记「${stop.name}」为当前位置`}
                  >
                    {state === "done" && <CheckCheck size={9} color="white" strokeWidth={2.5} />}
                    {state === "current" && <div className="vtl-dot-pulse" />}
                  </button>
                  {!isLast && <div className={`vtl-vline ${state === "done" ? "done" : ""}`} />}
                </div>

                {/* 右侧内容区 */}
                <div className="vtl-content">
                  <div className="vtl-header">
                    <span className="vtl-time">{stop.start_time}–{stop.end_time}</span>
                    <span className="vtl-name">{stop.name}</span>
                    {dur && <span className="vtl-dur-badge">{dur}</span>}
                    {state === "current" && <span className="vtl-here-badge">📍 我在这</span>}
                  </div>

                  {/* 排队情况（当前站 + 即将到达的站显示） */}
                  {state !== "done" && stop.queue_level && stop.queue_level !== "none" && (
                    <div className={`vtl-queue-row vtl-queue-row--${stop.queue_level}`}>
                      <span className="vtl-queue-dot">●</span>
                      <span className="vtl-queue-text">
                        {{
                          low:       "排队较少",
                          medium:    "排队一般",
                          high:      "排队较多",
                          very_high: "排队非常多",
                        }[stop.queue_level]}
                        {stop.queue_minutes > 0 && `（约 ${stop.queue_minutes} 分钟）`}
                      </span>
                    </div>
                  )}

                  {/* 预约状态行 */}
                  {state !== "done" && stop.booking_required && (
                    <div className="vtl-booking-row">
                      {/* 网页预约：默认已预约，可切换 */}
                      {stop.booking_url && (
                        bookedIds.has(stop.poi_id) ? (
                          <button
                            type="button"
                            className="vtl-btn vtl-btn--booked"
                            onClick={() => setBookedIds((prev) => {
                              const next = new Set(prev);
                              next.delete(stop.poi_id);
                              return next;
                            })}
                          >
                            <CalendarCheck size={12} />
                            已预约
                          </button>
                        ) : (
                          <a
                            href={stop.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="vtl-btn vtl-btn--book"
                            onClick={() => setBookedIds((prev) => new Set([...prev, stop.poi_id]))}
                          >
                            <ExternalLink size={12} />
                            去预约
                          </a>
                        )
                      )}
                      {/* 电话预约 */}
                      {stop.booking_phone && !stop.booking_url && (
                        <a
                          href={`tel:${stop.booking_phone}`}
                          className="vtl-btn vtl-btn--phone"
                        >
                          <Phone size={12} />
                          电话预约 {stop.booking_phone}
                        </a>
                      )}
                      {/* 仅备注，无链接/电话 */}
                      {!stop.booking_url && !stop.booking_phone && (
                        <span className="vtl-booking-note">需提前预约</span>
                      )}
                      {/* 预约备注 */}
                      {stop.booking_note && (
                        <span className="vtl-booking-note">{stop.booking_note}</span>
                      )}
                    </div>
                  )}

                  {/* 末站行程结束按钮 */}
                  {state === "current" && isLast && (
                    <div className="vtl-actions">
                      <button
                        type="button"
                        className="vtl-btn vtl-btn--arrive"
                        onClick={() => handleArrived(idx)}
                      >
                        <CheckCircle2 size={12} />
                        行程结束
                      </button>
                    </div>
                  )}
                </div>

                {/* ⋯ 更多操作按钮（done 状态不显示） */}
                {state !== "done" && (
                  <div className="vtl-menu-wrap">
                    <button
                      type="button"
                      className={`vtl-menu-trigger${menuIdx === idx ? " active" : ""}`}
                      onClick={() => {
                        setMenuIdx(menuIdx === idx ? null : idx);
                        setExtendIdx(null);
                        setRestIdx(null);
                      }}
                    >
                      <MoreHorizontal size={14} />
                    </button>
                    {renderMenu(idx, state)}
                  </div>
                )}
              </div>

              {/* ── 交通段 ── */}
              {!isLast && trans && (
                <div className="vtl-transit">
                  <div className="vtl-transit-spine">
                    <div className={`vtl-transit-vline ${state === "done" ? "done" : ""}`} />
                  </div>
                  <div
                    className={`vtl-transit-pill ${state === "done" ? "done" : ""}`}
                    style={{ "--transit-color": TRANSIT_COLOR[trans.mode] } as React.CSSProperties}
                  >
                    <span className="vtl-transit-icon">{TRANSIT_ICON[trans.mode]}</span>
                    <span className="vtl-transit-label">{TRANSIT_LABEL[trans.mode]}</span>
                    <span className="vtl-transit-sep">·</span>
                    <span className="vtl-transit-dur">{trans.duration_minutes}分钟</span>
                    <span className="vtl-transit-sep">·</span>
                    <span className="vtl-transit-dist">{formatDist(trans.distance_m)}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── 行程结束评价卡片 ── */}
      {showFeedback && !showSummary && (
        <TripEndFeedback
          scores={feedbackScores}
          setScores={setFeedbackScores}
          comment={feedbackComment}
          setComment={setFeedbackComment}
          onSubmit={() => { setShowSummary(true); }}
          onSkip={() => { setShowFeedback(false); }}
        />
      )}

      {/* ── 路线总结页 ── */}
      {showSummary && (
        <TripSummaryOverlay
          route={route}
          scores={feedbackScores}
          comment={feedbackComment}
          onFinish={(r, avg) => {
            setShowSummary(false);
            onTripFinished?.(r, avg);
          }}
        />
      )}
    </>
  );
}

// ── 路线摘要小卡片 ──────────────────────────────────────────
interface RouteSummaryCardProps {
  route: Route;
  index: number;
  onExpand: (routeId: string) => void;
}

const CATEGORY_EMOJI: Record<string, string> = {
  food: "🍜", restaurant: "🍜", culture: "🏛️", museum: "🏛️",
  nature: "🌿", park: "🌿", shopping: "🛍️", landmark: "📍",
  show: "🎭", rest: "☕", citywalk: "🚶", scenic: "🌄",
};

// 几个渐变作为无封面时的占位背景
const FALLBACK_GRADIENTS = [
  "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
  "linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)",
  "linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)",
];

function RouteSummaryCard({ route, index, onExpand }: RouteSummaryCardProps) {
  const [imgIndex, setImgIndex] = useState(0);
  const stops = route.stops ?? [];

  // 收集有封面图的 stops
  const imgStops = stops.filter((s) => s.cover_image_url);

  const startTime = stops[0]?.start_time ?? "";
  const endTime   = stops[stops.length - 1]?.end_time ?? "";
  const timeRange = startTime && endTime ? `${startTime} → ${endTime}` : "";

  // 站点流程预览（前3个）
  const previewStops = stops.slice(0, 3);
  const moreCount = stops.length - previewStops.length;

  // 综合分（归一到 0-10）
  const score = route.score <= 10 ? route.score : route.score / 10;

  const currentImg = imgStops[imgIndex]?.cover_image_url ?? null;
  const fallbackGradient = FALLBACK_GRADIENTS[index % FALLBACK_GRADIENTS.length];

  // 第一个 reason 作为图片角标，其余在右侧展示
  const reasons = route.reasons ?? [];
  const badgeReason = reasons[0] ?? null;
  const extraReasons = reasons.slice(1, 3); // 最多再展示2个

  return (
    <div className="route-summary-card" onClick={() => onExpand(route.route_id)}>
      {/* 左侧：图片 + 序号角标 + 圆点 */}
      <div className="rsc-left">
        <div
          className="rsc-img-wrap"
          style={!currentImg ? { background: fallbackGradient } : undefined}
        >
          {currentImg && (
            <img className="rsc-img" src={currentImg} alt={imgStops[imgIndex]?.name} />
          )}
          {/* 序号角标（左上角） */}
          <div className="rsc-index-badge">{index + 1}</div>
          {/* 核心亮点标签（右上角，叠在图片上） */}
          {badgeReason && (
            <div className="rsc-reason-badge">{badgeReason}</div>
          )}
        </div>
        {/* 圆点切换（有多张图时显示） */}
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

      {/* 右侧：文字内容 */}
      <div className="rsc-body">
        {/* 标题 + 分数 */}
        <div className="rsc-top">
          <span className="rsc-title">{route.title}</span>
          <span className="rsc-score">{score.toFixed(1)}</span>
        </div>

        {/* 亮点标签行（标题下方） */}
        {extraReasons.length > 0 && (
          <div className="rsc-reasons">
            {extraReasons.map((r) => (
              <span key={r} className="rsc-reason-tag">{r}</span>
            ))}
          </div>
        )}

        {/* 一句话摘要 */}
        {route.summary && (
          <p className="rsc-desc">{route.summary}</p>
        )}

        {/* 站点流程预览 */}
        {previewStops.length > 0 && (
          <div className="rsc-flow">
            {previewStops.map((s, i) => (
              <span key={s.poi_id} className="rsc-flow-item">
                {CATEGORY_EMOJI[s.category] ?? "📍"}{s.name}
                {(i < previewStops.length - 1 || moreCount > 0) && (
                  <span className="rsc-flow-arrow">→</span>
                )}
              </span>
            ))}
            {moreCount > 0 && (
              <span className="rsc-flow-more">+{moreCount}</span>
            )}
          </div>
        )}

        {/* 核心指标 */}
        <div className="rsc-metrics">
          {timeRange && (
            <span className="rsc-metric"><Clock size={10} />{timeRange}</span>
          )}
          <span className="rsc-metric"><Wallet size={10} />人均¥{route.total_cost_per_person}</span>
          <span className="rsc-metric"><MapPin size={10} />{stops.length}处</span>
        </div>
      </div>

      {/* 右箭头 */}
      <ChevronRight size={15} className="rsc-chevron" />
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────────
export function RouteCompare({ routes, loading = false, onAction, onPoiAction, onInjectChat, onTripFinished }: RouteCompareProps) {
  const [expandedRouteId, setExpandedRouteId] = useState<string | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);

  // 当 routes 更新（AI 重新规划）时，清除已选和展开状态
  useEffect(() => {
    setSelectedRouteId(null);
    setExpandedRouteId(null);
  }, [routes]);

  const showSkeletons = loading && routes.length === 0;
  const showRoutes    = routes.length > 0;
  const selectedRoute = routes.find((r) => r.route_id === selectedRouteId) ?? null;
  const expandedRoute = routes.find((r) => r.route_id === expandedRouteId) ?? null;

  function handleSelect(routeId: string) {
    setSelectedRouteId(routeId);
    setExpandedRouteId(null);
  }

  return (
    <section className="route-section">
      {/* ── 摘要小卡片列表 ── */}
      {!expandedRoute && (
        <>
          {showSkeletons && (
            <div className="route-summary-list">
              {[0, 1, 2].map((i) => (
                <div key={i} className="route-summary-card route-summary-card--skeleton">
                  <div className="rsc-left" />
                  <div className="rsc-body">
                    <div className="sk-line sk-title" />
                    <div className="sk-line sk-short" style={{ marginTop: 6 }} />
                    <div className="sk-metrics" style={{ marginTop: 8 }}>
                      <div className="sk-chip" /><div className="sk-chip" /><div className="sk-chip" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {showRoutes && (
            <div className="route-summary-list">
              <div className="route-summary-header">
                <span className="route-summary-header-title">为你规划了 {routes.length} 条方案</span>
                <span className="route-summary-header-hint">点击查看详情</span>
              </div>
              {routes.map((route, i) => (
                <RouteSummaryCard
                  key={route.route_id}
                  route={route}
                  index={i}
                  onExpand={setExpandedRouteId}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ── 展开详情视图 ── */}
      {expandedRoute && (
        <div className="route-detail-view">
          {/* 返回摘要列表 */}
          <button
            type="button"
            className="route-detail-back"
            onClick={() => setExpandedRouteId(null)}
          >
            <ChevronDown size={14} style={{ transform: "rotate(90deg)" }} />
            返回所有方案
          </button>

          <RouteCard
            route={expandedRoute}
            selected={expandedRoute.route_id === selectedRouteId}
            onSelect={handleSelect}
            onAction={onAction}
            onPoiAction={onPoiAction}
            onInjectChat={onInjectChat}
          />
        </div>
      )}

      {/* ── 已选方案行程轨道（展示在最底部） ── */}
      {selectedRoute && (
        <ActiveTripBar
          route={selectedRoute}
          onUnselect={() => setSelectedRouteId(null)}
          onAction={onAction}
          onPoiAction={onPoiAction}
          onInjectChat={onInjectChat}
          onTripFinished={onTripFinished}
        />
      )}
    </section>
  );
}

// ── 选定后折叠的「查看其他方案」区域 ─────────────────────────
interface CompareCollapsedProps {
  routes: Route[];
  selectedRouteId: string;
  onSelect: (id: string) => void;
  onAction?: (actionKey: string, routeId: string) => void;
  onPoiAction?: (action: PoiAction, routeId: string) => void;
}

function CompareCollapsed({ routes, selectedRouteId, onSelect, onAction, onPoiAction }: CompareCollapsedProps) {
  const [expanded, setExpanded] = useState(false);

  const otherRoutes = routes.filter((r) => r.route_id !== selectedRouteId);
  if (otherRoutes.length === 0) return null;

  return (
    <div className="compare-collapsed">
      <button
        type="button"
        className="compare-collapsed-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        <span>查看其他 {otherRoutes.length} 条方案</span>
        <ChevronDown
          size={13}
          style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}
        />
      </button>

      {expanded && (
        <div className="compare-collapsed-list">
          {otherRoutes.map((route) => (
            <RouteCard
              key={route.route_id}
              route={route}
              selected={false}
              onSelect={onSelect}
              onAction={onAction}
              onPoiAction={onPoiAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}
