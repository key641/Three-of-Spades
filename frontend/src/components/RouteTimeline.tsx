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
