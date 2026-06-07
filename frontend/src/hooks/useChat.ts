import { useRef, useState } from "react";
import { resetChatSession, sendChatMessageStream } from "../api/chatApi";
import type { AgentTraceStep, ChatResponse } from "../api/types";
import type { OnboardingProfile, TripConstraints } from "./useOnboarding";

export interface ChatMessage {
  role: "user" | "assistant" | "trace" | "clarify";
  content: string;
  timestamp: number;
  agentTrace?: AgentTraceStep[];
  /** clarify 角色专用：AI 追问的问题文本 */
  clarifyQuestion?: string;
  /** clarify 角色专用：用户已填写的回答（填写后变为只读展示） */
  clarifyAnswer?: string;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRequest, setLastRequest] = useState<Record<string, unknown> | null>(null);
  const hasSentProfile = useRef(false);
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
          content: "我想知道这些信息帮助规划",
          timestamp: Date.now(),
          // agent_trace 挂在前置气泡上展示，clarify 卡片本身不再重复
          agentTrace: res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined,
        };
        const clarifyRecord: ChatMessage = {
          role: "clarify",
          content: "",
          timestamp: Date.now() + 1,
          clarifyQuestion: res.clarifying_question ?? "",
        };
        setMessages((prev) => [...prev, preMsg, clarifyRecord]);
      } else {
        // 正常轮次：先插一条「理解！正在规划」前置气泡，再插 assistant 回复气泡
        const preMsg: ChatMessage = {
          role: "assistant",
          content: "理解！正在规划",
          timestamp: Date.now(),
          // agent_trace 挂在前置气泡上展示
          agentTrace: res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined,
        };
        const newMsgs: ChatMessage[] = [preMsg];
        // res.message 可能包含额外文案（如后端有说明性文字），有内容则追加
        if (res.message && res.message.trim()) {
          newMsgs.push({
            role: "assistant",
            content: res.message,
            timestamp: Date.now() + 1,
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
   */
  function answerClarify(
    answer: string,
    profile?: OnboardingProfile,
    trip?: TripConstraints,
  ) {
    // 1. 找到最后一条 clarify 消息，填入回答
    setMessages((prev) => {
      const idx = [...prev].reverse().findIndex((m) => m.role === "clarify");
      if (idx === -1) return prev;
      const realIdx = prev.length - 1 - idx;
      return prev.map((m, i) =>
        i === realIdx ? { ...m, clarifyAnswer: answer } : m,
      );
    });
    // 2. silent=true：不再往 messages 里额外插 user bubble
    send(answer, profile, trip, true);
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
    requestSeqRef.current += 1;
    inFlightRef.current = false;
    resetChatSession();
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

  return { messages, response, liveTrace, loading, error, lastRequest, send, inject, reset, answerClarify, patchRouteStops };
}

async function getCurrentLocationOptions(): Promise<Record<string, unknown>> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return {};
  }
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => resolve({}), 1200);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        window.clearTimeout(timer);
        resolve({
          current_lat: position.coords.latitude,
          current_lng: position.coords.longitude,
          start_lat: position.coords.latitude,
          start_lng: position.coords.longitude,
        });
      },
      () => {
        window.clearTimeout(timer);
        resolve({});
      },
      { enableHighAccuracy: false, maximumAge: 300000, timeout: 1000 },
    );
  });
}
