/**
 * GPS 坐标模块级缓存。
 *
 * - App.tsx 挂载时立即发起 GPS 请求，拿到坐标后调 setGpsCache() 写入；
 * - useChat 的 getCurrentLocationOptions() 调 waitForGps() 等待缓存写入，
 *   避免每次发请求都重新调浏览器 GPS（短 timeout 超时概率很高）。
 *
 * 逆地理编码策略（三层，从快到准）：
 *   1. 本地边界框匹配 —— 毫秒级，覆盖 11 个主要城市，作为初始快显
 *   2. Nominatim (OpenStreetMap) —— 免费、无需 key、全国覆盖，3~5s 内返回精确区/街道
 *   3. ip-api.com —— 网络异常时的城市级兜底
 */

let _cache: { lat: number; lng: number } | null = null;
const _listeners: Array<() => void> = [];

export const DEFAULT_LOCATION_CITY = "北京";
export const DEFAULT_LOCATION_LABEL = "北京市朝阳区望京";

export function setGpsCache(lat: number, lng: number): void {
  _cache = { lat, lng };
  _listeners.splice(0).forEach((fn) => fn());
}

export function getGpsCache(): { lat: number; lng: number } | null {
  return _cache;
}

// ── 本地粗略边界框（快速 fallback） ────────────────────────────

const CITY_BOUNDS = [
  { city: "北京",  latMin: 39.4, latMax: 41.1, lngMin: 115.4, lngMax: 117.5 },
  { city: "上海",  latMin: 30.7, latMax: 31.9, lngMin: 120.9, lngMax: 122.0 },
  { city: "广州",  latMin: 22.5, latMax: 23.9, lngMin: 112.9, lngMax: 114.0 },
  { city: "深圳",  latMin: 22.3, latMax: 22.8, lngMin: 113.7, lngMax: 114.6 },
  { city: "成都",  latMin: 30.0, latMax: 31.3, lngMin: 103.2, lngMax: 104.9 },
  { city: "杭州",  latMin: 29.2, latMax: 30.6, lngMin: 119.1, lngMax: 120.7 },
  { city: "南京",  latMin: 31.2, latMax: 32.6, lngMin: 118.3, lngMax: 119.3 },
  { city: "武汉",  latMin: 29.9, latMax: 31.4, lngMin: 113.7, lngMax: 115.1 },
  { city: "西安",  latMin: 33.4, latMax: 34.6, lngMin: 107.6, lngMax: 109.5 },
  { city: "重庆",  latMin: 28.1, latMax: 32.2, lngMin: 105.3, lngMax: 110.2 },
  { city: "厦门",  latMin: 24.1, latMax: 24.7, lngMin: 117.9, lngMax: 118.4 },
  { city: "天津",  latMin: 38.5, latMax: 40.3, lngMin: 116.7, lngMax: 118.1 },
  { city: "苏州",  latMin: 30.7, latMax: 31.8, lngMin: 119.9, lngMax: 121.2 },
  { city: "长沙",  latMin: 27.8, latMax: 28.7, lngMin: 112.3, lngMax: 113.6 },
  { city: "青岛",  latMin: 35.5, latMax: 37.0, lngMin: 119.3, lngMax: 121.0 },
  { city: "郑州",  latMin: 34.2, latMax: 34.9, lngMin: 113.0, lngMax: 114.2 },
  { city: "合肥",  latMin: 31.4, latMax: 32.5, lngMin: 116.8, lngMax: 117.6 },
  { city: "沈阳",  latMin: 41.2, latMax: 42.0, lngMin: 122.9, lngMax: 123.8 },
  { city: "哈尔滨",latMin: 45.4, latMax: 46.1, lngMin: 125.9, lngMax: 127.0 },
  { city: "济南",  latMin: 36.4, latMax: 37.3, lngMin: 116.5, lngMax: 117.5 },
  { city: "昆明",  latMin: 24.5, latMax: 25.3, lngMin: 102.4, lngMax: 103.1 },
  { city: "大连",  latMin: 38.8, latMax: 39.4, lngMin: 121.2, lngMax: 122.2 },
  { city: "宁波",  latMin: 29.4, latMax: 30.3, lngMin: 121.0, lngMax: 122.3 },
];

