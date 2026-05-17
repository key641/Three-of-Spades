import { RefreshCcw, Sparkles, TimerReset, Wallet } from "lucide-react";

export function ActionBar() {
  return (
    <div className="action-bar">
      <button title="换一家"><RefreshCcw size={16} />换一家</button>
      <button title="更省钱"><Wallet size={16} />更省钱</button>
      <button title="少排队"><TimerReset size={16} />少排队</button>
      <button title="亲子友好"><Sparkles size={16} />亲子友好</button>
    </div>
  );
}

