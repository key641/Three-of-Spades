import React, { useRef, useState, useEffect } from "react";
import { Footprints, UtensilsCrossed, Landmark, Ticket, MapPin, Baby, TreePine, ShoppingBag, Dices, Check } from "lucide-react";

import type { OnboardingProfile } from "../hooks/useOnboarding";
import { saveProfile } from "../hooks/useOnboarding";

// ── iOS 风格状态栏图标（与 App.tsx 同款 SVG） ──────────────
function IconCellular() {
  return (
    <svg width="17" height="11" viewBox="0 0 17 11" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M16 0H15C14.4477 0 14 0.447715 14 1V9.66667C14 10.219 14.4477 10.6667 15 10.6667H16C16.5523 10.6667 17 10.219 17 9.66667V1C17 0.447715 16.5523 0 16 0ZM10.3333 2.33333H11.3333C11.8856 2.33333 12.3333 2.78105 12.3333 3.33333V9.66667C12.3333 10.219 11.8856 10.6667 11.3333 10.6667H10.3333C9.78105 10.6667 9.33333 10.219 9.33333 9.66667V3.33333C9.33333 2.78105 9.78105 2.33333 10.3333 2.33333ZM6.66667 4.66667H5.66667C5.11438 4.66667 4.66667 5.11438 4.66667 5.66667V9.66667C4.66667 10.219 5.11438 10.6667 5.66667 10.6667H6.66667C7.21895 10.6667 7.66667 10.219 7.66667 9.66667V5.66667C7.66667 5.11438 7.21895 4.66667 6.66667 4.66667ZM2 6.66667H1C0.447715 6.66667 0 7.11438 0 7.66667V9.66667C0 10.219 0.447715 10.6667 1 10.6667H2C2.55228 10.6667 3 10.219 3 9.66667V7.66667C3 7.11438 2.55228 6.66667 2 6.66667Z" fill="currentColor"/>
    </svg>
  );
}
function IconWifi() {
  return (
    <svg width="16" height="11" viewBox="0 0 16 11" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M7.63661 2.27733C9.8525 2.27742 11.9837 3.12886 13.5896 4.65566C13.7105 4.77354 13.9038 4.77205 14.0229 4.65233L15.1789 3.48566C15.2392 3.42494 15.2729 3.34269 15.2724 3.25711C15.2719 3.17153 15.2373 3.08967 15.1763 3.02966C10.9612 -1.00989 4.31137 -1.00989 0.0962725 3.02966C0.0352139 3.08963 0.00057 3.17146 6.97078e-06 3.25704C-0.000556058 3.34262 0.0330082 3.42489 0.0932725 3.48566L1.24961 4.65233C1.36863 4.77223 1.56208 4.77372 1.68294 4.65566C3.28909 3.12876 5.4205 2.27732 7.63661 2.27733ZM7.63661 6.07299C8.8541 6.07292 10.0281 6.52545 10.9306 7.34266C11.0527 7.45864 11.245 7.45613 11.3639 7.33699L12.5186 6.17033C12.5794 6.10913 12.6132 6.02612 12.6123 5.93985C12.6114 5.85359 12.576 5.77127 12.5139 5.71133C9.76574 3.15494 5.5098 3.15494 2.76161 5.71133C2.69953 5.77127 2.66411 5.85363 2.6633 5.93992C2.66248 6.02621 2.69634 6.10922 2.75727 6.17033L3.91161 7.33699C4.03059 7.45613 4.22288 7.45864 4.34494 7.34266C5.24681 6.52599 6.41992 6.0735 7.63661 6.07299ZM9.9496 8.62681C9.95137 8.71332 9.91736 8.79672 9.85561 8.85733L7.85827 10.873C7.79972 10.9322 7.7199 10.9656 7.63661 10.9656C7.55332 10.9656 7.47349 10.9322 7.41494 10.873L5.41727 8.85733C5.35556 8.79668 5.32161 8.71325 5.32344 8.62674C5.32527 8.54023 5.36272 8.45831 5.42694 8.40033C6.70251 7.32144 8.5707 7.32144 9.84627 8.40033C9.91045 8.45836 9.94783 8.54031 9.9496 8.62681Z" fill="currentColor"/>
    </svg>
  );
}
function IconBattery() {
  return (
    <svg width="25" height="12" viewBox="0 0 25 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect opacity="0.35" x="0.5" y="0.5" width="21" height="10.3333" rx="2.16667" stroke="currentColor"/>
      <path opacity="0.4" d="M23 3.66663V7.66663C23.8047 7.32785 24.328 6.53976 24.328 5.66663C24.328 4.79349 23.8047 4.0054 23 3.66663Z" fill="currentColor"/>
      <rect x="2" y="2" width="18" height="7.33333" rx="1.33333" fill="currentColor"/>
    </svg>
  );
}

