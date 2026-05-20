import type { RouteStop } from "../api/types";

interface RouteTimelineProps {
  stops: RouteStop[];
}

export function RouteTimeline({ stops }: RouteTimelineProps) {
  return (
    <ol className="timeline">
      {stops.map((stop) => (
        <li key={stop.poi_id}>
          <time>{stop.start_time}-{stop.end_time}</time>
          <div>
            <strong>{stop.name}</strong>
            <p>
              {stop.category} · 预计消费 {stop.estimated_cost} · 排队 {stop.queue_minutes} 分钟
              {stop.travel_minutes_from_previous ? ` · 路上 ${stop.travel_minutes_from_previous} 分钟` : ""}
              {stop.distance_km_from_previous ? ` · ${stop.distance_km_from_previous} km` : ""}
              {stop.transport_mode_from_previous ? ` · ${stop.transport_mode_from_previous}` : ""}
            </p>
            {stop.reason ? <p>{stop.reason}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
