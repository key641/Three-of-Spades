import { useEffect, useMemo, useRef, useState } from "react";
import type { ClarificationGroup } from "../api/types";
import type { ChatMessage } from "../hooks/useChat";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  clarifyingQuestion?: string | null;
  clarificationGroups?: ClarificationGroup[];
  inferredContext?: Record<string, unknown>;
  onClarify?: (answer: string, options?: Record<string, unknown>) => void;
}

const CLARIFY_CHIPS: Record<string, string[]> = {
  default: ["我再补充一个", "先按默认来"],
  replanMode: ["重新生成路线", "只替换这个地点", "先不改了"],
  city: ["上海", "北京", "杭州", "成都"],
  tripGoal: ["景点游玩", "美食路线", "轻松 citywalk", "亲子友好"],
  people: ["1人", "2人", "3人", "4人以上"],
  budget: ["100以内", "100~200", "200~400", "400以上"],
  time: ["09:00 出发", "12:00 出发", "14:00 出发", "18:00 出发"],
};

function guessClarifyChips(question: string): string[] {
  if (/重新生成|重新规划|当前路线|某个地点|地点换掉|换掉|替换/.test(question)) {
    return CLARIFY_CHIPS.replanMode;
  }
  if (/城市|区域|哪里|去哪/.test(question)) return CLARIFY_CHIPS.city;
  if (/主要想|景点|美食|citywalk|目标/.test(question)) return CLARIFY_CHIPS.tripGoal;
  if (/几个人|人数|几人/.test(question)) return CLARIFY_CHIPS.people;
  if (/预算|多少钱|花多少/.test(question)) return CLARIFY_CHIPS.budget;
  if (/时间|几点|什么时候/.test(question)) return CLARIFY_CHIPS.time;
  return CLARIFY_CHIPS.default;
}

