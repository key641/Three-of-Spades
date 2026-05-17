import type { Route } from "../api/types";
import { RouteCard } from "./RouteCard";

interface RouteCompareProps {
  routes: Route[];
}

export function RouteCompare({ routes }: RouteCompareProps) {
  return (
    <section className="route-section">
      <h2>路线方案</h2>
      <div className="route-grid">
        {routes.length === 0 ? <p className="muted">还没有路线，先输入一次出行需求。</p> : null}
        {routes.map((route) => (
          <RouteCard key={route.route_id} route={route} />
        ))}
      </div>
    </section>
  );
}

