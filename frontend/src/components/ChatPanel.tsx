import React, { useEffect, useRef } from "react";
import { MapPin, AlertTriangle } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  /** 后端返回 need_clarification=true 时，显示追问文字 */
  clarifyingQuestion?: string | null;
  /** 用户点击快捷答案或输入后触发 */
  onClarify?: (answer: string) => void;
  /** 插入到第一条 user 消息气泡之后（追问卡片） */
  afterFirstUserMessage?: React.ReactNode;
  /** 插入到消息列表末尾、loading 打字动效之前（如 AgentTrace） */
  beforeLoadingBubble?: React.ReactNode;
}

// 常见追问的快捷回答
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
          <span /><span /><span />
        </div>
      )}

      {/* P2: need_clarification 追问卡片 */}
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

      {/* 错误提示 */}
      {error && (
        <div className="error-toast"><AlertTriangle size={13} style={{ flexShrink: 0 }} /> {error}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
