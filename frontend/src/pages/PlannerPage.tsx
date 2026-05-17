import { AgentTrace } from "../components/AgentTrace";
import { ChatPanel } from "../components/ChatPanel";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ReplanPanel } from "../components/ReplanPanel";
import { RouteCompare } from "../components/RouteCompare";
import { UserProfileBadge } from "../components/UserProfileBadge";
import { useChat } from "../hooks/useChat";

export function PlannerPage() {
  const { response, loading, error, send } = useChat();

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <h1>AI 本地路线智能规划</h1>
          <p>真实 Agent 链路：理解意图、召回 POI、规划路线、动态重规划。</p>
        </div>
        <UserProfileBadge />
      </section>

      <section className="workspace">
        <ChatPanel loading={loading} error={error} latestMessage={response?.message} onSend={send} />
        <AgentTrace steps={response?.agent_trace ?? []} />
      </section>

      <RouteCompare routes={response?.routes ?? []} />
      <ReplanPanel routes={response?.routes ?? []} />
      <FeedbackPanel />
    </main>
  );
}

