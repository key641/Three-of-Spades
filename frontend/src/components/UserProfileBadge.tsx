import { User } from "lucide-react";
import { useState } from "react";
import { clearProfile } from "../hooks/useOnboarding";

interface UserProfileDisplay {
  preferences?: string[];
  avoid_tags?: string[];
  [key: string]: unknown;
}

interface UserProfileBadgeProps {
  profile: UserProfileDisplay | null;
  nickname?: string;
  onReset?: () => void;
}

export function UserProfileBadge({ profile, nickname = "旅行者", onReset }: UserProfileBadgeProps) {
  const [open, setOpen] = useState(false);

  const prefs: string[]  = profile?.preferences ?? [];
  const avoids: string[] = profile?.avoid_tags  ?? [];

  function handleReset() {
    clearProfile();
    setOpen(false);
    onReset?.();
  }

  return (
    <>
      {/* 手机：图标按钮 */}
      <button
        className="profile-badge-btn"
        type="button"
        title="用户画像"
        onClick={() => setOpen(true)}
        aria-label="查看用户画像"
      >
        <User size={18} />
      </button>

      {/* 桌面：行内 Badge */}
      <aside className="profile-badge">
        <span>当前偏好画像</span>
        <strong>{prefs.slice(0, 3).join(" · ") || "暂无偏好"}</strong>
      </aside>

      {/* 手机端：底部抽屉 */}
      {open && (
        <div
          className="drawer-overlay"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="profile-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-handle" />

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <div style={{
                width: 40, height: 40, borderRadius: "50%",
                background: "var(--color-primary-bg)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 18,
              }}>🧭</div>
              <div>
                <p style={{ margin: 0, fontWeight: 700, fontSize: "var(--font-body)" }}>{nickname}</p>
                <p className="muted" style={{ margin: 0, fontSize: "var(--font-small)" }}>偏好画像 · 行程反馈后自动更新</p>
              </div>
            </div>

            {prefs.length > 0 && (
              <>
                <p style={{ fontSize: "var(--font-small)", margin: "16px 0 8px", color: "var(--color-muted)", fontWeight: 600 }}>
                  ✅ 我喜欢
                </p>
                <div className="profile-tags">
                  {prefs.map((tag) => (
                    <span key={tag} className="profile-tag">{tag}</span>
                  ))}
                </div>
              </>
            )}

            {avoids.length > 0 && (
              <>
                <p style={{ fontSize: "var(--font-small)", margin: "16px 0 8px", color: "var(--color-muted)", fontWeight: 600 }}>
                  🚫 我想避开
                </p>
                <div className="profile-tags">
                  {avoids.map((tag) => (
                    <span key={tag} className="profile-tag" style={{ background: "#FEF3F2", color: "#991B1B" }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </>
            )}

            {/* 重置画像 */}
            <button
              type="button"
              onClick={handleReset}
              style={{
                marginTop: 24, width: "100%",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                background: "var(--color-card)",
                color: "var(--color-muted)",
                fontSize: "var(--font-small)",
                minHeight: 44,
              }}
            >
              🔄 重新填写偏好
            </button>
          </div>
        </div>
      )}
    </>
  );
}