// ── 手机状态栏 ──────────────────────────────────────────────
function PhoneStatusBar() {
  const [time, setTime] = useState(() => {
    const now = new Date();
    return now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0");
  });

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0"));
    };
    const ms = (60 - new Date().getSeconds()) * 1000;
    const t = setTimeout(() => {
      tick();
      const interval = setInterval(tick, 60_000);
      return () => clearInterval(interval);
    }, ms);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="phone-status-bar">
      <span className="phone-status-time">{time}</span>
      <div className="phone-status-icons">
        <IconCellular />
        <IconWifi />
        <IconBattery />
      </div>
    </div>
  );
}

interface OnboardingPageProps {
  onDone: (profile: OnboardingProfile) => void;
}

// ── 数据配置 ──────────────────────────────────────────────────

const SCENARIOS: { key: string; icon: React.ReactNode; label: string; desc: string }[] = [
  { key: "citywalk",    icon: <Footprints size={20} strokeWidth={1.5} />, label: "街头漫游",  desc: "咖啡馆、集市、新店探索" },
  { key: "foodie",      icon: <UtensilsCrossed size={20} strokeWidth={1.5} />, label: "美食探店",  desc: "打卡餐厅、特色小吃、网红店" },
  { key: "culture",     icon: <Landmark size={20} strokeWidth={1.5} />, label: "文化艺术",  desc: "博物馆、美术馆、图书馆" },
  { key: "show_event",  icon: <Ticket size={20} strokeWidth={1.5} />, label: "演出活动",  desc: "演唱会、展览、赛事" },
  { key: "landmark",    icon: <MapPin size={20} strokeWidth={1.5} />, label: "热门景点",  desc: "城市地标、热门打卡" },
  { key: "family",      icon: <Baby size={20} strokeWidth={1.5} />, label: "亲子家庭",  desc: "乐园、科普场馆、亲子公园" },
  { key: "nature",      icon: <TreePine size={20} strokeWidth={1.5} />, label: "自然放松",  desc: "公园、露营、赏花、郊野" },
  { key: "shopping",    icon: <ShoppingBag size={20} strokeWidth={1.5} />, label: "逛街购物",  desc: "商场、潮流街区、品牌集合店" },
  { key: "freestyle",   icon: <Dices size={20} strokeWidth={1.5} />, label: "随心而行",  desc: "随机探索" },
];

// 偏好标签 — 按维度分组
const PREF_GROUPS: { group: string; emoji: string; tags: { key: string; label: string }[] }[] = [
  {
    group: "时间效率",
    emoji: "⏱",
    tags: [
      { key: "少排队",    label: "少排队" },
      { key: "路程紧凑",  label: "路程紧凑" },
      { key: "节奏慢",    label: "节奏慢" },
      { key: "特种兵", label: "特种兵" },
    ],
  },
  {
    group: "出行方式",
    emoji: "🚇",
    tags: [
      { key: "公交方便",  label: "公交方便" },
      { key: "少换乘",    label: "少换乘" },
      { key: "步行citywalk",  label: "步行citywalk" },
      { key: "自驾出行",    label: "自驾出行" },
    ],
  },
  {
    group: "消费偏好",
    emoji: "💰",
    tags: [
      { key: "性价比高",  label: "性价比高" },
      { key: "服务优先",  label: "服务优先" },
      { key: "体验优先",  label: "体验优先" },
    ],
  },
  {
    group: "体验风格",
    emoji: "✨",
    tags: [
      { key: "人少景美",  label: "人少景美" },
      { key: "热门打卡",  label: "热门打卡" },
      { key: "新鲜事物",  label: "新鲜事物" },
      { key: "小众特色",  label: "小众特色" },
      { key: "适合拍照",  label: "适合拍照" },
      { key: "室内为主",  label: "室内为主" },
      { key: "亲子友好",  label: "亲子友好" },
    ],
  },
];

