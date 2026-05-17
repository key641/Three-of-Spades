import type { AgentTraceStep } from "../api/types";

interface AgentTraceProps {
  steps: AgentTraceStep[];
}

export function AgentTrace({ steps }: AgentTraceProps) {
  return (
    <section className="panel">
      <h2>Agent 调用过程</h2>
      <div className="trace-list">
        {steps.length === 0 ? <p className="muted">发送需求后展示工具调用轨迹。</p> : null}
        {steps.map((step) => (
          <div className="trace-item" key={step.step}>
            <span>{step.label}</span>
            <strong>{step.status}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

