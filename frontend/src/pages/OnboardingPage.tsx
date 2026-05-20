import { useState } from "react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { saveProfile } from "../hooks/useOnboarding";

interface OnboardingPageProps {
  onDone: (profile: OnboardingProfile) => void;
}

// ── 数据配置 ──────────────────────────────────────────────────

const SCENARIOS: { key: string; emoji: string; label: string; desc: string }[] = [
  { key: "friends_citywalk", emoji: "👫", label: "朋友 citywalk",  desc: "和朋友漫步街头、打卡探店" },
  { key: "family_trip",      emoji: "👨‍👩‍👧", label: "家庭出行",    desc: "带长辈或小孩，轻松休闲" },
  { key: "solo_explore",     emoji: "🎒", label: "一个人探索",   desc: "独自发现城市的隐藏角落" },
  { key: "date_night",       emoji: "💑", label: "约会出行",     desc: "仪式感十足的两人路线" },
  { key: "foodie_tour",      emoji: "🍜", label: "美食打卡",     desc: "以美食为核心，边吃边逛" },
  { key: "culture_museum",   emoji: "🏛️", label: "文化艺术游",   desc: "博物馆、美术馆、历史街区" },
];

const PREF_TAGS: { key: string; emoji: string; label: string }[] = [
  { key: "少排队",   emoji: "⚡", label: "少排队" },
  { key: "吃好",     emoji: "🍽️", label: "吃好" },
  { key: "性价比",   emoji: "💰", label: "性价比高" },
  { key: "citywalk", emoji: "🚶", label: "citywalk" },
  { key: "网红打卡", emoji: "📸", label: "网红打卡" },
  { key: "安静",     emoji: "🌿", label: "环境安静" },
  { key: "亲子友好", emoji: "👶", label: "亲子友好" },
  { key: "有特色",   emoji: "✨", label: "有特色" },
  { key: "交通方便", emoji: "🚇", label: "交通方便" },
];

const AVOID_TAGS: { key: string; emoji: string; label: string }[] = [
  { key: "人多",   emoji: "👥", label: "人太多" },
  { key: "商业街", emoji: "🏬", label: "商业街" },
  { key: "贵",     emoji: "💸", label: "消费贵" },
  { key: "辣",     emoji: "🌶️", label: "辣的食物" },
  { key: "需排队", emoji: "⏳", label: "需要排队" },
];

const BUDGETS: { key: "low" | "mid" | "high"; label: string; desc: string; range: string }[] = [
  { key: "low",  label: "省钱游",  desc: "主打性价比",   range: "人均 ≤ ¥100" },
  { key: "mid",  label: "舒适游",  desc: "品质与价格均衡", range: "人均 ¥100 ~ ¥300" },
  { key: "high", label: "享受游",  desc: "不将就，体验优先", range: "人均 > ¥300" },
];

const CITIES = ["上海", "北京", "广州", "深圳", "成都", "杭州", "南京", "武汉", "西安"];

const TOTAL_STEPS = 3;

// ── 组件 ─────────────────────────────────────────────────────

