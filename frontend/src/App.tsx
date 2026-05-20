import { useState } from "react";
import type { OnboardingProfile } from "./hooks/useOnboarding";
import { loadProfile } from "./hooks/useOnboarding";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PlannerPage } from "./pages/PlannerPage";

export default function App() {
  // 如果 localStorage 中已有画像，直接跳过 onboarding
  const [profile, setProfile] = useState<OnboardingProfile | null>(() => loadProfile());

  if (!profile) {
    return <OnboardingPage onDone={(p) => setProfile(p)} />;
  }

  return <PlannerPage profile={profile} onResetProfile={() => setProfile(null)} />;
}
