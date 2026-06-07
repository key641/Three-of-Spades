import { useState, useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  X, Share2, Clock, MapPin, Wallet, Footprints,
  Star, Copy, MessageCircle, CheckCheck,
} from "lucide-react";
import type { Route, RouteStop } from "../api/types";
import { PhoneStatusBar } from "../App";

// ── 修复 Leaflet 默认图标路径 ────────────────────────────
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// ── 北京默认中心 ────────────────────────────────────────
const BEIJING_CENTER: [number, number] = [39.9042, 116.4074];

// ── 坐标提取（与 MapPanel 完全一致）────────────────────
function hashCoord(s: string, min: number, max: number): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return min + ((h % 1000) / 1000) * (max - min);
}

function getStopLatLng(stop: RouteStop): [number, number] {
  if (stop.lat && stop.lng) return [stop.lat, stop.lng];
  return [
    hashCoord(stop.poi_id + "lat", 39.78, 40.05),
    hashCoord(stop.poi_id + "lng", 116.20, 116.65),
  ];
}

// ── 类别颜色（与 MapPanel 完全一致）────────────────────
function categoryColor(c: string): string {
  const map: Record<string, string> = {
    food: "#FF6600", restaurant: "#FF6600",
    nature: "#52C41A", park: "#52C41A",
    culture: "#722ED1", museum: "#722ED1",
    shopping: "#1677FF", landmark: "#FA8C16",
    show: "#EB2F96", rest: "#13C2C2",
    citywalk: "#38c98a",
  };
  return map[c] ?? "#FF6600";
}

// ── 序号圆形图标（与 MapPanel 完全一致）────────────────
function makeNumberIcon(index: number, color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:28px;height:28px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 2px 8px rgba(0,0,0,0.25);
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-size:12px;font-weight:700;
    ">${index + 1}</div>`,
    iconSize:    [28, 28],
    iconAnchor:  [14, 14],
    popupAnchor: [0, -18],
  });
}

// ── 内嵌高德地图组件 ─────────────────────────────────────
function SummaryMap({ stops }: { stops: RouteStop[] }) {
  const wrapRef   = useRef<HTMLDivElement>(null);
  const mapRef    = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!wrapRef.current || mapRef.current) return;

    const map = L.map(wrapRef.current, {
      center: BEIJING_CENTER,
      zoom: 12,
      zoomControl: false,
      attributionControl: false,
      dragging: true,
      scrollWheelZoom: false,
    });

    // 高德矢量底图
    L.tileLayer(
      "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=1&scl=2&style=7",
      { subdomains: ["1","2","3","4"], maxZoom: 20 },
    ).addTo(map);
    // 高德注记层
    L.tileLayer(
      "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=2&scl=1&style=8",
      { subdomains: ["1","2","3","4"], maxZoom: 20, opacity: 0.9 },
    ).addTo(map);

    mapRef.current = map;
    map.invalidateSize();

    if (stops.length > 0) {
      const latlngs: [number, number][] = stops.map(getStopLatLng);

      // 绘制连线
      L.polyline(latlngs, {
        color: "#FF6600", weight: 2.5, opacity: 0.75, dashArray: "6 5",
      }).addTo(map);

      // 绘制标记
      stops.forEach((stop, idx) => {
        const pos   = latlngs[idx];
        const color = categoryColor(stop.category);
        L.marker(pos, { icon: makeNumberIcon(idx, color) })
          .addTo(map)
          .bindPopup(
            `<div style="font-size:13px;font-weight:600;min-width:80px">
              ${idx + 1}. ${stop.name}
            </div>`,
            { closeButton: false },
          );
      });

      // fitBounds 显示所有点
      map.fitBounds(L.latLngBounds(latlngs), {
        paddingTopLeft:     [20, 20],
        paddingBottomRight: [20, 20],
        maxZoom: 14,
        animate: false,
      });
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={wrapRef} style={{ width: "100%", height: "100%" }} />;
}

// ── Props ───────────────────────────────────────────────
export interface TripSummaryOverlayProps {
  route: Route;
  scores: Record<string, number>;
  comment: string;
  /** 退出总结页：传出路线和平均评分，由外层完成保存+跳转 */
  onFinish: (route: Route, avgScore: number) => void;
}

