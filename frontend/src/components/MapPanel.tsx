import { useEffect, useRef, useState } from "react";
import type { Route, RouteStop } from "../api/types";

// ── Mock POI 坐标系统（归一化坐标 0-100）────────────────────────
// 在真实场景下这里接入高德/Leaflet，坐标转投影计算
// 目前用 SVG viewport 100×100 来模拟一张地图
const BEIJING_AREAS: { name: string; x: number; y: number; type: "landmark" }[] = [
  { name: "故宫", x: 42, y: 35, type: "landmark" },
  { name: "天坛", x: 46, y: 65, type: "landmark" },
  { name: "颐和园", x: 18, y: 28, type: "landmark" },
  { name: "三里屯", x: 62, y: 38, type: "landmark" },
  { name: "南锣鼓巷", x: 48, y: 28, type: "landmark" },
  { name: "798艺术区", x: 72, y: 22, type: "landmark" },
  { name: "鸟巢", x: 60, y: 15, type: "landmark" },
  { name: "王府井", x: 50, y: 40, type: "landmark" },
];

// 根据 POI 名字/类型生成稳定的「虚拟坐标」（无真实地图时保持一致性）
function hashCoord(s: string, min: number, max: number): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return min + (h % 1000) / 1000 * (max - min);
}

function getPoiCoord(stop: RouteStop): { x: number; y: number } {
  // 先匹配已知北京地标
  const known = BEIJING_AREAS.find((a) => stop.name.includes(a.name) || a.name.includes(stop.name));
  if (known) return { x: known.x, y: known.y };
  // 否则基于 name hash 生成稳定坐标，分布在画布中央区域
  return {
    x: hashCoord(stop.name + "x", 20, 80),
    y: hashCoord(stop.name + "y", 20, 80),
  };
}

// 类别 → 颜色
function categoryColor(category: string): string {
  const map: Record<string, string> = {
    food:      "#FF6600",
    restaurant:"#FF6600",
    nature:    "#52C41A",
    park:      "#52C41A",
    culture:   "#722ED1",
    museum:    "#722ED1",
    shopping:  "#1677FF",
    landmark:  "#FA8C16",
    show:      "#EB2F96",
    rest:      "#13C2C2",
  };
  return map[category] ?? "#FF6600";
}

// ── 迷你地图背景（SVG 街道纹理）──────────────────────────────────
function MapBackground() {
  return (
    <g className="map-bg-layer">
      {/* 背景底色 */}
      <rect x="0" y="0" width="100" height="100" fill="#E8EDF2" />
      {/* 模拟街道网格 */}
      {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((v) => (
        <line key={`h${v}`} x1="0" y1={v} x2="100" y2={v} stroke="#fff" strokeWidth="0.5" opacity="0.7" />
      ))}
      {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((v) => (
        <line key={`v${v}`} x1={v} y1="0" x2={v} y2="100" stroke="#fff" strokeWidth="0.5" opacity="0.7" />
      ))}
      {/* 主干道（较粗） */}
      <line x1="0" y1="50" x2="100" y2="50" stroke="#fff" strokeWidth="1.2" opacity="0.9" />
      <line x1="50" y1="0" x2="50" y2="100" stroke="#fff" strokeWidth="1.2" opacity="0.9" />
      <line x1="0" y1="30" x2="100" y2="30" stroke="#fff" strokeWidth="0.8" opacity="0.8" />
      <line x1="0" y1="70" x2="100" y2="70" stroke="#fff" strokeWidth="0.8" opacity="0.8" />
      <line x1="30" y1="0" x2="30" y2="100" stroke="#fff" strokeWidth="0.8" opacity="0.8" />
      <line x1="70" y1="0" x2="70" y2="100" stroke="#fff" strokeWidth="0.8" opacity="0.8" />
      {/* 绿地/公园色块 */}
      <rect x="15" y="20" width="12" height="10" rx="2" fill="#C8E6C9" opacity="0.7" />
      <rect x="65" y="55" width="10" height="8" rx="2" fill="#C8E6C9" opacity="0.7" />
      <rect x="35" y="72" width="15" height="10" rx="2" fill="#C8E6C9" opacity="0.7" />
      {/* 水体 */}
      <ellipse cx="78" cy="32" rx="6" ry="4" fill="#BBDEFB" opacity="0.7" />
    </g>
  );
}

export interface MapPanelProps {
  routes: Route[];
  activeRouteIndex: number;        // 当前高亮方案索引
  activePoi: string | null;        // 当前高亮 POI id
  onPoiClick: (poiId: string) => void;
}

