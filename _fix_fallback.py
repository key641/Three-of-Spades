with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add missing keywords to _looks_like_route_related
old_route_kw = """            "citywalk",
            "逛",
            "玩",
            "游","""

new_route_kw = """            "citywalk",
            "逛",
            "玩",
            "游",
            "半日游",
            "一日游",
            "半日",
            "一日",
            "今天",
            "明天",
            "今晚",
            "打卡",
            "网红",
            "吃", """

if old_route_kw in content:
    content = content.replace(old_route_kw, new_route_kw, 1)
    print("Fallback keywords updated OK")
else:
    print("Keywords NOT FOUND")

# 2. Fix the _looks_like_route_related branch: when no routes, treat as NEW_PLAN
old_fallback = """        if self._looks_like_route_related(text):
            intent_type = MessageIntentType.MODIFY_PLAN if state.last_intent else MessageIntentType.NEW_PLAN
            return MessageRoute(
                intent_type=intent_type,
                turn_type=TurnType.MODIFY_CONSTRAINT if state.last_intent else TurnType.NEW_PLAN,
                planning_mode=PlanningMode.FULL_REPLAN if state.last_intent else PlanningMode.NEW_PLAN,
                confidence=0.45,
                references_previous_route=state.last_intent is not None,
                inherit_previous=state.last_intent is not None,
            )"""

new_fallback = """        if self._looks_like_route_related(text):
            # 没有已生成路线 且 消息像独立新规划 → NEW_PLAN，不继承脏上下文
            has_routes = bool(state.current_routes)
            looks_standalone = self._looks_like_new_plan_spec(text)
            if not has_routes and (looks_standalone or not state.last_intent):
                return MessageRoute(
                    intent_type=MessageIntentType.NEW_PLAN,
                    turn_type=TurnType.NEW_PLAN,
                    planning_mode=PlanningMode.NEW_PLAN,
                    confidence=0.55 if looks_standalone else 0.45,
                    inherit_previous=False,
                )
            intent_type = MessageIntentType.MODIFY_PLAN if state.last_intent else MessageIntentType.NEW_PLAN
            return MessageRoute(
                intent_type=intent_type,
                turn_type=TurnType.MODIFY_CONSTRAINT if state.last_intent else TurnType.NEW_PLAN,
                planning_mode=PlanningMode.FULL_REPLAN if state.last_intent else PlanningMode.NEW_PLAN,
                confidence=0.45,
                references_previous_route=state.last_intent is not None,
                inherit_previous=state.last_intent is not None,
            )"""

if old_fallback in content:
    content = content.replace(old_fallback, new_fallback, 1)
    print("Fallback route_related branch updated OK")
else:
    print("Fallback NOT FOUND")
    idx = content.find("_looks_like_route_related(text)")
    if idx >= 0:
        print(content[idx:idx+300])

# 3. Add _looks_like_new_plan_spec helper
old_general_chat = """        return MessageRoute(
            intent_type=MessageIntentType.GENERAL_CHAT,"""

# Find the end of _looks_like_route_related method
helper_code = """
    def _looks_like_new_plan_spec(self, text: str) -> bool:
        \"\"\"判断消息是否像独立新规划（含城市+目标或时间）。\"\"\"
        # 有城市名
        cities = [
            "上海", "北京", "杭州", "成都", "广州", "深圳",
            "南京", "苏州", "重庆", "武汉", "西安", "长沙",
        ]
        has_city = any(c in text for c in cities)
        # 有出行目标
        goal_terms = ["游", "玩", "逛", "吃", "拍照", "打卡", "景点", "citywalk",
                      "一日", "半日", "周末", "今天", "明天", "户外", "漫步"]
        has_goal = any(t in text for t in goal_terms)
        # 有时间
        import re
        has_time = bool(re.search(r"\\d{1,2}\\s*[点:：]|上午|下午|晚上|小时", text))
        return has_city or has_goal or has_time
"""

insert_pos = content.find(old_general_chat)
if insert_pos >= 0:
    content = content[:insert_pos] + helper_code + "\n" + content[insert_pos:]
    print("Helper method added OK")
else:
    print("Insert position not found")

with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
    f.write(content)
