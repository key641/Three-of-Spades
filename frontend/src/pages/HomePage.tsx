import { Menu, Footprints, UtensilsCrossed, Zap, BadgePercent, Baby, Coffee, Navigation, Sparkles, MapPinned, ArrowUpRight } from "lucide-react";
import type { Route } from "../api/types";
import type { OnboardingProfile } from "../hooks/useOnboarding";

export interface HomePageProps {
  profile: OnboardingProfile;
  onOpenSidebar?: () => void;
  /** 快捷标签点击时通知 App 层注入到全局输入栏 */
  onTagClick?: (text: string) => void;
  /** 正在进行的行程；新建会话后仍在首页展示 */
  activeTrip?: Route | null;
  onViewActiveTrip?: () => void;
}

// ── 高频快捷需求胶囊配置（严格遵循设计规范：使用 Lucide 矢量图标，杜绝 Emoji） ──
const QUICK_TAGS = [
  { label: "半天Citywalk", icon: Footprints, text: "半天 citywalk，节奏慢点" },
  { label: "美食探店", icon: UtensilsCrossed, text: "找附近好吃的餐厅探店，人均100左右" },
  { label: "少排队", icon: Zap, text: "少排队、人少景美的路线" },
  { label: "高性价比", icon: BadgePercent, text: "高性价比、体验好的路线" },
  { label: "亲子家庭", icon: Baby, text: "适合带娃半日游，安全省心" },
  { label: "静谧看书", icon: Coffee, text: "找个安静舒适的咖啡馆或书店待半天" },
];

export function HomePage({ onOpenSidebar, onTagClick, activeTrip, onViewActiveTrip }: HomePageProps) {
  return (
    <div className="home-shell">
      {/* 氛围层：以等高线和漫游轨迹建立“正在出发”的空间感。 */}
      <div className="home-atmosphere" aria-hidden="true">
        <span className="home-orbit home-orbit-one" />
        <span className="home-orbit home-orbit-two" />
        <span className="home-map-grid" />
        <span className="home-route-line home-route-line-one" />
        <span className="home-route-line home-route-line-two" />
        <span className="home-location-ping home-location-ping-one" />
        <span className="home-location-ping home-location-ping-two" />
      </div>

      {/* ── 顶部栏 ── */}
      <header className="home-topbar">
        <button
          type="button"
          className="home-menu-btn"
          onClick={onOpenSidebar}
          title="打开侧边栏菜单"
          aria-label="打开菜单"
        >
          <Menu size={20} />
        </button>
        <div className="home-topbar-status"><span />探索模式</div>
      </header>

      {activeTrip && (
        <button type="button" className="home-active-trip-banner" onClick={onViewActiveTrip}>
          <span className="home-active-trip-indicator" aria-hidden="true" />
          <span className="home-active-trip-copy">
            <span className="home-active-trip-kicker">当前行程进行中</span>
            <span className="home-active-trip-name">{activeTrip.title}</span>
          </span>
          <span className="home-active-trip-action"><Navigation size={15} /> 查看</span>
        </button>
      )}

      {/* ── 中间区域：品牌与出发引导 ── */}
      <main className="home-main-content">
        <div className="home-hero-brand">
          <div className="home-hero-kicker"><Sparkles size={13} /> 为此刻的你规划</div>
          <h1 className="home-brand-title-text">Drifto，随心而行</h1>
          <p className="home-brand-slogan">把一个念头，变成一段值得出发的路线</p>
          <div className="home-hero-signal" aria-label="AI 已准备好为你规划行程">
            <span className="home-hero-signal-icon"><MapPinned size={15} /></span>
            <span><b>AI 路线引擎已就绪</b><small>告诉我你的时间、心情和目的地</small></span>
            <ArrowUpRight size={16} />
          </div>
        </div>
      </main>

      {/* ── 底部沉底区域：快捷标签（输入栏由 App 层全局渲染） ── */}
      <footer className="home-bottom-dock">
        <div className="home-quick-tags-heading"><span>从一个灵感开始</span><i /></div>
        {/* 快捷需求胶囊 */}
        <div className="home-quick-tags" role="group" aria-label="快捷需求标签">
          {QUICK_TAGS.map((tag) => {
            const Icon = tag.icon;
            return (
              <button
                key={tag.label}
                type="button"
                className="home-quick-tag"
                onClick={() => onTagClick?.(tag.text)}
              >
                <Icon size={13} strokeWidth={2} className="home-quick-tag-icon" />
                <span>{tag.label}</span>
              </button>
            );
          })}
        </div>
      </footer>
    </div>
  );
}
