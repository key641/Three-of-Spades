import { Navigation } from "lucide-react";
import type { RouteStop } from "../api/types";
import { getCategoryLabel } from "../utils/categoryLabels";

interface RouteTimelineProps {
  stops: RouteStop[];
}

export function RouteTimeline({ stops }: RouteTimelineProps) {
  return (
    <ol className="timeline">
      {stops.map((stop, index) => (
        <li key={stop.poi_id}>
          {/* 左侧时间 */}
          <time>{stop.start_time}</time>

          {/* 圆点 + 竖线列 */}
          <div className="timeline-dot-col">
            <div className="timeline-dot" />
            <div className="timeline-line" />
          </div>

          {/* 右侧内容 */}
          <div className="timeline-body">
            {index > 0 && hasTransitInfo(stop) && (
              <div className="timeline-transit" aria-label={`从上一站到${stop.name}的交通方式`}>
                <Navigation size={12} />
                <span>{formatTransportMode(stop.transport_mode_from_previous)}</span>
                {stop.travel_minutes_from_previous != null && (
                  <span>{stop.travel_minutes_from_previous} 分钟</span>
                )}
                {stop.distance_km_from_previous != null && (
                  <span>{formatDistance(stop.distance_km_from_previous)}</span>
                )}
              </div>
            )}
            <strong>{stop.name}</strong>
            <p className="timeline-meta">
              <span className="tag-small">{getCategoryLabel(stop.category)}</span>
              {stop.estimated_cost > 0 && (
                <span style={{ fontSize: "12px", color: "var(--color-muted)" }}>
                  ¥{stop.estimated_cost}
                </span>
              )}
              {stop.queue_minutes > 0 && (
                <span className={stop.queue_minutes >= 30 ? "text-warning" : ""}
                  style={{ fontSize: "12px" }}>
                  排队 {stop.queue_minutes} 分
                </span>
              )}
              {stop.tags?.length > 0 && stop.tags.slice(0, 2).map((tag) => (
                <span key={tag} className="tag-small">{tag}</span>
              ))}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function hasTransitInfo(stop: RouteStop): boolean {
  return Boolean(
    stop.transport_mode_from_previous ||
      stop.travel_minutes_from_previous != null ||
      stop.distance_km_from_previous != null,
  );
}

function formatTransportMode(mode?: string | null): string {
  if (!mode) return "交通";
  return mode
    .split("/")
    .map((item) => {
      const key = item.trim().toLowerCase();
      const labels: Record<string, string> = {
        walk: "步行",
        walking: "步行",
        metro: "地铁",
        subway: "地铁",
        bus: "公交",
        taxi: "打车",
        drive: "驾车",
        driving: "驾车",
        bike: "骑行",
        bicycling: "骑行",
      };
      return labels[key] ?? item.trim();
    })
    .filter(Boolean)
    .join("/");
}

function formatDistance(distanceKm: number): string {
  if (distanceKm < 1) return `${Math.round(distanceKm * 1000)} 米`;
  return `${distanceKm.toFixed(1)} 公里`;
}
