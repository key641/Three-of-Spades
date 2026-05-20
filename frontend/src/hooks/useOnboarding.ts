/**
 * useOnboarding
 * 管理首次进入时的用户画像填写流程。
 * 数据持久化到 localStorage，避免每次刷新都要重填。
 */

export interface OnboardingProfile {
  user_id: string;
  nickname: string;
  city: string;
  scenarios: string[];        // 出行场景（多选）
  scenario: string;           // 兼容后端单字段，取 scenarios[0]
  preferences: string[];      // 偏好标签
  avoid_tags: string[];       // 避开标签
  budget_level: "low" | "mid" | "high";
  preference_weights: {
    quality: number;
    queue: number;
    distance: number;
    budget: number;
    preference: number;
  };
}

const STORAGE_KEY = "tos_onboarding_profile";

/** 根据偏好标签和预算档位动态计算 preference_weights */
export function buildWeights(
  preferences: string[],
  budget_level: "low" | "mid" | "high",
): OnboardingProfile["preference_weights"] {
  const queueBoost  = preferences.includes("少排队") ? 0.1 : 0;
  const budgetBoost = budget_level === "low" ? 0.1 : 0;
  const base = { quality: 0.3, queue: 0.25, distance: 0.2, budget: 0.15, preference: 0.1 };
  return {
    quality:    Math.max(0,   base.quality  - queueBoost / 2 - budgetBoost / 2),
    queue:      Math.min(0.5, base.queue    + queueBoost),
    distance:   base.distance,
    budget:     Math.min(0.4, base.budget   + budgetBoost),
    preference: base.preference,
  };
}

/** 从 localStorage 读取已有画像 */
export function loadProfile(): OnboardingProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as OnboardingProfile) : null;
  } catch {
    return null;
  }
}

/** 保存画像到 localStorage */
export function saveProfile(partial: Partial<OnboardingProfile>): OnboardingProfile {
  const scenarios = partial.scenarios ?? [];
  const preferences = partial.preferences ?? [];
  const budget_level = partial.budget_level ?? "mid";

  const profile: OnboardingProfile = {
    user_id:      `user_${Date.now()}`,
    nickname:     "旅行者",
    city:         "上海",
    scenarios,
    scenario:     scenarios[0] ?? "friends_citywalk",   // 向后兼容
    preferences,
    avoid_tags:   partial.avoid_tags ?? [],
    budget_level,
    ...partial,
    // 强制覆盖计算字段
    preference_weights: buildWeights(preferences, budget_level),
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  return profile;
}

/** 更新画像的部分字段（反馈后调用） */
export function updateProfile(patch: Partial<OnboardingProfile>): OnboardingProfile | null {
  const current = loadProfile();
  if (!current) return null;
  const merged = { ...current, ...patch };
  // 重新计算权重
  merged.preference_weights = buildWeights(merged.preferences, merged.budget_level);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

/** 清除画像 */
export function clearProfile() {
  localStorage.removeItem(STORAGE_KEY);
}
