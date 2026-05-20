import type { RouteScoreBreakdown } from "../api/types";

interface ScoreBreakdownProps {
  breakdown: RouteScoreBreakdown;
}

const LABELS: Array<{ key: keyof RouteScoreBreakdown; label: string }> = [
  { key: "quality",    label: "品质" },
  { key: "queue",      label: "排队少" },
  { key: "budget",     label: "预算" },
  { key: "distance",   label: "距离" },
  { key: "preference", label: "偏好" },
];

export function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  return (
    <div className="score-breakdown">
      {LABELS.map(({ key, label }) => {
        const value = breakdown[key] ?? 0;
        // 兼容 0-1 和 0-10 两种值域
        const pct = value <= 1 ? value * 100 : (value / 10) * 100;
        return (
          <div className="score-row" key={key}>
            <span className="score-label">{label}</span>
            <div className="score-bar-bg">
              <div className="score-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="score-val">{value <= 1 ? (value * 10).toFixed(0) : value}</span>
          </div>
        );
      })}
    </div>
  );
}
