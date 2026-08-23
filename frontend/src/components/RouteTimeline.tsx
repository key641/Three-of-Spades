import { MapPin, Star, Wallet, Footprints, Train, Bus, CarTaxiFront, Bike, Loader2, Navigation } from "lucide-react";
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

// ── 交通方式配置 ──────────────────────────────────────────────
const TRANSIT_MODE_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  walk:  { icon: <Footprints size={12} />,   label: "步行", color: "#52C41A" },
  metro: { icon: <Train size={12} />,        label: "地铁", color: "#1677FF" },
  bus:   { icon: <Bus size={12} />,          label: "公交", color: "#722ED1" },
  taxi:  { icon: <CarTaxiFront size={12} />, label: "打车", color: "#FA8C16" },
  bike:  { icon: <Bike size={12} />,         label: "骑行", color: "#13C2C2" },
};

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

function formatDistance(m?: number): string {
  if (m == null) return "";
  if (m >= 1000) return `${(m / 1000).toFixed(1)}km`;
  return `${m}m`;
}

function parseMin(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + (m || 0);
}
function fmtMin(totalMin: number): string {
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

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

// ── 站间交通条 ────────────────────────────────────────────────
interface TransitBarProps {
  transit: TransitSegment;
  isLoading?: boolean;
  isStart?: boolean;
  isReturn?: boolean;
}

function TransitBar({ transit, isLoading, isStart, isReturn }: TransitBarProps) {
  const cfg = TRANSIT_MODE_CONFIG[transit.mode] ?? TRANSIT_MODE_CONFIG.walk;
  const [showNav, setShowNav] = useState(false);
  const [countdown, setCountdown] = useState(5);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleNavigate = () => {
    setShowNav(true);
    setCountdown(5);
    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          setShowNav(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const prefix = isStart ? "从当前位置 · " : isReturn ? "返回 · " : "";

  return (
    <>
      <div className="transit-bar">
        <div className="transit-content" style={{ color: isLoading ? "var(--color-muted)" : cfg.color }}>
          {isLoading ? (
            <span className="transit-recalc"><Loader2 size={11} className="transit-recalc-spin" />重新计算交通…</span>
          ) : (
            <>
              <span className="transit-mode-label">{prefix}{cfg.label}</span>
              <span className="transit-detail">{transit.duration_minutes} 分钟<span className="transit-dist">·{formatDistance(transit.distance_m)}</span></span>
            </>
          )}
        </div>
        <button className="transit-nav-btn" type="button" onClick={handleNavigate} aria-label="开始导航">
          <Navigation size={13} />
        </button>
      </div>

      {showNav && (
        <div className="nav-toast-overlay" onClick={() => { if (timerRef.current) clearInterval(timerRef.current); setShowNav(false); }}>
          <div className="nav-toast" onClick={(e) => e.stopPropagation()}>
            <div className="nav-toast-icon"><Navigation size={20} /></div>
            <span className="nav-toast-text">正在跳转到外部导航软件</span>
            <span className="nav-toast-countdown">{countdown}s</span>
          </div>
        </div>
      )}
    </>
  );
}

// ── 单个 POI 卡片 ─────────────────────────────────────────────
interface PoiCardProps {
  stop: RouteStop;
  index: number;
  isRemoving?: boolean;
  onPoiAction?: (action: PoiAction) => void;
}

function PoiCard({ stop, index, isRemoving }: PoiCardProps) {
  const nameRef = useRef<HTMLParagraphElement>(null);
  const nameDragRef = useRef<{ dragging: boolean; startX: number; startScroll: number }>({ dragging: false, startX: 0, startScroll: 0 });

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
      {/* 图片 */}
      <div className="poi-card-img">
        <div className="poi-card-img-inner" style={{ background: CATEGORY_COLORS[stop.category] ?? "#F5F5F5" }}>
        {stop.cover_image_url ? (
          <img src={stop.cover_image_url} alt={stop.name} loading="lazy"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
          />
        ) : (
          <span className="poi-card-img-placeholder">{getCategoryLabel(stop.category)}</span>
        )}
          {stop.distance_m != null && (
            <div className="poi-card-dist-overlay">
              <MapPin size={9} />
              <span>{formatDistance(stop.distance_m)}</span>
            </div>
          )}
        </div>
      </div>

      {/* 信息主体 */}
      <div className="poi-card-body">
        {/* 名称 + ··· 按钮 */}
        <div className="poi-card-name-row">
          <div className="poi-card-name-group">
            <p ref={nameRef} className="poi-card-name poi-card-name--draggable"
              onMouseDown={handleNameMouseDown} onMouseMove={handleNameMouseMove}
              onMouseUp={handleNameMouseUp} onMouseLeave={handleNameMouseUp}
            >{stop.name}</p>
          </div>
        </div>

        {/* 第二行：评分 + 人均 + 需预约 + 排队 */}
        <div className="poi-card-meta">
          {stop.rating != null && (
            <span className="poi-meta-rating">
              <Star size={10} className="poi-meta-star" fill="currentColor" />
              <span className="poi-rating-score">{stop.rating.toFixed(1)}</span>
            </span>
          )}
          {stop.estimated_cost > 0 && (
            <span className="poi-meta-cost">¥{stop.estimated_cost}/人</span>
          )}
          {stop.booking_required && (
            <span className="poi-meta-tag poi-meta-tag--booking">需预约</span>
          )}
          {stop.queue_level && stop.queue_level !== "none" && stop.queue_minutes > 0 && (
            <span className={`poi-meta-tag poi-meta-tag--queue-${stop.queue_level}`}>
              等{stop.queue_minutes}分钟
            </span>
          )}

        </div>

        {/* 第三行：AI 推荐理由 */}
        {stop.brief && (
          <p className="poi-card-brief">{stop.brief}</p>
        )}
      </div>
    </div>
  );
}

// ── 主导出 ────────────────────────────────────────────────────
export function RouteTimeline({ stops: initialStops, onPoiAction, onStopsChange }: RouteTimelineProps) {
  const [stops, setStops] = useState<RouteStop[]>(initialStops);
  const [recalcingIdx, setRecalcingIdx] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  useEffect(() => { setStops(initialStops); }, [initialStops]);

  const handleRemove = useCallback((poiId: string) => {
    const idx = stops.findIndex((s) => s.poi_id === poiId);
    if (idx === -1) return;
    setRemovingId(poiId);
    setTimeout(() => {
      setRemovingId(null);
      const arr = stops.map((s) => ({ ...s }));
      if (idx > 0 && arr[idx].transit_to_next) {
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
          arr[idx - 1] = { ...arr[idx - 1], transit_to_next: { ...curTrans } };
        }
      } else if (idx > 0 && !arr[idx].transit_to_next) {
        arr[idx - 1] = { ...arr[idx - 1], transit_to_next: undefined };
      }
      const newStops = [...arr.slice(0, idx), ...arr.slice(idx + 1)];
      const loadingIdx = idx > 0 ? idx - 1 : null;
      setRecalcingIdx(loadingIdx);
      setTimeout(() => {
        const updated = recalcTimes(newStops, Math.max(idx - 1, 1));
        setStops(updated);
        setRecalcingIdx(null);
        onStopsChange?.(updated);
      }, 800);
    }, 280);
  }, [stops, onStopsChange]);

  const handlePoiAction = useCallback((action: PoiAction) => {
    if (action.type === "remove") { handleRemove(action.poiId); return; }
    onPoiAction?.(action);
  }, [handleRemove, onPoiAction]);

  const firstStop = stops[0];
  const lastStop = stops[stops.length - 1];
  const fromStartTransit = firstStop
    ? {
        mode: (firstStop.transport_mode_from_previous ?? "walk") as TransitSegment["mode"],
        duration_minutes: firstStop.amap_duration_minutes_from_previous ?? firstStop.travel_minutes_from_previous ?? 5,
        distance_m: firstStop.amap_distance_meters_from_previous ?? (firstStop.distance_km_from_previous ? firstStop.distance_km_from_previous * 1000 : 500),
      }
    : null;
  // 返程：用首站交通信息估算（返程通常和去程类似）
  const toHomeTransit = lastStop && fromStartTransit
    ? { ...fromStartTransit }
    : null;

  return (
    <div className="poi-card-list">
      {/* 出发：从当前位置到首站 */}
      {fromStartTransit && (
        <div className="poi-card-row poi-card-row--transit-only">
          <div className="poi-card-seq-col">
            <div className="transit-seq-icon transit-seq-icon--start" style={{ color: (TRANSIT_MODE_CONFIG[fromStartTransit.mode] ?? TRANSIT_MODE_CONFIG.walk).color }}>
              <MapPin size={12} />
            </div>
          </div>
          <div className="poi-card-row-main">
            <TransitBar transit={fromStartTransit} isStart />
          </div>
        </div>
      )}

      {stops.map((stop, idx) => {
        const transit = idx < stops.length - 1 ? stop.transit_to_next : null;
        const transitCfg = transit ? (TRANSIT_MODE_CONFIG[transit.mode] ?? TRANSIT_MODE_CONFIG.walk) : null;
        return (
          <div key={stop.poi_id} className="poi-card-row">
            <div className="poi-card-seq-col">
              <span className="poi-seq-circle" style={{ background: getCategoryStyle(stop.category).text }}>{idx + 1}</span>
              {transit && transitCfg && (
                <div className="transit-seq-icon" style={{ color: transitCfg.color }}>
                  {recalcingIdx === idx ? <Loader2 size={12} className="transit-recalc-spin" /> : transitCfg.icon}
                </div>
              )}
            </div>
            <div className="poi-card-row-main">
              <PoiCard stop={stop} index={idx} isRemoving={removingId === stop.poi_id} onPoiAction={handlePoiAction} />
              {transit && (
                <TransitBar transit={transit}
                  isLoading={recalcingIdx === idx}
                />
              )}
            </div>
          </div>
        );
      })}

      {/* 返程：从末站回家 */}
      {toHomeTransit && (
        <div className="poi-card-row poi-card-row--transit-only">
          <div className="poi-card-seq-col">
            <div className="transit-seq-icon transit-seq-icon--end" style={{ color: (TRANSIT_MODE_CONFIG[toHomeTransit.mode] ?? TRANSIT_MODE_CONFIG.walk).color }}>
              <Footprints size={12} />
            </div>
          </div>
          <div className="poi-card-row-main">
            <TransitBar transit={toHomeTransit} isReturn />
          </div>
        </div>
      )}
    </div>
  );
}
