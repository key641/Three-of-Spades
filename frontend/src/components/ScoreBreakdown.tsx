import type { RouteScoreBreakdown } from "../api/types";

interface ScoreBreakdownProps {
  breakdown: RouteScoreBreakdown;
}

const LABELS: Array<{ key: keyof RouteScoreBreakdown; label: string }> = [
  { key: "quality", label: "品质" },
  { key: "queue", label: "排队少" },
  { key: "budget", label: "预算" },
  { key: "distance", label: "距离" },
  { key: "preference", label: "偏好" },
];

function normalizeToPercent(value: number) {
  if (value <= 1) return value * 100;
  if (value <= 10) return value * 10;
  return Math.max(0, Math.min(100, value));
}

function normalizeToTenScale(value: number) {
  if (value <= 1) return value * 10;
  if (value <= 10) return value;
  return value / 10;
}

export function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  return (
    <div className="score-breakdown">
      {LABELS.map(({ key, label }) => {
        const value = breakdown[key] ?? 0;
        const pct = normalizeToPercent(value);
        const tenScale = normalizeToTenScale(value);
        return (
          <div className="score-row" key={key}>
            <span className="score-label">{label}</span>
            <div className="score-bar-bg">
              <div className="score-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="score-val">{tenScale.toFixed(1)}</span>
          </div>
        );
      })}
    </div>
  );
}
