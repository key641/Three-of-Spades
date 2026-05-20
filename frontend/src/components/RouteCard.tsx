import { Clock, Coins, Timer } from "lucide-react";
import type { Route } from "../api/types";
import { ActionBar } from "./ActionBar";
import { RouteTimeline } from "./RouteTimeline";
import { ScoreBreakdown } from "./ScoreBreakdown";

interface RouteCardProps {
  route: Route;
  onAction?: (action: string, routeId: string) => void;
}

export function RouteCard({ route, onAction }: RouteCardProps) {
  return (
    <article className="route-card">
      {/* 重规划提示 */}
      {route.replan_reason && (
        <div className="replan-notice">⚡ {route.replan_reason}</div>
      )}

      {/* 头部：标题 + 评分 */}
      <div className="route-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3>{route.title}</h3>
          <p className="muted">{route.summary}</p>
        </div>
        <div className="score">{route.score?.toFixed(1) ?? "—"}</div>
      </div>

      {/* 核心指标 */}
      <div className="metrics">
        <span>
          <Clock size={13} />
          {route.total_duration_minutes} 分钟
        </span>
        <span>
          <Coins size={13} />
          人均 ¥{route.total_cost_per_person}
        </span>
        <span>
          <Timer size={13} />
          排队 {route.total_queue_minutes} 分
        </span>
      </div>

      {/* 评分维度进度条 */}
      {route.score_breakdown && (
        <ScoreBreakdown breakdown={route.score_breakdown} />
      )}

      {/* 行程时间线 */}
      {route.stops?.length > 0 && (
        <RouteTimeline stops={route.stops} />
      )}

      {/* 推荐原因标签 */}
      {route.reasons?.length > 0 && (
        <div className="reason-list">
          {route.reasons.map((r) => (
            <span key={r} className="tag">{r}</span>
          ))}
        </div>
      )}

      {/* 操作按钮 */}
      <ActionBar routeId={route.route_id} onAction={onAction} />
    </article>
  );
}
