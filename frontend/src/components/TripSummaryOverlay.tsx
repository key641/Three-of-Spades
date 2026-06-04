import { useState, useMemo } from "react";
import {
  X, Share2, Clock, MapPin, Wallet, Footprints,
  Star, ChevronRight, Copy, MessageCircle, CheckCheck,
} from "lucide-react";
import type { Route, RouteStop } from "../api/types";

// ── 复用 MapPanel 的坐标 + 颜色逻辑 ─────────────────────
const BEIJING_AREAS: { name: string; x: number; y: number }[] = [
  { name: "故宫", x: 42, y: 35 },
  { name: "天坛", x: 46, y: 65 },
  { name: "颐和园", x: 18, y: 28 },
  { name: "三里屯", x: 62, y: 38 },
  { name: "南锣鼓巷", x: 48, y: 28 },
  { name: "798艺术区", x: 72, y: 22 },
  { name: "鸟巢", x: 60, y: 15 },
  { name: "王府井", x: 50, y: 40 },
];

function hashCoord(s: string, min: number, max: number): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return min + ((h % 1000) / 1000) * (max - min);
}

function getPoiCoord(stop: RouteStop) {
  const known = BEIJING_AREAS.find(
    (a) => stop.name.includes(a.name) || a.name.includes(stop.name)
  );
  if (known) return { x: known.x, y: known.y };
  return { x: hashCoord(stop.name + "x", 20, 80), y: hashCoord(stop.name + "y", 20, 80) };
}

function categoryColor(c: string): string {
  const map: Record<string, string> = {
    food: "#FF6B6B", restaurant: "#FF6B6B",
    culture: "#845EC2", museum: "#845EC2",
    nature: "#4CAF50", park: "#4CAF50",
    shopping: "#FF9800", landmark: "#2196F3",
    show: "#E040FB", rest: "#9E9E9E",
    citywalk: "#00BCD4", scenic: "#FF5722",
  };
  return map[c] ?? "#FF6600";
}

const CATEGORY_EMOJI: Record<string, string> = {
  food: "🍜", restaurant: "🍜", culture: "🏛️", museum: "🏛️",
  nature: "🌿", park: "🌿", shopping: "🛍️", landmark: "📍",
  show: "🎭", rest: "☕", citywalk: "🚶", scenic: "🌄",
};

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
  const coords = useMemo(() => stops.map(getPoiCoord), [stops]);

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
      {/* 顶栏 */}
      <div className="trip-summary-topbar">
        <button className="trip-summary-topbar-btn" onClick={() => onFinish(route, avgScoreNum)}>
          <X size={18} /> 退出
        </button>
        <span className="trip-summary-topbar-title">路线总结</span>
        <button className="trip-summary-topbar-btn" onClick={() => setShowShare(true)}>
          <Share2 size={16} /> 分享
        </button>
      </div>

      {/* 主体可滚动区 */}
      <div className="trip-summary-body">
        {/* 地图 */}
        <div className="trip-summary-map">
          <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" className="trip-summary-svg">
            {/* 背景网格 */}
            {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((v) => (
              <line key={`h${v}`} x1="0" y1={v} x2="100" y2={v} stroke="#e5e7eb" strokeWidth="0.15" />
            ))}
            {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((v) => (
              <line key={`v${v}`} x1={v} y1="0" x2={v} y2="100" stroke="#e5e7eb" strokeWidth="0.15" />
            ))}

            {/* 路径连线 */}
            {coords.length >= 2 &&
              coords.slice(0, -1).map((c, i) => {
                const next = coords[i + 1];
                return (
                  <g key={`p${i}`}>
                    <path
                      d={`M ${c.x} ${c.y} L ${next.x} ${next.y}`}
                      fill="none"
                      stroke="#FF6600"
                      strokeWidth="0.6"
                      strokeDasharray="2 1.5"
                      opacity="0.7"
                    />
                    <circle
                      cx={(c.x + next.x) / 2}
                      cy={(c.y + next.y) / 2}
                      r="0.6"
                      fill="#FF6600"
                      opacity="0.5"
                    />
                  </g>
                );
              })}

            {/* POI 点 */}
            {coords.map((c, i) => {
              const stop = stops[i];
              const color = categoryColor(stop.category);
              return (
                <g key={stop.poi_id}>
                  <circle cx={c.x} cy={c.y} r="2.5" fill={color} opacity="0.2" />
                  <circle cx={c.x} cy={c.y} r="1.6" fill={color} stroke="#fff" strokeWidth="0.4" />
                  <text x={c.x} y={c.y + 4.5} textAnchor="middle" fontSize="2.2" fill="#374151">
                    {i + 1}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* 标题 + 副标题 */}
        <div className="trip-summary-title-row">
          <h2 className="trip-summary-route-title">{route.title}</h2>
          <p className="trip-summary-route-sub">
            {startTime} → {endTime}
          </p>
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

        {/* 经过节点列表 */}
        <div className="trip-summary-section">
          <h3 className="trip-summary-section-title">经过节点</h3>
          <div className="trip-summary-stops">
            {stops.map((stop, idx) => {
              const dur =
                (parseMin(stop.end_time) - parseMin(stop.start_time));
              return (
                <div key={stop.poi_id} className="trip-summary-stop">
                  <div
                    className="trip-summary-stop-dot"
                    style={{ background: categoryColor(stop.category) }}
                  />
                  <div className="trip-summary-stop-info">
                    <span className="trip-summary-stop-name">
                      {CATEGORY_EMOJI[stop.category] ?? "📍"} {stop.name}
                    </span>
                    <span className="trip-summary-stop-meta">
                      {stop.start_time}–{stop.end_time} · {dur}min
                      {stop.estimated_cost > 0 && ` · ¥${stop.estimated_cost}`}
                    </span>
                  </div>
                  <ChevronRight size={14} className="trip-summary-stop-arrow" />
                </div>
              );
            })}
          </div>
        </div>

        {/* 我的评价 */}
        <div className="trip-summary-section">
          <h3 className="trip-summary-section-title">我的评价</h3>
          <div className="trip-summary-scores">
            <div className="trip-summary-avg-score">
              <span className="trip-summary-avg-num">{avgScore}</span>
              <span className="trip-summary-avg-label">综合评分</span>
            </div>
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
          </div>
          {comment && (
            <p className="trip-summary-comment">"{comment}"</p>
          )}
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
