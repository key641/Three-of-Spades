/**
 * RouteDetailOverlay — 通用路线只读详情覆盖页
 *
 * 首页精选路线 和 历史行程记录 共用同一套 UI。
 * 调用方把各自的数据转换成 RouteDetailData 传入即可。
 */
import { useState } from "react";
import { ArrowLeft, Clock, Copy, MapPin, Users, Wallet } from "lucide-react";
import { PhoneStatusBar } from "../App";

// ── 通用数据结构 ──────────────────────────────────────────────
export interface RouteDetailStop {
  /** 唯一 key */
  key: string;
  name: string;
  /** 封面图 URL，无则不显示 */
  img?: string;
  /** 时间范围文字，如 "10:00 – 11:30" 或 "约1.5小时" */
  timeLabel: string;
  /** 费用文字，如 "¥80" 或 "" */
  costLabel?: string;
  /** 简介 */
  brief?: string;
  /** 推荐亮点 */
  highlight?: string;
  /** 用户 tip */
  tip?: string;
  /** 标签 */
  tags?: string[];
  /** 排队提示文字及颜色，如 { text: "适度排队", color: "#F79009" } */
  queue?: { text: string; color: string };
  /** 到下一站交通，如 "🚇 地铁 1 号线 · 约8分钟" */
  transitToNext?: string;
}

export interface RouteDetailData {
  title: string;
  emoji: string;
  subtitle?: string;
  themeColor: string;
  badges?: string[];          // 如 ["🔥 热门", "✨ 新上线"]
  rating?: number;
  dateLabel?: string;         // 历史行程专用，如 "5月31日"
  stats: Array<{ icon: React.ReactNode; text: string }>;
  tags?: Array<{ label: string; color: string }>;
  feedback?: string;          // 历史行程：用户反馈文字
  stops: RouteDetailStop[];
  /** Hero 图：stops 列表之外的独立切换图（精选路线）*/
  heroImages?: string[];
  footerHint: string;
  copyBtnText: string;
}

// ── 交通/排队 ─────────────────────────────────────────────────
const QUEUE_META: Record<string, { text: string; color: string }> = {
  none:      { text: "",         color: "" },
  low:       { text: "少量等待", color: "#12B76A" },
  medium:    { text: "适度排队", color: "#F79009" },
  high:      { text: "较长排队", color: "#F04438" },
  very_high: { text: "排队较多", color: "#F04438" },
};
export { QUEUE_META };

const TRANSPORT_EMOJI: Record<string, string> = {
  walk: "🚶", metro: "🚇", bus: "🚌", taxi: "🚕", bike: "🚲",
};
export { TRANSPORT_EMOJI };

// ── 主组件 ────────────────────────────────────────────────────
interface RouteDetailOverlayProps {
  data: RouteDetailData;
  onClose: () => void;
  onCopy: () => void;
}

