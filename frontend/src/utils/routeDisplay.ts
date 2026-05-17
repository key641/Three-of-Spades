export function objectiveLabel(objective: string): string {
  const labels: Record<string, string> = {
    balanced: "综合最优",
    low_queue: "少排队",
    budget: "更省钱",
  };
  return labels[objective] ?? objective;
}

