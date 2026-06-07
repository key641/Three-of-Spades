import { MapPin, Star, Wallet, Footprints, Train, Bus, CarTaxiFront, Bike, MoreHorizontal, RefreshCcw, MessageSquare, Trash2, Phone, ExternalLink, PlusCircle, ArrowLeftRight, Check, Loader2 } from "lucide-react";
import { useEffect, useRef, useState, useCallback } from "react";
import type { RouteStop, TransitSegment } from "../api/types";
import { getCategoryLabel, getCategoryStyle } from "../utils/categoryLabels";

// ── POI 操作类型 ──────────────────────────────────────────────
export type PoiAction =
  | { type: "swap_same";   poiId: string; poiName: string }
  | { type: "swap_as";     poiId: string; poiName: string; category: string }
  | { type: "talk_ai";     poiId: string; poiName: string }
  | { type: "remove";      poiId: string; poiName: string };

export interface RouteTimelineProps {
  stops: RouteStop[];
  onPoiAction?: (action: PoiAction) => void;
  /** 注入聊天框文本（用于"增加节点"等操作） */
  onInjectChat?: (text: string) => void;
  /** stops 本地编辑后回调（删除、更换交通等） */
  onStopsChange?: (stops: RouteStop[]) => void;
}

// ── 排队程度配置 ──────────────────────────────────────────────
const QUEUE_LEVEL_CONFIG = {
  none:      { label: "无需排队",   color: "var(--color-success)" },
  low:       { label: "排队较少",   color: "var(--color-success)" },
  medium:    { label: "排队一般",   color: "var(--color-warning)" },
  high:      { label: "排队较多",   color: "var(--color-error)"   },
  very_high: { label: "排队非常多", color: "var(--color-error)"   },
};

// ── 人头排队图标（1/2/3 个小人，颜色对应人流程度） ─────────────
const CROWD_COLOR: Record<string, string> = {
  low:       "#12B76A",  // 绿 — 人少
  medium:    "#F79009",  // 黄 — 适中
  high:      "#F04438",  // 红 — 人多
  very_high: "#F04438",  // 红 — 非常多
};
const CROWD_COUNT: Record<string, number> = {
  low: 1, medium: 2, high: 3, very_high: 3,
};

