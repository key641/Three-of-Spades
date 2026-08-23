import { useEffect, useRef, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Route, RouteStop } from "../api/types";
import { getGpsCache } from "../utils/gpsCache";

// ── 修复 Leaflet 默认图标路径（Vite 打包时丢失）──────────────────
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// ── 北京默认中心 ────────────────────────────────────────────────
const BEIJING_CENTER: [number, number] = [39.9042, 116.4074];
const DEFAULT_ZOOM = 12;

// ── 类别 → 颜色 ────────────────────────────────────────────────
function categoryColor(category: string): string {
  const map: Record<string, string> = {
    food:       "#FF6600",
    restaurant: "#FF6600",
    nature:     "#52C41A",
    park:       "#52C41A",
    culture:    "#722ED1",
    museum:     "#722ED1",
    shopping:   "#1677FF",
    landmark:   "#FA8C16",
    show:       "#EB2F96",
    rest:       "#13C2C2",
    citywalk:   "#38c98a",
  };
  return map[category] ?? "#FF6600";
}

// ── 创建“序号 + 地点名”胶囊图标 ─────────────────────────────────
function makePoiClusterIcon(indices: number[]): L.DivIcon {
  const digits = indices.map((index) => `<span style="width:23px;height:23px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:#0B6CFF;color:#fff;font-size:11px;font-weight:800;border:2px solid #fff;margin-left:-5px;">${index + 1}</span>`).join("");
  const width = Math.max(54, 22 + indices.length * 19);
  return L.divIcon({
    className: "poi-cluster-icon",
    html: `<div style="height:34px;min-width:${width}px;padding:0 8px;border-radius:999px;
      display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.98);
      border:2px solid #0B6CFF;box-shadow:0 4px 12px rgba(11,108,255,.28);animation:poi-cluster-in .24s ease-out;">${digits}</div>`,
    iconSize: [width, 34],
    iconAnchor: [width / 2, 34],
  });
}

function makePoiPillIcon(
  index: number,
  name: string,
  color: string,
  active: boolean,
  offset: [number, number],
): L.DivIcon {
  const label = name;
  const width = Math.max(label.length * 13 + 46, 88);
  const height = active ? 34 : 30;
  const pointerHeight = 8;
  const [offsetX, offsetY] = offset;
  return L.divIcon({
    className: "poi-pill-icon",
    html: `<div style="position:relative;height:${height}px;width:${width}px;border-radius:999px;
      background:rgba(255,255,255,0.96);border:2px solid ${color};
      box-shadow:0 3px 10px rgba(0,0,0,${active ? "0.25" : "0.16"});
      display:flex;align-items:center;padding:0 9px 0 3px;box-sizing:border-box;
      color:#1a2a22;font-size:${active ? 13 : 12}px;font-weight:650;white-space:nowrap;
    "><span style="width:${height - 8}px;height:${height - 8}px;min-width:${height - 8}px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;margin-right:6px;
      background:${color};color:#fff;font-size:12px;font-weight:800;">${index + 1}</span>
      <span>${label}</span><i style="position:absolute;left:50%;bottom:-${pointerHeight}px;width:0;height:0;
      transform:translateX(-50%);border-left:${pointerHeight}px solid transparent;border-right:${pointerHeight}px solid transparent;
      border-top:${pointerHeight}px solid ${color};"></i></div>`,
    iconSize: [width, height + pointerHeight],
    // 胶囊底部尖角的尖端精确落在 POI 真实坐标；路线仍连接到该坐标。
    iconAnchor: [width / 2 - offsetX, height + pointerHeight - offsetY],
    popupAnchor: [0, -(height + pointerHeight + 4)],
  });
}

// ── 用户位置图标 ─────────────────────────────────────────────────
const USER_ICON = L.divIcon({
  className: "",
  html: `<div style="position:relative;width:24px;height:24px;">
    <div style="position:absolute;inset:0;border-radius:50%;
      background:rgba(22,119,255,0.2);
      animation:leaflet-pulse 2s ease-out infinite;"></div>
    <div style="position:absolute;inset:4px;border-radius:50%;
      background:#1677FF;border:2.5px solid white;
      box-shadow:0 2px 6px rgba(22,119,255,0.5);"></div>
  </div>`,
  iconSize:   [24, 24],
  iconAnchor: [12, 12],
});

