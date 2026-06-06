import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Route, RouteStop } from "../api/types";

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

// ── 创建序号圆形图标 ─────────────────────────────────────────────
function makeNumberIcon(index: number, color: string, active: boolean): L.DivIcon {
  const size = active ? 32 : 26;
  const fontSize = active ? 13 : 11;
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${color};border:${active ? "3px" : "2px"} solid white;
      box-shadow:0 2px 8px rgba(0,0,0,${active ? "0.35" : "0.2"});
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-size:${fontSize}px;font-weight:700;
    ">${index + 1}</div>`,
    iconSize:    [size, size],
    iconAnchor:  [size / 2, size / 2],
    popupAnchor: [0, -(size / 2 + 4)],
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
) {
  if (latlngs.length === 0) return;
  const vh = window.innerHeight;
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

export interface MapPanelProps {
  routes: Route[];
  activeRouteIndex: number;
  activePoi: string | null;
  onPoiClick: (poiId: string) => void;
  /** 底部面板当前档位，用于计算 fitBounds padding */
  sheetSnap?: "peek" | "half" | "full";
  /** 本地编辑后的最新 stops（优先级高于 routes[activeRouteIndex].stops） */
  liveStops?: RouteStop[];
}

export function MapPanel({ routes, activeRouteIndex, activePoi, onPoiClick, sheetSnap = "half", liveStops }: MapPanelProps) {
  const wrapRef      = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<L.Map | null>(null);
  const markersRef   = useRef<L.Marker[]>([]);
  const polylineRef  = useRef<L.Polyline | null>(null);
  const rafRef       = useRef<number>(0);
  const fitTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

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

      // 高德地图瓦片（无需 API Key）
      // style=7: 矢量路网  scl=2: 只渲染路网不渲染注记（文字标注）
      // 叠加一层 style=8（纯注记层）并用更小比例，让文字显示更小
      L.tileLayer(
        "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=1&scl=2&style=7",
        {
          subdomains: ["1", "2", "3", "4"],
          maxZoom: 20,
          attribution: "© 高德地图",
        },
      ).addTo(map);

      // 叠加注记层（文字/POI），size=2 使用较小字号
      L.tileLayer(
        "https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&size=2&scl=1&style=8",
        {
          subdomains: ["1", "2", "3", "4"],
          maxZoom: 20,
          opacity: 0.9,
        },
      ).addTo(map);

      L.control.attribution({ position: "bottomright", prefix: false })
        .addAttribution('<a href="https://www.amap.com" target="_blank">© 高德地图</a>')
        .addTo(map);

      // 缩放按钮放右侧，避开左上角的退出按钮
      L.control.zoom({ position: "topright" }).addTo(map);

      // 用户位置（北京望京）
      L.marker([40.002, 116.472], { icon: USER_ICON, zIndexOffset: 1000 }).addTo(map);

      mapRef.current = map;

      // 修正尺寸
      map.invalidateSize();

      // 初始视图偏移：half 档时底部面板遮住 75vh，可视区域只有上方 25vh。
      // 北京默认在容器几何中心（h/2），要让它出现在可见区域中央（h*0.125），
      // 需要把视图向下（正 y）移动 h*0.375，这样地图标点在视觉上向上落在可见区中间。
      requestAnimationFrame(() => {
        const h = el.clientHeight;
        const visibleH = h * 0.25;                // 上方可见区域高度
        const offsetY = (h - visibleH) / 2;       // ≈ 37.5% 容器高
        map.panBy([0, offsetY], { animate: false });
      });
    }

    // ResizeObserver：容器尺寸变化时刷新
    const ro = new ResizeObserver(() => {
      mapRef.current?.invalidateSize();
    });
    if (wrapRef.current) ro.observe(wrapRef.current);

    return () => {
      destroyed = true;
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 更新 POI 标记和路线连线 ───────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    polylineRef.current?.remove();
    polylineRef.current = null;

    // activeRouteIndex === -1 表示用户尚未主动选择方案，不渲染任何标记
    if (activeRouteIndex < 0) return;

    // liveStops（即 mapStops）是唯一数据源，不再 fallback 到 routes
    const stops = liveStops ?? [];
    if (stops.length === 0) return;

    const latlngs: [number, number][] = [];

    stops.forEach((stop, idx) => {
      const pos    = getStopLatLng(stop);
      const color  = categoryColor(stop.category);
      const active = stop.poi_id === activePoi;
      latlngs.push(pos);

      const marker = L.marker(pos, {
        icon: makeNumberIcon(idx, color, active),
        zIndexOffset: active ? 500 : 100,
      })
        .addTo(map)
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

    polylineRef.current = L.polyline(latlngs, {
      color: "#FF6600", weight: 2.5, opacity: 0.75, dashArray: "6 5",
    }).addTo(map);

    // fitBounds 立即执行一次（用当前 sheetSnap）
    fitToStops(map, latlngs, sheetSnap);

  // liveStops 有值时完全由它驱动，routes 仅作为 liveStops 为空时的 fallback
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveStops, activeRouteIndex, activePoi, sheetSnap]);

  // ── sheetSnap 变化时重新 fit（等 sheet 动画结束后再执行）──────
  useEffect(() => {
    if (fitTimerRef.current) clearTimeout(fitTimerRef.current);
    fitTimerRef.current = setTimeout(() => {
      const map = mapRef.current;
      if (!map || activeRouteIndex < 0) return;
      const stops = liveStops ?? [];
      if (stops.length === 0) return;
      const latlngs = stops.map(getStopLatLng) as [number, number][];
      fitToStops(map, latlngs, sheetSnap);
    }, 380); // 比 sheet 过渡动画 350ms 略长
    return () => { if (fitTimerRef.current) clearTimeout(fitTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetSnap]);

  // ── activePoi 变化时高亮 ──────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || activeRouteIndex < 0) return;
    const stops = liveStops ?? [];
    stops.forEach((stop, idx) => {
      const marker = markersRef.current[idx];
      if (!marker) return;
      const active = stop.poi_id === activePoi;
      marker.setIcon(makeNumberIcon(idx, categoryColor(stop.category), active));
      if (active) {
        marker.openPopup();
        map.panTo(marker.getLatLng(), { animate: true });
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePoi]);

  return (
    <div
      ref={wrapRef}
      className="map-panel"
      style={{ position: "absolute", inset: 0, overflow: "hidden" }}
    />
  );
}