// 单个小人 SVG path（简笔头+身）
export function PersonSvg({ color, opacity = 1 }: { color: string; opacity?: number }) {
  return (
    <svg width="10" height="18" viewBox="0 0 10 18" fill="none" style={{ opacity }}>
      {/* 头 */}
      <circle cx="5" cy="2.8" r="2.2" fill={color} />
      {/* 身体 */}
      <path d="M2.5 6.5 C2.5 6.5 1.5 7 1 9 L1.5 12 H8.5 L9 9 C8.5 7 7.5 6.5 7.5 6.5 Z" fill={color} />
      {/* 左腿 */}
      <path d="M3.5 12 L3 17" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
      {/* 右腿 */}
      <path d="M6.5 12 L7 17" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function CrowdIcon({ level }: { level: string }) {
  const color = CROWD_COLOR[level] ?? "#9CA3AF";
  const count = CROWD_COUNT[level] ?? 1;
  return (
    <span className="poi-crowd-svg">
      <PersonSvg color={color} />
      <PersonSvg color={color} opacity={count >= 2 ? 1 : 0.2} />
      <PersonSvg color={color} opacity={count >= 3 ? 1 : 0.2} />
    </span>
  );
}

// ── 交通方式配置 ──────────────────────────────────────────────
const TRANSIT_MODE_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  walk:  { icon: <Footprints size={12} />,   label: "步行", color: "#52C41A" },
  metro: { icon: <Train size={12} />,        label: "地铁", color: "#1677FF" },
  bus:   { icon: <Bus size={12} />,          label: "公交", color: "#722ED1" },
  taxi:  { icon: <CarTaxiFront size={12} />, label: "打车", color: "#FA8C16" },
  bike:  { icon: <Bike size={12} />,         label: "骑行", color: "#13C2C2" },
};

// ── 更换交通方式的可选项（步行/骑行/公交/驾车） ──────────────
type TransitMode = "walk" | "bike" | "metro" | "bus" | "taxi";

const TRANSIT_SWITCH_OPTIONS: {
  mode: TransitMode;
  icon: React.ReactNode;
  label: string;
  color: string;
  /** 根据距离估算时间（分钟/千米），speed in km/min */
  speedKmPerMin: number;
}[] = [
  { mode: "walk",  icon: <Footprints size={18} />, label: "步行", color: "#52C41A", speedKmPerMin: 0.083 }, // ~5 km/h
  { mode: "bike",  icon: <Bike size={18} />,       label: "骑行", color: "#13C2C2", speedKmPerMin: 0.25  }, // ~15 km/h
  { mode: "metro", icon: <Train size={18} />,      label: "地铁", color: "#1677FF", speedKmPerMin: 0.45  }, // ~27 km/h (含进出站)
  { mode: "bus",   icon: <Bus size={18} />,         label: "公交", color: "#722ED1", speedKmPerMin: 0.35  }, // ~21 km/h (含等待)
  { mode: "taxi",  icon: <CarTaxiFront size={18} />, label: "驾车", color: "#FA8C16", speedKmPerMin: 0.5   }, // ~30 km/h (城市)
];

/** 根据距离（米）和速度估算时间（分钟），最少 1 分钟 */
function estimateTime(distanceM: number, speedKmPerMin: number): number {
  if (!distanceM || distanceM <= 0) return 5;
  return Math.max(1, Math.round(distanceM / 1000 / speedKmPerMin));
}

// ── 可换品类列表 ──────────────────────────────────────────────
const CATEGORY_COLORS: Record<string, string> = {
  citywalk:   "#E8F5E9",
  cafe:       "#FFF8E1",
  restaurant: "#FFF3E0",
  museum:     "#E3F2FD",
  park:       "#E8F5E9",
  shopping:   "#FCE4EC",
  scenic:     "#E0F7FA",
  snack:      "#FBE9E7",
};

function formatReviewCount(count: number): string {
  if (count >= 10000) return `${(count / 10000).toFixed(1)}万`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return String(count);
}

function formatDistance(m?: number): string {
  if (m == null) return "";
  if (m >= 1000) return `${(m / 1000).toFixed(1)}km`;
  return `${m}m`;
}

function normalizeTransitMode(mode?: string | null): TransitSegment["mode"] {
  if (!mode) return "walk";
  if (mode.includes("metro") || mode.includes("地铁")) return "metro";
  if (mode.includes("bus") || mode.includes("公交")) return "bus";
  if (mode.includes("taxi") || mode.includes("drive") || mode.includes("打车") || mode.includes("驾车")) return "taxi";
  if (mode.includes("bike") || mode.includes("骑行")) return "bike";
  return "walk";
}

function buildTransitDescription(stop: RouteStop): string | undefined {
  const steps = stop.route_steps_from_previous?.filter(Boolean) ?? [];
  if (steps.length > 0) return steps.join(" · ");
  return undefined;
}

function withBackendTransitSegments(input: RouteStop[]): RouteStop[] {
  const stops = input.map((stop) => ({ ...stop }));
  for (let i = 0; i < stops.length - 1; i++) {
    if (stops[i].transit_to_next) continue;
    const next = stops[i + 1];
    if (!next.transport_mode_from_previous && next.travel_minutes_from_previous == null && next.distance_km_from_previous == null) {
      continue;
    }
    stops[i].transit_to_next = {
      mode: normalizeTransitMode(next.transport_mode_from_previous),
      duration_minutes: next.travel_minutes_from_previous ?? next.amap_duration_minutes_from_previous ?? 0,
      distance_m: next.amap_distance_meters_from_previous ?? Math.round((next.distance_km_from_previous ?? 0) * 1000),
      description: buildTransitDescription(next),
    };
  }
  return stops;
}

function transitFromPreviousStop(stop: RouteStop): TransitSegment | undefined {
  if (!stop.transport_mode_from_previous && stop.travel_minutes_from_previous == null && stop.distance_km_from_previous == null) {
    return undefined;
  }
  return {
    mode: normalizeTransitMode(stop.transport_mode_from_previous),
    duration_minutes: stop.travel_minutes_from_previous ?? stop.amap_duration_minutes_from_previous ?? 0,
    distance_m: stop.amap_distance_meters_from_previous ?? Math.round((stop.distance_km_from_previous ?? 0) * 1000),
    description: buildTransitDescription(stop),
  };
}

function startPlaceholderStop(): RouteStop {
  return {
    poi_id: "__start__",
    name: "出发地",
    category: "start",
    start_time: "",
    end_time: "",
    estimated_cost: 0,
    queue_minutes: 0,
    tags: [],
  };
}

// ── 时间工具 ─────────────────────────────────────────────────
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

// ── Transit 菜单弹窗 ──────────────────────────────────────────
interface TransitMenuProps {
  transit: TransitSegment;
  fromStop: RouteStop;
  toStop: RouteStop;
  onSwitchMode: (mode: TransitMode, durationMin: number) => void;
  onAddStop: () => void;
  onClose: () => void;
}

function TransitMenu({ transit, fromStop, toStop, onSwitchMode, onAddStop, onClose }: TransitMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [showModePicker, setShowModePicker] = useState(false);

  // 点击外部关闭
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div className="transit-menu" ref={ref}>
      {!showModePicker ? (
        <>
          <button
            className="transit-menu-item"
            onClick={() => setShowModePicker(true)}
          >
            <ArrowLeftRight size={13} />
            <span>更换交通方式</span>
          </button>
          <button
            className="transit-menu-item"
            onClick={() => { onAddStop(); onClose(); }}
          >
            <PlusCircle size={13} />
            <span>增加节点</span>
          </button>
        </>
      ) : (
        <div className="transit-mode-picker">
          <div className="transit-mode-picker-title">
            <button className="transit-mode-picker-back" onClick={() => setShowModePicker(false)}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9 11L5 7L9 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            选择交通方式
          </div>
          <div className="transit-mode-picker-route">
            {fromStop.name} → {toStop.name}
          </div>
          <div className="transit-mode-picker-grid">
            {TRANSIT_SWITCH_OPTIONS.map(({ mode, icon, label, color, speedKmPerMin }) => {
              const estMin = estimateTime(transit.distance_m, speedKmPerMin);
              const isCurrent = transit.mode === mode;
              return (
                <button
                  key={mode}
                  className={`transit-mode-option${isCurrent ? " current" : ""}`}
                  style={{ "--mode-color": color } as React.CSSProperties}
                  onClick={() => {
                    if (!isCurrent) {
                      onSwitchMode(mode, estMin);
                      onClose();
                    }
                  }}
                  disabled={isCurrent}
                >
                  <span className="transit-mode-option-icon">{icon}</span>
                  <span className="transit-mode-option-label">{label}</span>
                  <span className="transit-mode-option-time">{estMin}分钟</span>
                  {isCurrent && <Check size={11} className="transit-mode-option-check" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 站间交通条 ────────────────────────────────────────────────
interface TransitBarProps {
  transit: TransitSegment;
  fromStop: RouteStop;
  toStop: RouteStop;
  isLoading?: boolean;
  onSwitchMode?: (mode: TransitMode, durationMin: number) => void;
  onAddStop?: () => void;
}

function TransitBar({ transit, fromStop, toStop, isLoading, onSwitchMode, onAddStop }: TransitBarProps) {
  const cfg = TRANSIT_MODE_CONFIG[transit.mode] ?? TRANSIT_MODE_CONFIG.walk;
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="transit-bar">
      <div className="transit-line" style={{ borderColor: isLoading ? "var(--color-border)" : cfg.color }} />
      <div className="transit-content" style={{ color: isLoading ? "var(--color-muted)" : cfg.color }}>
        {isLoading ? (
          <span className="transit-recalc">
            <Loader2 size={11} className="transit-recalc-spin" />
            重新计算交通…
          </span>
        ) : (
          <>
            <span className="transit-icon">{cfg.icon}</span>
            <span className="transit-mode-label">{cfg.label}</span>
            <span className="transit-detail">
              {transit.duration_minutes} 分钟
              <span className="transit-dist">·{formatDistance(transit.distance_m)}</span>
            </span>
            {transit.description && (
              <span className="transit-desc">{transit.description}</span>
            )}
          </>
        )}
      </div>
      {/* 右侧操作按钮 */}
      {!isLoading && (onSwitchMode || onAddStop) && (
        <div className="transit-menu-wrap">
          <button
            type="button"
            className="transit-more-btn"
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            aria-label="交通段操作"
          >
            <MoreHorizontal size={13} />
          </button>
          {menuOpen && (
            <TransitMenu
              transit={transit}
              fromStop={fromStop}
              toStop={toStop}
              onSwitchMode={(mode, dur) => { onSwitchMode?.(mode, dur); setMenuOpen(false); }}
              onAddStop={() => { onAddStop?.(); setMenuOpen(false); }}
              onClose={() => setMenuOpen(false)}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ── POI 操作 Popover ──────────────────────────────────────────
interface PoiPopoverProps {
  stop: RouteStop;
  onAction: (action: PoiAction) => void;
  onClose: () => void;
  /** 当前方案总节点数，为 1 时禁止删除 */
  stopsTotal: number;
}

function PoiPopover({ stop, onAction, onClose, stopsTotal }: PoiPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div className="poi-popover" ref={ref}>
      <div className="poi-popover-header">{stop.name}</div>

      <button
        className="poi-popover-item"
        onClick={() => { onAction({ type: "swap_same", poiId: stop.poi_id, poiName: stop.name }); onClose(); }}
      >
        <RefreshCcw size={13} />
        <span>换一个同类地点</span>
      </button>

      <button
        className="poi-popover-item"
        onClick={() => { onAction({ type: "talk_ai", poiId: stop.poi_id, poiName: stop.name }); onClose(); }}
      >
        <MessageSquare size={13} />
        <span>跟 AI 说想怎么改</span>
      </button>

      <button
        className="poi-popover-item danger"
        disabled={stopsTotal <= 1}
        style={stopsTotal <= 1 ? { opacity: 0.38, cursor: "not-allowed" } : undefined}
        onClick={() => { if (stopsTotal <= 1) return; onAction({ type: "remove", poiId: stop.poi_id, poiName: stop.name }); onClose(); }}
      >
        <Trash2 size={13} />
        <span>{stopsTotal <= 1 ? "至少保留 1 个节点" : "删除该节点"}</span>
      </button>
    </div>
  );
}

// ── 单个 POI 卡片 ─────────────────────────────────────────────
interface PoiCardProps {
  stop: RouteStop;
  index: number;
  isRemoving?: boolean;
  onPoiAction?: (action: PoiAction) => void;
  /** 当前方案总节点数，用于禁止删除最后一个节点 */
  stopsTotal: number;
}

function PoiCard({ stop, index, isRemoving, onPoiAction, stopsTotal }: PoiCardProps) {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const nameRef = useRef<HTMLParagraphElement>(null);
  const nameDragRef = useRef<{ dragging: boolean; startX: number; startScroll: number }>({ dragging: false, startX: 0, startScroll: 0 });
  const queueCfg = stop.queue_level ? QUEUE_LEVEL_CONFIG[stop.queue_level] : null;

  const handleNameMouseDown = (e: React.MouseEvent) => {
    const el = nameRef.current;
    if (!el || el.scrollWidth <= el.offsetWidth) return;
    nameDragRef.current = { dragging: true, startX: e.clientX, startScroll: el.scrollLeft };
    el.style.cursor = "grabbing";
    e.preventDefault();
  };
  const handleNameMouseMove = (e: React.MouseEvent) => {
    const el = nameRef.current;
    if (!el || !nameDragRef.current.dragging) return;
    const dx = nameDragRef.current.startX - e.clientX;
    el.scrollLeft = nameDragRef.current.startScroll + dx;
  };
  const handleNameMouseUp = () => {
    const el = nameRef.current;
    if (!el) return;
    nameDragRef.current.dragging = false;
    el.style.cursor = el.scrollWidth > el.offsetWidth ? "grab" : "";
  };

  return (
    <div className={`poi-card${isRemoving ? " poi-card--removing" : ""}`}>
      {/* POI 图片（占满左侧，序号+时间浮层叠加） */}
      <div
        className="poi-card-img"
        style={{ background: CATEGORY_COLORS[stop.category] ?? "#F5F5F5" }}
      >
        {stop.cover_image_url ? (
          <img
            src={stop.cover_image_url}
            alt={stop.name}
            loading="lazy"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
          />
        ) : (
          <span className="poi-card-img-placeholder">
            {getCategoryLabel(stop.category)}
          </span>
        )}
        {/* 序号 + 时间浮在图片左上角 */}
        <div className="poi-card-seq-overlay">
          <span className="poi-seq-num">{index + 1}</span>
          <span className="poi-seq-time">{stop.start_time}–{stop.end_time}</span>
        </div>
      </div>

      {/* POI 信息主体 */}
      <div className="poi-card-body">
        {/* 品类标签 + 名称 + ··· 按钮 */}
        <div className="poi-card-name-row">
          <div className="poi-card-name-group">
            {(() => {
              const cs = getCategoryStyle(stop.category);
              return (
                <span
                  className="poi-category-tag"
                  style={{ background: cs.bg, color: cs.text, borderColor: cs.border }}
                >
                  {getCategoryLabel(stop.category)}
                </span>
              );
            })()}
            <p
              ref={nameRef}
              className="poi-card-name poi-card-name--draggable"
              onMouseDown={handleNameMouseDown}
              onMouseMove={handleNameMouseMove}
              onMouseUp={handleNameMouseUp}
              onMouseLeave={handleNameMouseUp}
            >{stop.name}</p>
          </div>
          <div className="poi-more-wrap">
            <button
              className="poi-more-btn"
              type="button"
              aria-label="更多操作"
              onClick={(e) => { e.stopPropagation(); setPopoverOpen((v) => !v); }}
            >
              <MoreHorizontal size={14} />
            </button>
            {popoverOpen && onPoiAction && (
              <PoiPopover
                stop={stop}
                onAction={onPoiAction}
                onClose={() => setPopoverOpen(false)}
                stopsTotal={stopsTotal}
              />
            )}
          </div>
        </div>

        {/* 评分 + 评论数 + 商圈 + 距离（一行） */}
        <div className="poi-card-meta">
          {stop.rating != null && (
            <>
              <Star size={10} className="poi-meta-star" fill="currentColor" />
              <span className="poi-rating-score">{stop.rating.toFixed(1)}</span>
              {(stop.district || stop.distance_m != null) && <span className="poi-meta-sep">·</span>}
            </>
          )}
          {stop.district && <span className="poi-district">{stop.district}</span>}
          {stop.distance_m != null && (
            <>
              {stop.district && <span className="poi-meta-sep">·</span>}
              <MapPin size={10} />
              <span>{formatDistance(stop.distance_m)}</span>
            </>
          )}
        </div>

        {/* 排队程度（人头图标）+ 时间 + 预约入口 */}
        {(stop.queue_level && stop.queue_level !== "none" || stop.booking_required || true) && (
          <div className="poi-queue-row">
            {stop.queue_level === "none" ? (
              <span className="poi-no-queue-tag">无需排队</span>
            ) : stop.queue_level && (
              <span className="poi-crowd-icon" data-level={stop.queue_level} title={queueCfg?.label}>
                <CrowdIcon level={stop.queue_level} />
                {stop.queue_minutes > 0 && (
                  <span className="poi-queue-minutes">约{stop.queue_minutes}分钟</span>
                )}
              </span>
            )}
            {stop.booking_required && (
              <span className="poi-booking-tag">
                需预约
                {stop.booking_url && (
                  <a href={stop.booking_url} target="_blank" rel="noopener noreferrer" className="poi-booking-tag-link">
                    <ExternalLink size={9} />
                  </a>
                )}
                {stop.booking_phone && !stop.booking_url && (
                  <a href={`tel:${stop.booking_phone}`} className="poi-booking-tag-link">
                    <Phone size={9} />
                  </a>
                )}
              </span>
            )}
            {stop.booking_note && (
              <span className="poi-booking-note">{stop.booking_note}</span>
            )}
            {stop.estimated_cost > 0 && (
              <span className="poi-foot-item poi-cost-inline">
                <Wallet size={11} />
                人均¥{stop.estimated_cost}
              </span>
            )}
          </div>
        )}

        {/* 用户评价区（标题 + AI 总结斜体内容） */}
        {stop.brief && (
          <div className="poi-review-block">
            <div className="poi-review-header">
              <span className="poi-review-title">用户评价</span>
              {stop.review_count != null && (
                <span className="poi-review-count">（{formatReviewCount(stop.review_count)}评价）</span>
              )}
              <span className="poi-detail-chevron">›</span>
            </div>
            <p className="poi-review-content">{stop.brief}</p>
          </div>
        )}

      </div>
    </div>
  );
}

// ── 主导出 ────────────────────────────────────────────────────
export function RouteTimeline({ stops: initialStops, onPoiAction, onInjectChat, onStopsChange }: RouteTimelineProps) {
  // 本地可编辑 stops 副本
  const [stops, setStops] = useState<RouteStop[]>(() => withBackendTransitSegments(initialStops));
  // 正在重算 transit 的 index（fromStop index，即被删节点前一个节点的下标）
  const [recalcingIdx, setRecalcingIdx] = useState<number | null>(null);
  // 正在淡出删除的 poiId
  const [removingId, setRemovingId] = useState<string | null>(null);

  // 当父组件传入 stops 发生变化（AI 重新规划）时，同步本地副本
  useEffect(() => {
    setStops(withBackendTransitSegments(initialStops));
  }, [initialStops]);

  // ── 删除节点 ─────────────────────────────────────────────
  const handleRemove = useCallback((poiId: string) => {
    const idx = stops.findIndex((s) => s.poi_id === poiId);
    if (idx === -1) return;

    // 触发淡出动画
    setRemovingId(poiId);

    setTimeout(() => {
      setRemovingId(null);
      const arr = stops.map((s) => ({ ...s }));

      // 合并前后 transit：
      // 如果被删节点不是第一个，且有前一个节点，则把被删节点的 transit_to_next 接给前一个节点
      if (idx > 0 && arr[idx].transit_to_next) {
        // 前驱节点的 transit = 被删节点的 transit_to_next（方向保持正确）
        // 时长估算：前驱→被删 + 被删→后继 → 如果前后都有距离则合并，否则直接用被删的 transit
        const prevTrans = arr[idx - 1].transit_to_next;
        const curTrans  = arr[idx].transit_to_next!;
        if (prevTrans) {
          arr[idx - 1] = {
            ...arr[idx - 1],
            transit_to_next: {
              mode: curTrans.mode,
              duration_minutes: prevTrans.duration_minutes + curTrans.duration_minutes,
              distance_m: prevTrans.distance_m + curTrans.distance_m,
              description: undefined,
            },
          };
        } else {
          arr[idx - 1] = {
            ...arr[idx - 1],
            transit_to_next: { ...curTrans },
          };
        }
      } else if (idx > 0 && !arr[idx].transit_to_next) {
        // 被删节点是最后一个（没有 transit_to_next），前驱节点 transit 清空
        arr[idx - 1] = { ...arr[idx - 1], transit_to_next: undefined };
      }

      const newStops = [...arr.slice(0, idx), ...arr.slice(idx + 1)];

      // 显示重算 loading（前驱节点的 transit segment）
      const loadingIdx = idx > 0 ? idx - 1 : null;
      setRecalcingIdx(loadingIdx);

      // 模拟重算延迟（约 800ms）后完成
      setTimeout(() => {
        const updated = recalcTimes(newStops, Math.max(idx - 1, 1));
        setStops(updated);
        setRecalcingIdx(null);
        onStopsChange?.(updated);
      }, 800);
    }, 280); // 等淡出动画结束再删除
  }, [stops, onStopsChange]);

  // ── 处理 PoiAction ────────────────────────────────────────
  const handlePoiAction = useCallback((action: PoiAction) => {
    if (action.type === "remove") {
      handleRemove(action.poiId);
      return;
    }
    onPoiAction?.(action);
  }, [handleRemove, onPoiAction]);

  // ── 更换交通方式 ──────────────────────────────────────────
  const handleSwitchMode = useCallback((fromIdx: number, mode: TransitMode, durationMin: number) => {
    setRecalcingIdx(fromIdx);
    setTimeout(() => {
      setStops((prev) => {
        const arr = prev.map((s) => ({ ...s }));
        if (arr[fromIdx].transit_to_next) {
          arr[fromIdx] = {
            ...arr[fromIdx],
            transit_to_next: {
              ...arr[fromIdx].transit_to_next!,
              mode,
              duration_minutes: durationMin,
            },
          };
        }
        return recalcTimes(arr, fromIdx + 1);
      });
      setRecalcingIdx(null);
    }, 600);
  }, []);

  // ── 增加节点（注入聊天框） ────────────────────────────────
  const handleAddStop = useCallback((fromIdx: number) => {
    const fromStop = stops[fromIdx];
    const toStop   = stops[fromIdx + 1];
    if (!fromStop || !toStop) return;
    const hint = `我想在「${fromStop.name}」和「${toStop.name}」之间增加一个节点，请帮我推荐合适的地点并重新衔接行程`;
    onInjectChat?.(hint);
  }, [stops, onInjectChat]);

  return (
    <div className="poi-card-list">
      {stops.map((stop, idx) => (
        <div key={stop.poi_id}>
          {idx === 0 && transitFromPreviousStop(stop) && (
            <TransitBar
              transit={transitFromPreviousStop(stop)!}
              fromStop={startPlaceholderStop()}
              toStop={stop}
            />
          )}
          <PoiCard
            stop={stop}
            index={idx}
            isRemoving={removingId === stop.poi_id}
            onPoiAction={handlePoiAction}
            stopsTotal={stops.length}
          />
          {idx < stops.length - 1 && stop.transit_to_next && (
            <TransitBar
              transit={stop.transit_to_next}
              fromStop={stop}
              toStop={stops[idx + 1]}
              isLoading={recalcingIdx === idx}
              onSwitchMode={(mode, dur) => handleSwitchMode(idx, mode, dur)}
              onAddStop={() => handleAddStop(idx)}
            />
          )}
        </div>
      ))}
    </div>
  );
}
