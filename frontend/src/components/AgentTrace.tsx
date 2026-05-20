import { CheckCircle, Loader } from "lucide-react";
import { useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { STEP_ICONS } from "../utils/traceIcons";

interface AgentTraceProps {
  steps: AgentTraceStep[];
  loading?: boolean;
}

export function AgentTrace({ steps, loading = false }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);

  // 没有数据且不在加载时，不渲染
  if (!loading && steps.length === 0) return null;

  return (
    <div className="trace-panel" style={{ marginTop: "12px" }}>
      {/* 折叠切换按钮 */}
      <button
        className="trace-toggle"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        {loading ? (
          <>
            <Loader size={14} style={{ animation: "spin 1s linear infinite" }} />
            <span>Agent 正在处理…</span>
          </>
        ) : (
          <>
            <CheckCircle size={14} style={{ color: "var(--color-success)" }} />
            <span>已完成 {steps.length} 步</span>
            <span style={{ marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
          </>
        )}
      </button>

      {/* 步骤列表 */}
      {(expanded || loading) && (
        <div className="trace-list">
          {steps.map((step, i) => (
            <div
              className="trace-item"
              key={step.step}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <span className="trace-icon">
                {STEP_ICONS[step.step] ?? "⚙️"}
              </span>
              <span className="trace-label">{step.label}</span>
              <span className={`trace-status status-${step.status}`}>
                {step.status}
              </span>
            </div>
          ))}

          {/* loading 时末尾显示一个占位行 */}
          {loading && (
            <div className="trace-item" style={{ animationDelay: `${steps.length * 60}ms` }}>
              <span className="trace-icon">⏳</span>
              <span className="trace-label" style={{ color: "var(--color-muted)" }}>处理中…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