const AVOID_TAGS: { key: string; emoji: string; label: string }[] = [
  { key: "人多",   emoji: "👥", label: "人太多" },
  { key: "商业街", emoji: "🏬", label: "商业街" },
  { key: "贵",     emoji: "💸", label: "消费贵" },
  { key: "辣",     emoji: "🌶️", label: "辣的食物" },
  { key: "需排队", emoji: "⏳", label: "需要排队" },
  { key: "太远",   emoji: "📏", label: "距离太远" },
  { key: "体力消耗大", emoji: "💦", label: "体力消耗大" },
];

const TOTAL_STEPS = 2;

// ── 自定义标签输入组件 ────────────────────────────────────────
interface CustomTagInputProps {
  placeholder: string;
  onAdd: (tag: string) => void;
  isAvoid?: boolean;
}

function CustomTagInput({ placeholder, onAdd, isAvoid = false }: CustomTagInputProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function handleOpen() {
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  function handleConfirm() {
    const trimmed = value.trim();
    if (trimmed) {
      onAdd(trimmed);
      setValue("");
    }
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") { e.preventDefault(); handleConfirm(); }
    if (e.key === "Escape") { setValue(""); setEditing(false); }
  }

  if (!editing) {
    return (
      <button
        type="button"
        className={`ob-tag ob-tag-add${isAvoid ? " avoid" : ""}`}
        onClick={handleOpen}
      >
        + 自定义
      </button>
    );
  }

  return (
    <span className="ob-tag-input-wrap">
      <input
        ref={inputRef}
        className="ob-tag-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleConfirm}
        placeholder={placeholder}
        maxLength={12}
      />
    </span>
  );
}

// ── 主组件 ───────────────────────────────────────────────────

export function OnboardingPage({ onDone }: OnboardingPageProps) {
  const [step, setStep] = useState(1);
  const [nickname,    setNickname]    = useState("");
  const [scenarios,   setScenarios]   = useState<string[]>([]);
  const [prefs,       setPrefs]       = useState<string[]>([]);
  const [avoids,      setAvoids]      = useState<string[]>([]);
  const [saving,      setSaving]      = useState(false);

  function toggleTag(list: string[], setList: (v: string[]) => void, key: string) {
    setList(list.includes(key) ? list.filter((t) => t !== key) : [...list, key]);
  }

  function addCustomPref(tag: string) {
    if (!prefs.includes(tag)) setPrefs((prev) => [...prev, tag]);
  }

  function addCustomAvoid(tag: string) {
    if (!avoids.includes(tag)) setAvoids((prev) => [...prev, tag]);
  }

  function canNext() {
    if (step === 1) return scenarios.length >= 1;
    if (step === 2) return prefs.length >= 1;
    return true;
  }

  function handleFinish() {
    const profile = saveProfile({
      nickname: nickname.trim() || undefined,
      scenarios,
      scenario: scenarios[0] ?? "citywalk",
      preferences: prefs,
      avoid_tags: avoids,
      budget_level: "flex",
    });
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      onDone(profile);
    }, 2000);
  }

  return (
    <div className="ob-shell">
      {/* 保存偏好加载遮罩 */}
      {saving && (
        <div className="ob-saving-mask">
          <div className="ob-saving-spinner" />
          <p className="ob-saving-text">正在保存你的偏好…</p>
        </div>
      )}

      {/* 手机状态栏 */}
      <PhoneStatusBar />

      {/* 顶部进度条 */}
      <div className="ob-progress">
        <div className="ob-progress-bar" style={{ width: `${(step / TOTAL_STEPS) * 100}%` }} />
      </div>

      {/* 内容区 */}
      <div className="ob-content">
        {/* ── Step 1：选择出行场景 ── */}
        {step === 1 && (
          <div className="ob-step">
            <div className="ob-step-tag">第 1 步 / 共 2 步</div>
            <h1 className="ob-title">你平时出门喜欢怎么玩？</h1>
            <p className="ob-subtitle">可多选，仅作参考 — 不会限制你的路线选择，随时可以改</p>
            <div className="ob-scenario-grid">
              {SCENARIOS.map(({ key, icon, label, desc }) => (
                <button
                  key={key}
                  type="button"
                  className={`ob-scenario-card${scenarios.includes(key) ? " selected" : ""}${key === "freestyle" ? " ob-scenario-card--full" : ""}`}
                  onClick={() => toggleTag(scenarios, setScenarios, key)}
                >
                  <span className="ob-scenario-icon">{icon}</span>
                  <span className="ob-scenario-label">{label}</span>
                  <span className="ob-scenario-desc">{desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 2：结构化偏好 + 避开 ── */}
        {step === 2 && (
          <div className="ob-step">
            <div className="ob-step-tag">第 2 步 / 共 2 步</div>
            <h1 className="ob-title">你的出行偏好</h1>
            <p className="ob-subtitle">至少选 1 个，帮助 AI 排出更准的路线（可多选）</p>

            {/* ✅ 我喜欢 — 分维度展示 */}
            <div className="ob-pref-section-label">✅ 我喜欢</div>
            {PREF_GROUPS.map(({ group, emoji, tags }) => (
              <div key={group} className="ob-pref-group">
                <div className="ob-pref-group-title">{emoji} {group}</div>
                <div className="ob-tag-grid">
                  {tags.map(({ key, label }) => (
                    <button
                      key={key}
                      type="button"
                      className={`ob-tag${prefs.includes(key) ? " selected" : ""}`}
                      onClick={() => toggleTag(prefs, setPrefs, key)}
                    >
                      {label}
                    </button>
                  ))}
                  {/* 自定义输入只在最后一组(体验风格)显示，避免每组都有 */}
                  {group === "体验风格" && (
                    <CustomTagInput placeholder="输入偏好…" onAdd={addCustomPref} />
                  )}
                </div>
              </div>
            ))}

            {/* 已选自定义偏好标签展示 */}
            {prefs.filter((p) => !PREF_GROUPS.flatMap((g) => g.tags).map((t) => t.key).includes(p)).length > 0 && (
              <div className="ob-tag-grid" style={{ marginTop: 4 }}>
                {prefs
                  .filter((p) => !PREF_GROUPS.flatMap((g) => g.tags).map((t) => t.key).includes(p))
                  .map((p) => (
                    <button
                      key={p}
                      type="button"
                      className="ob-tag selected"
                      onClick={() => setPrefs((prev) => prev.filter((x) => x !== p))}
                    >
                      {p} ×
                    </button>
                  ))}
              </div>
            )}

            {/* 🚫 我想避开 */}
            <div className="ob-pref-section-label" style={{ marginTop: 28 }}>🚫 我想避开</div>
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
              <CustomTagInput placeholder="输入要避开的…" onAdd={addCustomAvoid} isAvoid />
            </div>

            {/* 已选自定义避开标签展示 */}
            {avoids.filter((a) => !AVOID_TAGS.map((t) => t.key).includes(a)).length > 0 && (
              <div className="ob-tag-grid" style={{ marginTop: 4 }}>
                {avoids
                  .filter((a) => !AVOID_TAGS.map((t) => t.key).includes(a))
                  .map((a) => (
                    <button
                      key={a}
                      type="button"
                      className="ob-tag selected-avoid"
                      onClick={() => setAvoids((prev) => prev.filter((x) => x !== a))}
                    >
                      {a} ×
                    </button>
                  ))}
              </div>
            )}
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
            ✅ 保存我的出行偏好
          </button>
        )}
      </div>
    </div>
  );
}
