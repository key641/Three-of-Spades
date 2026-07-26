/**
 * mockData.ts
 * 内联 mock_weather.json 数据（避免跨目录 JSON import 范围问题）
 * + 动态路线生成逻辑（猜你喜欢）
 */
import type { OnboardingProfile } from "../hooks/useOnboarding";

// ── 路线相关类型（与 HomePage 保持一致，集中定义避免循环依赖） ─
export type PoiCategory = "景点" | "美食" | "购物" | "娱乐" | "运动" | "文化" | "自然";

export interface PoiDetail {
  name: string;
  img: string;
  duration: string;
  durationMin: number;
  category: PoiCategory;
  travelMin?: number;
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
  labelColor?: [string, string];
  reason?: string;
}

// ── 天气数据（来源：data/seed/mock_weather.json） ───────────────────────────
export interface WeatherScenario {
  condition: string;
  temperature_c: number;
  rain_probability: number;
  wind_level: number;
  comfort_level: string;
  suggested_preferences: string[];
}

const MOCK_WEATHER_DB: Record<string, Record<string, WeatherScenario>> = {
  北京: {
    sunny:  { condition: "sunny",       temperature_c: 23, rain_probability: 0.06, wind_level: 2, comfort_level: "comfortable", suggested_preferences: ["citywalk", "拍照", "自然风景"] },
    rainy:  { condition: "rainy",       temperature_c: 20, rain_probability: 0.78, wind_level: 4, comfort_level: "wet",         suggested_preferences: ["室内", "雨天", "少走路"] },
    hot:    { condition: "hot",         temperature_c: 35, rain_probability: 0.12, wind_level: 2, comfort_level: "hot",         suggested_preferences: ["室内", "少走路", "咖啡"] },
    cloudy: { condition: "cloudy",      temperature_c: 21, rain_probability: 0.24, wind_level: 3, comfort_level: "mild",        suggested_preferences: ["citywalk", "拍照", "吃好"] },
    night:  { condition: "night_clear", temperature_c: 19, rain_probability: 0.08, wind_level: 2, comfort_level: "comfortable", suggested_preferences: ["晚上", "夜景", "吃好"] },
  },
  上海: {
    sunny:  { condition: "sunny",       temperature_c: 24, rain_probability: 0.08, wind_level: 2, comfort_level: "comfortable", suggested_preferences: ["citywalk", "拍照", "自然风景"] },
    rainy:  { condition: "rainy",       temperature_c: 21, rain_probability: 0.86, wind_level: 4, comfort_level: "wet",         suggested_preferences: ["室内", "雨天", "少走路"] },
    hot:    { condition: "hot",         temperature_c: 34, rain_probability: 0.18, wind_level: 2, comfort_level: "hot",         suggested_preferences: ["室内", "少走路", "咖啡"] },
    cloudy: { condition: "cloudy",      temperature_c: 22, rain_probability: 0.28, wind_level: 3, comfort_level: "mild",        suggested_preferences: ["citywalk", "拍照", "吃好"] },
    night:  { condition: "night_clear", temperature_c: 20, rain_probability: 0.10, wind_level: 2, comfort_level: "comfortable", suggested_preferences: ["晚上", "夜景", "吃好"] },
  },
};

/** 根据城市 + 当前时间返回今日天气场景（同一天始终一致） */
export function getMockWeather(city = "北京"): WeatherScenario & { label: string } {
  const cityData = MOCK_WEATHER_DB[city] ?? MOCK_WEATHER_DB["北京"];
  const h = new Date().getHours();
  if (h >= 22 || h < 6) return { ...cityData.night, label: "夜间" };
  const today = new Date();
  const dayHash =
    today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
  const scenes = ["sunny", "cloudy", "hot", "rainy"] as const;
  const scene = scenes[dayHash % scenes.length];
  const labels: Record<string, string> = { sunny: "晴", cloudy: "多云", hot: "高温", rainy: "阴雨" };
  return { ...cityData[scene], label: labels[scene] ?? "晴" };
}

// ── 路线候选池（北京，按主题分组） ────────────────────────────────────────────
interface RouteTemplate {
  id: string;
  title: string;
  subtitle: string;
  theme: string;
  emoji: string;
  poi_details: PoiDetail[];
  start_time: string;
  end_time: string;
  per_person_cost: string;
  district: string;
  tags: string[];
  label: string;
  labelColor: [string, string];
  reason: string;
  /** 匹配这些用户偏好标签时优先展示 */
  matchTags: string[];
  /** 天气建议偏好（来自 mock_weather suggested_preferences）匹配时加权 */
  weatherTags: string[];
}