const DISTRICT_BOUNDS = [
  { city: "北京", district: "朝阳区",  latMin: 39.85, latMax: 40.10, lngMin: 116.40, lngMax: 116.65 },
  { city: "北京", district: "海淀区",  latMin: 39.90, latMax: 40.15, lngMin: 116.15, lngMax: 116.42 },
  { city: "北京", district: "东城区",  latMin: 39.88, latMax: 39.96, lngMin: 116.35, lngMax: 116.44 },
  { city: "北京", district: "西城区",  latMin: 39.88, latMax: 39.96, lngMin: 116.27, lngMax: 116.38 },
  { city: "北京", district: "丰台区",  latMin: 39.78, latMax: 39.90, lngMin: 116.20, lngMax: 116.47 },
  { city: "北京", district: "石景山区",latMin: 39.89, latMax: 39.97, lngMin: 116.13, lngMax: 116.25 },
  { city: "北京", district: "通州区",  latMin: 39.80, latMax: 40.01, lngMin: 116.55, lngMax: 116.90 },
  { city: "北京", district: "顺义区",  latMin: 40.00, latMax: 40.25, lngMin: 116.55, lngMax: 117.00 },
  { city: "上海", district: "浦东新区",latMin: 30.95, latMax: 31.45, lngMin: 121.45, lngMax: 122.00 },
  { city: "上海", district: "黄浦区",  latMin: 31.20, latMax: 31.24, lngMin: 121.46, lngMax: 121.51 },
  { city: "上海", district: "静安区",  latMin: 31.22, latMax: 31.26, lngMin: 121.41, lngMax: 121.48 },
  { city: "上海", district: "徐汇区",  latMin: 31.16, latMax: 31.22, lngMin: 121.41, lngMax: 121.47 },
  { city: "上海", district: "长宁区",  latMin: 31.20, latMax: 31.24, lngMin: 121.36, lngMax: 121.43 },
  { city: "上海", district: "杨浦区",  latMin: 31.23, latMax: 31.30, lngMin: 121.48, lngMax: 121.55 },
  { city: "上海", district: "闵行区",  latMin: 30.98, latMax: 31.18, lngMin: 121.29, lngMax: 121.50 },
];

/** 本地边界框快速匹配（毫秒级，作为 API 回来前的占位） */
export function coordsToLocationLabel(lat: number, lng: number): string | null {
  const cityEntry = CITY_BOUNDS.find(
    (b) => lat >= b.latMin && lat <= b.latMax && lng >= b.lngMin && lng <= b.lngMax,
  );
  if (!cityEntry) return null;
  const districtEntry = DISTRICT_BOUNDS.find(
    (b) => b.city === cityEntry.city && lat >= b.latMin && lat <= b.latMax && lng >= b.lngMin && lng <= b.lngMax,
  );
  return districtEntry ? `${cityEntry.city}${districtEntry.district}` : cityEntry.city;
}

/** Resolve only the city name for request defaults. */
export function coordsToCity(lat: number, lng: number): string | null {
  const entry = CITY_BOUNDS.find(
    (item) => lat >= item.latMin && lat <= item.latMax && lng >= item.lngMin && lng <= item.lngMax,
  );
  return entry?.city ?? null;
}

// ── Nominatim 逆地理编码（OpenStreetMap，免费无 key） ──────────

interface NominatimResult {
  address?: {
    city?: string;
    town?: string;
    county?: string;
    state?: string;
    suburb?: string;
    neighbourhood?: string;
    city_district?: string;
    quarter?: string;
  };
  display_name?: string;
}

/**
 * 调用 Nominatim 逆地理编码，返回「城市+区」格式的中文字符串。
 * 超时 6s 或失败时返回 null，调用方自行降级。
 */
export async function reverseGeocodeNominatim(lat: number, lng: number): Promise<string | null> {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&accept-language=zh-CN&zoom=14`;
    const res = await fetch(url, {
      headers: { "User-Agent": "TripPlannerApp/1.0" },
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    const data: NominatimResult = await res.json();
    const addr = data.address;
    if (!addr) return null;

    // 城市：优先 city > town > county > state
    const city = addr.city || addr.town || addr.county || addr.state || "";
    // 区/街道：suburb > city_district > quarter > neighbourhood
    const district = addr.suburb || addr.city_district || addr.quarter || addr.neighbourhood || "";

    if (!city) return null;
    // 去掉"市"后缀使文字更紧凑，如"北京市" → "北京"
    const cityShort = city.replace(/市$/, "");
    // 去掉"区"重复，如"朝阳区区" 不存在，但 suburb 可能含"街道"
    const districtShort = district.replace(/街道$/, "").replace(/\s/g, "");

    return districtShort ? `${cityShort}${districtShort}` : cityShort;
  } catch {
    return null;
  }
}

/**
 * 等待 GPS 缓存写入，最多等待 maxMs 毫秒。
 * 若在 maxMs 内缓存写入则立即返回，否则超时返回 null。
 */
export function waitForGps(maxMs: number): Promise<{ lat: number; lng: number } | null> {
  if (_cache) return Promise.resolve(_cache);
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      const idx = _listeners.indexOf(onReady);
      if (idx !== -1) _listeners.splice(idx, 1);
      resolve(null);
    }, maxMs);
    function onReady() {
      clearTimeout(timer);
      resolve(_cache);
    }
    _listeners.push(onReady);
  });
}
