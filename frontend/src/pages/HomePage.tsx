import { Clock, Eye, MapPin, Sparkles, Users, Wallet, Sun, Navigation, Flame } from "lucide-react";
import { useState } from "react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { RouteDetailOverlay } from "../components/RouteDetailOverlay";
import type { RouteDetailData } from "../components/RouteDetailOverlay";

// ── 类型定义 ──────────────────────────────────────────────────
export interface PoiDetail {
  name: string;
  img: string;           // 图片 URL（mock 用 unsplash）
  duration: string;      // 在该 POI 停留时长，如 "约1小时"
}

export interface PresetRoute {
  id: string;
  title: string;
  subtitle: string;        // ≤30字路线说明
  theme: string;
  emoji: string;
  pois: string[];          // 名称列表（流程图用）
  poi_details: PoiDetail[];// 含图片的详细 POI 列表
  start_time: string;      // 如 "09:30"
  end_time: string;        // 如 "12:30"
  per_person_cost: string; // 如 "¥80~150"
  district: string;
  tags: string[];
  hot?: boolean;
  isNew?: boolean;
}

// ── Mock 精选路线数据 ─────────────────────────────────────────
const FEATURED_ROUTES: PresetRoute[] = [
  {
    id: "feat_1",
    title: "朝阳半日 Citywalk",
    subtitle: "从望京出发，穿三里屯到工体，感受北京最年轻的街头气息",
    theme: "citywalk",
    emoji: "🚶",
    pois: ["望京 SOHO", "三里屯太古里", "工人体育场"],
    poi_details: [
      { name: "望京 SOHO", img: "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=600&q=80", duration: "约45分钟" },
      { name: "三里屯太古里", img: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80", duration: "约1小时" },
      { name: "工人体育场", img: "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&q=80", duration: "约45分钟" },
    ],
    start_time: "10:00",
    end_time: "13:00",
    per_person_cost: "¥60~120",
    district: "朝阳区",
    tags: ["citywalk", "打卡", "街头"],
    hot: true,
  },
  {
    id: "feat_2",
    title: "北京文化艺术半日游",
    subtitle: "798 艺术区到鼓楼，一条沉浸式文艺路线，适合拍照打卡",
    theme: "culture",
    emoji: "🎨",
    pois: ["798 艺术区", "南锣鼓巷", "鼓楼"],
    poi_details: [
      { name: "798 艺术区", img: "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=600&q=80", duration: "约1.5小时" },
      { name: "南锣鼓巷", img: "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=600&q=80", duration: "约1小时" },
      { name: "鼓楼", img: "https://images.unsplash.com/photo-1563492065599-3520f775eeed?w=600&q=80", duration: "约45分钟" },
    ],
    start_time: "13:00",
    end_time: "17:00",
    per_person_cost: "¥100~200",
    district: "朝阳/东城",
    tags: ["艺术", "展览", "文化"],
  },
  {
    id: "feat_3",
    title: "美食探店下午茶路线",
    subtitle: "三里屯到国贸，咖啡馆加网红餐厅连环打卡，适合闺蜜出行",
    theme: "foodie",
    emoji: "🍜",
    pois: ["三里屯咖啡街", "SKP RENDEZ-VOUS", "国贸商城 B1"],
    poi_details: [
      { name: "三里屯咖啡街", img: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80", duration: "约1小时" },
      { name: "SKP RENDEZ-VOUS", img: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80", duration: "约1小时" },
      { name: "国贸商城 B1", img: "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80", duration: "约1小时" },
    ],
    start_time: "14:00",
    end_time: "17:00",
    per_person_cost: "¥150~300",
    district: "朝阳区",
    tags: ["美食", "咖啡", "下午茶"],
    isNew: true,
  },
  {
    id: "feat_4",
    title: "亲子一日游·自然放松",
    subtitle: "奥林匹克森林公园漫步，孩子和大人都能找到乐趣的绿色路线",
    theme: "nature",
    emoji: "🌿",
    pois: ["奥森北园入口", "龙形水系", "奥森南园"],
    poi_details: [
      { name: "奥森北园入口", img: "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=600&q=80", duration: "约1小时" },
      { name: "龙形水系", img: "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5?w=600&q=80", duration: "约1.5小时" },
      { name: "奥森南园", img: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600&q=80", duration: "约1小时" },
    ],
    start_time: "09:00",
    end_time: "14:00",
    per_person_cost: "¥30~80",
    district: "朝阳区",
    tags: ["亲子", "自然", "公园"],
  },
];

const MOCK_WEATHER = {
  condition: "晴", tempHigh: 28, tempLow: 17,
  tip: "适合户外出行",
};

// ── 精选路线大卡片 ────────────────────────────────────────────
function FeaturedRouteCard({
  route,
  onView,
}: {
  route: PresetRoute;
  onView: (route: PresetRoute) => void;
}) {
  const [imgIndex, setImgIndex] = useState(0);

  return (
    <div className="home-feat-card">
      {/* 左侧：图片 + 小圆点 */}
      <div className="home-feat-left">
        <div className="home-feat-img-wrap">
          <img
            className="home-feat-img"
            src={route.poi_details[imgIndex].img}
            alt={route.poi_details[imgIndex].name}
          />
          {/* 徽章 */}
          {(route.hot || route.isNew) && (
            <div className="home-feat-badges-overlay">
              {route.hot && <span className="home-feat-badge home-feat-badge--hot"><Flame size={10} /> 热门</span>}
              {route.isNew && <span className="home-feat-badge home-feat-badge--new">新</span>}
            </div>
          )}
        </div>
        {/* 小圆点指示器（图片正下方） */}
        <div className="home-feat-dots">
          {route.poi_details.map((_, i) => (
            <button
              key={i}
              type="button"
              className={`home-feat-dot ${i === imgIndex ? "home-feat-dot--active" : ""}`}
              onClick={(e) => { e.stopPropagation(); setImgIndex(i); }}
            />
          ))}
        </div>
      </div>

      {/* 右侧：文字内容 */}
      <div className="home-feat-body">
        {/* ① 标题 */}
        <div className="home-feat-title-row">
          <h3 className="home-feat-title">{route.title}</h3>
        </div>

        {/* ② 路线说明 */}
        <p className="home-feat-subtitle">{route.subtitle}</p>

        {/* ③ 路线流程图 */}
        <div className="home-feat-flow">
          {route.pois.map((poi, i) => (
            <div key={poi} className="home-feat-flow-item">
              <div
                className="home-feat-flow-node"
                onClick={(e) => { e.stopPropagation(); setImgIndex(i); }}
              >
                <span className="home-feat-flow-num">{i + 1}</span>
                <span className="home-feat-flow-name">{poi}</span>
              </div>
              {i < route.pois.length - 1 && (
                <span className="home-feat-flow-arrow" />
              )}
            </div>
          ))}
        </div>

        {/* ④ 时间 + 人均 + 按钮 */}
        <div className="home-feat-footer">
          <div className="home-feat-stats">
            <span className="home-feat-stat">
              <Clock size={11} />
              {route.start_time} – {route.end_time}
            </span>
            <span className="home-feat-stat">
              <Users size={11} />
              人均 {route.per_person_cost}
            </span>
          </div>
          <button
            type="button"
            className="home-feat-go-btn"
            onClick={() => onView(route)}
          >
            <Eye size={12} /> 查看
          </button>
        </div>
      </div>
    </div>
  );
}

// ── PresetRoute → 通用格式适配 ────────────────────────────
const THEME_COLORS: Record<string, string> = {
  citywalk: "#4FA8E8",
  culture:  "#845EC2",
  foodie:   "#FF5A3C",
  nature:   "#10B981",
  family:   "#F59E0B",
  shopping: "#FF9800",
};

function presetRouteToDetailData(route: PresetRoute): RouteDetailData {
  const themeColor = THEME_COLORS[route.theme] ?? "#FF5A3C";
  const badges: string[] = [];
  if (route.hot)   badges.push("热门");
  if (route.isNew) badges.push("新上线");

  return {
    title: route.title,
    emoji: route.emoji,
    subtitle: route.subtitle,
    themeColor,
    badges,
    stats: [
      { icon: <Clock size={13} />,  text: `${route.start_time} – ${route.end_time}` },
      { icon: <Wallet size={13} />, text: `人均 ${route.per_person_cost}` },
      { icon: <MapPin size={13} />, text: `${route.poi_details.length} 个地点` },
      { icon: <Users size={13} />,  text: route.district },
    ],
    tags: route.tags.map((t) => ({ label: t, color: themeColor })),
    heroImages: route.poi_details.map((p) => p.img),
    stops: route.poi_details.map((poi) => ({
      key: poi.name,
      name: poi.name,
      img: poi.img,
      timeLabel: poi.duration,
    })),
    footerHint: "此为精选模板，复制后 AI 将根据你的偏好个性化调整",
    copyBtnText: "复制同款路线，开始规划",
  };
}

// ── 路线规划入口卡片 ──────────────────────────────────────────
const PLAN_BUBBLES = [
  "今天人少景美，路线推荐来了",
  "尝尝附近刚开的新店",
  "来一场说走就走的 citywalk",
];

function PlanningEntryCard({ onStart }: { onStart: () => void }) {
  return (
    <div className="home-plan-card">
      {/* 装饰区：气泡想法 */}
      <div className="home-plan-bubbles">
        {PLAN_BUBBLES.map((text, i) => (
          <div key={i} className={`home-plan-bubble home-plan-bubble--${i}`}>
            {text}
          </div>
        ))}
      </div>

      {/* 底部行动按钮 */}
      <button type="button" className="home-plan-btn" onClick={onStart}>
        <Sparkles size={15} />
        开始规划今日出行
      </button>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────
export interface HomePageProps {
  profile: OnboardingProfile;
  onStartPlanning: (presetGoals?: string[], presetTitle?: string) => void;
}

export function HomePage({ profile, onStartPlanning }: HomePageProps) {
  const [viewRoute, setViewRoute] = useState<PresetRoute | null>(null);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 6)  return "夜深了";
    if (h < 11) return "早上好";
    if (h < 13) return "中午好";
    if (h < 18) return "下午好";
    return "晚上好";
  })();

  const firstName = "旅行者"; // 后续可从 profile.user_id 或设置中取昵称

  return (
    <div className="home-shell">
      {/* ── 顶部标题区 ── */}
      <header className="home-header">
        <div className="home-header-text">
          <p className="home-greeting">{greeting}，{firstName}</p>
          <h1 className="home-title">今天想去哪儿？</h1>
        </div>
        <div className="home-header-avatar">
          <Navigation size={22} strokeWidth={1.5} className="home-avatar-icon" />
        </div>
      </header>

      {/* ── 今日天气 ── */}
      <div className="home-weather-banner">
        <Sun size={15} className="home-weather-icon" />
        <div className="home-weather-info">
          <span className="home-weather-main">
            {MOCK_WEATHER.condition} {MOCK_WEATHER.tempHigh}°/{MOCK_WEATHER.tempLow}°
          </span>
          <span className="home-weather-tip">{MOCK_WEATHER.tip}</span>
        </div>
        <span className="home-weather-date">{(() => {
          const d = new Date();
          const days = ["周日","周一","周二","周三","周四","周五","周六"];
          return `${d.getMonth()+1}月${d.getDate()}日 ${days[d.getDay()]}`;
        })()}</span>
      </div>

      <div className="home-scroll">
        {/* ── 路线规划入口 ── */}
        <section className="home-section">
          <div className="home-section-header">
            <h2 className="home-section-title"><Navigation size={15} /> 路线规划</h2>
            <span className="home-section-sub">AI 一键定制</span>
          </div>
          <PlanningEntryCard onStart={() => onStartPlanning()} />
        </section>

        {/* ── 今日精选路线 ── */}
        <section className="home-section">
          <div className="home-section-header">
            <h2 className="home-section-title"><Sparkles size={15} /> 今日精选路线</h2>
            <span className="home-section-sub">AI 根据当日天气生成</span>
          </div>
          <div className="home-feat-list">
            {FEATURED_ROUTES.map((route) => (
              <FeaturedRouteCard
                key={route.id}
                route={route}
                onView={(r) => setViewRoute(r)}
              />
            ))}
          </div>
        </section>

        {/* 底部安全区 */}
        <div style={{ height: 24 }} />
      </div>

      {/* ── 精选路线详情覆盖页 ── */}
      {viewRoute && (
        <RouteDetailOverlay
          data={presetRouteToDetailData(viewRoute)}
          onClose={() => setViewRoute(null)}
          onCopy={() => {
            setViewRoute(null);
            onStartPlanning(
              viewRoute.tags
                .filter((t) =>
                  ["citywalk","foodie","culture","nature","show_event","shopping","landmark","family"].includes(t)
                )
                .concat([viewRoute.theme]),
              viewRoute.title
            );
          }}
        />
      )}
    </div>
  );
}
