// POI 分类：英文 key → 中文标签
export const CATEGORY_LABELS: Record<string, string> = {
  // API 返回的英文 key
  cafe:       "咖啡馆",
  restaurant: "餐厅",
  scenic:     "景点",
  bar:        "酒吧",
  museum:     "博物馆",
  park:       "公园",
  shopping:   "购物",
  snack:      "小吃",
  hotel:      "酒店",
  transport:  "交通",
  // 兼容中文 key（与首页一致）
  景点: "景点",
  美食: "美食",
  购物: "购物",
  娱乐: "娱乐",
  运动: "运动",
  文化: "文化",
  自然: "自然",
};

// 分类颜色（与首页 POI_CATEGORY_COLORS 保持一致）
export const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  cafe:       { bg: "rgba(255, 122, 77, 0.1)",  text: "#FF7A4D", border: "rgba(255, 122, 77, 0.25)"  },
  restaurant: { bg: "rgba(255, 122, 77, 0.1)",  text: "#FF7A4D", border: "rgba(255, 122, 77, 0.25)"  },
  snack:      { bg: "rgba(255, 122, 77, 0.1)",  text: "#FF7A4D", border: "rgba(255, 122, 77, 0.25)"  },
  scenic:     { bg: "rgba(79, 168, 232, 0.1)",  text: "#4FA8E8", border: "rgba(79, 168, 232, 0.25)"  },
  museum:     { bg: "rgba(99, 102, 241, 0.1)",  text: "#6366F1", border: "rgba(99, 102, 241, 0.25)"  },
  park:       { bg: "rgba(52, 211, 153, 0.1)",  text: "#10B981", border: "rgba(52, 211, 153, 0.25)"  },
  shopping:   { bg: "rgba(245, 158, 11, 0.1)",  text: "#F59E0B", border: "rgba(245, 158, 11, 0.25)"  },
  bar:        { bg: "rgba(132, 94, 194, 0.1)",  text: "#845EC2", border: "rgba(132, 94, 194, 0.25)"  },
  hotel:      { bg: "rgba(156, 163, 175, 0.1)", text: "#6B7280", border: "rgba(156, 163, 175, 0.25)" },
  transport:  { bg: "rgba(156, 163, 175, 0.1)", text: "#6B7280", border: "rgba(156, 163, 175, 0.25)" },
  // 兼容中文 key
  景点: { bg: "rgba(79, 168, 232, 0.1)",  text: "#4FA8E8", border: "rgba(79, 168, 232, 0.25)"  },
  美食: { bg: "rgba(255, 122, 77, 0.1)",  text: "#FF7A4D", border: "rgba(255, 122, 77, 0.25)"  },
  购物: { bg: "rgba(245, 158, 11, 0.1)",  text: "#F59E0B", border: "rgba(245, 158, 11, 0.25)"  },
  娱乐: { bg: "rgba(132, 94, 194, 0.1)",  text: "#845EC2", border: "rgba(132, 94, 194, 0.25)"  },
  运动: { bg: "rgba(16, 185, 129, 0.1)",  text: "#10B981", border: "rgba(16, 185, 129, 0.25)"  },
  文化: { bg: "rgba(99, 102, 241, 0.1)",  text: "#6366F1", border: "rgba(99, 102, 241, 0.25)"  },
  自然: { bg: "rgba(52, 211, 153, 0.1)",  text: "#34D399", border: "rgba(52, 211, 153, 0.25)"  },
};

export function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function getCategoryStyle(category: string): { bg: string; text: string; border: string } {
  return CATEGORY_COLORS[category] ?? { bg: "rgba(156,163,175,0.1)", text: "#6B7280", border: "rgba(156,163,175,0.25)" };
}
