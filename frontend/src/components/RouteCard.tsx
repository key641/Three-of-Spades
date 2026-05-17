import { Clock, Coins, Timer } from "lucide-react";
import type { Route } from "../api/types";
import { ActionBar } from "./ActionBar";
import { RouteTimeline } from "./RouteTimeline";

interface RouteCardProps {
  route: Route;
}

export function RouteCard({ route }: RouteCardProps) {
  return (
    <article className="route-card">
      <div className="route-card-header">
        <div>
          <h3>{route.title}</h3>
          <p>{route.summary}</p>
        </div>
        <div className="score">{route.score}</div>
      </div>

      <div className="metrics">
        <span><Clock size={16} />{route.total_duration_minutes} 分钟</span>
        <span><Coins size={16} />人均 {route.total_cost_per_person}</span>
        <span><Timer size={16} />排队 {route.total_queue_minutes} 分钟</span>
      </div>

      <RouteTimeline stops={route.stops} />

      <div className="reason-list">
        {route.reasons.map((reason) => (
          <span key={reason}>{reason}</span>
        ))}
      </div>

      <ActionBar />
    </article>
  );
}

