import React, { useEffect, useMemo, useRef, useState } from "react";
import { MapPin, AlertTriangle, Send, CheckCircle } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import type { ClarificationGroup } from "../api/types";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  /** 旧版纯文本追问文案（无 group 时显示 chips；有 group 时作为 group 面板的标题） */
  clarifyingQuestion?: string | null;
  /** 结构化追问分组（后端返回 clarification_groups 时使用） */
  clarificationGroups?: ClarificationGroup[];
  /** 后端推断的已知上下文，展示在 group 面板顶部 */
  inferredContext?: Record<string, unknown>;
  /** 用户提交追问回答时触发 */
  onClarify?: (answer: string, extra?: Record<string, unknown>) => void;
  /** 插入到第一条 user 消息气泡之后（追问卡片） */
  afterFirstUserMessage?: React.ReactNode;
  /** 插入到消息列表末尾、loading 打字动效之前（如 AgentTrace） */
  beforeLoadingBubble?: React.ReactNode;
  /** 插入到最后一条 assistant 消息之后（如路线方案卡片），仅在非 loading 状态显示 */
  afterLastAssistant?: React.ReactNode;
}

// ── 追问卡片（活跃 / 只读两态） ────────────────────────────────
function ClarifyCard({
  question,
  answer,
  onSubmit,
}: {
  question: string;
  /** 已填写的回答；有值则只读展示 */
  answer?: string;
  onSubmit?: (val: string) => void;
}) {
  const [inputVal, setInputVal] = useState("");
  const readonly = !!answer;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const val = inputVal.trim();
    if (!val || !onSubmit) return;
    onSubmit(val);
    setInputVal("");
  }

  return (
    <div
      style={{
        background: "var(--color-card)",
        border: `1.5px solid ${readonly ? "rgba(74,222,128,0.35)" : "#4ade80"}`,
        borderRadius: "var(--radius-md)",
        padding: "14px 16px",
        maxWidth: "min(92%, 520px)",
        width: "100%",
        margin: "0 auto",
        boxSizing: "border-box",
        outline: readonly ? "none" : "3px solid rgba(74,222,128,0.10)",
        opacity: readonly ? 0.85 : 1,
        transition: "border 0.2s, opacity 0.2s",
      }}
    >
      {/* 问题文字 */}
      <p style={{
        margin: "0 0 10px",
        fontSize: "var(--font-body)",
        color: "var(--color-text)",
        lineHeight: 1.5,
      }}>
        {question}
      </p>

      {readonly ? (
        /* ── 只读态：展示用户的回答 ── */
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: "rgba(74,222,128,0.08)",
          borderRadius: "var(--radius-sm)",
          padding: "8px 12px",
        }}>
          <CheckCircle size={14} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
          <span style={{
            fontSize: "var(--font-body)",
            color: "var(--color-text)",
            fontWeight: 500,
          }}>
            {answer}
          </span>
        </div>
      ) : (
        /* ── 活跃态：输入框 + 发送按钮 ── */
        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", gap: 8, alignItems: "center" }}
        >
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="输入你的回答..."
            style={{
              flex: 1,
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              padding: "8px 12px",
              fontSize: "var(--font-body)",
              color: "var(--color-text)",
              outline: "none",
            }}
            autoFocus
          />
          <button
            type="submit"
            disabled={!inputVal.trim()}
            style={{
              background: inputVal.trim() ? "#4ade80" : "var(--color-border)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              padding: "8px 12px",
              cursor: inputVal.trim() ? "pointer" : "not-allowed",
              color: inputVal.trim() ? "#14532d" : "var(--color-muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.15s",
              flexShrink: 0,
            }}
          >
            <Send size={16} />
          </button>
        </form>
      )}
    </div>
  );
}

const EMPTY_CLARIFICATION_GROUPS: ClarificationGroup[] = [];

