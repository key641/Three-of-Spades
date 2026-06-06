import React, { useEffect, useRef, useState } from "react";
import { MapPin, AlertTriangle, Send, CheckCircle } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  /** 后端返回 need_clarification=true 时，最新一条 clarify 消息尚未回答，触发提交 */
  onClarify?: (answer: string) => void;
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

export function ChatPanel({
  messages,
  loading,
  error,
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

  if (messages.length === 0 && !loading && !error) {
    return (
      <div style={{ textAlign: "center", padding: "32px 0", color: "var(--color-muted)" }}>
        <MapPin size={32} strokeWidth={1.5} style={{ marginBottom: 12, color: "var(--color-accent)" }} />
        <p style={{ margin: 0, fontSize: "var(--font-body)" }}>
          告诉我你想去哪儿、几个人、大概预算
          <br />
          AI 帮你规划最佳路线
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
            <div ref={lastResponseRef} style={{ height: 0 }} />
          )}

          {/* ── clarify 消息：持久追问卡片 ── */}
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
            <div style={{ marginTop: 8 }}>{afterLastAssistant}</div>
          )}
        </React.Fragment>
      ))}

      {/* 实时 AgentTrace：loading 过程中始终显示 */}
      {beforeLoadingBubble && loading && (
        <div ref={agentTraceRef}>{beforeLoadingBubble}</div>
      )}
      {loading && (
        <div className="bubble bubble-assistant typing-dots">
          <span /><span /><span />
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
