import { useRef, useState } from "react";
import { resetChatSession, sendChatMessageStream } from "../api/chatApi";
import type { AgentTraceStep, ChatResponse } from "../api/types";
import type { OnboardingProfile, TripConstraints } from "./useOnboarding";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  async function send(message: string, profile?: OnboardingProfile, trip?: TripConstraints, silent = false) {
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
      const res = await sendChatMessageStream(message, profile, includeProfile, (step) => {
        setLiveTrace((prev) => [...prev, step]);
      }, trip);

      if (includeProfile) {
        hasSentProfile.current = true;
        lastProfileSigRef.current = profileSig;
      }

      // 仅接收最新请求，避免响应乱序覆盖。
      if (requestSeq !== requestSeqRef.current) return;

      setResponse(res);
      setLiveTrace(res.agent_trace);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: res.message,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
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

  return { messages, response, liveTrace, loading, error, send, inject, reset };
}
