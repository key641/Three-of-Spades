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
import routeThemeCamera from "../assets/route-theme-camera.png";
import routeThemeCoin from "../assets/route-theme-coin.png";
import routeThemeKite from "../assets/route-theme-kite.png";
import routeThemeMoon from "../assets/route-theme-moon.png";
import routeThemeUmbrella from "../assets/route-theme-umbrella.png";
import routeThemeBoy from "../assets/route-theme-boy.png";
import routeThemeFood from "../assets/route-theme-food.png";
import routeThemeFlower from "../assets/route-theme-flower.png";
import routeThemeMilk from "../assets/route-theme-milk.png";

export interface RouteCompareProps {
  routes: Route[];
  loading?: boolean;
  /** 从 RouteOptimizeBar 冒泡上来的路线级操作 */
  onAction?: (actionKey: string, routeId: string) => void;
  /** 从 PoiCard 冒泡上来的 POI 级操作 */
  onPoiAction?: (action: PoiAction, routeId: string) => void;
  /** 行程完结并关闭总结页时回调（保存记录+回首页） */
  onTripFinished?: (route: Route, avgScore: number) => void;
  /** 当用户切换预览的路线时回调（路线 id），用于同步地图 */
  onRoutePreview?: (routeId: string) => void;
  /** 已选方案的 stops 被本地编辑后，把最新 stops 传给父级（用于地图同步） */
  onLiveStopsChange?: (routeId: string, stops: RouteStop[]) => void;
  /** 看板视图中自动展开详情，跳过摘要卡片列表 */
  autoExpand?: boolean;
  /** 自动选中第一条路线并展示行程跟踪条 */
  autoSelect?: boolean;
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
export interface ActiveTripBarProps {
  route: Route;
  onUnselect: () => void;
  onAction?: (actionKey: string, routeId: string) => void;
  onPoiAction?: (action: PoiAction, routeId: string) => void;
  onTripFinished?: (route: Route, avgScore: number) => void;
  /** stops 被本地编辑（删除/排序/插入）后回调，用于同步地图 */
  onStopsChange?: (stops: RouteStop[]) => void;
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
onSubmit();
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


export function ActiveTripBar({ route, onUnselect, onAction, onTripFinished, onStopsChange }: ActiveTripBarProps) {
  // 本地可编辑 stops 列表
  const [stops, setStops] = useState<RouteStop[]>(route.stops);
  // 当前所在节点
  const [activeIdx, setActiveIdx] = useState(0);
  // 行程结束评价
  const [showFeedback, setShowFeedback] = useState(false);
  const [tripEnded, setTripEnded] = useState(false);
  const feedbackRef = useRef<HTMLDivElement>(null);
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
    const recalculated = recalcTimes(newStops, fromIdx);
    setStops(recalculated);
    onStopsChange?.(recalculated);
  }

