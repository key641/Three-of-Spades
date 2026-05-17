import type { Route } from "../api/types";

interface ReplanPanelProps {
  routes: Route[];
}

export function ReplanPanel({ routes }: ReplanPanelProps) {
  return (
    <section className="panel full-width">
      <h2>动态事件模拟</h2>
      <div className="action-bar">
        <button disabled={routes.length === 0}>餐厅排队 90 分钟</button>
        <button disabled={routes.length === 0}>交通堵车</button>
        <button disabled={routes.length === 0}>我们有点累了</button>
      </div>
      <p className="muted">下一步接入 `/api/routes/replan` 后，这里展示重规划前后变化。</p>
    </section>
  );
}

