import { Send } from "lucide-react";
import { FormEvent, useState } from "react";

interface ChatPanelProps {
  loading: boolean;
  error: string | null;
  latestMessage?: string;
  onSend: (message: string) => void;
}

export function ChatPanel({ loading, error, latestMessage, onSend }: ChatPanelProps) {
  const [message, setMessage] = useState("我们三个人周六下午在上海 citywalk，想吃好但别排队，人均300以内");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (message.trim()) onSend(message.trim());
  }

  return (
    <section className="panel">
      <h2>对话入口</h2>
      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={4} />
        <button type="submit" disabled={loading} title="发送">
          <Send size={18} />
          {loading ? "规划中" : "发送"}
        </button>
      </form>
      {latestMessage ? <p className="assistant-message">{latestMessage}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}

