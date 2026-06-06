import React, { useEffect, useRef } from "react";
import { MapPin, AlertTriangle } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  clarifyingQuestion?: string | null;
  /** 用户点击快捷答案或输入后触发 */
  onClarify?: (answer: string) => void;
  /** 插入到第一条 user 消息气泡之后（追问卡片） */
  afterFirstUserMessage?: React.ReactNode;
  /** 插入到消息列表末尾、loading 打字动效之前（如 AgentTrace） */
  beforeLoadingBubble?: React.ReactNode;
}

const CLARIFY_CHIPS: Record<string, string[]> = {
  default: ["1人", "2人", "3人及以上", "不确定"],
  people:  ["1人", "2人", "3人", "4人以上"],
  budget:  ["100以内", "100~200", "200~400", "400以上"],
  time:    ["上午", "下午", "晚上", "全天"],
};

function guessClarifyChips(question: string): string[] {
  if (/几个人|人数|几人/.test(question))  return CLARIFY_CHIPS.people;
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
  afterFirstUserMessage,
  beforeLoadingBubble,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const agentTraceRef = useRef<HTMLDivElement>(null);
  // 记录上一次 loading 状态，用于检测 false→true 的跳变
  const prevLoadingRef = useRef(false);

  useEffect(() => {
    const justStarted = loading && !prevLoadingRef.current;
    prevLoadingRef.current = loading;

    if (justStarted && agentTraceRef.current) {
      // 追问选完、AI 开始响应：将 AgentTrace 滚到视口顶部
      agentTraceRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (!loading && agentTraceRef.current) {
      // loading 结束后，等路线卡片等内容渲染完再滚到 AgentTrace 顶部
      // 用两帧延迟确保 DOM 已更新
      const el = agentTraceRef.current;
      // 100ms 延迟，确保路线卡片等下方内容渲染完毕后再滚动
      setTimeout(() => {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } else if (!loading) {
      // 无 AgentTrace 时才滚到底部
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
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
        <MapPin size={32} strokeWidth={1.5} style={{ marginBottom: 12, color: "var(--color-accent)" }} />
        <p style={{ margin: 0, fontSize: "var(--font-body)" }}>
          告诉我你想去哪儿、几个人、大概预算
          <br />
          AI 帮你规划合适路线
        </p>
      </div>
    );
  }

  // 找到第一条 user 消息的索引，追问卡片插入其后
  const firstUserIdx = messages.findIndex((m) => m.role === "user");
  // 找到最后一条 assistant 消息的索引，beforeLoadingBubble 插入其前
  const lastAssistantIdx = messages.reduce<number>(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1,
  );

  return (
    <div className="message-list">
      {messages.map((msg, idx) => (
        <React.Fragment key={msg.timestamp}>
          <div className={`message-block message-block-${msg.role}`}>
            <div className={`bubble bubble-${msg.role}`}>
              {msg.content}
            </div>
            {msg.role === "assistant" && msg.agentTrace && msg.agentTrace.length > 0 && (
              <div className="message-trace">
                <AgentTrace steps={msg.agentTrace} />
              </div>
            )}
          </div>
          {/* 第一条 user 消息后插入追问内容 */}
          {afterFirstUserMessage && idx === firstUserIdx && (
            <>{afterFirstUserMessage}</>
          )}
        </React.Fragment>
      ))}

      {/* loading 时显示打字动效（无 assistant 消息时，AgentTrace 也在此之前） */}
      {beforeLoadingBubble && lastAssistantIdx === -1 && (
        <div ref={agentTraceRef}>{beforeLoadingBubble}</div>
      )}
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

      {/* 错误提示 */}
      {error && (
        <div className="error-toast"><AlertTriangle size={13} style={{ flexShrink: 0 }} /> {error}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