// ── fitBounds 辅助：根据 sheetSnap 调整底部 padding ─────────────
function fitToStops(
  map: L.Map,
  latlngs: [number, number][],
  snap: "peek" | "half" | "full",
  options?: { boardView?: boolean; boardOverlayHeight?: number },
) {
  if (latlngs.length === 0) return;
  const vh = window.innerHeight;

  if (options?.boardView) {
    // 看板地图会被底部时间轴覆盖。以时间轴的实时高度作为底部安全区，
    // 让所有 POI（以及开启时的用户位置）完整落在上方真正可见的地图里。
    const bounds = L.latLngBounds(latlngs);
    const mapHeight = map.getSize().y;
    const overlayHeight = Math.min(
      Math.max(options.boardOverlayHeight ?? Math.round(vh * 0.55), 0),
      Math.max(mapHeight - 88, 0),
    );
    map.fitBounds(bounds, {
      // 进一步收紧安全边距，使全部点位保持完整可见的前提下再放大一级。
      paddingTopLeft:     [14, 22],
      paddingBottomRight: [14, Math.round(overlayHeight + 14)],
      maxZoom: 18,
      animate: true,
    });
    return;
  }

  // 底部面板遮挡高度对应的像素 padding（让路线集中在可见区域中央）
  const snapPaddingBottom: Record<string, number> = {
    peek: Math.round(vh * 0.14),  // peek ≈ 12vh 手柄，可见区域大
    half: Math.round(vh * 0.77),  // half ≈ 75vh 面板，只剩上方 25%
    full: Math.round(vh * 0.93),  // full 几乎全遮，保留一点
  };
  const paddingBottom = snapPaddingBottom[snap] ?? Math.round(vh * 0.14);
  map.fitBounds(L.latLngBounds(latlngs), {
    paddingTopLeft:     [52, 56],
    paddingBottomRight: [52, paddingBottom],
    maxZoom: 15,
    animate: true,
  });
}

// ── POI 坐标提取 ────────────────────────────────────────────────
function hashCoord(s: string, min: number, max: number): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return min + (h % 1000) / 1000 * (max - min);
}

function getStopLatLng(stop: RouteStop): [number, number] {
  if (stop.lat && stop.lng) return [stop.lat, stop.lng];
  return [
    hashCoord(stop.poi_id + "lat", 39.78, 40.05),
    hashCoord(stop.poi_id + "lng", 116.20, 116.65),
  ];
}

// ── 高德 polyline（lng,lat;lng,lat）→ Leaflet（lat,lng） ─────────
function parseAmapPolyline(polyline?: string): [number, number][] {
  if (!polyline) return [];
  return polyline.split(";").flatMap((part) => {
    const [lngText, latText] = part.trim().split(",");
    const lng = Number(lngText);
    const lat = Number(latText);
    return Number.isFinite(lat) && Number.isFinite(lng) ? [[lat, lng] as [number, number]] : [];
  });
}

function squaredDistance([latA, lngA]: [number, number], [latB, lngB]: [number, number]) {
  return (latA - latB) ** 2 + (lngA - lngB) ** 2;
}

// 未接入真实道路数据时，用平滑贝塞尔弧线表达行程方向，避免呈现生硬直线。
function makeFallbackRoutePath(from: [number, number], to: [number, number]): [number, number][] {
  const [fromLat, fromLng] = from;
  const [toLat, toLng] = to;
  const deltaLat = toLat - fromLat;
  const deltaLng = toLng - fromLng;
  const distance = Math.hypot(deltaLat, deltaLng);
  const bend = distance * 4;
  const direction = (fromLat + fromLng > toLat + toLng) ? -1 : 1;
  const control1: [number, number] = [
    fromLat + deltaLat * 0.28 + deltaLng * bend * direction,
    fromLng + deltaLng * 0.28 - deltaLat * bend * direction,
  ];
  const control2: [number, number] = [
    fromLat + deltaLat * 0.72 + deltaLng * bend * direction,
    fromLng + deltaLng * 0.72 - deltaLat * bend * direction,
  ];
  return Array.from({ length: 17 }, (_, index) => {
    const t = index / 16;
    const inverse = 1 - t;
    return [
      inverse ** 3 * fromLat + 3 * inverse ** 2 * t * control1[0] + 3 * inverse * t ** 2 * control2[0] + t ** 3 * toLat,
      inverse ** 3 * fromLng + 3 * inverse ** 2 * t * control1[1] + 3 * inverse * t ** 2 * control2[1] + t ** 3 * toLng,
    ] as [number, number];
  });
}

