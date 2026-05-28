import { useRef, useState } from "react";
import { sendChatMessageStream } from "../api/chatApi";
import type { AgentTraceStep, ChatResponse } from "../api/types";
import type { OnboardingProfile } from "./useOnboarding";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export function useChat(profile?: OnboardingProfile) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasSentProfile = useRef(false);

  async function send(message: string) {
    const userMsg: ChatMessage = { role: "user", content: message, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setResponse(null);
    setLiveTrace([]);
    setLoading(true);
    setError(null);
    try {
      const includeProfile = !hasSentProfile.current;
      const res = await sendChatMessageStream(message, profile, includeProfile, (step) => {
        setLiveTrace((prev) => [...prev, step]);
      });
      hasSentProfile.current = true;
      setResponse(res);
      setLiveTrace(res.agent_trace);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: res.message,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "请求失败，请检查后端是否启动");
    } finally {
      setLoading(false);
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
    hasSentProfile.current = false;
  }

  return { messages, response, liveTrace, loading, error, send, inject, reset };
}
