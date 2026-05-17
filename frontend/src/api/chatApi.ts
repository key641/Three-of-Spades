import { postJson } from "./client";
import type { ChatResponse } from "./types";

export function sendChatMessage(message: string): Promise<ChatResponse> {
  return postJson<ChatResponse>("/api/chat", {
    session_id: "session_demo",
    user_id: "user_demo",
    message,
    event_type: "user_message",
  });
}