export function ChatPanel({
  messages,
  loading,
  error,
  clarifyingQuestion,
  clarificationGroups = EMPTY_CLARIFICATION_GROUPS,
  inferredContext,
  onClarify,
  afterFirstUserMessage,
  beforeLoadingBubble,
  afterLastAssistant,
}: ChatPanelProps) {
  const bottomRef       = useRef<HTMLDivElement>(null);
  const agentTraceRef   = useRef<HTMLDivElement>(null);
  // 最后一轮 AI 回答的起点标记（loading 结束后滚到这里）
  const lastResponseRef = useRef<HTMLDivElement>(null);
  const prevLoadingRef  = useRef(false);

  // structured group 面板的用户选择状态：groupId -> optionId
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    const justStarted  = loading && !prevLoadingRef.current;
    const justFinished = !loading && prevLoadingRef.current;
    prevLoadingRef.current = loading;

    if (justStarted) {
      // loading 刚开始：滚到实时 trace 顶部
      agentTraceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (justFinished) {
      // loading 刚结束：滚到本轮 AI 回答的起点（思考 + 说话 + 方案卡片顶部）
      setTimeout(() => {
        lastResponseRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    }
  }, [messages, loading]);

  // 每轮新追问时重置已选答案
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

  // 最后一条 assistant 消息的索引：方案卡片插入其后
  const lastAssistantIdx = messages.reduce<number>(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1,
  );

  // 最后一条非 user 消息（assistant / clarify / trace）：loading 结束后滚到此处顶部
  const lastAiMsgIdx = messages.reduce<number>(
    (acc, m, i) => (m.role !== "user" ? i : acc),
    -1,
  );

  // 最后一条 clarify 消息：若尚未回答，则是"活跃"的追问卡片
  const lastClarifyIdx = messages.reduce<number>(
    (acc, m, i) => (m.role === "clarify" ? i : acc),
    -1,
  );
  const activeClarifyIdx =
    lastClarifyIdx !== -1 && !messages[lastClarifyIdx].clarifyAnswer
      ? lastClarifyIdx
      : -1;

  return (
    <div className="message-list">
      {messages.map((msg, idx) => (
        <React.Fragment key={msg.timestamp}>
          {/* 最后一条 AI 消息的起点标记，loading 结束后滚到此处 */}
          {idx === lastAiMsgIdx && (
            <div ref={lastResponseRef} className="scroll-marker" style={{ height: 0 }} />
          )}

          {/* ── clarify 消息：持久追问卡片（LYNN 方案） ── */}
          {msg.role === "clarify" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {/* AgentTrace（如有）附在卡片上方 */}
              {msg.agentTrace && msg.agentTrace.length > 0 && (
                <div className="message-trace">
                  <AgentTrace steps={msg.agentTrace} />
                </div>
              )}
              <ClarifyCard
                question={msg.clarifyQuestion ?? ""}
                answer={msg.clarifyAnswer}
                onSubmit={
                  /* 只有活跃的最后一张卡片才可提交 */
                  idx === activeClarifyIdx && onClarify ? onClarify : undefined
                }
              />
            </div>
          ) : msg.role === "trace" ? (
            /* trace 记录：只渲染 AgentTrace，没有气泡 */
            msg.agentTrace && msg.agentTrace.length > 0 ? (
              <div className="message-trace" style={{ marginBottom: 8 }}>
                <AgentTrace steps={msg.agentTrace} />
              </div>
            ) : null
          ) : (
            /* user / assistant 气泡 */
            <div className={`message-block message-block-${msg.role}`}>
              {/* assistant 消息：先渲染 agent 思考步骤，再渲染气泡 */}
              {msg.role === "assistant" && msg.agentTrace && msg.agentTrace.length > 0 && (
                <div className="message-trace">
                  <AgentTrace steps={msg.agentTrace} />
                </div>
              )}
              <div className={`bubble bubble-${msg.role}`}>
                {msg.content}
              </div>
            </div>
          )}

          {/* 第一条 user 消息后插入追问内容（TripSetupPanel 路径） */}
          {afterFirstUserMessage && idx === firstUserIdx && (
            <>{afterFirstUserMessage}</>
          )}

          {/* 最后一条 assistant 消息后插入方案卡片（非 loading 状态） */}
          {afterLastAssistant && !loading && idx === lastAssistantIdx && (
            <div style={{ marginTop: 0 }}>{afterLastAssistant}</div>
          )}
        </React.Fragment>
      ))}

      {/* 实时 AgentTrace + typing-dots：loading 过程中始终显示，包裹在 message-block-assistant 中保持结构一致 */}
      {beforeLoadingBubble && loading && (
        <div className="message-block message-block-assistant" ref={agentTraceRef}>
          <div className="message-trace">{beforeLoadingBubble}</div>
          <div className="bubble bubble-assistant typing-dots">
            <span />
            <span />
            <span />
          </div>
        </div>
      )}

      {/* ── Structured group 追问面板（keyki 逻辑，有 clarificationGroups 时显示）── */}
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
              确认，帮我规划 →
            </button>
            <button
              className="chip"
              type="button"
              onClick={() => submitStructuredClarification(true)}
              style={{ minHeight: 34, opacity: 0.65 }}
            >
              跳过可选，直接安排
            </button>
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
