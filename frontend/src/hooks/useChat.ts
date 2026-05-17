import { useState } from "react";
import { sendChatMessage } from "../api/chatApi";
import type { ChatResponse } from "../api/types";

export function useChat() {
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(message: string) {
    setLoading(true);
    setError(null);
    try {
      setResponse(await sendChatMessage(message));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return { response, loading, error, send };
}

