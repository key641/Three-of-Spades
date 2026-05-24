import { AlertTriangle, BrainCircuit, CheckCircle, Loader } from "lucide-react";
import { useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { buildThinkingSummary } from "../utils/agentThinking";
import { STEP_ICONS } from "../utils/traceIcons";

interface AgentTraceProps {
  steps: AgentTraceStep[];
  loading?: boolean;
}

export function AgentTrace({ steps, loading = false }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const hasIssue = issueCount > 0;
  const thinking = buildThinkingSummary(steps, loading);

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
            <span>{thinking.headline}</span>
            <span className="trace-summary-status">实时更新中</span>
          </>
        ) : (
          <>
            {hasIssue ? (
              <AlertTriangle size={14} style={{ color: "#92400E" }} />
            ) : (
              <CheckCircle size={14} style={{ color: "var(--color-success)" }} />
            )}
            <span>{thinking.headline}</span>
            <span className={hasIssue ? "trace-summary-status is-warning" : "trace-summary-status"}>
              {thinking.statusText}
            </span>
            <span style={{ marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
          </>
        )}
      </button>

      <div className="trace-thinking">
        <div className="trace-thinking-title">
          <BrainCircuit size={15} />
          <span>{loading ? "正在组织路线思路" : thinking.statusText}</span>
        </div>
        <div className="trace-thinking-list">
          {thinking.items.map((item) => (
            <span className="trace-thinking-item" key={item}>
              {item}
            </span>
          ))}
        </div>
      </div>

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
