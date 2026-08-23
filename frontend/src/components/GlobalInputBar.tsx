import { FormEvent, useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";

/**
 * 全局底部输入栏 — 固定在 App 层级，不随页面切换卸载。
 * 受控组件：value + onChange 由 App 管理。
 */

export interface GlobalInputBarProps {
  /** 当前模式：home 单行 / plan 多行 */
  mode: "home" | "plan";
  /** 输入文字（受控） */
  value: string;
  /** 文字变化回调 */
  onChange: (text: string) => void;
  /** 发送回调 */
  onSend: (text: string) => void;
  /** 是否禁用 */
  disabled?: boolean;
  /** placeholder */
  placeholder?: string;
}

export function GlobalInputBar({ mode, value, onChange, onSend, disabled = false, placeholder }: GlobalInputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasText = value.trim().length > 0;
  const canSend = hasText && !disabled;

  function handleSubmit(e?: FormEvent) {
    if (e) e.preventDefault();
    const msg = value.trim();
    if (!msg || disabled) return;
    onSend(msg);
    onChange("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
  }

  // value 变化时自适应 textarea 高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [value]);

  // 模式切换时清空文字
  useEffect(() => {
    onChange("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <div className="home-input-bar-container global-input-bar">
      <form className="home-input-bar" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          className="home-input-field"
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? "去哪玩、怎么逛，问我就行…"}
          rows={1}
          disabled={disabled}
          aria-label="输入出行需求"
        />
        <button
          type="submit"
          className={`home-send-btn${canSend ? " active" : ""}`}
          disabled={!canSend}
          aria-label="发送"
        >
          <ArrowUp size={20} strokeWidth={2.5} />
        </button>
      </form>
      <div className="home-ai-disclaimer">内容由 AI 生成，仅供参考</div>
    </div>
  );
}
