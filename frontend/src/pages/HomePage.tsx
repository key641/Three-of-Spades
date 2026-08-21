import { FormEvent, useEffect, useRef, useState } from "react";
import { Clock, MapPin, Users, Wallet, Sun, Star, ArrowLeft, FlaskConical } from "lucide-react";
import logoSvg from "../assets/logo.svg";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { PhoneStatusBar } from "../App";
import { RouteCard } from "../components/RouteCard";
import type { Route, RouteStop } from "../api/types";
import { DEFAULT_LOCATION_LABEL } from "../utils/gpsCache";

// ── 类型定义 ──────────────────────────────────────────────────
export type PoiCategory = "景点" | "美食" | "购物" | "娱乐" | "运动" | "文化" | "自然";

export interface PoiDetail {
  name: string;
  img: string;
  duration: string;
  durationMin: number;   // 停留分钟数
  category: PoiCategory; // 地点分类
  travelMin?: number;    // 到下一个地点的交通分钟数
}

export interface PresetRoute {
  id: string;
  title: string;
  subtitle: string;
  theme: string;
  emoji: string;
  pois: string[];
  poi_details: PoiDetail[];
  start_time: string;
  end_time: string;
  per_person_cost: string;
  district: string;
  tags: string[];
  hot?: boolean;
  isNew?: boolean;
  label?: string;
  labelColor?: [string, string]; // [浅色, 深色] 渐变
  reason?: string; // 推荐理由
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
      { name: "望京 SOHO", img: "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "景点", travelMin: 15 },
      { name: "三里屯太古里", img: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80", duration: "约1小时", durationMin: 60, category: "购物", travelMin: 10 },
      { name: "工人体育场", img: "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "娱乐" },
    ],
    start_time: "10:00",
    end_time: "13:00",
    per_person_cost: "¥60~120",
    district: "朝阳区",
    tags: ["citywalk", "打卡", "街头"],
    hot: true,
    label: "猜你喜欢",
    labelColor: ["#38c98a", "#1a9e68"],
    reason: "街头氛围一绝，拍照超出片，不踩雷",
  },
  {
    id: "feat_2",
    title: "北京文化艺术半日游",
    subtitle: "798 艺术区到鼓楼，一条沉浸式文艺路线",
    theme: "culture",
    emoji: "🎨",
    pois: ["798 艺术区", "南锣鼓巷", "鼓楼"],
    poi_details: [
      { name: "798 艺术区", img: "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "文化", travelMin: 20 },
      { name: "南锣鼓巷", img: "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=600&q=80", duration: "约1小时", durationMin: 60, category: "景点", travelMin: 15 },
      { name: "鼓楼", img: "https://images.unsplash.com/photo-1563492065599-3520f775eeed?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "文化" },
    ],
    start_time: "13:00",
    end_time: "17:00",
    per_person_cost: "¥100~200",
    district: "朝阳/东城",
    tags: ["艺术", "展览", "文化"],
    label: "人少景美",
    labelColor: ["#845EC2", "#5c3d99"],
    reason: "人少不挤，文艺感满满，强烈推荐",
  },
  {
    id: "feat_3",
    title: "美食探店下午茶",
    subtitle: "三里屯到国贸，咖啡馆加网红餐厅连环打卡",
    theme: "foodie",
    emoji: "🍜",
    pois: ["三里屯咖啡街", "SKP RENDEZ-VOUS", "国贸商城 B1"],
    poi_details: [
      { name: "三里屯咖啡街", img: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80", duration: "约1小时", durationMin: 60, category: "美食", travelMin: 10 },
      { name: "SKP RENDEZ-VOUS", img: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80", duration: "约1小时", durationMin: 60, category: "购物", travelMin: 10 },
      { name: "国贸商城 B1", img: "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80", duration: "约1小时", durationMin: 60, category: "美食" },
    ],
    start_time: "14:00",
    end_time: "17:00",
    per_person_cost: "¥150~300",
    district: "朝阳区",
    tags: ["美食", "咖啡", "下午茶"],
    isNew: true,
    label: "新店打卡",
    labelColor: ["#FF7A4D", "#cc3d1a"],
    reason: "新开的店都在这，一条街全打完",
  },
  {
    id: "feat_4",
    title: "亲子一日游·自然放松",
    subtitle: "奥林匹克森林公园漫步，绿色休闲路线",
    theme: "nature",
    emoji: "🌿",
    pois: ["奥森北园入口", "龙形水系", "奥森南园"],
    poi_details: [
      { name: "奥森北园入口", img: "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=600&q=80", duration: "约1小时", durationMin: 60, category: "自然", travelMin: 10 },
      { name: "龙形水系", img: "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "自然", travelMin: 10 },
      { name: "奥森南园", img: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600&q=80", duration: "约1小时", durationMin: 60, category: "运动" },
    ],
    start_time: "09:00",
    end_time: "14:00",
    per_person_cost: "¥30~80",
    district: "朝阳区",
    tags: ["亲子", "自然", "公园"],
    label: "高性价比",
    labelColor: ["#F59E0B", "#b45309"],
    reason: "带娃出门首选，花费少玩得开心",
  },
];

const MOCK_WEATHER = { condition: "晴", tempHigh: 28, tempLow: 17, tip: "适合户外出行" };
const MOCK_LOCATION = DEFAULT_LOCATION_LABEL;

const THEME_COLORS: Record<string, string> = {
  citywalk: "#4FA8E8",
  culture:  "#845EC2",
  foodie:   "#FF5A3C",
  nature:   "#10B981",
  family:   "#F59E0B",
  shopping: "#FF9800",
};

// ── PresetRoute → Route 类型转换 ────────────────────────────
// POI 分类 → 简介模板（让 RouteCard 有内容可展示）
const PRESET_BRIEF: Record<string, string> = {
  景点: "热门打卡地，人气高，适合拍照留念",
  美食: "口碑好评如潮，推荐必吃招牌菜",
  购物: "品牌集聚，逛街购物的绝佳去处",
  娱乐: "精彩体验，值得一玩",
  运动: "环境舒适，活力满满",
  文化: "历史底蕴深厚，沉浸式文化体验",
  自然: "空气清新，适合放松漫步",
};

// POI 分类 → 默认评分（让评分星级有内容）
const PRESET_RATING: Record<string, number> = {
  景点: 4.7, 美食: 4.8, 购物: 4.5,
  娱乐: 4.6, 运动: 4.4, 文化: 4.7, 自然: 4.6,
};

function presetRouteToRoute(route: PresetRoute): Route {
  const [startH, startM] = route.start_time.split(":").map(Number);
  let cursor = startH * 60 + startM;

  // 从 per_person_cost 字符串中提取均值，如 "¥60~120" → 90
  const parseCost = (s: string): number => {
    const nums = s.replace(/[¥￥]/g, "").split("~").map(Number).filter((n) => !isNaN(n));
    if (nums.length === 0) return 0;
    return Math.round(nums.reduce((a, b) => a + b, 0) / nums.length);
  };
  const costPerPerson = parseCost(route.per_person_cost);
  const costPerStop = route.poi_details.length > 0
    ? Math.round(costPerPerson / route.poi_details.length)
    : 0;

  const stops: RouteStop[] = route.poi_details.map((poi, i) => {
    const s = cursor;
    cursor += poi.durationMin;
    const e = cursor;
    if (poi.travelMin) cursor += poi.travelMin;
    const fmtMin = (m: number) =>
      `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

    const stop: RouteStop = {
      poi_id: `preset_${route.id}_${i}`,
      name: poi.name,
      category: {
        景点: "landmark", 美食: "restaurant", 购物: "shopping",
        娱乐: "show", 运动: "citywalk", 文化: "culture", 自然: "nature",
      }[poi.category] ?? "landmark",
      start_time: fmtMin(s),
      end_time:   fmtMin(e),
      estimated_cost: costPerStop,
      queue_minutes: 0,
      queue_level: "low",        // 精选路线默认排队较少
      tags: route.tags.slice(0, 3),
      cover_image_url: poi.img,
      district: route.district,
      rating: PRESET_RATING[poi.category] ?? 4.6,
      review_count: 1000 + i * 300,
      brief: PRESET_BRIEF[poi.category] ?? "值得一去的好地方",
    };

    if (poi.travelMin && i < route.poi_details.length - 1) {
      stop.transit_to_next = {
        mode: "walk",
        duration_minutes: poi.travelMin,
        distance_m: Math.round(poi.travelMin * 80), // ~步行 80m/min
      };
    }

    return stop;
  });

  const [endH, endM] = route.end_time.split(":").map(Number);
  const totalMin = (endH * 60 + endM) - (startH * 60 + startM);

  return {
    route_id: route.id,
    title: `${route.emoji} ${route.title}`,
    objective: route.theme,
    summary: route.subtitle,
    total_duration_minutes: totalMin,
    total_cost_per_person: costPerPerson,
    total_queue_minutes: 0,
    score: 8.5,
    score_breakdown: { quality: 0.85, queue: 0.9, budget: 0.8, distance: 0.85, preference: 0.88 },
    stops,
    reasons: route.reason ? [route.reason] : [],
  };
}

// ── 首页精选路线详情覆盖页（复用 RouteCard 样式） ─────────────
function PresetRouteDetailOverlay({
  route,
  onClose,
  onCopy,
}: {
  route: PresetRoute;
  onClose: () => void;
  onCopy: () => void;
}) {
  const routeData = presetRouteToRoute(route);

  return (
    <div className="preset-detail-overlay">
      {/* 状态栏 */}
      <PhoneStatusBar />

      {/* 顶部导航栏 */}
      <div className="preset-detail-topbar">
        <button type="button" className="preset-detail-back" onClick={onClose}>
          <ArrowLeft size={18} />
        </button>
        <span className="preset-detail-topbar-title">{route.title}</span>
        <div style={{ width: 36 }} />
      </div>

      {/* 滚动主体：RouteCard */}
      <div className="preset-detail-body">
        <RouteCard
          route={routeData}
          selected={false}
          onSelect={onCopy}
        />
        {/* 底部提示 */}
        <p className="preset-detail-hint">可根据此方案个性化调整</p>
        <div style={{ height: 32 }} />
      </div>
    </div>
  );
}

// ── POI 分类颜色 & 图标 ───────────────────────────────────────
const POI_CATEGORY_COLORS: Record<string, string> = {
  景点: "#4FA8E8",
  美食: "#FF7A4D",
  购物: "#F59E0B",
  娱乐: "#845EC2",
  运动: "#10B981",
  文化: "#6366F1",
  自然: "#34D399",
};

const POI_CATEGORY_ICONS: Record<string, string> = {
  景点: "📍",
  美食: "🍜",
  购物: "🛍",
  娱乐: "🎡",
  运动: "🏃",
  文化: "🎨",
  自然: "🌿",
};

// ── 时间进度条组件 ────────────────────────────────────────────
function PoiTimeline({ route }: { route: PresetRoute }) {
  const segments: { color: string; flex: number }[] = [];
  route.poi_details.forEach((poi, i) => {
    segments.push({ color: POI_CATEGORY_COLORS[poi.category] ?? "#4FA8E8", flex: poi.durationMin });
    if (i < route.poi_details.length - 1 && poi.travelMin) {
      segments.push({ color: "#D1D5DB", flex: poi.travelMin });
    }
  });
  return (
    <div className="home-feat-timeline-bar">
      {segments.map((seg, i) => (
        <div
          key={i}
          className="home-feat-timeline-seg"
          style={{ flex: seg.flex, background: seg.color }}
        />
      ))}
    </div>
  );
}

// ── 横向精选路线小卡片（含图片轮播） ─────────────────────────
function FeaturedRouteCard({
  route,
  onView,
}: {
  route: PresetRoute;
  onView: (route: PresetRoute) => void;
}) {
  const themeColor = THEME_COLORS[route.theme] ?? "#38c98a";
  const imgs = route.poi_details.map((p) => p.img);
  const total = imgs.length;
  const [imgIndex, setImgIndex] = useState(0);
  const dragRef = useRef<{ startX: number; startY: number; moved: boolean; locked: boolean | null } | null>(null);
  const imgWrapRef = useRef<HTMLDivElement>(null);

  // 用原生 touchmove（passive:false）阻止横滑时外层卡片列表滚动
  useEffect(() => {
    const el = imgWrapRef.current;
    if (!el) return;
    function onTouchMove(e: TouchEvent) {
      if (!dragRef.current) return;
      const touch = e.touches[0];
      const dx = Math.abs(touch.clientX - dragRef.current.startX);
      const dy = Math.abs(touch.clientY - dragRef.current.startY);
      // 首次判定方向后锁定：横向则阻止外层滚动
      if (dragRef.current.locked === null) {
        dragRef.current.locked = dx > dy;
      }
      if (dragRef.current.locked) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
    el.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => el.removeEventListener("touchmove", onTouchMove);
  }, []);

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = { startX: e.clientX, startY: e.clientY, moved: false, locked: null };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!dragRef.current) return;
    const dx = Math.abs(e.clientX - dragRef.current.startX);
    const dy = Math.abs(e.clientY - dragRef.current.startY);
    if (dragRef.current.locked === null && (dx > 6 || dy > 6)) {
      dragRef.current.locked = dx > dy;
    }
    if (dragRef.current.locked && dx > 6) {
      dragRef.current.moved = true;
      e.stopPropagation();
    }
  }
  function onPointerUp(e: React.PointerEvent) {
    if (!dragRef.current) return;
    const delta = e.clientX - dragRef.current.startX;
    const moved = dragRef.current.moved;
    dragRef.current = null;
    if (!moved) return;
    e.stopPropagation();
    if (delta < -30) setImgIndex((i) => Math.min(i + 1, total - 1));
    else if (delta > 30) setImgIndex((i) => Math.max(i - 1, 0));
  }

  return (
    <button
      type="button"
      className="home-feat-mini-card"
      onClick={() => onView(route)}
      style={{ "--theme-color": themeColor } as React.CSSProperties}
    >
      {/* 封面图 + 遮罩 + 标题（可滑动切换） */}
      <div
        ref={imgWrapRef}
        className="home-feat-mini-img-wrap"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={(e) => { if (dragRef.current?.moved) e.stopPropagation(); }}
      >
        {/* 图片轨道 */}
        <div
          className="home-feat-img-track"
          style={{ transform: `translateX(-${imgIndex * 100}%)` }}
        >
          {imgs.map((src, i) => (
            <img key={i} className="home-feat-mini-img" src={src} alt={route.poi_details[i].name} />
          ))}
        </div>
        {/* 底部遮罩：标题 + 推荐理由 + 圆点 */}
        <div className="home-feat-mini-overlay">
          <div className="home-feat-mini-title-img">{route.title}</div>
          {route.reason && (
            <div className="home-feat-mini-reason-img">"{route.reason}"</div>
          )}
          {total > 1 && (
            <div className="home-feat-mini-dots">
              {imgs.map((_, i) => (
                <span key={i} className={`home-feat-mini-dot${i === imgIndex ? " active" : ""}`} />
              ))}
            </div>
          )}
        </div>
        {/* 尖角标签 */}
        {route.label && (
          <span
            className="home-feat-label"
            style={route.labelColor ? {
              background: `linear-gradient(135deg, ${route.labelColor[0]} 0%, ${route.labelColor[1]} 100%)`,
            } : undefined}
          >{route.label}</span>
        )}
      </div>
      {/* 文字区 */}
      <div className="home-feat-mini-body">
        {/* 地点流：彩点 + 名称 + 箭头 */}
        <div className="home-feat-poi-line">
          {route.poi_details.map((poi, i) => (
            <span key={i} className="home-feat-poi-inline">
              <span
                className="home-feat-poi-dot"
                style={{ background: POI_CATEGORY_COLORS[poi.category] } as React.CSSProperties}
              />
              <span className="home-feat-poi-name">{poi.name}</span>
              {i < route.poi_details.length - 1 && (
                <span className="home-feat-poi-sep">›</span>
              )}
            </span>
          ))}
        </div>
        {/* 时间 + 费用 + 进度条 */}
        <div className="home-feat-bottom">
          <div className="home-feat-meta-row">
            <Clock size={9} strokeWidth={2} />
            <span>{route.start_time}–{route.end_time}</span>
            <span className="home-feat-meta-dot">·</span>
            <Wallet size={9} strokeWidth={2} />
            <span>{route.per_person_cost}</span>
          </div>
          <PoiTimeline route={route} />
        </div>
      </div>
    </button>
  );
}

// ── 弹幕推荐问题（按时间段） ─────────────────────────────────
function getDanmakuList(): string[] {
  const h = new Date().getHours();
  if (h < 6) return [
    "夜深了，来个附近静谧的饮品小居吧",
    "推荐两三家晚上开着的网红餐厅",
    "香炉飘啥方向走走，寻个夜宵奇遇",
    "要不来一场周末夜晚的 City Walk？",
    "找个24小时开着的和颐酒栈，有点想去",
    "凌晨了，有什么地方还能坐着发呆？",
  ];
  if (h < 11) return [
    "一早好！帮我前面找个早食小居吧",
    "阳光就不错，赶紧出门赶公园散步吧",
    "上午还青春，第一杯和路边的美居也很幸福",
    "今天天气不错，适合来一场晨跑路线",
    "推荐一个安静的早午餐地方，不用排队",
    "早餐附近有什么人少又好吃的？",
  ];
  if (h < 14) return [
    "午饭时间，附近有什么值得去的馆子？",
    "今天天气好，适合户外漫步，有推荐吗",
    "中午有两小时空档，附近能逛的地方",
    "来个不用排队的午餐，要有包间",
    "饭后散步去哪儿合适？推荐个路线",
    "午后想喝杯咖啡，安静有氛围那种",
  ];
  if (h < 18) return [
    "下午了，附近有什么适合拍照的地方？",
    "今天晴，推荐一条下午的 Citywalk 路线",
    "想找个氛围好的咖啡馆坐坐，不要太吵",
    "下午三点，还来得及出发去哪逛逛？",
    "帮我找几个人少景美的打卡点",
    "四点钟太阳正好，哪里适合漫步？",
  ];
  return [
    "来几个附近放松的地点，晚上出去转转",
    "推荐个适合聚餐的餐厅，6人左右",
    "晚上想看演出或者展览，有什么推荐",
    "夜幕下适合散步的地方，要有夜景",
    "晚饭吃什么？帮我选个附近口碑好的",
    "夜生活推荐，想感受一下城市烟火气",
  ];
}

// 弹幕轮播组件 — 8s 自动切换，支持拖拽 snap，循环轮播
function DanmakuSuggestions({ onSelect }: { onSelect: (text: string) => void }) {
  const allItems = getDanmakuList();
  const total = allItems.length;
  const [index, setIndex] = useState(0);
  const indexRef = useRef(0);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  // 每个 page 的 offsetLeft 缓存
  const offsetsRef = useRef<number[]>([]);
  // 当前基准偏移（滑到 index 对应位置）
  const baseOffsetRef = useRef(0);
  // 拖拽状态
  const dragRef = useRef<{ startX: number; dragging: boolean; suggestion: string | null } | null>(null);
  const [dragDelta, setDragDelta] = useState(0);
  const [isAnimating, setIsAnimating] = useState(true);
  // 定时器 ref，拖拽时暂停
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 读取所有 page 的 offsetLeft
  function cacheOffsets() {
    offsetsRef.current = pageRefs.current.map((el) => el?.offsetLeft ?? 0);
  }

  // 跳到指定 index
  function goTo(i: number) {
    const next = ((i % total) + total) % total;
    cacheOffsets();
    baseOffsetRef.current = offsetsRef.current[next] ?? 0;
    indexRef.current = next;
    setIndex(next);
    setDragDelta(0);
    setIsAnimating(true);
  }

  // 初始化缓存
  useEffect(() => {
    cacheOffsets();
  }, []);

  // 8 秒自动切换
  function startTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => goTo(indexRef.current + 1), 8000);
  }

  useEffect(() => {
    startTimer();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  // ── 拖拽处理 ──
  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const suggestion = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-suggestion]")?.dataset.suggestion ?? null;
    dragRef.current = { startX: e.clientX, dragging: true, suggestion };
    setIsAnimating(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!dragRef.current?.dragging) return;
    setDragDelta(e.clientX - dragRef.current.startX);
  }

  function onPointerUp(e: React.PointerEvent) {
    if (!dragRef.current?.dragging) return;
    const { startX, suggestion } = dragRef.current;
    const delta = e.clientX - startX;
    dragRef.current = null;
    // 滑动超过 40px 则切换
    if (delta < -40) {
      goTo(index + 1);
    } else if (delta > 40) {
      goTo(index - 1);
    } else {
      // 回弹
      setDragDelta(0);
      setIsAnimating(true);
      if (Math.abs(delta) <= 8 && suggestion) {
        onSelect(suggestion);
      }
    }
  }

  function onPointerCancel() {
    dragRef.current = null;
    setDragDelta(0);
    setIsAnimating(true);
  }

  const translateX = baseOffsetRef.current - dragDelta;

  return (
    <div className="home-danmaku-wrap">
      <div
        className="home-danmaku-track-outer"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        style={{ cursor: "grab", userSelect: "none" }}
      >
        <div
          className="home-danmaku-track"
          style={{
            transform: `translateX(-${translateX}px)`,
            transition: isAnimating ? "transform 0.45s cubic-bezier(0.4,0,0.2,1)" : "none",
          }}
        >
          {allItems.map((text, i) => (
            <div
              key={i}
              className="home-danmaku-page"
              ref={(el) => { pageRefs.current[i] = el; }}
            >
              <button
                type="button"
                className="home-danmaku-item"
                data-suggestion={text}
                onClick={(event) => {
                  // Pointer taps are handled by the drag surface on pointer-up;
                  // detail=0 preserves keyboard activation without double-firing.
                  if (event.detail === 0) onSelect(text);
                }}
              >
                {text}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────
export interface HomePageProps {
  profile: OnboardingProfile;
  onStartPlanning: (presetGoals?: string[], presetTitle?: string, initialMsg?: string) => void;
  onProfileClick?: () => void;
  onEvaluationClick?: () => void;
}

export function HomePage({ profile, onStartPlanning, onProfileClick, onEvaluationClick }: HomePageProps) {
  const [viewRoute, setViewRoute] = useState<PresetRoute | null>(null);
  const [inputText, setInputText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 6)  return "夜深了";
    if (h < 11) return "早上好";
    if (h < 13) return "中午好";
    if (h < 18) return "下午好";
    return "晚上好";
  })();

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 100) + "px";
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const msg = inputText.trim();
    if (!msg) return;
    onStartPlanning(undefined, undefined, msg);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  function handleSuggestionSelect(text: string) {
    setInputText(text);
    window.requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 100) + "px";
      textarea.focus({ preventScroll: true });
      textarea.setSelectionRange(text.length, text.length);
    });
  }

  // 生成头像文字：取 scenarios 第一个 emoji 或 user_id 首字符
  const avatarLabel = (() => {
    const scenarioEmojiMap: Record<string, string> = {
      citywalk: "🚶", foodie: "🍜", culture: "🎨", nature: "🌿",
      family: "👨‍👩‍👧", shopping: "🛍️", landmark: "📍", show_event: "🎭",
    };
    const first = profile.scenarios?.[0];
    return (first && scenarioEmojiMap[first]) || profile.user_id?.slice(0, 1).toUpperCase() || "U";
  })();

  return (
    <div className="home-shell">
      {/* ── 顶部行：问候语 + 头像 ── */}
      <div className="home-topbar">
        <span className="home-topbar-greeting">
          {greeting}{profile.nickname ? `，${profile.nickname}` : ""}
        </span>
        <button
          type="button"
          className="home-evaluation-entry"
          onClick={onEvaluationClick}
          aria-label="打开测评"
        >
          <FlaskConical size={14} />
          测评
        </button>
        <button
          type="button"
          className="home-avatar"
          onClick={onProfileClick}
          aria-label="我的"
        >
          <span className="home-avatar-label">{avatarLabel}</span>
        </button>
      </div>

      {/* ── 主体内容：上下居中 ── */}
      <div className="home-main-content">
        {/* 品牌标题区 */}
        <div className="home-greeting-area">
          <div className="home-brand-title">
            <img src={logoSvg} alt="logo" className="home-brand-logo" />
            <span className="home-brand-text">AI出行规划</span>
          </div>
        </div>

        {/* ── 定位 + 天气信息条（同一行，居中） ── */}
        <div className="home-location-bar">
          <MapPin size={12} className="home-location-icon" />
          <span>{MOCK_LOCATION}</span>
          <span className="home-location-sep">·</span>
          <Sun size={11} className="home-weather-inline-icon" />
          <span>{MOCK_WEATHER.condition} {MOCK_WEATHER.tempHigh}°</span>
        </div>

      {/* ── 主输入卡片 ── */}
      <form className="home-input-card" onSubmit={handleSubmit}>
        <div className="home-input-form">
          <textarea
            ref={textareaRef}
            className="home-input-textarea"
            value={inputText}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="随便说说，比如「朝阳半天 citywalk，预算100」…"
            rows={2}
            aria-label="输入出行想法"
          />
        </div>

        {/* 弹幕推荐：点击填入输入框 */}
        <DanmakuSuggestions onSelect={handleSuggestionSelect} />

        {/* 底部发送按钮 */}
        <button
          type="submit"
          className="home-input-send"
          disabled={!inputText.trim()}
        >
          开始规划
        </button>
      </form>

        {/* ── 猜你喜欢（横向滚动） ── */}
        <div className="home-featured-section">
          <div className="home-featured-header">
            <h2 className="home-featured-title">
              <Star size={14} fill="currentColor" />
              猜你喜欢
            </h2>
          </div>
          <div className="home-featured-scroll">
            {FEATURED_ROUTES.map((route) => (
              <FeaturedRouteCard
                key={route.id}
                route={route}
                onView={(r) => setViewRoute(r)}
              />
            ))}
          </div>
        </div>
      </div>{/* ── /home-main-content ── */}

      {/* ── 精选路线详情覆盖页（复用 RouteCard 样式） ── */}
      {viewRoute && (
        <PresetRouteDetailOverlay
          route={viewRoute}
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
