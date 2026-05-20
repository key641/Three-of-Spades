import { Zap } from "lucide-react";
import { useState } from "react";
import type { Route } from "../api/types";

interface ReplanPanelProps {
  routes: Route[];
  onReplan?: (event: string) => void;
}

const EVENTS = [
  { key: "queue90",  emoji: "🍽️", label: "餐厅排队 90 分钟" },
  { key: "traffic",  emoji: "🚗", label: "交通堵车了" },
  { key: "tired",    emoji: "😴", label: "我们有点累了" },
];

export function ReplanPanel({ routes, onReplan }: ReplanPanelProps) {
  const [open, setOpen] = useState(false);
  const hasRoutes = routes.length > 0;

  return (
    <>
      {/* 触发按钮 */}
      <button
        className="fab-replan"
        type="button"
        disabled={!hasRoutes}
        onClick={() => setOpen(true)}
        title="模拟突发事件，触发重规划"
      >
        <Zap size={15} />
        模拟突发事件 · 触发重规划
      </button>

      {/* 桌面端备用：简单内联按钮组（通过 CSS 控制） */}
      <div className="replan-desktop-panel" style={{ display: "none" }}>
        <h2>动态事件模拟</h2>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {EVENTS.map(({ key, emoji, label }) => (
            <button
              key={key}
              type="button"
              disabled={!hasRoutes}
              onClick={() => onReplan?.(key)}
            >
              {emoji} {label}
            </button>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 10, fontSize: "12px" }}>
          点击后将调用 /api/routes/replan，展示重规划前后变化。
        </p>
      </div>

      {/* 底部抽屉（手机端） */}
      {open && (
        <div
          className="drawer-overlay"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-handle" />
            <h3 style={{ margin: "0 0 4px" }}>模拟突发情况</h3>
            <p className="muted" style={{ fontSize: "12px", marginBottom: 16 }}>
              选择一个事件，Agent 将为你重新规划路线
            </p>
            <div className="drawer-event-btns">
              {EVENTS.map(({ key, emoji, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    onReplan?.(key);
                    setOpen(false);
                  }}
                >
                  <span style={{ marginRight: 8 }}>{emoji}</span>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
