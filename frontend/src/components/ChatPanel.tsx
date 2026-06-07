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
  /** 插入到最后一条 assistant 消息之后（如路线方案卡片），仅在非 loading 状态显示 */
  afterLastAssistant?: React.ReactNode;
}

const CLARIFY_CHIPS: Record<string, string[]> = {
  default: ["1人", "2人", "3人及以上", "不确定"],
  people: ["1人", "2人", "3人", "4人以上"],
  budget: ["100以内", "100~200", "200~400", "400以上"],
  time: ["上午", "下午", "晚上", "全天"],
};

function guessClarifyChips(question: string): string[] {
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
  onClarify,
  afterFirstUserMessage,
  beforeLoadingBubble,
  afterLastAssistant,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const agentTraceRef = useRef<HTMLDivElement>(null);
  const lastResponseRef = useRef<HTMLDivElement>(null);
  const prevLoadingRef = useRef(false);

  useEffect(() => {
    const justStarted = loading && !prevLoadingRef.current;
    const justFinished = !loading && prevLoadingRef.current;
    prevLoadingRef.current = loading;

    if (justStarted) {
      agentTraceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (justFinished) {
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
          AI 帮你规划合适路线
        </p>
      </div>
    );
  }

  const firstUserIdx = messages.findIndex((m) => m.role === "user");
  const lastAssistantIdx = messages.reduce<number>(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1,
  );
  const lastAiMsgIdx = messages.reduce<number>(
    (acc, m, i) => (m.role !== "user" ? i : acc),
    -1,
  );

  return (
    <div className="message-list">
      {messages.map((msg, idx) => (
        <React.Fragment key={msg.timestamp}>
          {idx === lastAiMsgIdx && <div ref={lastResponseRef} style={{ height: 0 }} />}

          <div className={`message-block message-block-${msg.role}`}>
            {msg.role === "assistant" && msg.agentTrace && msg.agentTrace.length > 0 && (
              <div className="message-trace">
                <AgentTrace steps={msg.agentTrace} />
              </div>
            )}
            <div className={`bubble bubble-${msg.role}`}>
              {msg.content}
            </div>
          </div>

          {afterFirstUserMessage && idx === firstUserIdx && <>{afterFirstUserMessage}</>}

          {afterLastAssistant && !loading && idx === lastAssistantIdx && (
            <div style={{ marginTop: 8 }}>{afterLastAssistant}</div>
          )}
        </React.Fragment>
      ))}

      {beforeLoadingBubble && loading && (
        <div ref={agentTraceRef}>{beforeLoadingBubble}</div>
      )}
      {loading && (
        <div className="bubble bubble-assistant typing-dots">
          <span /><span /><span />
        </div>
      )}

      {clarifyingQuestion && !loading && (
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

      {error && (
        <div className="error-toast"><AlertTriangle size={13} style={{ flexShrink: 0 }} /> {error}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