// ── 分享面板 ────────────────────────────────────────────
function SharePanel({ route, onClose }: { route: Route; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const shareCode = `TRIP-${route.route_id.slice(0, 6).toUpperCase()}`;

  function handleCopy() {
    navigator.clipboard?.writeText(shareCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleWechat() {
    // 在真实场景中调用微信 JS-SDK 的分享接口
    alert("正在打开微信分享…");
    onClose();
  }

  function handleInApp() {
    // 应用内分享（如发送到好友聊天）
    alert("已分享到应用内好友");
    onClose();
  }

  return (
    <div className="summary-share-overlay" onClick={onClose}>
      <div className="summary-share-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="summary-share-title">分享行程</div>

        <div className="summary-share-options">
          <button className="summary-share-btn" onClick={handleWechat}>
            <div className="summary-share-icon wechat">
              <MessageCircle size={22} />
            </div>
            <span>微信好友</span>
          </button>
          <button className="summary-share-btn" onClick={handleInApp}>
            <div className="summary-share-icon inapp">
              <Share2 size={22} />
            </div>
            <span>应用内分享</span>
          </button>
          <button className="summary-share-btn" onClick={handleCopy}>
            <div className="summary-share-icon copy">
              {copied ? <CheckCheck size={22} /> : <Copy size={22} />}
            </div>
            <span>{copied ? "已复制" : "复制分享码"}</span>
          </button>
        </div>

        <div className="summary-share-code">
          <span className="summary-share-code-label">分享码</span>
          <code className="summary-share-code-value">{shareCode}</code>
        </div>

        <button className="summary-share-cancel" onClick={onClose}>取消</button>
      </div>
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────
export function TripSummaryOverlay({ route, scores, comment, onFinish }: TripSummaryOverlayProps) {
  const [showShare, setShowShare] = useState(false);
  const stops = route.stops ?? [];

  // 计算平均分（用于回调）
  const scoreValues = Object.values(scores).filter((v) => v > 0);
  const avgScoreNum = scoreValues.length > 0
    ? scoreValues.reduce((a, b) => a + b, 0) / scoreValues.length
    : 0;
  const avgScore = avgScoreNum > 0 ? avgScoreNum.toFixed(1) : "-";

  // 统计
  const startTime = stops[0]?.start_time ?? "";
  const endTime = stops[stops.length - 1]?.end_time ?? "";
  const totalDur = route.total_duration_minutes;
  const totalCost = route.total_cost_per_person;
  const totalDist = stops.reduce(
    (s, st) => s + (st.transit_to_next?.distance_m ?? 0), 0
  );
  const _totalTravel = stops.reduce(
    (s, st) => s + (st.transit_to_next?.duration_minutes ?? 0), 0
  );

  const scoreLabels: Record<string, string> = {
    route: "路线合理", time: "时间安排", budget: "预算控制", ai: "AI 准确度",
  };
  const scoreEmojis: Record<string, string> = {
    route: "📍", time: "⏱️", budget: "💰", ai: "🤖",
  };

  return (
    <div className="trip-summary-overlay">
      {/* 手机状态栏 */}
      <PhoneStatusBar />
      {/* 顶栏 */}
      <div className="trip-summary-topbar">
        <button className="trip-summary-topbar-btn" onClick={() => onFinish(route, avgScoreNum)}>
          <X size={18} />
        </button>
        <span className="trip-summary-topbar-title">路线总结</span>
        <button className="trip-summary-topbar-btn" onClick={() => setShowShare(true)}>
          <Share2 size={16} />
        </button>
      </div>

      {/* 主体可滚动区 */}
      <div className="trip-summary-body">
        {/* 高德地图（与行程规划页保持一致） */}
        <div className="trip-summary-map">
          <SummaryMap stops={stops} />
        </div>

        {/* 标题 + 副标题 */}
        <div className="trip-summary-title-row">
          <h2 className="trip-summary-route-title">{route.title}</h2>
          <span className="trip-summary-route-sub">{startTime} → {endTime}</span>
        </div>

        {/* 数据指标卡片 */}
        <div className="trip-summary-stats">
          <div className="trip-summary-stat">
            <Clock size={16} className="trip-summary-stat-icon" />
            <span className="trip-summary-stat-value">{totalDur}<small>min</small></span>
            <span className="trip-summary-stat-label">总耗时</span>
          </div>
          <div className="trip-summary-stat">
            <Footprints size={16} className="trip-summary-stat-icon" />
            <span className="trip-summary-stat-value">{(totalDist / 1000).toFixed(1)}<small>km</small></span>
            <span className="trip-summary-stat-label">总路程</span>
          </div>
          <div className="trip-summary-stat">
            <MapPin size={16} className="trip-summary-stat-icon" />
            <span className="trip-summary-stat-value">{stops.length}</span>
            <span className="trip-summary-stat-label">经过节点</span>
          </div>
          <div className="trip-summary-stat">
            <Wallet size={16} className="trip-summary-stat-icon" />
            <span className="trip-summary-stat-value">¥{totalCost}</span>
            <span className="trip-summary-stat-label">人均花费</span>
          </div>
        </div>

        {/* 我的评价 */}
        <div className="trip-summary-section">
          <h3 className="trip-summary-section-title">我的评价</h3>
          <div className="trip-summary-score-items">
            {Object.entries(scores).map(([key, val]) => (
              <div key={key} className="trip-summary-score-item">
                <span>{scoreEmojis[key]} {scoreLabels[key]}</span>
                <div className="trip-summary-score-stars">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star
                      key={s}
                      size={14}
                      fill={s <= val ? "#FACC15" : "none"}
                      stroke={s <= val ? "#FACC15" : "#D1D5DB"}
                      strokeWidth={1.5}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          {comment && (
            <p className="trip-summary-comment">"{comment}"</p>
          )}
        </div>

        {/* 经过节点列表 */}
        <div className="trip-summary-section">
          <h3 className="trip-summary-section-title">经过节点</h3>
          <div className="trip-summary-stops-vtl">
            {stops.map((stop, idx) => {
              const dur = parseMin(stop.end_time) - parseMin(stop.start_time);
              const isLast = idx === stops.length - 1;
              return (
                <div key={stop.poi_id} className={`tsv-item${isLast ? " tsv-item--last" : ""}`}>
                  {/* 左侧竖线+圆点 */}
                  <div className="tsv-spine">
                    <div
                      className="tsv-dot"
                      style={{ background: categoryColor(stop.category) }}
                    />
                    {!isLast && <div className="tsv-line" />}
                  </div>
                  {/* 内容：地点名 + 时间，同一行 */}
                  <div className="tsv-content">
                    <span className="tsv-name">{stop.name}</span>
                    <span className="tsv-time">
                      {stop.start_time}–{stop.end_time}
                      {stop.estimated_cost > 0 && ` · ¥${stop.estimated_cost}`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 底部安全间距 */}
        <div style={{ height: 40 }} />
      </div>

      {/* 分享面板 */}
      {showShare && (
        <SharePanel route={route} onClose={() => setShowShare(false)} />
      )}
    </div>
  );
}

// ── helper ──
function parseMin(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}