function getRoutePath(from: [number, number], to: [number, number], polyline?: string, source?: string | null): [number, number][] {
  const roadPath = parseAmapPolyline(polyline);
  if (source === "amap" && roadPath.length >= 3) {
    const lastPoint = roadPath[roadPath.length - 1];
    const forwardDistance = squaredDistance(roadPath[0], from) + squaredDistance(lastPoint, to);
    const reverseDistance = squaredDistance(lastPoint, from) + squaredDistance(roadPath[0], to);
    const orientedPath = forwardDistance <= reverseDistance ? roadPath : [...roadPath].reverse();
    // 将真实起终点拼入道路轨迹，确保路线严格从用户/上一站出发、抵达当前站。
    return [from, ...orientedPath, to];
  }
  return makeFallbackRoutePath(from, to);
}

// ── POI 胶囊定位：底部尖角始终垂直指向真实坐标 ───────────────────
function getPoiPillOffsets(points: [number, number][]): [number, number][] {
  // 不再为避让而拉开卡片，避免地点与实际地图位置产生过大的视觉距离。
  return points.map(() => [0, 0]);
}

function getOverlappingPoiGroups(map: L.Map, points: [number, number][], stops: RouteStop[]): number[][] {
  const groups: number[][] = [];
  const visited = new Set<number>();
  const rects = points.map((position, index) => {
    const point = map.latLngToContainerPoint(position);
    const width = Math.max(stops[index].name.length * 13 + 46, 88);
    // 使用收紧后的核心碰撞区：仅在胶囊实际大面积压住时才融合，避免过早聚合。
    const horizontalThreshold = 14;
    const verticalThreshold = 7;
    return {
      left: point.x - width / 2 + horizontalThreshold,
      right: point.x + width / 2 - horizontalThreshold,
      top: point.y - 38 + verticalThreshold,
      bottom: point.y + 2 - verticalThreshold,
    };
  });
  const intersects = (a: typeof rects[number], b: typeof rects[number]) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

  for (let index = 0; index < points.length; index++) {
    if (visited.has(index)) continue;
    const group = [index];
    visited.add(index);
    for (let cursor = 0; cursor < group.length; cursor++) {
      const current = group[cursor];
      for (let candidate = 0; candidate < points.length; candidate++) {
        if (!visited.has(candidate) && intersects(rects[current], rects[candidate])) {
          visited.add(candidate);
          group.push(candidate);
        }
      }
    }
    if (group.length > 1) groups.push(group);
  }
  return groups;
}

export interface MapPanelProps {
  routes: Route[];
  activeRouteIndex: number;
  activePoi: string | null;
  onPoiClick: (poiId: string) => void;
  /** 底部面板当前档位，用于计算 fitBounds padding */
  sheetSnap?: "peek" | "half" | "full";
  /** 本地编辑后的最新 stops（优先级高于 routes[activeRouteIndex].stops） */
  liveStops?: RouteStop[];
  /** 是否显示用户当前位置（方案详情页 board 视图时为 true） */
  showUserLocation?: boolean;
  /** 是否为方案详情页（board 视图），此时点位适配到上方可见地图区域 */
  isBoardView?: boolean;
  /** 看板底部信息面板的实时高度，用于避开被遮挡区域 */
  boardOverlayHeight?: number;
}

