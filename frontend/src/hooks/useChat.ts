import { useRef, useState } from "react";
import { sendChatMessage } from "../api/chatApi";
import type { ChatResponse } from "../api/types";
import type { OnboardingProfile } from "./useOnboarding";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export function useChat(profile?: OnboardingProfile) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasSentProfile = useRef(false);

  async function send(message: string) {
    const userMsg: ChatMessage = { role: "user", content: message, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);
    try {
      const includeProfile = !hasSentProfile.current;
      const res = await sendChatMessage(message, profile, includeProfile);
      hasSentProfile.current = true;
      setResponse(res);
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
    setError(null);
    hasSentProfile.current = false;
  }

  return { messages, response, loading, error, send, inject, reset };
}
