import { AlertTriangle, BrainCircuit, CheckCircle, Loader } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AgentTraceStep } from "../api/types";
import { buildNarrativeText, buildThinkingSummary, getLiveProgressLabel } from "../utils/agentThinking";

interface AgentTraceProps {
  steps: AgentTraceStep[];
  loading?: boolean;
  /** 用户原始输入，用于叙述开头"用户说「…」" */
  userInput?: string;
}

/** 打字机 hook：target 变化时逐字符追加输出 */
function useTypewriter(target: string, speed = 32): { displayed: string; typing: boolean } {
  const [displayed, setDisplayed] = useState("");
  const [typing, setTyping] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevTargetRef = useRef("");

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    // target 缩短（新一轮叙述重置）或完全不同时重置
    const prev = prevTargetRef.current;
    if (!target.startsWith(prev) || target.length < prev.length) {
      setDisplayed("");
      prevTargetRef.current = "";
    }

    if (!target) {
      setTyping(false);
      return;
    }

    const startFrom = prevTargetRef.current.length;
    if (startFrom >= target.length) {
      setTyping(false);
      return;
    }

    setTyping(true);

    let idx = startFrom;
    function tick() {
      idx++;
      const next = target.slice(0, idx);
      setDisplayed(next);
      prevTargetRef.current = next;
      if (idx < target.length) {
        timerRef.current = setTimeout(tick, speed);
      } else {
        setTyping(false);
      }
    }
    timerRef.current = setTimeout(tick, speed);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [target, speed]);

  return { displayed, typing };
}

export function AgentTrace({ steps, loading = false, userInput }: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const issueCount = steps.filter((step) => step.status === "fallback" || step.status === "error").length;
  const hasIssue = issueCount > 0;
  const thinking = buildThinkingSummary(steps, loading);
  const liveProgressLabel = getLiveProgressLabel(steps);
  const narrative = buildNarrativeText(steps, userInput);

  // 打字机输出
  const { displayed, typing } = useTypewriter(narrative, 32);

  // 没有数据且不在加载时，不渲染
  if (!loading && steps.length === 0) return null;

  // 将已输出文本按 " → " 切分成片段渲染
  const segments = displayed ? displayed.split(" → ").filter(Boolean) : [];

  return (
    <div className="trace-panel">
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

      {/* 展开后：叙述段落（打字机输出） */}
      {(loading || expanded) && (
        <div className="trace-narrative-panel">
          <div className="trace-narrative-title">
            <BrainCircuit size={15} />
            <span>{loading ? "正在组织路线思路…" : "思考过程"}</span>
          </div>

          {segments.length > 0 ? (
            <div className="trace-narrative-body">
              {segments.map((seg, i) => (
                <span key={i} className="trace-narrative-seg">
                  {renderSegment(seg)}
                  {/* 最后一个 segment 末尾加光标；其余 segment 后加箭头 */}
                  {i < segments.length - 1 ? (
                    <span className="trace-narrative-arrow">→</span>
                  ) : (
                    (typing || loading) && <span className="trace-typewriter-cursor" />
                  )}
                </span>
              ))}
              {/* loading 时末尾追加进度提示（打字结束后才显示，避免遮挡光标） */}
              {loading && !typing && (
                <span className="trace-narrative-seg trace-narrative-seg--loading">
                  <span className="trace-narrative-arrow">→</span>
                  <Loader size={11} style={{ animation: "spin 1s linear infinite", flexShrink: 0 }} />
                  <span>{liveProgressLabel}</span>
                </span>
              )}
            </div>
          ) : loading ? (
            <div className="trace-narrative-body">
              <span className="trace-narrative-seg trace-narrative-seg--loading">
                <Loader size={11} style={{ animation: "spin 1s linear infinite", flexShrink: 0 }} />
                <span>{liveProgressLabel}</span>
              </span>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

/**
 * 将单个叙述片段中的 **粗体内容** 渲染为 <strong>，其余保持文本。
 */
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
