/**
 * useOnboarding
 * 管理首次进入时的用户画像填写流程。
 * 数据持久化到 localStorage，避免每次刷新都要重填。
 *
 * 设计说明：
 *  - OnboardingProfile   长期偏好画像（出行场景、偏好、预算偏好）
 *  - TripConstraints     当次出行约束（城市、人数、时长、本次预算）—— 不持久化，每次规划前填写
 */

export interface OnboardingProfile {
  user_id: string;
  nickname?: string;           // 用户昵称
  scenarios: string[];        // 出行场景（多选）
  scenario: string;           // 兼容后端单字段，取 scenarios[0]
  preferences: string[];      // 偏好标签
  avoid_tags: string[];       // 避开标签
  budget_level: "low" | "mid" | "high" | "flex";
  preference_weights: {
    quality: number;
    queue: number;
    distance: number;
    budget: number;
    preference: number;
  };
}

/** 当次出行约束 — 每次规划时临时填写，不持久化到 localStorage */
export interface TripConstraints {
  city: string;                    // 出行城市
  location: string;                // 出发位置（更具体的地址）
  people: number;                  // 出行人数
  duration: number;                // 时长（小时，保留作兼容字段）
  start_time: string;              // 出发时间（如 "10:00"），空字符串表示不填
  end_time: string;                // 结束时间（如 "18:00"），空字符串表示不填
  budget_per_person: number | null; // 本次人均预算（元），null 表示不限
  today_goals: string[];           // 今天想玩什么（场景标签，可多选）
}

export const DEFAULT_TRIP_CONSTRAINTS: TripConstraints = {
  city: "",          // 不预设城市，由后端追问或从消息中提取
  location: "",      // 不预设出发地，由后端追问或 GPS 获取
  people: 2,
  duration: 3,
  start_time: "",
  end_time: "",
  budget_per_person: null,
  today_goals: [],
};

const STORAGE_KEY = "tos_onboarding_profile";
const ANDY_USER_ID = "user_andy";
const ANDY_NICKNAME = "Andy";

type OnboardingProfilePatch = Omit<Partial<OnboardingProfile>, "preference_weights"> & {
  preference_weights?: Partial<OnboardingProfile["preference_weights"]>;
};

/** 根据偏好标签和预算档位动态计算 preference_weights */
export function buildWeights(
  preferences: string[],
  budget_level: "low" | "mid" | "high" | "flex",
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
    if (!raw) return null;
    const profile = JSON.parse(raw) as OnboardingProfile;
    // Demo 统一使用 Andy 的用户档案；迁移旧的“小桃”/匿名本地记录，保留其已有偏好。
    if (profile.user_id !== ANDY_USER_ID || !profile.nickname || profile.nickname === "小桃") {
      const andyProfile = { ...profile, user_id: ANDY_USER_ID, nickname: ANDY_NICKNAME };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(andyProfile));
      return andyProfile;
    }
    return profile;
  } catch {
    return null;
  }
}

/** 保存画像到 localStorage */
export function saveProfile(partial: Partial<OnboardingProfile>): OnboardingProfile {
  const scenarios = partial.scenarios ?? [];
  const preferences = partial.preferences ?? [];
  const budget_level = partial.budget_level ?? "flex";

  const profile: OnboardingProfile = {
    scenarios,
    scenario:     scenarios[0] ?? "citywalk",   // 向后兼容
    preferences,
    avoid_tags:   partial.avoid_tags ?? [],
    budget_level,
    ...partial,
    // 统一写入 Andy 的用户身份，防止提交表单时被传入值覆盖。
    user_id:      ANDY_USER_ID,
    nickname:     ANDY_NICKNAME,
    // 强制覆盖计算字段
    preference_weights: buildWeights(preferences, budget_level),
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  return profile;
}

/** 更新画像的部分字段（反馈后调用） */
export function updateProfile(patch: OnboardingProfilePatch): OnboardingProfile | null {
  const current = loadProfile();
  if (!current) return null;

  const merged: OnboardingProfile = {
    ...current,
    ...patch,
    preference_weights: current.preference_weights,
  };

  // 先按当前偏好和预算计算基础权重，再叠加反馈 patch。
  const baseWeights = buildWeights(merged.preferences, merged.budget_level);
  merged.preference_weights = {
    ...baseWeights,
    ...(patch.preference_weights ?? {}),
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

/** 清除画像 */
export function clearProfile() {
  localStorage.removeItem(STORAGE_KEY);
}
