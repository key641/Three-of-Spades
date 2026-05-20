export const CATEGORY_LABELS: Record<string, string> = {
  citywalk:   "City Walk",
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
};

export function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}
