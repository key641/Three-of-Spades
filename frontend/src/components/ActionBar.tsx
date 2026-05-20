import { RefreshCcw, Sparkles, TimerReset, Wallet } from "lucide-react";

interface ActionBarProps {
  routeId?: string;
  onAction?: (action: string, routeId: string) => void;
}

const ACTIONS = [
  { key: "swap",    icon: <RefreshCcw size={14} />, label: "换一家",   msg: "帮我替换一个地点" },
  { key: "budget",  icon: <Wallet size={14} />,     label: "更省钱",   msg: "重新规划，降低预算" },
  { key: "queue",   icon: <TimerReset size={14} />, label: "少排队",   msg: "重新规划，避开排队" },
  { key: "family",  icon: <Sparkles size={14} />,   label: "亲子友好", msg: "加入亲子友好筛选条件" },
];

export function ActionBar({ routeId = "", onAction }: ActionBarProps) {
  return (
    <div className="action-bar">
      {ACTIONS.map(({ key, icon, label }) => (
        <button
          key={key}
          type="button"
          title={label}
          onClick={() => onAction?.(key, routeId)}
        >
          {icon}
          {label}
        </button>
      ))}
    </div>
  );
}
