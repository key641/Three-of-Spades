import { useRef, useState } from "react";
import { getChatSessionId, resetChatSession, sendChatMessageStream, setChatSessionId } from "../api/chatApi";
import type { AgentTraceStep, ChatResponse, ClarificationGroup } from "../api/types";
import type { OnboardingProfile, TripConstraints } from "./useOnboarding";
import { waitForGps } from "../utils/gpsCache";

export interface ChatMessage {
  role: "user" | "assistant" | "trace" | "clarify";
  content: string;
  timestamp: number;
  agentTrace?: AgentTraceStep[];
  /** 当前轮次的用户输入原文，用于 AgentTrace 叙述中「用户说…」开头 */
  agentUserInput?: string;
  /** clarify 角色专用：AI 追问的问题文本（兜底单问题） */
  clarifyQuestion?: string;
  /** clarify 角色专用：后端返回的多组追问（优先使用） */
  clarificationGroups?: ClarificationGroup[];
  /** clarify 角色专用：用户已填写的回答（填写后变为只读展示） */
  clarifyAnswer?: string;
  /** clarify 角色专用：用户选择的各组答案 label 汇总文本，用于展示已回答状态 */
  clarifyAnswerLabels?: string;
}

export interface ChatSessionSnapshot {
  sessionId: string;
  messages: ChatMessage[];
  response: ChatResponse | null;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRequest, setLastRequest] = useState<Record<string, unknown> | null>(null);
  const hasSentProfile = useRef(false);
  const activeProfileSigRef = useRef<string | null>(null);
  const requestSeqRef = useRef(0);
  const inFlightRef = useRef(false);
  const lastProfileSigRef = useRef<string | null>(null);

  function buildProfileSignature(profile?: OnboardingProfile) {
    if (!profile) return null;
    return JSON.stringify({
      user_id: profile.user_id,
      scenarios: profile.scenarios,
      preferences: profile.preferences,
      avoid_tags: profile.avoid_tags,
      budget_level: profile.budget_level,
      preference_weights: profile.preference_weights,
    });
  }

  async function send(
    message: string,
    profile?: OnboardingProfile,
    trip?: TripConstraints,
    silent = false,
    options: Record<string, unknown> = {},
  ) {
    if (inFlightRef.current) return;

    if (!silent) {
      const userMsg: ChatMessage = { role: "user", content: message, timestamp: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
    }
    setResponse(null);
    setLiveTrace([]);
    setLoading(true);
    setError(null);
    inFlightRef.current = true;

    const requestSeq = ++requestSeqRef.current;

    try {
    const profileSig = buildProfileSignature(profile);
    activeProfileSigRef.current = profileSig;
    const includeProfile =
      !hasSentProfile.current ||
      (profileSig !== null && profileSig !== lastProfileSigRef.current);
      const locationOptions = await getCurrentLocationOptions();

      // 记录本次发送的请求体快照，供 Debug Panel 展示
      setLastRequest({
        session_id: "(当前会话ID)",
        message,
        ...(trip?.city ? { trip_city: trip.city } : { trip_city: "(未传，后端追问)" }),
        start_lat: (locationOptions as Record<string, unknown>).start_lat ?? null,
        start_lng: (locationOptions as Record<string, unknown>).start_lng ?? null,
        preferences: profile?.preferences ?? [],
        scenarios: profile?.scenarios ?? [],
        avoid_tags: profile?.avoid_tags ?? [],
        ...options,
      });

      const res = await sendChatMessageStream(
        message,
        profile,
        includeProfile,
        (step) => {
          setLiveTrace((prev) => [...prev, step]);
        },
        trip,
        { ...locationOptions, ...options },
        (routes) => {
          setResponse((prev) => ({
            session_id: prev?.session_id ?? "",
            message: prev?.message ?? "",
            need_clarification: prev?.need_clarification ?? false,
            clarifying_question: prev?.clarifying_question ?? null,
            clarification_type: prev?.clarification_type ?? null,
            clarification_groups: prev?.clarification_groups ?? [],
            inferred_context: prev?.inferred_context ?? {},
            intent: prev?.intent ?? null,
            user_profile: prev?.user_profile ?? null,
            agent_trace: prev?.agent_trace ?? [],
            routes,
          }));
        },
      );

      if (includeProfile) {
        hasSentProfile.current = true;
        lastProfileSigRef.current = profileSig;
      }

      // 仅接收最新请求，避免响应乱序覆盖。
      if (requestSeq !== requestSeqRef.current) return;

      setResponse(res);
      setLiveTrace(res.agent_trace);

      if (res.need_clarification) {
        // 追问轮次：先插一条友好的前置气泡，再插入 clarify 卡片
        const preMsg: ChatMessage = {
          role: "assistant",
          content: res.message || "我想多了解一点，帮你规划得更准",
          timestamp: Date.now(),
          // agent_trace 挂在前置气泡上展示，clarify 卡片本身不再重复
          agentTrace: res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined,
          agentUserInput: message,
        };
        const clarifyRecord: ChatMessage = {
          role: "clarify",
          content: "",
          timestamp: Date.now() + 1,
          // 优先使用多组追问，兜底用单问题文本
          clarificationGroups: res.clarification_groups && res.clarification_groups.length > 0
            ? res.clarification_groups
            : undefined,
          clarifyQuestion: res.clarifying_question ?? "",
        };
        setMessages((prev) => [...prev, preMsg, clarifyRecord]);
      } else {
        // 正常轮次：直接插入 assistant 回复气泡
        // agent_trace 挂在回复气泡上展示；若无回复文案则用 trace 类型（只渲染思考步骤，无气泡）
        const traceData = res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined;
        const newMsgs: ChatMessage[] = [];

        if (res.message && res.message.trim()) {
          // 有回复文案：正常 assistant 气泡，挂 agent_trace
          newMsgs.push({
            role: "assistant",
            content: res.message,
            timestamp: Date.now(),
            agentTrace: traceData,
            agentUserInput: message,
          });
        } else if (traceData) {
          // 无回复文案但有思考步骤：插入 trace 类型消息（只渲染 AgentTrace，不渲染气泡）
          newMsgs.push({
            role: "trace",
            content: "",
            timestamp: Date.now(),
            agentTrace: traceData,
            agentUserInput: message,
          });
        }
        setMessages((prev) => [...prev, ...newMsgs]);
      }
    } catch (requestError) {
      if (requestSeq !== requestSeqRef.current) return;
      setError(requestError instanceof Error ? requestError.message : "请求失败，请检查后端是否启动");
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
        inFlightRef.current = false;
      }
    }
  }

  /**
   * 用户回答追问：把最后一条 clarify 记录的 clarifyAnswer 填上（就地更新，不加新气泡），
   * 然后 silent=true 发起下一轮请求。
   * @param answer        发送给后端的消息文本
   * @param labelSummary  可选，用于在气泡中展示的已回答摘要（各选项 label 拼接）
   * @param clarifyValues 可选，用户选择的各选项 value 合并对象（如 {city, target_district}），
   *                      会作为 options 附加到下一轮请求，让后端直接拿到结构化字段
   */
  function answerClarify(
    answer: string,
    profile?: OnboardingProfile,
    trip?: TripConstraints,
    labelSummary?: string,
    clarifyValues?: Record<string, unknown>,
  ) {
    // 1. 找到最后一条 clarify 消息，填入回答
    setMessages((prev) => {
      const idx = [...prev].reverse().findIndex((m) => m.role === "clarify");
      if (idx === -1) return prev;
      const realIdx = prev.length - 1 - idx;
      return prev.map((m, i) =>
        i === realIdx
          ? { ...m, clarifyAnswer: answer, clarifyAnswerLabels: labelSummary ?? answer }
          : m,
      );
    });
    // 2. silent=true：不再往 messages 里额外插 user bubble
    //    把结构化 value 作为 options 附带，后端直接读取 city/target_district 等字段
    send(answer, profile, trip, true, clarifyValues ?? {});
  }

  /** 在本地直接插入一条消息（用于欢迎语，不走网络） */
  function inject(role: "user" | "assistant", content: string) {
    const msg: ChatMessage = { role, content, timestamp: Date.now() };
    setMessages((prev) => [...prev, msg]);
  }

  /** 清空对话历史（重置 profile 后调用） */
  function reset() {
    setMessages([]);
    setResponse(null);
    setLiveTrace([]);
    setError(null);
    setLoading(false);
    hasSentProfile.current = false;
    lastProfileSigRef.current = null;
    activeProfileSigRef.current = null;
    requestSeqRef.current += 1;
    inFlightRef.current = false;
    resetChatSession();
  }

  /**
   * 当前会话的可恢复快照。
   * 历史记录只保留用户与助手的最终内容，不存 Agent 推理步骤或实时状态。
   */
  function snapshot(): ChatSessionSnapshot {
    return {
      sessionId: getChatSessionId(),
      messages: messages
        .filter((message) => message.role !== "trace")
        .map(({ agentTrace: _agentTrace, agentUserInput: _agentUserInput, ...message }) => message),
      response,
    };
  }

  /** 恢复已完成会话。恢复过程不触发接口请求，也不会展示实时 Agent 思考态。 */
  function restore(saved: ChatSessionSnapshot) {
    requestSeqRef.current += 1;
    inFlightRef.current = false;
    setChatSessionId(saved.sessionId);
    // 兼容此前已保存的快照：恢复时同样剥离旧版本中残留的思考步骤。
    setMessages(
      saved.messages
        .filter((message) => message.role !== "trace")
        .map(({ agentTrace: _agentTrace, agentUserInput: _agentUserInput, ...message }) => message),
    );
    setResponse(saved.response);
    setLiveTrace([]);
    setLoading(false);
    setError(null);
    hasSentProfile.current = true;
    lastProfileSigRef.current = activeProfileSigRef.current;
  }

  /**
   * 直接修改底层 response.routes 中某条路线的 stops（本地删除/排序等操作）。
   * routeId 对应要修改的路线，newStops 是更新后的站点列表。
   */
  function patchRouteStops(routeId: string, newStops: import("../api/types").RouteStop[]) {
    setResponse((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        routes: prev.routes.map((r) =>
          r.route_id === routeId ? { ...r, stops: newStops } : r
        ),
      };
    });
  }

  return { messages, response, liveTrace, loading, error, lastRequest, send, inject, reset, snapshot, restore, answerClarify, patchRouteStops };
}

// 默认起点：北京市西城区西单
const DEFAULT_START = {
  start_location_name: "北京市西城区西单",
  start_lat: 39.9072,
  start_lng: 116.3740,
  current_lat: 39.9072,
  current_lng: 116.3740,
};

async function getCurrentLocationOptions(): Promise<Record<string, unknown>> {
  // App.tsx 挂载时已发起 GPS 请求，这里等待最多 4 秒让缓存写入。
  // 用户只要在弹窗出现后的 4 秒内点了"允许"，坐标就能传给后端。
  const coords = await waitForGps(4000);
  if (coords) {
    return {
      current_lat: coords.lat,
      current_lng: coords.lng,
      start_lat:   coords.lat,
      start_lng:   coords.lng,
    };
  }
  // 无 GPS 时使用默认西单起点，避免后端追问城市
  return DEFAULT_START;
}
