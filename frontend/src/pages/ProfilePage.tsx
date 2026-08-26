import { useState } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Send } from "lucide-react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { PhoneStatusBar } from "../App";
import homeBackground from "../assets/home-background-250.png";
import andyAvatar from "../assets/andy-avatar-64.png";

const SCENARIO_LABEL: Record<string, string> = {
  citywalk: "街头漫游",
  foodie: "美食探店",
  culture: "文化艺术",
  show_event: "演出活动",
  landmark: "热门景点",
  family: "亲子家庭",
  nature: "自然放松",
  shopping: "逛街购物",
  freestyle: "随心而行",
};

function FeedbackOverlay({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit() {
    if (!text.trim()) return;
    setSubmitted(true);
    setTimeout(onClose, 1400);
  }

  return (
    <div className="profile-subpage-overlay">
      <PhoneStatusBar />
      <div className="profile-subpage-topbar">
        <button type="button" className="profile-subpage-back" onClick={onClose} aria-label="返回">
          <ArrowLeft size={18} />
        </button>
        <span className="profile-subpage-title">意见反馈</span>
        <span className="profile-subpage-topbar-spacer" />
      </div>
      <div className="feedback-body">
        {submitted ? (
          <div className="feedback-success">
            <p className="feedback-success-title">感谢你的反馈！</p>
            <p className="feedback-success-desc">我们会认真阅读每一条建议，持续改进 Drifto。</p>
          </div>
        ) : (
          <>
            <p className="feedback-hint">遇到了问题，或者有什么想对我们说的？<br />每一条反馈我们都会认真对待。</p>
            <textarea
              className="feedback-textarea"
              placeholder="写下你的想法或建议……"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={6}
              autoFocus
            />
            <div className="feedback-actions">
              <button type="button" className="feedback-cancel" onClick={onClose}>取消</button>
              <button type="button" className="feedback-submit" disabled={!text.trim()} onClick={handleSubmit}>
                <Send size={13} />
                提交反馈
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function AboutOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div className="profile-subpage-overlay about-subpage-overlay">
      <img src={homeBackground} alt="" className="about-background-art" aria-hidden="true" width={250} height={619} decoding="async" />
      <PhoneStatusBar />
      <div className="profile-subpage-topbar">
        <button type="button" className="profile-subpage-back" onClick={onClose} aria-label="返回">
          <ArrowLeft size={18} />
        </button>
        <span className="profile-subpage-title">关于 Drifto</span>
        <span className="profile-subpage-topbar-spacer" />
      </div>
      <div className="about-body">
        <div className="about-hero">
          <p className="about-tagline">随漂流动，随心而行</p>
        </div>
        <div className="about-content">
          <p className="about-para">城市从来不缺好去处，<br />缺的是一个懂你的人，陪你找到它。</p>
          <p className="about-para">Drifto 是一款由 AI 驱动的出行规划助手。<br />说出此刻的心情、预算，或仅仅一句“我想出去走走”，<br />它就会为你生成一条专属于此刻的路线。</p>
          <p className="about-para">不是千篇一律的攻略，<br />是今天的你，在这座城市里独一无二的一段漫游。</p>
          <div className="about-divider" />
          <div className="about-feature-list">
            <div className="about-feature-item"><div><p className="about-feature-title">智能路线规划</p><p className="about-feature-desc">根据偏好、时间、预算生成个性化方案</p></div></div>
            <div className="about-feature-item"><div><p className="about-feature-title">排队预测</p><p className="about-feature-desc">提前感知人流，把等待时间从行程里抹掉</p></div></div>
            <div className="about-feature-item"><div><p className="about-feature-title">边走边改</p><p className="about-feature-desc">临时换地点、延长停留，一句话搞定</p></div></div>
          </div>
          <div className="about-divider" />
          <p className="about-footer-text">Drifto 由黑客松团队「黑桃三」打造<br /><span className="about-footer-sub">愿每一次出发，都刚刚好</span></p>
        </div>
      </div>
    </div>
  );
}

export interface ProfilePageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
  onBack?: () => void;
}

export function ProfilePage({ profile, onResetProfile, onBack }: ProfilePageProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  return (
    <div className="profile-shell">
      <header className="profile-header profile-header--archive">
        <div className="profile-header-topbar">
          {onBack ? <button type="button" className="profile-back-btn" onClick={onBack} aria-label="返回"><ChevronLeft size={20} strokeWidth={2.5} /></button> : <span />}
          <h1 className="profile-page-title">个人中心</h1>
          <span className="profile-topbar-spacer" />
        </div>
        <div className="profile-header-user">
          <img src={andyAvatar} alt="Andy" className="profile-avatar" width={48} height={48} decoding="async" />
          <div className="profile-header-info"><p className="profile-name">{profile.nickname || "旅行者"}</p></div>
        </div>
      </header>

      <div className="profile-scroll profile-scroll--archive">
        <section className="profile-feature-card profile-preference-card">
          <div className="profile-card-heading">
            <h2 className="profile-section-title">我的出行偏好</h2>
            <button type="button" className="profile-card-action" onClick={() => setShowResetConfirm(true)}>重新设置 <ChevronRight size={14} /></button>
          </div>
          {profile.scenarios.length > 0 && <div className="profile-pref-group"><p className="profile-pref-group-title">常玩场景</p><div className="profile-pref-tags">{profile.scenarios.map((item) => <span key={item} className="profile-pref-tag">{SCENARIO_LABEL[item] ?? item}</span>)}</div></div>}
          {profile.preferences.length > 0 && <div className="profile-pref-group"><p className="profile-pref-group-title">偏好特点</p><div className="profile-pref-tags">{profile.preferences.map((item) => <span key={item} className="profile-pref-tag profile-pref-tag--pref">{SCENARIO_LABEL[item] ?? item}</span>)}</div></div>}
          {profile.avoid_tags.length > 0 && <div className="profile-pref-group profile-pref-group--last"><p className="profile-pref-group-title">避开禁忌</p><div className="profile-pref-tags">{profile.avoid_tags.map((item) => <span key={item} className="profile-pref-tag profile-pref-tag--avoid">{item}</span>)}</div></div>}
        </section>
        <section className="profile-menu-list profile-menu-list--quiet">
          <button type="button" className="profile-menu-item" onClick={() => setShowFeedback(true)}><span className="profile-menu-label">意见反馈</span><ChevronRight size={14} className="profile-menu-arrow" /></button>
          <button type="button" className="profile-menu-item" onClick={() => setShowAbout(true)}><span className="profile-menu-label">关于 Drifto</span><span className="profile-menu-version">v1.0.0</span></button>
        </section>
      </div>

      {showResetConfirm && <div className="profile-reset-mask"><div className="profile-reset-dialog"><p className="profile-reset-title">重置出行偏好？</p><p className="profile-reset-desc">将清除已保存的偏好设置，重新完成初始配置。</p><div className="profile-reset-actions"><button type="button" className="profile-reset-cancel" onClick={() => setShowResetConfirm(false)}>取消</button><button type="button" className="profile-reset-confirm" onClick={() => { setShowResetConfirm(false); onResetProfile(); }}>确认重置</button></div></div></div>}
      {showFeedback && <FeedbackOverlay onClose={() => setShowFeedback(false)} />}
      {showAbout && <AboutOverlay onClose={() => setShowAbout(false)} />}
    </div>
  );
}