export function ChatPanel({
  messages,
  loading,
  error,
  clarifyingQuestion,
  clarificationGroups = [],
  inferredContext,
  onClarify,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, clarifyingQuestion]);

  useEffect(() => {
    setAnswers({});
  }, [clarifyingQuestion, clarificationGroups]);

  const requiredGroups = useMemo(
    () => clarificationGroups.filter((group) => group.required),
    [clarificationGroups],
  );
  const hasStructuredClarification = clarificationGroups.length > 0;
  const canSubmitClarification = requiredGroups.every((group) => answers[group.id]);

  function mergeClarificationValues(skipOptional: boolean): Record<string, unknown> {
    const merged: Record<string, unknown> = {};
    for (const group of clarificationGroups) {
      if (skipOptional && !group.required) continue;
      const optionId = answers[group.id];
      const option = group.options.find((item) => item.id === optionId);
      if (!option?.value) continue;
      for (const [key, value] of Object.entries(option.value)) {
        if (Array.isArray(value) && Array.isArray(merged[key])) {
          merged[key] = [...(merged[key] as unknown[]), ...value];
        } else {
          merged[key] = value;
        }
      }
    }
    return merged;
  }

  function selectedLabels(skipOptional: boolean): string {
    const labels: string[] = [];
    for (const group of clarificationGroups) {
      if (skipOptional && !group.required) continue;
      const optionId = answers[group.id];
      const option = group.options.find((item) => item.id === optionId);
      if (option) labels.push(option.label);
    }
    return labels.join("；") || "按默认偏好直接安排";
  }

  function submitStructuredClarification(skipOptional = false) {
    if (!canSubmitClarification) return;
    onClarify?.(selectedLabels(skipOptional), {
      event_type: "clarification_answer",
      event_payload: { clarification_answers: answers },
      ...mergeClarificationValues(skipOptional),
    });
  }

  if (messages.length === 0 && !loading && !error) {
    return (
      <div style={{ textAlign: "center", padding: "32px 0", color: "var(--color-muted)" }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🗺️</div>
        <p style={{ margin: 0, fontSize: "var(--font-body)" }}>
          告诉我你想去哪儿、几个人、大概预算
          <br />
          AI 帮你规划合适路线
        </p>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div key={msg.timestamp} className={`message-block message-block-${msg.role}`}>
          <div className={`bubble bubble-${msg.role}`}>{msg.content}</div>
          {msg.role === "assistant" && msg.agentTrace && msg.agentTrace.length > 0 && (
            <div className="message-trace">
              <AgentTrace steps={msg.agentTrace} />
            </div>
          )}
        </div>
      ))}

      {loading && (
        <div className="bubble bubble-assistant typing-dots">
          <span />
          <span />
          <span />
        </div>
      )}

      {clarifyingQuestion && !loading && hasStructuredClarification && (
        <div
          style={{
            alignSelf: "flex-start",
            background: "linear-gradient(180deg, rgba(240, 255, 248, 0.96), rgba(248, 255, 252, 0.96))",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            maxWidth: "92%",
            display: "grid",
            gap: 12,
          }}
        >
          <p style={{ margin: 0, fontSize: "var(--font-body)", color: "var(--color-text)", fontWeight: 700 }}>
            {clarifyingQuestion}
          </p>

          {inferredContext && Object.keys(inferredContext).length > 0 && (
            <div style={{ fontSize: 12, color: "var(--color-muted)" }}>
              已理解：
              {Object.entries(inferredContext).map(([key, value]) => (
                <span key={key} style={{ marginLeft: 8 }}>
                  {String(value)}
                </span>
              ))}
            </div>
          )}

          {clarificationGroups.map((group) => (
            <div
              key={group.id}
              style={{
                background: "rgba(255, 255, 255, 0.72)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "12px",
              }}
            >
              <div style={{ marginBottom: 10, fontWeight: 700, fontSize: "var(--font-body)" }}>
                {group.title}
                {group.required && <span style={{ color: "var(--color-accent)", marginLeft: 6 }}>*</span>}
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--space-sm)",
                  padding: 0,
                }}
              >
                {group.options.map((option) => {
                  const selected = answers[group.id] === option.id;
                  return (
                    <button
                      key={option.id}
                      className="chip"
                      type="button"
                      onClick={() => setAnswers((prev) => ({ ...prev, [group.id]: option.id }))}
                      style={{
                        minHeight: 32,
                        borderColor: selected ? "var(--color-accent)" : undefined,
                        background: selected ? "rgba(20, 184, 116, 0.12)" : undefined,
                        color: selected ? "var(--color-accent)" : undefined,
                        fontWeight: selected ? 700 : undefined,
                      }}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="chip"
              type="button"
              disabled={!canSubmitClarification}
              onClick={() => submitStructuredClarification(false)}
              style={{ minHeight: 34, opacity: canSubmitClarification ? 1 : 0.45 }}
            >
              开始规划
            </button>
            <button
              className="chip"
              type="button"
              disabled={!canSubmitClarification}
              onClick={() => submitStructuredClarification(true)}
              style={{ minHeight: 34, opacity: canSubmitClarification ? 1 : 0.45 }}
            >
              跳过可选，直接安排
            </button>
          </div>
        </div>
      )}

      {clarifyingQuestion && !loading && !hasStructuredClarification && (
        <div
          style={{
            alignSelf: "flex-start",
            background: "var(--color-card)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            padding: "12px 14px",
            maxWidth: "88%",
          }}
        >
          <p style={{ margin: "0 0 10px", fontSize: "var(--font-body)", color: "var(--color-text)" }}>
            {clarifyingQuestion}
          </p>
          <div className="chips" style={{ padding: 0 }}>
            {guessClarifyChips(clarifyingQuestion).map((chip) => (
              <button
                key={chip}
                className="chip"
                type="button"
                onClick={() => onClarify?.(chip)}
                style={{ minHeight: 30 }}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <div className="error-toast">⚠️ {error}</div>}

      <div ref={bottomRef} />
    </div>
  );
}
