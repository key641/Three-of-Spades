with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the system prompt by anchor
anchor = '"你是路线规划 Agent 的消息路由器，只输出 JSON。"'
idx = content.find(anchor)
if idx < 0:
    print("Anchor not found")
    exit()

# Find the end of the system prompt dict (closing brace with comma on its own line)
end_anchor = '                },'
end_idx = content.index(end_anchor, idx)
# Find the next line
next_end = content.index("\n", end_idx)
end_idx = content.index(end_anchor, next_end)

# Build the enhanced prompt
route_keywords = [
    "路线", "规划", "行程", "出行", "旅游", "旅行", "游玩", "推荐",
    "去哪", "哪里玩", "怎么玩", "适合", "户外", "漫步", "散步",
    "景点", "餐厅", "咖啡", "拍照", "预算", "排队", "便宜", "省钱",
    "亲子", "朋友", "情侣", "小时", "分钟", "上午", "下午", "晚上",
    "citywalk", "打卡", "网红", "半日游", "一日游", "半日", "一日", "周末",
    "今天", "明天", "吃", "逛", "玩", "游",
]

new_prompt = """                {
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的消息路由器，只输出 JSON。"
                        "intent_type 只能是 new_plan、modify_plan、replan、route_detail_question、general_chat。"
                        "turn_type 只能是 new_plan、add_constraint、modify_constraint、remove_constraint、route_detail、general_chat。"
                        "planning_mode 只能是 new_plan、full_replan、partial_replan、route_detail、general_chat。"
                        "必须输出 confidence、reason、evidence。evidence 是用户原话里的关键短语数组。"
                        "candidate_planning_modes 只在确实无法区分多个方式时输出；原话已明确则不输出。"
                        ""
                        "## 领域知识（判断参考）"
                        "以下关键词高度暗示用户想规划/修改路线，不是闲聊："
                        "路线、规划、行程、出行、旅游、旅行、游玩、推荐、去哪、哪里玩、怎么玩、景点、餐厅、咖啡、拍照、"
                        "户外、漫步、散步、citywalk、打卡、网红、半日游、一日游、半日、一日、周末、今天、明天、"
                        "小时、分钟、上午、下午、晚上、吃、逛、玩、游、亲子、朋友、情侣、预算、排队、便宜、省钱"
                        "注意：即使不命中上述关键词，只要表达了出行/游玩意图，也应判为 new_plan。"
                        ""
                        "## 各意图判断指引"
                        "- route_detail_question：消息含"刚刚/上一条/这条路" + "怎么去/多久/费用"，且 has_current_routes=true。"
                        "- add_constraint：消息含追加词（还要、也要、还想、也想、加一个、顺便）+ 约束词（吃饭、餐厅、拍照、少排队、省钱），且 has_previous_intent=true。inherit_previous=true，preserve_scenario=true。"
                        "- full_replan：消息含整体偏好调整（更省钱、便宜一点、少排队、少走路、亲子友好、适合拍照、整体不满意、重新生成、重新规划、换个路线），且 has_previous_intent=true。inherit_previous=true。"
                        "- partial_replan：消息含局部替换或突发状况（换一家、换掉、不喜欢这家、第二站、下雨、堵车、关门、排队+分钟数），且 has_current_routes=true。inherit_previous=true。"
                        "- new_plan：首次规划，或消息包含城市+目标+时间等完整出行描述，或无任何历史上下文。"
                        "- general_chat：纯打招呼、感谢、问天气等与路线规划完全无关。"
                        ""
                        "## 示例"
                        "示例：用户说"重新生成路线" -> planning_mode=full_replan，confidence>=0.8。"
                        "示例：用户说"只替换这个地点" -> intent_type=replan，planning_mode=partial_replan，confidence>=0.8。"
                        "示例：用户说"换个便宜点的" -> candidate_planning_modes=[full_replan,partial_replan]，confidence<0.5。"
                        "示例：用户说"半日游" -> new_plan，confidence>=0.8。"
                        "示例：用户说"上海一日游拍照" -> new_plan，confidence>=0.9。"
                        "示例：用户说"还要吃饭" -> add_constraint，inherit_previous=true，preserve_scenario=true。"
                    ),
                },"""

# Now find and replace
# The system prompt starts at idx and ends at end_idx
# Find the actual start of the dict
start = content.rfind("                {", 0, idx)
actual_end = content.index("                },", end_idx) + len("                },")

old_block = content[start:actual_end]
content = content[:start] + new_prompt + content[actual_end:]

with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Router prompt enhanced OK")
print(f"New prompt length: {len(new_prompt)}")
