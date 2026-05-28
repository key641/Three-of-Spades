import { FormEvent, useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { AgentTrace } from "../components/AgentTrace";
import { ChatPanel } from "../components/ChatPanel";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ReplanPanel } from "../components/ReplanPanel";
import { RouteCompare } from "../components/RouteCompare";
import { UserProfileBadge } from "../components/UserProfileBadge";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import type { ChatMessage } from "../hooks/useChat";
import { useChat } from "../hooks/useChat";

interface PlannerPageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
}

// 根据画像生成个性化快捷 Chips
function buildChips(profile: OnboardingProfile): string[] {
  const city = profile.city ?? "上海";
  const base: string[] = [];
  if (profile.preferences.includes("少排队"))  base.push("少排队路线，避开人流");
  if (profile.preferences.includes("吃好"))    base.push(`${city}今天吃什么`);
  if (profile.preferences.includes("亲子友好")) base.push("带小孩，亲子友好路线");
  if (profile.budget_level === "low")           base.push("预算100以内，高性价比");
  if (profile.preferences.includes("网红打卡")) base.push("网红打卡路线推荐");
  base.unshift(`${city}半天 citywalk，2人`);
  return base.slice(0, 4);
}

// 根据场景和偏好构建 ReplanPanel 的事件提示文本
function buildReplanMessage(eventKey: string, currentRouteId?: string): string {
  const routeHint = currentRouteId ? `（当前路线 ${currentRouteId}）` : "";
  const map: Record<string, string> = {
    queue90:  `餐厅排队 90 分钟${routeHint}，帮我换一个等待时间短的替代方案`,
    traffic:  `路上堵车了${routeHint}，帮我调整后续行程`,
    tired:    `我们有点累了${routeHint}，帮我缩短行程或推荐就近休息的地方`,
  };
  return map[eventKey] ?? `发生了突发情况${routeHint}，请帮我重新规划`;
}

// 根据 ActionBar 操作构建请求文本
function buildActionMessage(actionKey: string, routeId: string): string {
  const map: Record<string, string> = {
    swap:   `帮我替换路线 ${routeId} 中的一个地点`,
    budget: `对路线 ${routeId} 重新规划，降低人均消费`,
    queue:  `对路线 ${routeId} 重新规划，避开需要排队的地点`,
    family: `对路线 ${routeId} 加入亲子友好筛选条件`,
  };
  return map[actionKey] ?? `请优化路线 ${routeId}`;
}

export function PlannerPage({ profile, onResetProfile }: PlannerPageProps) {
  const { messages, response, liveTrace, loading, error, send, inject, reset } = useChat(profile);
  const [inputText, setInputText] = useState("");
  const [localProfile, setLocalProfile] = useState<OnboardingProfile>(profile);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const welcomeSentRef = useRef(false);

  const chips = buildChips(localProfile);

  // P2: 首次进入时本地注入 AI 欢迎消息（不走网络请求）
  useEffect(() => {
    if (welcomeSentRef.current) return;
    welcomeSentRef.current = true;
    const prefs = localProfile.preferences.slice(0, 3);
    const prefHint = prefs.length > 0 ? `（${prefs.join("、")}）` : "";
    inject(
      "assistant",
      `你好 ${localProfile.nickname}！我已了解你的偏好${prefHint}，随时告诉我想去 ${localProfile.city} 的哪儿，我来帮你规划 🗺️`,
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const msg = inputText.trim();
    if (!msg || loading) return;
    send(msg);
    setInputText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  // P1: 重规划 — 接通 send
  function handleReplan(eventKey: string) {
    const currentRouteId = response?.routes?.[0]?.route_id;
    send(buildReplanMessage(eventKey, currentRouteId));
  }

  // P1: ActionBar — 接通 send
  function handleAction(actionKey: string, routeId: string) {
    send(buildActionMessage(actionKey, routeId));
  }

  // P2: 重置 profile — 同时清空对话
  function handleResetProfile() {
    reset();
    onResetProfile();
  }

  const hasRoutes = (response?.routes?.length ?? 0) > 0;
  const displayProfile: { preferences?: string[]; avoid_tags?: string[] } =
    response?.user_profile ?? {
      preferences: localProfile.preferences,
      avoid_tags:  localProfile.avoid_tags,
    };

  return (
    <div className="app-shell">
      {/* ── 固定顶部标题栏 ── */}
      <header className="topbar">
        <div>
          <h1>🗺️ 现在就出发</h1>
          <p>AI 本地路线智能规划 · 理解意图 · 召回 POI · 生成路线</p>
        </div>
        <UserProfileBadge
          profile={displayProfile}
          nickname={localProfile.nickname}
          onReset={handleResetProfile}
        />
      </header>

      {/* ── 可滚动主内容区 ── */}
      <main className="scroll-area">
        <div className="workspace">
          {/* 左栏：消息气泡 + Agent Trace */}
          <div>
            {/* 快捷 Chips（无历史消息时显示） */}
            {messages.length === 0 && !loading && (
              <div className="chips" style={{ marginBottom: "12px" }}>
                {chips.map((chip) => (
                  <button
                    key={chip}
                    className="chip"
                    type="button"
                    onClick={() => {
                      setInputText(chip);
                      textareaRef.current?.focus();
                    }}
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}

            <ChatPanel
              messages={messages}
              loading={loading}
              error={error}
              clarifyingQuestion={response?.need_clarification ? (response.clarifying_question ?? null) : null}
              onClarify={(answer) => send(answer)}
            />
            <AgentTrace steps={loading ? liveTrace : response?.agent_trace ?? liveTrace} loading={loading} />
          </div>

          {/* 右栏占位 */}
          <div />
        </div>

        {/* 路线结果区 */}
        {(hasRoutes || loading) && (
          <RouteCompare
            routes={response?.routes ?? []}
            loading={loading}
            onAction={handleAction}
          />
        )}

        {/* 动态重规划 */}
        <ReplanPanel
          routes={response?.routes ?? []}
          onReplan={handleReplan}
        />

        {/* 行程反馈 */}
        {hasRoutes && (
          <FeedbackPanel
            onProfileUpdated={(updated) => setLocalProfile(updated)}
          />
        )}
      </main>

      {/* ── 固定底部输入栏 ── */}
      <form className="input-bar" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={`告诉我你想怎么玩，例如「${localProfile.city}半天 citywalk」…`}
          rows={1}
          disabled={loading}
          aria-label="输入出行需求"
        />
        <button
          type="submit"
          className="send-btn"
          disabled={loading || !inputText.trim()}
          title="发送"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
