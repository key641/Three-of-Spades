import { ChevronDown, Footprints, TimerReset, Wallet, MessageSquare, Sparkles } from "lucide-react";
import { useState } from "react";

interface RouteOptimizeBarProps {
  routeId?: string;
  onAction?: (action: string, routeId: string) => void;
}

const OPTIMIZE_ACTIONS = [
  { key: "budget", icon: <Wallet size={13} />,      label: "压缩预算",          desc: "降低人均消费，换更实惠的地点" },
  { key: "queue",  icon: <TimerReset size={13} />,  label: "避开高排队",         desc: "替换当前排队多的地点" },
  { key: "walk",   icon: <Footprints size={13} />,  label: "更轻松步行更少",     desc: "减少步行距离，换交通更便利的地点" },
  { key: "talk",   icon: <MessageSquare size={13}/>, label: "跟 AI 说",          desc: "自定义描述你的诉求" },
];

export function RouteOptimizeBar({ routeId = "", onAction }: RouteOptimizeBarProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="optimize-bar">
      {/* 折叠触发按钮 */}
      <button
        type="button"
        className="optimize-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="optimize-toggle-label">
          <Sparkles size={13} />
          <span>优化这条路线</span>
        </span>
        <ChevronDown
          size={13}
          className="optimize-chevron"
          style={{ transform: expanded ? "rotate(180deg)" : "none" }}
        />
      </button>

      {/* 展开后的操作列表 */}
      {expanded && (
        <div className="optimize-actions">
          {OPTIMIZE_ACTIONS.map(({ key, icon, label, desc }) => (
            <button
              key={key}
              type="button"
              className="optimize-action-item"
              onClick={() => { onAction?.(key, routeId); setExpanded(false); }}
            >
              <span className="optimize-action-icon">{icon}</span>
              <span className="optimize-action-text">
                <span className="optimize-action-label">{label}</span>
                <span className="optimize-action-desc">{desc}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// 保留旧名兼容（如有其他引用）
export const ActionBar = RouteOptimizeBar;
