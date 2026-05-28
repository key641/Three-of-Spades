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

      {(loading || expanded) && (
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
      )}

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
              <span className="trace-content">
                <span className="trace-label">{step.label}</span>
                <TraceDetails details={step.details} />
              </span>
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

function TraceDetails({ details }: { details?: Record<string, unknown> }) {
  if (!details || Object.keys(details).length === 0) return null;

  const items = flattenDetails(details)
    .filter((item) => item.value !== "" && item.value !== "[]" && item.value !== "{}")
    .slice(0, 12);

  if (items.length === 0) return null;

  return (
    <div className="trace-detail-grid">
      {items.map((item) => (
        <span className="trace-detail-chip" key={`${item.key}:${item.value}`}>
          <span className="trace-detail-key">{labelDetailKey(item.key)}</span>
          <span className="trace-detail-value">{item.value}</span>
        </span>
      ))}
    </div>
  );
}

function flattenDetails(details: Record<string, unknown>, prefix = ""): Array<{ key: string; value: string }> {
  return Object.entries(details).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(value)) {
      return [{ key: nextKey, value: value.map(formatDetailValue).join("、") }];
    }
    if (isRecord(value)) {
      const simpleEntries = Object.entries(value).filter(([, child]) => !isRecord(child) && !Array.isArray(child));
      if (simpleEntries.length === Object.keys(value).length) {
        return [{ key: nextKey, value: simpleEntries.map(([childKey, child]) => `${labelDetailKey(childKey)}:${formatDetailValue(child)}`).join("、") }];
      }
      return flattenDetails(value, nextKey);
    }
    return [{ key: nextKey, value: formatDetailValue(value) }];
  });
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function labelDetailKey(key: string): string {
  const labels: Record<string, string> = {
    intent_type_label: "意图",
    turn_type_label: "本轮类型",
    inherit_previous: "继承上轮",
    preserve_scenario: "保留场景",
    references_previous_route: "引用路线",
    confidence: "置信度",
    source: "来源",
    kept: "保留",
    added: "新增",
    changed: "修改",
    removed: "移除",
    preferences: "偏好",
    avoid_tags: "避开",
    names: "候选点",
    count: "数量",
    route_titles: "路线",
    objectives: "目标",
    delta: "变更",
  };
  const parts = key.split(".");
  const lastKey = parts[parts.length - 1] ?? key;
  return labels[key] ?? labels[lastKey] ?? key;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
