import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  LoaderCircle,
  Play,
  XCircle,
} from "lucide-react";
import { postJson } from "../api/client";

interface TraceStep {
  step: string;
  label: string;
  status: string;
  details: Record<string, unknown>;
}

interface EvaluationResult {
  name: string;
  category: string;
  passed: boolean;
  score: number;
  duration_ms: number;
  problem_step: string | null;
  failures: string[];
  warning_steps: string[];
  failure_codes: string[];
  dimension_scores: DimensionScore[];
  input: { session_id: string; user_id: string; message: string; city?: string | null };
  output: {
    message: string;
    need_clarification: boolean;
    intent?: { city?: string | null } | null;
    routes: unknown[];
    agent_trace: TraceStep[];
  } | null;
  error: string | null;
}

interface DimensionScore {
  dimension: string;
  label: string;
  score: number;
  passed_checks: number;
  total_checks: number;
}

interface IssueSummary {
  code: string;
  label: string;
  step: string;
  count: number;
  case_names: string[];
}

interface EvaluationResponse {
  summary: {
    total: number; passed: number; failed: number; pass_rate: number; average_score: number; duration_ms: number;
    dimension_scores: DimensionScore[]; issues: IssueSummary[];
  };
  results: EvaluationResult[];
}

export function EvaluationPage({ onBack }: { onBack: () => void }) {
  const [report, setReport] = useState<EvaluationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [customInputs, setCustomInputs] = useState("");
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  async function runEvaluation() {
    setRunning(true);
    setError("");
    setExpanded({});
    const messages = customInputs.split("\n").map((value) => value.trim()).filter(Boolean).slice(0, 20);
    const cases = messages.map((message, index) => ({
      name: `自定义用例 ${index + 1}`,
      message,
      expectation: { min_routes: 0, expect_trace: true },
    }));
    try {
      const next = await postJson<EvaluationResponse>("/api/evaluation/run", { cases });
      setReport(next);
      const firstFailed = next.results.findIndex((result) => !result.passed);
      if (firstFailed >= 0) setExpanded({ [firstFailed]: true });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "测评请求失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="evaluation-shell">
      <header className="evaluation-header">
        <button type="button" className="evaluation-back" onClick={onBack} aria-label="返回">
          <ArrowLeft size={20} />
        </button>
        <div>
          <div className="evaluation-kicker"><FlaskConical size={14} /> SYSTEM EVALUATION</div>
          <h1>测评</h1>
          <p>批量检查输入、输出与 Agent 中间过程</p>
        </div>
      </header>

      <main className="evaluation-content">
        <section className="evaluation-run-card">
          <label htmlFor="evaluation-inputs">自定义输入（可选，每行一条，最多 20 条）</label>
          <textarea
            id="evaluation-inputs"
            value={customInputs}
            onChange={(event) => setCustomInputs(event.target.value)}
            placeholder={"留空运行内置典型用例\n或输入：上海半天 citywalk，少排队"}
            rows={4}
          />
          <div className="evaluation-run-footer">
            <span>{customInputs.trim() ? "将运行自定义批次" : "将运行 20 条分层基线用例"}</span>
            <button type="button" onClick={runEvaluation} disabled={running}>
              {running ? <LoaderCircle className="spin" size={17} /> : <Play size={16} fill="currentColor" />}
              {running ? "运行中…" : "开始测评"}
            </button>
          </div>
        </section>

        {error && <div className="evaluation-error"><AlertTriangle size={17} />{error}</div>}

        {report && (
          <>
            <section className="evaluation-summary">
              <div><span>综合得分</span><strong>{report.summary.average_score}</strong></div>
              <div><span>通过率</span><strong>{Math.round(report.summary.pass_rate * 100)}%</strong></div>
              <div><span>通过</span><strong className="evaluation-pass">{report.summary.passed}</strong></div>
              <div><span>失败</span><strong className="evaluation-fail">{report.summary.failed}</strong></div>
              <div><span>总耗时</span><strong>{(report.summary.duration_ms / 1000).toFixed(1)}s</strong></div>
            </section>

            <section className="evaluation-diagnostics">
              <div className="evaluation-dimension-panel">
                <h2>分维度质量</h2>
                {report.summary.dimension_scores.map((item) => (
                  <div className="evaluation-dimension-row" key={item.dimension}>
                    <span>{item.label}</span>
                    <div><i style={{ width: `${item.score}%` }} /></div>
                    <strong>{item.score}</strong>
                  </div>
                ))}
              </div>
              <div className="evaluation-issue-panel">
                <h2>重点问题</h2>
                {report.summary.issues.length === 0
                  ? <p className="evaluation-empty">本批次未发现规则性问题</p>
                  : report.summary.issues.slice(0, 5).map((issue) => (
                    <div className="evaluation-issue-row" key={issue.code}>
                      <span><strong>{issue.label}</strong><small>{issue.step} · {issue.case_names.join("、")}</small></span>
                      <b>{issue.count}</b>
                    </div>
                  ))}
              </div>
            </section>

            <section className="evaluation-results">
              {report.results.map((result, index) => {
                const isOpen = Boolean(expanded[index]);
                return (
                  <article className={`evaluation-case ${result.passed ? "passed" : "failed"}`} key={`${result.name}-${index}`}>
                    <button
                      type="button"
                      className="evaluation-case-head"
                      onClick={() => setExpanded((prev) => ({ ...prev, [index]: !prev[index] }))}
                    >
                      {result.passed
                        ? <CheckCircle2 className="evaluation-pass" size={20} />
                        : <XCircle className="evaluation-fail" size={20} />}
                      <span className="evaluation-case-title">
                        <strong>{result.name}</strong>
                        <small>{result.category} · 得分 {result.score} · {result.duration_ms} ms · {result.output?.agent_trace.length ?? 0} 步</small>
                      </span>
                      {result.problem_step && <span className="evaluation-problem">问题：{result.problem_step}</span>}
                      {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    </button>

                    {isOpen && (
                      <div className="evaluation-case-body">
                        <div className="evaluation-io-grid">
                          <div><h3>输入</h3><p>{result.input.message}</p></div>
                          <div>
                            <h3>最终输出</h3>
                            <p>{result.output?.message || result.error || "无输出"}</p>
                            {result.output && (
                              <small>
                                城市：{result.output.intent?.city || "未识别"} ·
                                路线：{result.output.routes.length} 条 ·
                                追问：{result.output.need_clarification ? "是" : "否"}
                              </small>
                            )}
                          </div>
                        </div>

                        {result.failures.length > 0 && (
                          <div className="evaluation-failures">
                            {result.failures.map((failure) => <p key={failure}><XCircle size={14} />{failure}</p>)}
                          </div>
                        )}

                        <h3 className="evaluation-trace-title">中间过程</h3>
                        <ol className="evaluation-trace">
                          {(result.output?.agent_trace ?? []).map((step, stepIndex) => (
                            <li className={`status-${step.status}`} key={`${step.step}-${stepIndex}`}>
                              <span className="evaluation-trace-index">{stepIndex + 1}</span>
                              <div>
                                <strong>{step.step}</strong>
                                <p>{step.label}</p>
                                {Object.keys(step.details).length > 0 && (
                                  <details>
                                    <summary>查看步骤数据</summary>
                                    <pre>{JSON.stringify(step.details, null, 2)}</pre>
                                  </details>
                                )}
                              </div>
                              <span className="evaluation-trace-status">{step.status}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </article>
                );
              })}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
