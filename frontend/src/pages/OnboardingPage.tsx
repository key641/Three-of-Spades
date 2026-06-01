import React, { useRef, useState } from "react";
import { Footprints, UtensilsCrossed, Landmark, Ticket, MapPin, Baby, TreePine, ShoppingBag, Dices, Check } from "lucide-react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { saveProfile } from "../hooks/useOnboarding";

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
  const [scenarios,   setScenarios]   = useState<string[]>([]);
  const [prefs,       setPrefs]       = useState<string[]>([]);
  const [avoids,      setAvoids]      = useState<string[]>([]);

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
      scenarios,
      scenario: scenarios[0] ?? "citywalk",
      preferences: prefs,
      avoid_tags: avoids,
      budget_level: "flex",
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
