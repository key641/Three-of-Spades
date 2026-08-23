import { Footprints, TimerReset, Wallet, Coffee } from "lucide-react";

interface RouteOptimizeBarProps {
  routeId?: string;
  onAction?: (action: string, routeId: string) => void;
}

const OPTIMIZE_ACTIONS = [
  { key: "budget", icon: <Wallet size={13} />,      label: "压缩预算",      desc: "降低人均消费，换更实惠的地点" },
  { key: "queue",  icon: <TimerReset size={13} />,  label: "避开高排队",     desc: "替换当前排队多的地点" },
  { key: "walk",   icon: <Footprints size={13} />,  label: "步行更少",       desc: "减少步行距离，换交通更便利的地点" },
  { key: "relax",  icon: <Coffee size={13} />,        label: "行程更轻松",   desc: "减少地点，留出更多休息时间" },
];

export function RouteOptimizeBar({ routeId = "", onAction }: RouteOptimizeBarProps) {
  return (
    <div className="optimize-bar">
      <div className="optimize-actions">
        {OPTIMIZE_ACTIONS.map(({ key, icon, label, desc }) => (
          <button
            key={key}
            type="button"
            className="optimize-action-item"
            onClick={() => onAction?.(key, routeId)}
          >
            <span className="optimize-action-icon">{icon}</span>
            <span className="optimize-action-text">
              <span className="optimize-action-label">{label}</span>
              <span className="optimize-action-desc">{desc}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// 保留旧名兼容（如有其他引用）
export const ActionBar = RouteOptimizeBar;