export function OnboardingPage({ onDone }: OnboardingPageProps) {
  const [step, setStep] = useState(1);
  const [scenarios,  setScenarios]  = useState<string[]>([]);
  const [prefs,      setPrefs]      = useState<string[]>([]);
  const [avoids,     setAvoids]     = useState<string[]>([]);
  const [budgetLevel, setBudgetLevel] = useState<"low" | "mid" | "high">("mid");
  const [city,       setCity]       = useState("上海");
  const [nickname,   setNickname]   = useState("");

  function toggleTag(list: string[], setList: (v: string[]) => void, key: string) {
    setList(list.includes(key) ? list.filter((t) => t !== key) : [...list, key]);
  }

  function canNext() {
    if (step === 1) return scenarios.length >= 1;
    if (step === 2) return prefs.length >= 1;
    return true;
  }

  function handleFinish() {
    const profile = saveProfile({
      nickname: nickname.trim() || "旅行者",
      city,
      scenarios,                                  // 完整多选列表
      scenario: scenarios[0] ?? "friends_citywalk", // 后端兼容字段
      preferences: prefs,
      avoid_tags: avoids,
      budget_level: budgetLevel,
    });
    onDone(profile);
  }

  return (
    <div className="ob-shell">
      {/* 顶部进度条 */}
      <div className="ob-progress">
        <div className="ob-progress-bar" style={{ width: `${(step / TOTAL_STEPS) * 100}%` }} />
      </div>

      {/* 内容区 */}
      <div className="ob-content">
        {/* ── Step 1：选择出行场景 ── */}
        {step === 1 && (
          <div className="ob-step">
            <div className="ob-step-tag">第 1 步 / 共 3 步</div>
            <h1 className="ob-title">你平时喜欢怎么玩？</h1>
            <p className="ob-subtitle">可多选，仅作参考 — 不会限制你的路线选择，随时可以改</p>
            <div className="ob-scenario-grid">
              {SCENARIOS.map(({ key, emoji, label, desc }) => (
                <button
                  key={key}
                  type="button"
                  className={`ob-scenario-card${scenarios.includes(key) ? " selected" : ""}`}
                  onClick={() => toggleTag(scenarios, setScenarios, key)}
                >
                  <span className="ob-scenario-emoji">{emoji}</span>
                  <span className="ob-scenario-label">{label}</span>
                  <span className="ob-scenario-desc">{desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 2：偏好标签 + 避开标签 ── */}
        {step === 2 && (
          <div className="ob-step">
            <div className="ob-step-tag">第 2 步 / 共 3 步</div>
            <h1 className="ob-title">你的出行偏好</h1>
            <p className="ob-subtitle">至少选 1 个，帮助 AI 排出更准的路线（可多选）</p>

            <div className="ob-section-label">✅ 我喜欢</div>
            <div className="ob-tag-grid">
              {PREF_TAGS.map(({ key, emoji, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`ob-tag${prefs.includes(key) ? " selected" : ""}`}
                  onClick={() => toggleTag(prefs, setPrefs, key)}
                >
                  {emoji} {label}
                </button>
              ))}
            </div>

            <div className="ob-section-label" style={{ marginTop: 24 }}>🚫 我想避开</div>
            <div className="ob-tag-grid">
              {AVOID_TAGS.map(({ key, emoji, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`ob-tag avoid${avoids.includes(key) ? " selected-avoid" : ""}`}
                  onClick={() => toggleTag(avoids, setAvoids, key)}
                >
                  {emoji} {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 3：预算 + 城市 + 昵称 ── */}
        {step === 3 && (
          <div className="ob-step">
            <div className="ob-step-tag">第 3 步 / 共 3 步</div>
            <h1 className="ob-title">最后一点设置</h1>
            <p className="ob-subtitle">帮助 AI 更精准地匹配路线与价位</p>

            {/* 预算选择 */}
            <div className="ob-section-label">人均预算</div>
            <div className="ob-budget-grid">
              {BUDGETS.map(({ key, label, desc, range }) => (
                <button
                  key={key}
                  type="button"
                  className={`ob-budget-card${budgetLevel === key ? " selected" : ""}`}
                  onClick={() => setBudgetLevel(key)}
                >
                  <span className="ob-budget-label">{label}</span>
                  <span className="ob-budget-desc">{desc}</span>
                  <span className="ob-budget-range">{range}</span>
                </button>
              ))}
            </div>

            {/* 城市 */}
            <div className="ob-section-label" style={{ marginTop: 24 }}>所在城市</div>
            <div className="ob-city-grid">
              {CITIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`ob-tag${city === c ? " selected" : ""}`}
                  onClick={() => setCity(c)}
                >
                  {c}
                </button>
              ))}
            </div>

            {/* 昵称（可选） */}
            <div className="ob-section-label" style={{ marginTop: 24 }}>
              你的昵称
              <span className="ob-optional">（可选）</span>
            </div>
            <input
              className="ob-input"
              type="text"
              placeholder="例如：爱吃的小明"
              maxLength={20}
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
          </div>
        )}
      </div>

      {/* 底部操作区 */}
      <div className="ob-footer">
        {step > 1 && (
          <button
            type="button"
            className="ob-btn-back"
            onClick={() => setStep((s) => s - 1)}
          >
            ← 上一步
          </button>
        )}
        {step < TOTAL_STEPS ? (
          <button
            type="button"
            className="ob-btn-next"
            disabled={!canNext()}
            onClick={() => setStep((s) => s + 1)}
          >
            下一步 →
          </button>
        ) : (
          <button
            type="button"
            className="ob-btn-done"
            onClick={handleFinish}
          >
            🚀 开始规划路线
          </button>
        )}
      </div>
    </div>
  );
}
