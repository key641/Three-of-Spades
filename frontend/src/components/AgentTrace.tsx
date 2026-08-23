import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Loader, Check } from "lucide-react";
import type { AgentTraceStep } from "../api/types";
import { buildNarrativeSentences, buildThinkingSummary, getLiveProgressLabel } from "../utils/agentThinking";

interface AgentTraceProps {
  steps: AgentTraceStep[];
  loading?: boolean;
  /** 用户原始输入，用于叙述开头"用户说「…」" */
  userInput?: string;
}

export function AgentTrace({ steps, loading = false, userInput }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const hasIssue = issueCount > 0;
  const liveProgressLabel = getLiveProgressLabel(steps);
  const sentences = buildNarrativeSentences(steps, userInput);

  // 完成态 = loading 已结束
  const showFinished = !loading;
  const thinking = buildThinkingSummary(steps, !showFinished);

  // loading 中自动展开；loading 结束后保持当前展开状态，不自动折叠（避免位置跳动）
  useEffect(() => {
    if (loading) {
      setExpanded(true);
    }
  }, [loading]);

  // loading 中自动滚动到底部
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (loading && expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [sentences, loading, expanded]);

  // 没有数据且不在加载时，不渲染
  if (!loading && steps.length === 0) return null;

  // 状态文案
  const statusText = showFinished
    ? (hasIssue ? "思考完成（遇到问题）" : "思考完毕")
    : thinking.headline;

  return (
    <div className="trace-panel">
      {/* 状态标签栏 */}
      <button
        className="trace-toggle"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        <span className="trace-toggle-status">
          {showFinished ? (
            <Check size={13} className="trace-toggle-icon--done" />
          ) : (
            <Loader size={13} className="trace-toggle-icon--loading" />
          )}
          <span>{statusText}</span>
        </span>
        {expanded ? <ChevronUp size={14} style={{ opacity: 0.5 }} /> : <ChevronDown size={14} style={{ opacity: 0.5 }} />}
      </button>

      {/* 展开后：思考步骤逐行直接渲染 */}
      {expanded && (
        <div className="trace-narrative-panel">
          <div className="trace-narrative-body" ref={scrollRef}>
            {sentences.length > 0 ? (
              sentences.map((seg, i) => (
                <div key={i} className="trace-step-row">
                  <span className="trace-step-dot" />
                  <span className="trace-step-text">{renderSegment(seg)}</span>
                </div>
              ))
            ) : (
              <div className="trace-step-row">
                <span className="trace-step-spinner" />
                <span className="trace-step-text">{liveProgressLabel}</span>
              </div>
            )}
            {/* loading 中在末尾显示当前进度 */}
            {loading && sentences.length > 0 && (
              <div className="trace-step-row trace-step-row--active">
                <span className="trace-step-spinner" />
                <span className="trace-step-text">{liveProgressLabel}</span>
              </div>
            )}
          </div>
          <div className="trace-narrative-divider" />
        </div>
      )}
    </div>
  );
}

function renderSegment(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  if (parts.length === 1) return text;
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        return part;
      })}
    </>
  );
}