  // ── 标记到达 ─────────────────────────────────────────────
  function handleArrived(idx: number) {
    if (idx === activeIdx && idx !== stops.length - 1) return;
    setActiveIdx(idx);
    // 到达末站时触发评价卡片
    // 注意：删节点后 activeIdx 可能已被 clamp 到末站，此时 activeIdx === stops.length - 1，
    // 所以不能用 activeIdx !== stops.length - 1 作为判断条件，
    // 改为：只要到达末站且评价卡片还未展示，就展示
    if (idx === stops.length - 1 && !showFeedback && !tripEnded) {
      setShowFeedback(true);
      // 等待 DOM 渲染后自动滚动到评价卡片
      setTimeout(() => {
        feedbackRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
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
    onStopsChange?.(prev);
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

        {/* 删除当前节点（只剩 1 个时不可删）*/}
        <button
          className="vtl-menu-item vtl-menu-item--danger"
          disabled={stops.length <= 1}
          onClick={() => handleDeleteStop(idx)}
          style={stops.length <= 1 ? { opacity: 0.38, cursor: "not-allowed" } : undefined}
        >
          <X size={13} />
          {stops.length <= 1 ? "至少保留 1 个节点" : "删除当前节点"}
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

          return (
            <div key={stop.poi_id} className={`vtl-item ${state}${isLast ? " last-item" : ""}`}>
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
                    <div className="vtl-name-row">
                      {/* 排队小标签在地名前面 */}
                      {state !== "done" && stop.queue_level && stop.queue_level !== "none" && stop.queue_minutes > 0 && (
                        <span className={`vtl-queue-tag vtl-queue-tag--${stop.queue_level}`}>
                          等{stop.queue_minutes}分钟
                        </span>
                      )}
                      {state !== "done" && stop.queue_level === "none" && (
                        <span className="vtl-noqueue-tag">无需排队</span>
                      )}
                      <span className="vtl-name">{stop.name}</span>
                    </div>
                    {/* 更多按钮与地点同行 */}
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
                        className={`vtl-btn vtl-btn--arrive${tripEnded ? " vtl-btn--ended" : ""}`}
                        disabled={tripEnded}
                        onClick={() => { setTripEnded(true); handleArrived(idx); }}
                      >
                        <CheckCircle2 size={12} />
                        {tripEnded ? "行程已结束" : "行程结束"}
                      </button>
                    </div>
                  )}
                </div>

              </div>

              {/* ── 交通段 ── */}
              {!isLast && trans && (
                <div className="vtl-transit">
                  {/* 与 vtl-spine 等宽的占位，背景延续虚线 */}
                  <div className={`vtl-transit-spine ${state === "done" ? "done" : ""}`} />
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
                  <button type="button" className="vtl-nav-btn" title="导航">
                    <Navigation size={12} />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── 行程结束评价卡片 ── */}
      {showFeedback && !showSummary && (
        <div ref={feedbackRef}>
        <TripEndFeedback
          scores={feedbackScores}
          setScores={setFeedbackScores}
          comment={feedbackComment}
          setComment={setFeedbackComment}
          onSubmit={() => { setShowSummary(true); }}
          onSkip={() => { setShowFeedback(false); }}
        />
        </div>
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
  onPreview?: (routeId: string) => void;
}

const CATEGORY_EMOJI: Record<string, string> = {
  food: "🍜", restaurant: "🍜", culture: "🏛️", museum: "🏛️",
  nature: "🌿", park: "🌿", shopping: "🛍️", landmark: "📍",
  show: "🎭", rest: "☕", citywalk: "🚶", scenic: "🌄",
};

// category → 彩点颜色（与首页猜你喜欢一致）
const CATEGORY_COLOR: Record<string, string> = {
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

// 去除字符串首尾的 emoji 字符
function stripLeadingEmoji(text: string): string {
  return text.replace(/^[\u{1F000}-\u{1FFFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\uFE0F\s]+/u, "").trim();
}

// 几个渐变作为无封面时的占位背景
const FALLBACK_GRADIENTS = [
  "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
  "linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)",
  "linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)",
];

// 路线亮点标签：高饱和多巴胺配色，按方案顺序循环。
const LABEL_GRADIENTS: [string, string][] = [
["#ff5d8f", "#ff8a5b"],
["#4f7cff", "#5bc8ff"],
["#ffbd2e", "#ff7b54"],
["#8b5cf6", "#d36cff"],
["#18b98b", "#50d6a4"],
];

const ROUTE_THEME_ILLUSTRATIONS: Record<string, { src: string; label: string }> = {
  photo_citywalk: { src: routeThemeCamera, label: "相机" },
  photo_food: { src: routeThemeCamera, label: "相机" },
  budget: { src: routeThemeCoin, label: "金币" },
  nature_relax: { src: routeThemeFlower, label: "花朵" },
  night_friendly: { src: routeThemeMoon, label: "月亮" },
  indoor_rainy: { src: routeThemeUmbrella, label: "雨伞" },
  balanced: { src: routeThemeBoy, label: "出发" },
  food_first: { src: routeThemeFood, label: "美食" },
  low_walking: { src: routeThemeMilk, label: "轻松休闲" },
};

function getRouteThemeIllustration(route: Route) {
  const routeText = `${route.title} ${route.summary}`;
  if (/春游|踏青|春日/.test(routeText)) return { src: routeThemeKite, label: "风筝" };
  return ROUTE_THEME_ILLUSTRATIONS[route.objective] ?? ROUTE_THEME_ILLUSTRATIONS.balanced;
}

function RouteSummaryCard({ route, index, onExpand, onPreview }: RouteSummaryCardProps) {
  const [imgIndex, setImgIndex] = useState(0);
  const [failedImageUrls, setFailedImageUrls] = useState<Set<string>>(() => new Set());
  const stops = route.stops ?? [];

  // 收集可展示的封面图。加载失败时即时移除，稳定回退到本地渐变背景。
  const imgStops = stops.filter((s) => s.cover_image_url && !failedImageUrls.has(s.cover_image_url));

  const startTime = stops[0]?.start_time ?? "";
  const endTime   = stops[stops.length - 1]?.end_time ?? "";
  const timeRange = startTime && endTime ? `${startTime} → ${endTime}` : "";

  // 交通时间：优先用 route.total_travel_minutes，否则从 stops 累加
  const travelMin = route.total_travel_minutes ?? stops.reduce((sum, s) => sum + (s.travel_minutes_from_previous ?? 0), 0);

  // 站点流程预览（前3个）
  const previewStops = stops.slice(0, 3);
  const moreCount = stops.length - previewStops.length;

  // 综合分（归一到 0-10）
  const score = route.score <= 10 ? route.score : route.score / 10;

  const fallbackGradient = FALLBACK_GRADIENTS[index % FALLBACK_GRADIENTS.length];

  // 图片角标保持简短，避免较长的推荐理由挤压封面图。
  const reasons = route.reasons ?? [];
  const badgeReason = reasons[0]?.slice(0, 7) ?? null;
  const themeIllustration = getRouteThemeIllustration(route);

  // ── 图片滑动逻辑 ──────────────────────────────────────────
  const imgWrapRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; locked: boolean | null } | null>(null);

  // 拦截原生 touchmove，防止横滑时触发外层滚动
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
    <div className="route-summary-card" onClick={() => { onExpand(route.route_id); onPreview?.(route.route_id); }}>
      {/* 左侧：图片 + 标签 + 圆点 */}
      <div className="rsc-left">
        <div
          ref={imgWrapRef}
          className="rsc-img-wrap"
          style={imgStops.length === 0 ? { background: fallbackGradient } : undefined}
          onTouchStart={imgStops.length > 1 ? handleTouchStart : undefined}
          onTouchEnd={imgStops.length > 1 ? handleTouchEnd : undefined}
        >
          {/* 图片轨道：横排所有图片，translateX 切换 */}
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
                  loading="lazy"
                  decoding="async"
                  onError={() => setFailedImageUrls((urls) => {
                    const nextUrls = new Set(urls);
                    nextUrls.add(s.cover_image_url!);
                    return nextUrls;
                  })}
                />
              ))}
            </div>
          )}
          {/* 核心亮点标签（左上角，尖角样式，与首页猜你喜欢标签一致） */}
          {badgeReason && (
            <div
              className="rsc-reason-badge"
              style={{
                background: `linear-gradient(135deg, ${LABEL_GRADIENTS[index % LABEL_GRADIENTS.length][0]} 0%, ${LABEL_GRADIENTS[index % LABEL_GRADIENTS.length][1]} 100%)`,
              }}
            >{badgeReason}</div>
          )}
          {/* 圆点（有多张图时，图片内底部 overlay） */}
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

      {/* 右侧：文字内容 */}
      <div className="rsc-body">
        <img
          src={themeIllustration.src}
          alt=""
          className="rsc-theme-illustration"
          aria-hidden="true"
          width={58}
          height={58}
          loading="lazy"
          decoding="async"
        />

        {/* 第一行：标题 + 时间范围 */}
        <div className="rsc-top">
          <span className="rsc-title">{stripLeadingEmoji(route.title)}</span>
          {timeRange && <span className="rsc-time-inline">{timeRange}</span>}
        </div>

        {/* 第二行：地点流（彩点 + 名称 + 分隔符，超出可横滑） */}
        {stops.length > 0 && (
          <div className="rsc-poi-line">
            {stops.map((s, i) => (
              <span key={s.poi_id} className="rsc-poi-inline">
                <span
                  className="rsc-poi-dot"
                  style={{ background: CATEGORY_COLOR[s.category] ?? "#9CA3AF" }}
                />
                <span className="rsc-poi-name">{s.name}</span>
                {i < stops.length - 1 && (
                  <span className="rsc-poi-sep">›</span>
                )}
              </span>
            ))}
          </div>
        )}

        {/* 第三行：首站距离 + 交通时间 */}
        <div className="rsc-meta-row">
          {(() => {
            const dist = stops[0]?.distance_m;
            return dist != null ? (
              <>
                <MapPin size={9} strokeWidth={2} />
                <span>首站{dist >= 1000 ? `${(dist / 1000).toFixed(1)}km` : `${dist}m`}</span>
              </>
            ) : null;
          })()}
          {travelMin > 0 && (
            <>
              {stops[0]?.distance_m != null && <span className="rsc-meta-dot">·</span>}
              <Clock size={9} strokeWidth={2} />
              <span>交通{travelMin}分钟</span>
            </>
          )}
        </div>
      </div>

      {/* 右箭头 */}
      <ChevronRight size={15} className="rsc-chevron" />
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────────
export function RouteCompare({ routes, loading = false, onAction, onPoiAction, onTripFinished, onRoutePreview, onLiveStopsChange, autoExpand = false, autoSelect = false }: RouteCompareProps) {
  const [expandedRouteId, setExpandedRouteId] = useState<string | null>(null);
  // 保存用户选中的完整路线（含编辑后的 stops）
  const [selectedRoute, setSelectedRoute] = useState<Route | null>(() => autoSelect && routes.length > 0 ? { ...routes[0] } : null);

  // 当 AI 重新规划（route_id 集合变化）时才清除已选和展开状态。
  // 注意：不能用 routes 引用，因为 patchRouteStops 也会改变 routes 引用（修改 stops），
  // 那样会导致每次删节点都把 selectedRoute 清空。
  const routeIdsKey = routes.map((r) => r.route_id).join(",");
  useEffect(() => {
    if (!autoSelect) {
      setSelectedRoute(null);
    }
    setExpandedRouteId(null);
    // 看板视图自动展开 / 选中第一条
    if (routes.length > 0) {
      if (autoExpand) setExpandedRouteId(routes[0].route_id);
      if (autoSelect) setSelectedRoute({ ...routes[0] });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeIdsKey]);

  const showSkeletons = loading && routes.length === 0;
  const showRoutes    = routes.length > 0;
  const expandedRoute = routes.find((r) => r.route_id === expandedRouteId) ?? null;
  // 从最新 routes 中取选中路线的最新数据（patchRouteStops 会更新 routes，确保 stops 最新）
  const liveSelectedRoute = selectedRoute
    ? (routes.find((r) => r.route_id === selectedRoute.route_id) ?? selectedRoute)
    : null;

  function handleSelect(route: Route) {
    setSelectedRoute(route);
    setExpandedRouteId(null);
    onRoutePreview?.(route.route_id);
  }

  return (
    <section className="route-section">
      {/* ── 摘要小卡片列表：选中方案后仍保留，便于随时比较和切换。 ── */}
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
              {routes.map((route, i) => (
                <RouteSummaryCard
                  key={route.route_id}
                  route={route}
                  index={i}
                  onExpand={setExpandedRouteId}
                  onPreview={onRoutePreview}
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
            selected={expandedRoute.route_id === selectedRoute?.route_id}
            onSelect={handleSelect}
            onAction={onAction}
            onPoiAction={onPoiAction}
            onStopsChange={(routeId, newStops) => onLiveStopsChange?.(routeId, newStops)}
          />
        </div>
      )}

      {/* ── 已选方案行程轨道；其余方案保留在下方，支持随时重新比较。 ── */}
      {liveSelectedRoute && (
        <>
          <ActiveTripBar
            route={liveSelectedRoute}
            onUnselect={() => setSelectedRoute(null)}
            onAction={onAction}
            onPoiAction={onPoiAction}
            onTripFinished={onTripFinished}
            onStopsChange={(newStops) => onLiveStopsChange?.(liveSelectedRoute.route_id, newStops)}
          />
          {routes.length > 1 && (
            <CompareCollapsed
              routes={routes}
              selectedRouteId={liveSelectedRoute.route_id}
              onSelect={handleSelect}
              onAction={onAction}
              onPoiAction={onPoiAction}
            />
          )}
        </>
      )}
    </section>
  );
}

// ── 选定后折叠的「查看其他方案」区域 ─────────────────────────
interface CompareCollapsedProps {
  routes: Route[];
  selectedRouteId: string;
  onSelect: (route: Route) => void;
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