const ROUTE_POOL: RouteTemplate[] = [
  // ── citywalk ──
  {
    id: "dyn_cw1",
    title: "朝阳半日 Citywalk",
    subtitle: "从望京出发，穿三里屯到工体，感受北京最年轻的街头气息",
    theme: "citywalk", emoji: "🚶",
    poi_details: [
      { name: "望京 SOHO",    img: "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "景点", travelMin: 15 },
      { name: "三里屯太古里", img: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "购物", travelMin: 10 },
      { name: "工人体育场",   img: "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "娱乐" },
    ],
    start_time: "10:00", end_time: "13:00", per_person_cost: "¥60~120",
    district: "朝阳区", tags: ["citywalk", "打卡", "街头"],
    label: "猜你喜欢", labelColor: ["#38c98a", "#1a9e68"],
    reason: "街头氛围一绝，拍照超出片，不踩雷",
    matchTags: ["citywalk", "拍照"],
    weatherTags: ["citywalk", "拍照"],
  },
  {
    id: "dyn_cw2",
    title: "胡同穿行·东城老北京",
    subtitle: "南锣鼓巷出发，深入东四胡同群，体验老北京烟火气",
    theme: "citywalk", emoji: "🏘️",
    poi_details: [
      { name: "南锣鼓巷",   img: "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "景点", travelMin: 10 },
      { name: "东四胡同群", img: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "文化", travelMin: 15 },
      { name: "钟鼓楼广场", img: "https://images.unsplash.com/photo-1563492065599-3520f775eeed?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "文化" },
    ],
    start_time: "09:30", end_time: "13:00", per_person_cost: "¥30~80",
    district: "东城区", tags: ["citywalk", "胡同", "历史"],
    label: "老北京味", labelColor: ["#F59E0B", "#b45309"],
    reason: "市井感十足，随手都是好照片",
    matchTags: ["citywalk", "历史", "文化"],
    weatherTags: ["citywalk", "拍照"],
  },
  {
    id: "dyn_cw3",
    title: "后海夜游·燕京夜生活",
    subtitle: "什刹海畔漫步，感受北京夜晚的温柔与烟火",
    theme: "citywalk", emoji: "🌙",
    poi_details: [
      { name: "什刹海前海",   img: "https://images.unsplash.com/photo-1579003593419-98f949b9398f?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "景点", travelMin: 10 },
      { name: "后海酒吧街",   img: "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "娱乐", travelMin: 10 },
      { name: "银锭桥观景台", img: "https://images.unsplash.com/photo-1601974902700-3d09c73b86c3?w=600&q=80", duration: "约30分钟", durationMin: 30, category: "景点" },
    ],
    start_time: "19:00", end_time: "22:00", per_person_cost: "¥80~200",
    district: "西城区", tags: ["夜景", "citywalk", "晚上"],
    label: "夜间推荐", labelColor: ["#6366F1", "#4338CA"],
    reason: "后海夜景绝了，夏夜必去",
    matchTags: ["夜景", "晚上", "citywalk"],
    weatherTags: ["晚上", "夜景"],
  },

  // ── culture ──
  {
    id: "dyn_cu1",
    title: "798 艺术半日游",
    subtitle: "从 798 到鼓楼，沉浸式文艺路线一步到位",
    theme: "culture", emoji: "🎨",
    poi_details: [
      { name: "798 艺术区", img: "https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "文化", travelMin: 20 },
      { name: "南锣鼓巷",  img: "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "景点", travelMin: 15 },
      { name: "鼓楼",      img: "https://images.unsplash.com/photo-1563492065599-3520f775eeed?w=600&q=80", duration: "约45分钟",  durationMin: 45, category: "文化" },
    ],
    start_time: "13:00", end_time: "17:00", per_person_cost: "¥100~200",
    district: "朝阳/东城", tags: ["艺术", "展览", "文化"],
    label: "人少景美", labelColor: ["#845EC2", "#5c3d99"],
    reason: "人少不挤，文艺感满满，强烈推荐",
    matchTags: ["文化", "展览", "艺术"],
    weatherTags: ["室内"],
  },
  {
    id: "dyn_cu2",
    title: "博物馆·历史穿越半日",
    subtitle: "国家博物馆出发，首博收官，感受五千年文明脉络",
    theme: "culture", emoji: "🏛️",
    poi_details: [
      { name: "中国国家博物馆", img: "https://images.unsplash.com/photo-1565118531796-763e5082d113?w=600&q=80", duration: "约2小时",  durationMin: 120, category: "文化", travelMin: 20 },
      { name: "天安门广场",     img: "https://images.unsplash.com/photo-1508193638397-1c4234db14d8?w=600&q=80", duration: "约45分钟", durationMin: 45,  category: "景点", travelMin: 15 },
      { name: "首都博物馆",     img: "https://images.unsplash.com/photo-1531218150217-54595bc2b934?w=600&q=80", duration: "约1.5小时", durationMin: 90,  category: "文化" },
    ],
    start_time: "09:00", end_time: "14:00", per_person_cost: "¥0~50",
    district: "东城/西城", tags: ["历史", "博物馆", "文化"],
    label: "免费打卡", labelColor: ["#06B6D4", "#0369a1"],
    reason: "大部分免费，知识量超大，拍照巨出片",
    matchTags: ["文化", "历史", "家庭"],
    weatherTags: ["室内", "雨天"],
  },

  // ── foodie ──
  {
    id: "dyn_fo1",
    title: "美食探店下午茶",
    subtitle: "三里屯到国贸，咖啡馆加网红餐厅连环打卡",
    theme: "foodie", emoji: "🍜",
    poi_details: [
      { name: "三里屯咖啡街",      img: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80", duration: "约1小时", durationMin: 60, category: "美食", travelMin: 10 },
      { name: "SKP RENDEZ-VOUS",   img: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80", duration: "约1小时", durationMin: 60, category: "购物", travelMin: 10 },
      { name: "国贸商城 B1",        img: "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80", duration: "约1小时", durationMin: 60, category: "美食" },
    ],
    start_time: "14:00", end_time: "17:00", per_person_cost: "¥150~300",
    district: "朝阳区", tags: ["美食", "咖啡", "下午茶"],
    label: "新店打卡", labelColor: ["#FF7A4D", "#cc3d1a"],
    reason: "新开的店都在这，一条街全打完",
    matchTags: ["美食", "咖啡", "购物"],
    weatherTags: ["室内", "少走路", "咖啡"],
  },
  {
    id: "dyn_fo2",
    title: "簋街夜宵·夜晚烟火气",
    subtitle: "东直门簋街，麻小海鲜一条街，最正宗的北京宵夜体验",
    theme: "foodie", emoji: "🦐",
    poi_details: [
      { name: "簋街（东直门段）",  img: "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "美食", travelMin: 10 },
      { name: "胡大饭馆",          img: "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "美食", travelMin: 10 },
      { name: "夜市小吃摊",        img: "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&q=80", duration: "约45分钟",  durationMin: 45, category: "美食" },
    ],
    start_time: "18:30", end_time: "21:30", per_person_cost: "¥100~200",
    district: "东城区", tags: ["美食", "夜宵", "晚上"],
    label: "夜宵首选", labelColor: ["#EF4444", "#b91c1c"],
    reason: "麻小鲜香，啤酒冰凉，京城烟火气全在这",
    matchTags: ["美食", "夜宵", "晚上"],
    weatherTags: ["晚上", "吃好"],
  },
  {
    id: "dyn_fo3",
    title: "国贸午市·精致午餐路线",
    subtitle: "CBD 商圈精选餐厅，工作日午餐好去处",
    theme: "foodie", emoji: "🍱",
    poi_details: [
      { name: "国贸三期餐厅层",  img: "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80", duration: "约1小时",  durationMin: 60, category: "美食", travelMin: 10 },
      { name: "嘉里中心小吃",    img: "https://images.unsplash.com/photo-1547592180-85f173990554?w=600&q=80", duration: "约45分钟", durationMin: 45, category: "美食", travelMin: 10 },
      { name: "银泰中心甜品街",  img: "https://images.unsplash.com/photo-1464305795204-6f5bbfc7fb81?w=600&q=80", duration: "约30分钟", durationMin: 30, category: "美食" },
    ],
    start_time: "12:00", end_time: "14:00", per_person_cost: "¥80~180",
    district: "朝阳区", tags: ["美食", "午餐", "室内"],
    label: "打工人必备", labelColor: ["#F59E0B", "#b45309"],
    reason: "商务氛围，选择多，不用排太久",
    matchTags: ["美食", "吃好", "室内"],
    weatherTags: ["室内", "少走路"],
  },

  // ── nature ──
  {
    id: "dyn_na1",
    title: "亲子一日游·奥森自然放松",
    subtitle: "奥林匹克森林公园漫步，绿色休闲路线",
    theme: "nature", emoji: "🌿",
    poi_details: [
      { name: "奥森北园入口", img: "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "自然", travelMin: 10 },
      { name: "龙形水系",     img: "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "自然", travelMin: 10 },
      { name: "奥森南园",     img: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "运动" },
    ],
    start_time: "09:00", end_time: "14:00", per_person_cost: "¥30~80",
    district: "朝阳区", tags: ["亲子", "自然", "公园"],
    label: "高性价比", labelColor: ["#F59E0B", "#b45309"],
    reason: "带娃出门首选，花费少玩得开心",
    matchTags: ["自然风景", "亲子", "公园"],
    weatherTags: ["citywalk", "自然风景"],
  },
  {
    id: "dyn_na2",
    title: "香山红叶·秋日登山游",
    subtitle: "北京最美秋色，俯瞰京城全景",
    theme: "nature", emoji: "🍂",
    poi_details: [
      { name: "香山公园南门", img: "https://images.unsplash.com/photo-1515934751635-c81c6bc9a2d8?w=600&q=80", duration: "约45分钟",  durationMin: 45, category: "自然", travelMin: 20 },
      { name: "鬼见愁主峰",   img: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "自然", travelMin: 15 },
      { name: "碧云寺",       img: "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "文化" },
    ],
    start_time: "08:00", end_time: "13:00", per_person_cost: "¥10~60",
    district: "海淀区", tags: ["自然", "登山", "秋天"],
    label: "绝美秋色", labelColor: ["#EF4444", "#b91c1c"],
    reason: "秋天非来不可，漫山红叶超美",
    matchTags: ["自然风景", "运动", "拍照"],
    weatherTags: ["citywalk", "自然风景"],
  },

  // ── shopping ──
  {
    id: "dyn_sh1",
    title: "西单购物逛街全攻略",
    subtitle: "从西单大悦城到君太，京城最全购物路线",
    theme: "shopping", emoji: "🛍️",
    poi_details: [
      { name: "西单大悦城",    img: "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&q=80", duration: "约1.5小时", durationMin: 90, category: "购物", travelMin: 10 },
      { name: "西单北大街",    img: "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "购物", travelMin: 10 },
      { name: "君太百货",      img: "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=600&q=80", duration: "约1小时",   durationMin: 60, category: "购物" },
    ],
    start_time: "13:00", end_time: "17:00", per_person_cost: "¥200~500",
    district: "西城区", tags: ["购物", "商场", "逛街"],
    label: "逛街必去", labelColor: ["#FF9800", "#e65100"],
    reason: "北京最热闹的商业街，什么都有",
    matchTags: ["购物", "逛街"],
    weatherTags: ["室内", "少走路"],
  },
];

// ── 日期种子随机数（同一天同一结果） ────────────────────────────────────────
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

/**
 * 根据用户偏好 + 当日天气建议，从路线池中动态选取 3 条路线
 * 同一天相同用户返回相同结果（稳定）
 */
export function getDailyRecommendedRoutes(
  profile: OnboardingProfile,
  weatherSuggestedPrefs: string[],
): PresetRoute[] {
  const today = new Date();
  const daySeed =
    today.getFullYear() * 10000 +
    (today.getMonth() + 1) * 100 +
    today.getDate();

  // 合并用户偏好标签
  const userTags = new Set([
    ...profile.preferences,
    ...profile.scenarios,
    ...weatherSuggestedPrefs,
  ]);

  // 对每条路线计算匹配分
  const scored = ROUTE_POOL.map((route) => {
    let score = 0;
    route.matchTags.forEach((t) => { if (userTags.has(t)) score += 2; });
    route.weatherTags.forEach((t) => { if (userTags.has(t)) score += 1; });
    // 加一点随机扰动（基于日期+路线id），防止每天总是同样排名
    const rand = seededRandom(daySeed + route.id.charCodeAt(4))();
    score += rand * 1.5;
    return { route, score };
  });

  // 降序排列，取前 3
  scored.sort((a, b) => b.score - a.score);
  const selected = scored.slice(0, 3);

  return selected.map(({ route }) => ({
    id: route.id,
    title: route.title,
    subtitle: route.subtitle,
    theme: route.theme,
    emoji: route.emoji,
    pois: route.poi_details.map((p) => p.name),
    poi_details: route.poi_details,
    start_time: route.start_time,
    end_time: route.end_time,
    per_person_cost: route.per_person_cost,
    district: route.district,
    tags: route.tags,
    label: route.label,
    labelColor: route.labelColor,
    reason: route.reason,
  }));
}