export function MapPanel({ routes, activeRouteIndex, activePoi, onPoiClick, sheetSnap = "half", liveStops, showUserLocation = false, isBoardView = false, boardOverlayHeight }: MapPanelProps) {
  const wrapRef      = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<L.Map | null>(null);
  const markersRef   = useRef<L.Marker[]>([]);
  const clusterMarkersRef = useRef<L.Marker[]>([]);
  const routeLayersRef = useRef<L.Polyline[]>([]);
  const userMarkerRef = useRef<L.Marker | null>(null);
  const rafRef       = useRef<number>(0);
  const fitTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const renderMarkersRef = useRef<() => void>(() => {});
  const pillOffsetsRef = useRef<[number, number][]>([]);
  const updateClustersRef = useRef<() => void>(() => {});

  const getVisibleUserPosition = useCallback((): [number, number] | null => {
    if (!showUserLocation || !userMarkerRef.current) return null;
    const { lat, lng } = userMarkerRef.current.getLatLng();
    return [lat, lng];
  }, [showUserLocation]);

  // ── 初始化地图 ────────────────────────────────────────────────
  useEffect(() => {
    let destroyed = false;

    // 延迟到下一帧，确保 DOM 已布局完毕，容器有真实像素尺寸
    rafRef.current = requestAnimationFrame(() => {
      if (destroyed || !wrapRef.current || mapRef.current) return;

      const el = wrapRef.current;
      // 如果容器仍然没有高度（极端情况），用 setTimeout 再等一帧
      if (el.clientHeight === 0) {
        rafRef.current = requestAnimationFrame(() => {
          if (destroyed || !wrapRef.current || mapRef.current) return;
          createMap(wrapRef.current!);
        });
      } else {
        createMap(el);
      }
    });

    function createMap(el: HTMLDivElement) {
      const map = L.map(el, {
        center: BEIJING_CENTER,
        zoom:   DEFAULT_ZOOM,
        zoomControl: false,
        attributionControl: false,
      });

      // 高德平面矢量底图（style=7 纯路网平面渲染 + style=8 中文注记层叠加）
      L.tileLayer(
        "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=1&scl=2&style=7",
        {
          subdomains: ["1", "2", "3", "4"],
          maxZoom: 20,
          attribution: "© 高德地图",
        },
      ).addTo(map);

      // 中文注记层（道路名/地名/POI）
      L.tileLayer(
        "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=2&scl=1&style=8",
        {
          subdomains: ["1", "2", "3", "4"],
          maxZoom: 20,
          opacity: 0.85,
        },
      ).addTo(map);

      L.control.attribution({ position: "bottomright", prefix: false })
        .addAttribution('<a href="https://www.amap.com" target="_blank">© 高德地图</a>')
        .addTo(map);

      // 看板演示固定使用北京望京位置，确保路线缩放基准稳定一致。
      const defaultUserPos: [number, number] = [40.002, 116.472];
      userMarkerRef.current = L.marker(defaultUserPos, { icon: USER_ICON, zIndexOffset: 1000 }).addTo(map);

      mapRef.current = map;
      // 每次缩放结束后，根据最新屏幕像素判断是否仍重叠：重叠则融合，放大分开后自动还原为地点胶囊。
      map.on("zoomend moveend", () => updateClustersRef.current());

      // 修正尺寸（确保容器已拿到真实像素后再刷一次）
      map.invalidateSize();
      requestAnimationFrame(() => {
        map.invalidateSize();
        // 尺寸修正后立即渲染标记（此时 map 已就绪，LiveStops 也已传入）
        renderMarkersRef.current();
      });

      // half 档时底部面板遮住 75vh，需视图偏移让地图内容显示在可见中央
      if (sheetSnap !== "peek") {
        requestAnimationFrame(() => {
          const h = el.clientHeight;
          const visibleH = sheetSnap === "full" ? h * 0.07 : h * 0.25;
          const offsetY = (h - visibleH) / 2;
          map.panBy([0, offsetY], { animate: false });
        });
      }
    }

    // ResizeObserver：容器尺寸变化时刷新
    const ro = new ResizeObserver(() => {
      const map = mapRef.current;
      if (!map) return;
      map.invalidateSize();
      // 屏幕旋转或容器尺寸变化后，重新计算 zoom 与中心点，避免点位溢出可视区。
      requestAnimationFrame(() => renderMarkersRef.current());
    });
    if (wrapRef.current) ro.observe(wrapRef.current);

    return () => {
      destroyed = true;
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      clusterMarkersRef.current.forEach((marker) => marker.remove());
      clusterMarkersRef.current = [];
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 当 showUserLocation 变化时，更新用户位置标记 ──────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (showUserLocation && userMarkerRef.current) {
      // 演示态始终使用望京默认点，不跟随浏览器 GPS 更新。
      userMarkerRef.current.setLatLng([40.002, 116.472]);
    }
  }, [showUserLocation]);

  // ── 更新 POI 标记和路线连线（抽取为可复用函数）──────────────
  const renderMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    clusterMarkersRef.current.forEach((m) => m.remove());
    clusterMarkersRef.current = [];
    routeLayersRef.current.forEach((layer) => layer.remove());
    routeLayersRef.current = [];

    // activeRouteIndex === -1 表示用户尚未主动选择方案，不渲染任何标记
    if (activeRouteIndex < 0) return;

    // liveStops（即 mapStops）是唯一数据源，不再 fallback 到 routes
    const stops = liveStops ?? [];
    if (stops.length === 0) return;

    const latlngs = stops.map(getStopLatLng) as [number, number][];
    const pillOffsets = getPoiPillOffsets(latlngs);
    pillOffsetsRef.current = pillOffsets;

    stops.forEach((stop, idx) => {
      const pos = latlngs[idx];
      const color = categoryColor(stop.category);
      const active = stop.poi_id === activePoi;

      const marker = L.marker(pos, {
        icon: makePoiPillIcon(idx, stop.name, color, active, pillOffsets[idx]),
        zIndexOffset: active ? 500 : 100,
      })
        .addTo(map)
        // 点击弹窗：显示详细信息
        .bindPopup(
          `<div style="font-size:13px;font-weight:600;color:#1a2a22;min-width:100px">
            <b>${idx + 1}. ${stop.name}</b>
            ${stop.address ? `<br/><span style="color:#6b7c74;font-size:11px;font-weight:400">${stop.address}</span>` : ""}
          </div>`,
          { offset: [0, -8] as [number, number], closeButton: false },
        )
        .on("click", () => onPoiClick(stop.poi_id));

      markersRef.current.push(marker);
      if (active) marker.openPopup();
    });

    // 从“当前位置 → 1 → 2 → 3 …… → 回家”完整绘制。后续站点优先使用高德道路轨迹，
    // 缺失时按地图坐标生成弧线作为可见降级，避免路线出现断段。
    const userPosition = getVisibleUserPosition();
    const routeOrigins = userPosition
      ? [userPosition, ...latlngs]
      : [...latlngs.slice(0, -1)];
    const routeTargets = userPosition
      ? [...latlngs, userPosition]
      : latlngs.slice(1);
    const routeStops = userPosition
      ? [...stops, null]
      : stops.slice(1);
    const routeColors = ["#0B6CFF", "#8B5CF6", "#F97316", "#10B981", "#EC4899", "#06B6D4"];
    routeLayersRef.current = routeTargets.flatMap((target, index) => {
      const routePath = getRoutePath(
        routeOrigins[index],
        target,
        routeStops[index]?.polyline_from_previous,
        routeStops[index]?.route_leg_source_from_previous,
      );
      const color = routeColors[index % routeColors.length];
      const outline = L.polyline(routePath, {
        color: "#FFFFFF", weight: 12, opacity: 0.96, lineCap: "round", lineJoin: "round",
      }).addTo(map);
      const route = L.polyline(routePath, {
        color, weight: 7, opacity: 1, lineCap: "round", lineJoin: "round",
      }).addTo(map);
      return [outline, route];
    });

    const updateClusters = () => {
      clusterMarkersRef.current.forEach((marker) => marker.remove());
      clusterMarkersRef.current = [];
      markersRef.current.forEach((marker) => marker.setOpacity(1));

      const groups = getOverlappingPoiGroups(map, latlngs, stops);
      groups.forEach((indices) => {
        // 隐藏发生视觉重叠的单点胶囊，改由一个显示所有序号的融合胶囊承载。
        indices.forEach((index) => markersRef.current[index]?.setOpacity(0));
        const center: [number, number] = [
          indices.reduce((sum, index) => sum + latlngs[index][0], 0) / indices.length,
          indices.reduce((sum, index) => sum + latlngs[index][1], 0) / indices.length,
        ];
        const cluster = L.marker(center, {
          icon: makePoiClusterIcon(indices),
          zIndexOffset: 700,
        }).addTo(map).on("click", () => {
          // 点击融合胶囊即聚焦并放大，放大到不重叠后会自动还原成单个地点标签。
          map.flyTo(center, Math.min(map.getZoom() + 2, 18), { duration: 0.35 });
        });
        clusterMarkersRef.current.push(cluster);
      });
    };
    updateClustersRef.current = updateClusters;

    // POI 与地图上实际显示的用户位置必须共同参与 bounds 计算。
    const allBoundsPoints = userPosition ? [...latlngs, userPosition] : latlngs;

    // 根据上方真实可视区域执行 fitBounds，自动计算缩放级别和中心点。
    // fitBounds 会在保持所有点可见的前提下尽可能放大路线。

    fitToStops(map, allBoundsPoints, sheetSnap, {
      boardView: isBoardView,
      boardOverlayHeight,
    });
    updateClusters();
    map.once("moveend", updateClusters);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveStops, activeRouteIndex, activePoi, sheetSnap, showUserLocation, isBoardView, boardOverlayHeight, getVisibleUserPosition]);

  // 把最新 renderMarkers 存入 ref，供 createMap 回调调用
  renderMarkersRef.current = renderMarkers;

  // ── 标记渲染 useEffect：依赖变化时重新渲染 ─────────────────
  useEffect(() => {
    renderMarkers();
  }, [renderMarkers]);

  // ── sheetSnap 变化时重新 fit（等 sheet 动画结束后再执行）──────
  useEffect(() => {
    if (fitTimerRef.current) clearTimeout(fitTimerRef.current);
    fitTimerRef.current = setTimeout(() => {
      const map = mapRef.current;
      if (!map || activeRouteIndex < 0) return;
      const stops = liveStops ?? [];
      if (stops.length === 0) return;
      const latlngs = stops.map(getStopLatLng) as [number, number][];

      // 使用当前可见的用户标记坐标，保证重算缩放时用户位置始终在范围内。
      const userPosition = getVisibleUserPosition();
      const allBoundsPoints = userPosition ? [...latlngs, userPosition] : latlngs;

      fitToStops(map, allBoundsPoints, sheetSnap, {
        boardView: isBoardView,
        boardOverlayHeight,
      });
    }, 380); // 比 sheet 过渡动画 350ms 略长
    return () => { if (fitTimerRef.current) clearTimeout(fitTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetSnap, showUserLocation, isBoardView, boardOverlayHeight, getVisibleUserPosition]);

  // ── activePoi 变化时高亮 ──────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || activeRouteIndex < 0) return;
    const stops = liveStops ?? [];
    stops.forEach((stop, idx) => {
      const marker = markersRef.current[idx];
      if (!marker) return;
      const active = stop.poi_id === activePoi;
      marker.setIcon(makePoiPillIcon(
        idx,
        stop.name,
        categoryColor(stop.category),
        active,
        pillOffsetsRef.current[idx] ?? [0, -22],
      ));
      if (active) {
        marker.openPopup();
        // 看板模式必须维持“全部 POI + 用户位置”的整体视野，不能因点选而把其他点推离可视区。
        if (!isBoardView) map.panTo(marker.getLatLng(), { animate: true });
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePoi, isBoardView]);

  return (
    <div
      ref={wrapRef}
      className="map-panel"
      style={{ position: "absolute", inset: 0, overflow: "hidden" }}
    />
  );
}
