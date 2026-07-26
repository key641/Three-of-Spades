import React, { useEffect, useRef, useState } from "react";
import { MapPin, AlertTriangle } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import type { ClarificationGroup } from "../api/types";
import { AgentTrace } from "./AgentTrace";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  clarifyingQuestion?: string | null;
  /** 后端返回的结构化追问选项组 */
  clarificationGroups?: ClarificationGroup[];
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


/** 逐题追问卡片：每次显示一个问题，支持点击选项 + 自由输入，最后拼接成 prompt */
function ClarifyStepCard({
  groups,
  fallbackQuestion,
  onComplete,
}: {
  groups: ClarificationGroup[];
  fallbackQuestion?: string | null;
  onComplete: (answer: string) => void;
}) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [inputText, setInputText] = useState("");

  // 没有结构化 groups 时，退回到旧版 chip 模式
  if (groups.length === 0 && fallbackQuestion) {
    return (
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
          {fallbackQuestion}
        </p>
        <div className="chips" style={{ padding: 0 }}>
          {guessClarifyChips(fallbackQuestion).map((chip) => (
            <button
              key={chip}
              className="chip"
              type="button"
              onClick={() => onComplete(chip)}
              style={{ minHeight: 30 }}
            >
              {chip}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (groups.length === 0) return null;

  const currentGroup = groups[step];
  const isLast = step === groups.length - 1;
  const isRequired = currentGroup.required;
  const filled = inputText.trim().length > 0;

  function handleNext() {
    const answer = inputText.trim();
    if (!answer && isRequired) return; // 必填不能空
    const newAnswers = { ...answers };
    if (answer) newAnswers[currentGroup.id] = answer;
    setAnswers(newAnswers);
    setInputText("");

    if (isLast) {
      // 拼接所有答案：按 group 顺序，用中文逗号分隔
      const parts: string[] = [];
      for (const g of groups) {
        const a = newAnswers[g.id];
        if (a) parts.push(a);
      }
      onComplete(parts.join("，"));
      return;
    }
    setStep(step + 1);
  }

  function handleSkip() {
    if (isLast) {
      const parts: string[] = [];
      for (const g of groups) {
        const a = answers[g.id];
        if (a) parts.push(a);
      }
      onComplete(parts.join("，"));
      return;
    }
    setStep(step + 1);
  }

  function handleChipClick(label: string) {
    setInputText(label);
  }

  return (
    <div
      style={{
        alignSelf: "flex-start",
        background: "var(--color-card)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: "14px 16px",
        maxWidth: "88%",
      }}
    >
      {/* 进度 */}
      <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 10, color: "var(--color-muted)", background: "var(--color-bg)", padding: "2px 8px", borderRadius: 10 }}>
          {step + 1}/{groups.length}
        </span>
        {isRequired ? (
          <span style={{ color: "#f87171", fontSize: 10, fontWeight: 600 }}>必填</span>
        ) : (
          <span style={{ color: "#94a3b8", fontSize: 10 }}>可选</span>
        )}
      </div>

      {/* 问题标题 */}
      <p style={{
        margin: "0 0 10px",
        fontSize: "var(--font-body)",
        color: "var(--color-text)",
        fontWeight: 600,
      }}>
        {currentGroup.title}
      </p>

      {/* 快捷选项 */}
      {currentGroup.options.length > 0 && (
        <div className="chips" style={{ padding: 0, marginBottom: 10 }}>
          {currentGroup.options.map((option) => (
            <button
              key={option.id}
              className="chip"
              type="button"
              onClick={() => handleChipClick(option.label)}
              style={{
                minHeight: 30,
                ...(inputText === option.label ? { background: "var(--color-accent)", color: "#fff", borderColor: "var(--color-accent)" } : {}),
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}

      {/* 自由输入框 */}
      <input
        type="text"
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") handleNext(); }}
        placeholder="或直接输入..."
        style={{
          width: "100%",
          padding: "8px 10px",
          fontSize: "var(--font-body)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          background: "var(--color-bg)",
          color: "var(--color-text)",
          outline: "none",
          boxSizing: "border-box",
        }}
        autoFocus
      />

      {/* 按钮 */}
      <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "flex-end" }}>
        {!isRequired && (
          <button
            type="button"
            onClick={handleSkip}
            style={{
              padding: "6px 14px",
              fontSize: 12,
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              color: "var(--color-muted)",
              cursor: "pointer",
            }}
          >
            跳过
          </button>
        )}
        <button
          type="button"
          onClick={handleNext}
          disabled={isRequired && !filled}
          style={{
            padding: "6px 18px",
            fontSize: 12,
            fontWeight: 600,
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: isRequired && !filled ? "var(--color-border)" : "var(--color-accent)",
            color: isRequired && !filled ? "var(--color-muted)" : "#fff",
            cursor: isRequired && !filled ? "not-allowed" : "pointer",
          }}
        >
          {isLast ? "开始规划" : "下一步"}
        </button>
      </div>
    </div>
  );
}

export function ChatPanel({
  messages,
  loading,
  error,
  clarifyingQuestion,
  clarificationGroups,
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

      {(clarifyingQuestion || (clarificationGroups && clarificationGroups.length > 0)) && !loading && (
        <ClarifyStepCard
          groups={clarificationGroups ?? []}
          fallbackQuestion={clarifyingQuestion}
          onComplete={(combinedAnswer) => onClarify?.(combinedAnswer)}
        />
      )}

      {error && (
        <div className="error-toast"><AlertTriangle size={13} style={{ flexShrink: 0 }} /> {error}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