export function RouteDetailOverlay({ data, onClose, onCopy }: RouteDetailOverlayProps) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  // Hero 图源：优先用 heroImages（精选路线独立图），否则用 stops 里的图
  const heroSources = data.heroImages ?? data.stops.map((s) => s.img).filter(Boolean) as string[];
  const heroImg = heroSources[activeIdx];

  return (
    <div className="rd-overlay">
      {/* ── 手机状态栏（与首页保持一致） ── */}
      <PhoneStatusBar />

      {/* ── Hero 图区域 ── */}
      <div className="rd-hero">
        {heroImg ? (
          <>
            <img className="rd-hero-img" src={heroImg} alt={data.title} />
            <div className="rd-hero-mask" />
          </>
        ) : (
          <div className="rd-hero-placeholder" style={{ background: data.themeColor }} />
        )}

        {/* 返回按钮 */}
        <button type="button" className="rd-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>

        {/* 徽章 */}
        {data.badges && data.badges.length > 0 && (
          <div className="rd-hero-badges">
            {data.badges.map((b) => (
              <span key={b} className="rd-hero-badge">{b}</span>
            ))}
          </div>
        )}

        {/* 标题叠层 */}
        <div className="rd-hero-title-wrap">
          <span className="rd-hero-emoji">{data.emoji}</span>
          <div>
            <h2 className="rd-hero-title">{data.title}</h2>
            {data.dateLabel && <p className="rd-hero-date">{data.dateLabel}</p>}
          </div>
          {data.rating != null && (
            <div className="rd-hero-rating" style={{ background: "rgba(0,0,0,0.35)" }}>
              ⭐ {data.rating.toFixed(1)}
            </div>
          )}
        </div>

        {/* 圆点指示器 */}
        {heroSources.length > 1 && (
          <div className="rd-hero-dots">
            {heroSources.map((_, i) => (
              <button
                key={i}
                type="button"
                className={`rd-hero-dot${i === activeIdx ? " active" : ""}`}
                onClick={() => setActiveIdx(i)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── 滚动主体 ── */}
      <div className="rd-body">
        {/* 副标题 */}
        {data.subtitle && <p className="rd-subtitle">{data.subtitle}</p>}

        {/* 指标格子 */}
        <div className="rd-stats">
          {data.stats.map((s, i) => (
            <div key={i} className="rd-stat">
              <span className="rd-stat-icon" style={{ color: data.themeColor }}>{s.icon}</span>
              <span>{s.text}</span>
            </div>
          ))}
        </div>

        {/* 标签 */}
        {data.tags && data.tags.length > 0 && (
          <div className="rd-tags">
            {data.tags.map((t) => (
              <span
                key={t.label}
                className="rd-tag"
                style={{ borderColor: t.color, color: t.color }}
              >
                {t.label}
              </span>
            ))}
          </div>
        )}

        {/* 用户反馈（历史行程） */}
        {data.feedback && (
          <div className="rd-feedback">
            💬 <span>{data.feedback}</span>
          </div>
        )}

        {/* 节点时间线 */}
        <h3 className="rd-section-title">📍 行程节点</h3>
        {data.stops.length > 0 ? (
          <div className="rd-timeline">
            {data.stops.map((stop, idx) => (
              <div key={stop.key} className="rd-tl-item">
                {/* 左轴 */}
                <div className="rd-tl-axis">
                  <div className="rd-tl-dot" style={{ background: data.themeColor }} />
                  {idx < data.stops.length - 1 && <div className="rd-tl-line" />}
                </div>

                {/* 右侧卡片 */}
                <div
                  className={`rd-tl-card${expandedIdx === idx ? " expanded" : ""}${activeIdx === idx ? " highlighted" : ""}`}
                  onClick={() => {
                    setExpandedIdx(expandedIdx === idx ? null : idx);
                    // 同步切换 Hero（只在有 stops 图时）
                    if (!data.heroImages) setActiveIdx(idx);
                  }}
                >
                  {/* 封面图 */}
                  {stop.img && (
                    <img className="rd-tl-img" src={stop.img} alt={stop.name} />
                  )}

                  {/* 主行 */}
                  <div className="rd-tl-main">
                    <span className="rd-tl-num" style={{ background: data.themeColor }}>
                      {idx + 1}
                    </span>
                    <div className="rd-tl-name-wrap">
                      <p className="rd-tl-name">{stop.name}</p>
                      <p className="rd-tl-time">{stop.timeLabel}</p>
                    </div>
                    {(stop.queue || stop.costLabel) && (
                      <div className="rd-tl-right">
                        {stop.queue && stop.queue.text && (
                          <span className="rd-tl-queue" style={{ color: stop.queue.color }}>
                            {stop.queue.text}
                          </span>
                        )}
                        {stop.costLabel && (
                          <span className="rd-tl-cost">{stop.costLabel}</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 展开详情 */}
                  {expandedIdx === idx && (stop.brief || stop.highlight || stop.tip || (stop.tags && stop.tags.length > 0)) && (
                    <div className="rd-tl-expand">
                      {stop.brief     && <p className="rd-tl-brief">{stop.brief}</p>}
                      {stop.highlight && <p className="rd-tl-highlight">✨ {stop.highlight}</p>}
                      {stop.tip       && <p className="rd-tl-tip">💬 {stop.tip}</p>}
                      {stop.tags && stop.tags.length > 0 && (
                        <div className="rd-tl-tags">
                          {stop.tags.slice(0, 4).map((t) => (
                            <span key={t} className="rd-tl-tag">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 到下一站交通 */}
                  {stop.transitToNext && (
                    <div className="rd-tl-transit">{stop.transitToNext}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rd-no-stops">
            <span>🗺️</span>
            <p>暂无详细节点信息</p>
          </div>
        )}

        <div style={{ height: 100 }} />
      </div>

      {/* ── 底部固定按钮 ── */}
      <div className="rd-footer">
        <p className="rd-footer-hint">{data.footerHint}</p>
        <button
          type="button"
          className="rd-copy-btn"
          style={{ background: data.themeColor }}
          onClick={onCopy}
        >
          <Copy size={15} />
          {data.copyBtnText}
        </button>
      </div>
    </div>
  );
}
