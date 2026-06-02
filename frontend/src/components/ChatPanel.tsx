import { useEffect, useRef } from "react";
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
}

// 常见追问的快捷回答
const CLARIFY_CHIPS: Record<string, string[]> = {
  default: ["我再补充一下", "先按默认来"],
  replanMode: ["重新生成路线", "只替换这个地点", "先不改了"],
  city: ["上海", "北京", "杭州", "成都"],
  tripGoal: ["景点游玩", "美食路线", "轻松 citywalk", "亲子友好"],
  people:  ["1人", "2人", "3人", "4人以上"],
  budget:  ["100以内", "100~200", "200~400", "400以上"],
  time:    ["上午", "下午", "晚上", "全天"],
};

function guessClarifyChips(question: string): string[] {
  if (/重新生成|重新规划|当前路线|某个地点|地点换掉|换掉|替换/.test(question)) {
    return CLARIFY_CHIPS.replanMode;
  }
  if (/城市|区域|哪里|去哪/.test(question)) return CLARIFY_CHIPS.city;
  if (/主要想玩|景点|美食|citywalk|目标/.test(question)) return CLARIFY_CHIPS.tripGoal;
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
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, clarifyingQuestion]);

  if (messages.length === 0 && !loading && !error) {
    return (
      <div style={{ textAlign: "center", padding: "32px 0", color: "var(--color-muted)" }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🗺️</div>
        <p style={{ margin: 0, fontSize: "var(--font-body)" }}>
          告诉我你想去哪儿、几个人、大概预算
          <br />
          AI 帮你规划最佳路线
        </p>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <div key={msg.timestamp} className={`message-block message-block-${msg.role}`}>
          <div className={`bubble bubble-${msg.role}`}>
            {msg.content}
          </div>
          {msg.role === "assistant" && msg.agentTrace && msg.agentTrace.length > 0 && (
            <div className="message-trace">
              <AgentTrace steps={msg.agentTrace} />
            </div>
          )}
        </div>
      ))}

      {/* loading 时显示打字动效 */}
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
            🤔 {clarifyingQuestion}
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
        <div className="error-toast">⚠️ {error}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
