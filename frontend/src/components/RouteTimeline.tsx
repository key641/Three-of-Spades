import type { RouteStop } from "../api/types";
import { getCategoryLabel } from "../utils/categoryLabels";

interface RouteTimelineProps {
  stops: RouteStop[];
}

export function RouteTimeline({ stops }: RouteTimelineProps) {
  return (
    <ol className="timeline">
      {stops.map((stop) => (
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
            {(stop.transport_mode_from_previous || stop.travel_minutes_from_previous || stop.distance_km_from_previous) && (
              <p className="timeline-leg">
                {formatTransportMode(stop.transport_mode_from_previous)}
                {stop.travel_minutes_from_previous ? ` · 约 ${stop.travel_minutes_from_previous} 分钟` : ""}
                {stop.distance_km_from_previous ? ` · ${stop.distance_km_from_previous} 公里` : ""}
              </p>
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
              {stop.queue_minutes > 0 && (
                <span style={{ fontSize: "12px", color: "var(--color-muted)" }}>
                  实时模拟
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

function formatTransportMode(mode?: string | null) {
  if (!mode) return "交通";
  const labels: Record<string, string> = {
    walk: "步行",
    taxi: "打车",
    drive: "打车",
    metro: "地铁",
    bus: "公交",
    bike: "骑行",
  };
  return mode
    .split("/")
    .map((part) => labels[part] ?? part)
    .join("或");
}
