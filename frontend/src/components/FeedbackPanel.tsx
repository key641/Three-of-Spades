import { Star } from "lucide-react";
import { useState } from "react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import { updateProfile } from "../hooks/useOnboarding";

interface FeedbackItem {
  key: string;
  emoji: string;
  label: string;
}

const ITEMS: FeedbackItem[] = [
  { key: "route",  emoji: "📍", label: "路线合理性" },
  { key: "food",   emoji: "🍽️", label: "餐厅满意度" },
  { key: "time",   emoji: "⏱️", label: "时间安排" },
  { key: "budget", emoji: "💰", label: "预算控制" },
  { key: "ai",     emoji: "🤖", label: "AI 准确度" },
];

interface FeedbackPanelProps {
  onProfileUpdated?: (profile: OnboardingProfile) => void;
}

/**
 * 根据评分结果调整 preference_weights：
 * - 预算评分低 (<3) → 提高 budget 权重（用户对预算更敏感）
 * - 排队/时间评分低 (<3) → 提高 queue 权重
 * - 路线/餐厅高分 (>=4) → 适当强化 quality/preference 权重
 */
function deriveWeightPatch(scores: Record<string, number>): Partial<OnboardingProfile["preference_weights"]> {
  const patch: Partial<OnboardingProfile["preference_weights"]> = {};
  if ((scores.budget ?? 3) < 3) patch.budget = 0.3;
  if ((scores.time   ?? 3) < 3) patch.queue  = 0.35;
  if ((scores.route  ?? 3) >= 4 && (scores.food ?? 3) >= 4) patch.quality = 0.35;
  return patch;
}

export function FeedbackPanel({ onProfileUpdated }: FeedbackPanelProps) {
  const [scores, setScores] = useState<Record<string, number>>({
    route: 4, food: 4, time: 4, budget: 4, ai: 4,
  });
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit() {
    const weightPatch = deriveWeightPatch(scores);
    const current = updateProfile({
      // 合并权重更新
      ...(Object.keys(weightPatch).length > 0
        ? { preference_weights: weightPatch as OnboardingProfile["preference_weights"] }
        : {}),
    });
    if (current) onProfileUpdated?.(current);
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="feedback-section">
        <p className="feedback-thanks">✅ 感谢反馈，偏好档案已更新！下次路线会更准 🎯</p>
      </div>
    );
  }

  return (
    <div className="feedback-section">
      <h2>这次行程怎么样？</h2>
      <div className="feedback-rows">
        {ITEMS.map(({ key, emoji, label }) => (
          <div className="feedback-row" key={key}>
            <span className="feedback-row-label">
              <span>{emoji}</span>
              {label}
            </span>
            <div className="star-rating">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  size={22}
                  className={`star ${star <= (scores[key] ?? 0) ? "filled" : ""}`}
                  onClick={() => setScores((prev) => ({ ...prev, [key]: star }))}
                  fill={star <= (scores[key] ?? 0) ? "#FACC15" : "none"}
                  strokeWidth={1.5}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <button className="feedback-submit" type="button" onClick={handleSubmit}>
        提交反馈
      </button>
    </div>
  );
}