export function MapPanel({ routes, activeRouteIndex, activePoi, onPoiClick }: MapPanelProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  const activeRoute = routes[activeRouteIndex] ?? null;
  const stops = activeRoute?.stops ?? [];

  // 计算 POI 坐标列表
  const coords = stops.map((s) => getPoiCoord(s));

  // 用户当前位置（固定 mock：北京朝阳区望京附近）
  const userPos = { x: 62, y: 32 };

  useEffect(() => {
    // 点击地图空白处，清除 tooltip
    const handler = () => setTooltip(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  return (
    <div className="map-panel">
      {/* SVG 地图主体 */}
      <svg
        ref={svgRef}
        className="map-svg"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
      >
        <MapBackground />

        {/* ── 路径连线 ── */}
        {coords.length >= 2 && (
          <g className="map-path-layer">
            {coords.slice(0, -1).map((c, i) => {
              const next = coords[i + 1];
              const midX = (c.x + next.x) / 2;
              const midY = (c.y + next.y) / 2;
              return (
                <g key={`path-${i}`}>
                  <path
                    d={`M ${c.x} ${c.y} Q ${midX + 3} ${midY - 3} ${next.x} ${next.y}`}
                    fill="none"
                    stroke="#FF6600"
                    strokeWidth="0.6"
                    strokeDasharray="2 1.5"
                    opacity="0.7"
                  />
                  {/* 箭头指示方向 */}
                  <circle
                    cx={(c.x + next.x * 2) / 3}
                    cy={(c.y + next.y * 2) / 3}
                    r="0.5"
                    fill="#FF6600"
                    opacity="0.6"
                  />
                </g>
              );
            })}
          </g>
        )}

        {/* ── 用户位置标记 ── */}
        <g className="map-user-pin">
          {/* 脉冲圈 */}
          <circle cx={userPos.x} cy={userPos.y} r="4" fill="#1677FF" opacity="0.15">
            <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.2;0;0.2" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle cx={userPos.x} cy={userPos.y} r="2.2" fill="#1677FF" stroke="#fff" strokeWidth="0.8" />
          <circle cx={userPos.x} cy={userPos.y} r="0.8" fill="#fff" />
        </g>

        {/* ── POI 标注 ── */}
        {stops.map((stop, idx) => {
          const { x, y } = coords[idx];
          const color = categoryColor(stop.category);
          const isActive = stop.poi_id === activePoi;
          const r = isActive ? 3.8 : 2.8;

          return (
            <g
              key={stop.poi_id}
              className="map-poi"
              style={{ cursor: "pointer" }}
              onClick={(e) => {
                e.stopPropagation();
                onPoiClick(stop.poi_id);
                setTooltip({ x, y, text: stop.name });
              }}
            >
              {/* 序号圆圈 */}
              <circle
                cx={x}
                cy={y}
                r={r + 1.2}
                fill="white"
                stroke={color}
                strokeWidth={isActive ? 1.2 : 0.8}
                opacity={isActive ? 1 : 0.9}
                style={{ filter: isActive ? `drop-shadow(0 0 2px ${color})` : "none" }}
              />
              <circle cx={x} cy={y} r={r} fill={color} />
              <text
                x={x}
                y={y + 0.5}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="white"
                fontSize={isActive ? "2.6" : "2.2"}
                fontWeight="bold"
              >
                {idx + 1}
              </text>

              {/* 地点名（仅激活时显示完整，否则显示短名） */}
              <text
                x={x}
                y={y - r - 2}
                textAnchor="middle"
                fill={isActive ? "#20242A" : "#66707C"}
                fontSize={isActive ? "2.8" : "2.2"}
                fontWeight={isActive ? "600" : "400"}
                style={{ pointerEvents: "none" }}
              >
                {stop.name.length > 5 ? stop.name.slice(0, 5) + "…" : stop.name}
              </text>
            </g>
          );
        })}

        {/* ── 无方案时的占位提示 ── */}
        {stops.length === 0 && (
          <g>
            <text x="50" y="45" textAnchor="middle" fill="#A0ADB8" fontSize="4">
              📍 规划完成后
            </text>
            <text x="50" y="53" textAnchor="middle" fill="#A0ADB8" fontSize="4">
              地点将在地图上显示
            </text>
          </g>
        )}
      </svg>

      {/* Tooltip（POI 名称） */}
      {tooltip && (
        <div
          className="map-tooltip"
          style={{
            left: `${tooltip.x}%`,
            top:  `${tooltip.y}%`,
          }}
        >
          {tooltip.text}
        </div>
      )}

      {/* 图例 */}
      {stops.length > 0 && (
        <div className="map-legend">
          <span className="map-legend-item">
            <span className="map-legend-dot" style={{ background: "#1677FF" }} /> 出发点
          </span>
          <span className="map-legend-item">
            <span className="map-legend-dot" style={{ background: "#FF6600" }} /> 行程地点
          </span>
        </div>
      )}
    </div>
  );
}
