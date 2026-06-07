import { Wallet, CheckCircle2, Circle, MapPin, AlertCircle, Zap } from "lucide-react";
import { useState } from "react";
import type { Route, RouteStop } from "../api/types";
import { RouteOptimizeBar } from "./ActionBar";
import { RouteTimeline, type PoiAction } from "./RouteTimeline";

function stripLeadingEmoji(text: string): string {
  return text.replace(/^[\u{1F000}-\u{1FFFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\uFE0F\s]+/u, "").trim();
}

interface RouteCardProps {
  route: Route;
  selected?: boolean;
  onSelect?: (route: Route) => void;
  onAction?: (action: string, routeId: string) => void;
  onPoiAction?: (action: PoiAction, routeId: string) => void;
  onInjectChat?: (text: string) => void;
  /** stops 被本地编辑后回调（用于地图同步） */
  onStopsChange?: (routeId: string, stops: RouteStop[]) => void;
}

function formatDuration(minutes: number): string {
  if (minutes >= 60) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h}小时${m}分` : `${h}小时`;
  }
  return `${minutes}分钟`;
}

/** 从 stops 提取时间段，如 "12:00 → 18:00"；若无数据则降级为时长 */
function formatTimeRange(route: Route): string {
  const stops = route.stops;
  if (stops?.length) {
    const start = stops[0].start_time;
    const end   = stops[stops.length - 1].end_time;
    if (start && end) return `${start} → ${end}`;
  }
  return formatDuration(route.total_duration_minutes);
}

/** 根据 score_breakdown.preference + reasons 数量计算前端匹配度（0-10） */
function calcMatchScore(route: Route): number {
  const prefRaw = route.score_breakdown?.preference ?? 0;
  // preference 字段可能是 0-1 / 0-10 / 0-100，统一归一到 0-10
  const prefScore = prefRaw <= 1 ? prefRaw * 10 : prefRaw <= 10 ? prefRaw : prefRaw / 10;
  // reasons 数量加成（每条 +0.3，上限 +1.5）
  const reasonBonus = Math.min((route.reasons?.length ?? 0) * 0.3, 1.5);
  // 整体分数加成（高分路线匹配度也应该高）
  const overallRaw = route.score <= 10 ? route.score : route.score / 10;
  const overallBonus = overallRaw * 0.2;
  return Math.min(10, prefScore * 0.6 + overallBonus + reasonBonus + 3.5);
}

/** 从站点数据中提取出行提示（排队 / 预约汇总） */
function buildTripTips(route: Route): string[] {
  const tips: string[] = [];
  const stops = route.stops ?? [];

  // 需要预约的站点
  const bookingStops = stops.filter((s) => s.booking_required);
  if (bookingStops.length > 0) {
    const names = bookingStops.map((s) => `「${s.name}」`).join("、");
    const hasPhone = bookingStops.some((s) => s.booking_phone);
    const hasUrl   = bookingStops.some((s) => s.booking_url);
    if (hasUrl) {
      tips.push(`${names} 可在线预约，建议出发前提前锁定`);
    } else if (hasPhone) {
      tips.push(`${names} 需电话预约，出发前记得致电`);
    } else {
      tips.push(`${names} 建议提前预约`);
    }
  }

  // 有排队较多的站点
  const highQueueStops = stops.filter(
    (s) => s.queue_level === "high" || s.queue_level === "very_high"
  );
  if (highQueueStops.length > 0 && bookingStops.length === 0) {
    const names = highQueueStops.map((s) => `「${s.name}」`).join("、");
    tips.push(`${names} 人气较旺，建议错峰前往或提早出发`);
  }

  return tips;
}

export function RouteCard({ route, selected, onSelect, onAction, onPoiAction, onInjectChat, onStopsChange }: RouteCardProps) {
  const [localStops, setLocalStops] = useState<RouteStop[]>(route.stops ?? []);
  const tripTips = buildTripTips(route);
  const stopCount = localStops.length;

  return (
    <article className={`route-card${selected ? " route-card--selected" : ""}`}>
      {/* 重规划提示 */}
      {route.replan_reason && (
        <div className="replan-notice"><Zap size={12} style={{ flexShrink: 0 }} /> {route.replan_reason}</div>
      )}

      {/* 头部：标题 + 人均 + 地点数 */}
      <div className="route-card-header">
        <h3 className="route-card-title">{stripLeadingEmoji(route.title)}</h3>
        <div className="route-card-header-meta">
          <span className="route-header-meta-item">
            <Wallet size={11} />
            人均¥{route.total_cost_per_person}
          </span>
          {stopCount > 0 && (
            <span className="route-header-meta-item">
              <MapPin size={11} />
              {stopCount}个地点
            </span>
          )}
        </div>
      </div>

      {/* 核心摘要：一句话说明白这条路线 */}
      {route.summary && (
        <p className="route-summary">{route.summary}</p>
      )}

      {/* 出行提示（排队 / 预约汇总） */}
      {tripTips.length > 0 && (
        <div className="route-trip-tips">
          <span className="route-trip-tips-icon"><AlertCircle size={12} /></span>
          <div className="route-trip-tips-list">
            {tripTips.map((tip, i) => (
              <span key={i} className="route-trip-tip">{tip}</span>
            ))}
          </div>
        </div>
      )}

      {/* POI 站点卡片列表 */}
      {localStops.length > 0 && (
        <RouteTimeline
          stops={localStops}
          onPoiAction={onPoiAction
            ? (action) => onPoiAction(action, route.route_id)
            : undefined}
          onInjectChat={onInjectChat}
          onStopsChange={(newStops) => {
            setLocalStops(newStops);
            onStopsChange?.(route.route_id, newStops);
          }}
        />
      )}

      {/* 路线级优化按钮（折叠式） */}
      <RouteOptimizeBar routeId={route.route_id} onAction={onAction} />

      {/* ── 选定方案按钮 ── */}
      <button
        type="button"
        className={`route-select-btn${selected ? " selected" : ""}`}
        onClick={() => onSelect?.({ ...route, stops: localStops })}
      >
        {selected ? (
          <>
            <CheckCircle2 size={15} />
            当前出行方案
          </>
        ) : (
          <>
            <Circle size={15} />
            选这条
          </>
        )}
      </button>
    </article>
  );
}
