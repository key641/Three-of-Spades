with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    content = f.read()

# Build the enhanced system prompt
old_prompt_start = """                {
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的消息路由器，只输出 JSON。"
                        "intent_type 只能是 new_plan、modify_plan、replan、route_detail_question、general_chat。"
                        "turn_type 只能是 new_plan、add_constraint、modify_constraint、remove_constraint、route_detail、general_chat。"
                        "planning_mode 只能是 new_plan、full_replan、partial_replan、route_detail、general_chat。"
                        "必须输出 confidence、reason、evidence。evidence 是用户原话里的关键短语数组。"
                        "candidate_planning_modes 只在用户原话确实无法区分多个规划方式时输出；如果原话已经明确，不要输出候选。"
                        "route_detail_question 表示用户在问上一轮已生成路线的细节，例如两点之间怎么去、某站排队多久、费用多少。"
                        "modify_plan 表示用户要修改上一轮路线并重新规划。"
                        "full_replan 表示基于偏好或整体目标重新生成一组候选方案，例如重新生成路线、重新规划、换一条路线、更省钱、少排队、整体不满意。"
                        "partial_replan 表示保留原方案并局部替换或调整，例如只替换这个地点、换一家、不喜欢这家、第二站换掉、下雨、堵车、关门、排队90分钟。"
                        "add_constraint 表示用户在上一轮基础上追加需求，例如"还要吃饭""也想拍照""加一个餐厅"，必须 inherit_previous=true。"
                        "如果只是追加需求而不是切换主题，preserve_scenario=true；只有"改成美食路线""只想吃吃喝喝"这类明确切换才 preserve_scenario=false。"
                        "示例1：用户说"重新生成路线"，输出 planning_mode=full_replan，candidate_planning_modes=[]，confidence>=0.8。"
                        "示例2：用户说"只替换这个地点"，输出 intent_type=replan，planning_mode=partial_replan，candidate_planning_modes=[]，confidence>=0.8。"
                        "示例3：用户说"换个便宜点的"，可能是全量重规划也可能是局部替换，输出 candidate_planning_modes=[\"full_replan\",\"partial_replan\"]，confidence<0.5。"
                    ),
                },"""

# Collect all keywords from _fallback_classify
route_keywords = [
    "路线", "规划", "行程", "出行", "旅游", "旅行", "游玩", "推荐", "有推荐",
    "去哪", "哪里玩", "怎么玩", "适合", "户外", "漫步", "散步", "城市漫步",
    "景点", "餐厅", "咖啡", "拍照", "预算", "排队", "便宜", "省钱",
    "亲子", "朋友", "情侣", "人均", "小时", "分钟", "上午", "下午", "晚上",
    "半日游", "一日游", "半日", "一日", "周末", "今天", "明天", "晚上",
    "吃", "逛", "玩", "游", "citywalk", "打卡", "网红",
]

add_constraint_hints = "还要、也要、还想、也想、加一个、加个、加上、顺便、安排 + 吃饭/餐厅/美食/小吃/咖啡/拍照/打卡/少排队/省钱"

full_replan_hints = "更省钱、便宜一点、预算低、少排队、不排队、少走路、亲子友好、适合拍照、整体不满意、重新生成、重新规划、换个路线、换一条路线、不要商业街、吃好一点"

partial_replan_hints = "换一家、换个店、换一个店、换掉、替换、不喜欢这家、不想去这家、这家太贵、这家不好、这个地方不想去、第二站、第三站、当前路线、这条路线、下雨、雨天、堵车、交通堵、关门、闭店、临时关闭、等位、太累、累了、走不动"

route_detail_hints = "怎么过去、怎么去、如何过去、如何去 + 刚刚/上面/上一条/这个路线/这条路线/那俩/两个地点/两地"

new_prompt = f"""                {{
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的消息路由器，只输出 JSON。"
                        "intent_type 只能是 new_plan、modify_plan、replan、route_detail_question、general_chat。"
                        "turn_type 只能是 new_plan、add_constraint、modify_constraint、remove_constraint、route_detail、general_chat。"
                        "planning_mode 只能是 new_plan、full_replan、partial_replan、route_detail、general_chat。"
                        "必须输出 confidence、reason、evidence。evidence 是用户原话里的关键短语数组。"
                        "candidate_planning_modes 只在确实无法区分多个方式时输出；原话已明确则不输出。"
                        ""
                        "## 领域知识（作为判断参考）"
                        "以下关键词高度暗示用户想规划/修改路线，不是闲聊："
                        "{", ".join(route_keywords[:25])}"
                        "{", ".join(route_keywords[25:])}"
                        "注意：即使不命中上述关键词，如果用户表达了出行/游玩意图，也应判为 new_plan。"
                        ""
                        "## 各意图判断指引"
                        "- route_detail_question：消息含"刚刚/上一条/这个路线/这条路线 + 怎么去/多久/费用"，且 has_current_routes=true。"
                        "- add_constraint：消息含追加词({add_constraint_hints})，且 has_previous_intent=true。inherit_previous=true，preserve_scenario=true。"
                        "- full_replan：消息含整体偏好调整({full_replan_hints})，且 has_previous_intent=true。inherit_previous=true，preserve_scenario=true。"
                        "- partial_replan：消息含局部替换或突发状况({partial_replan_hints})，且 has_current_routes=true。inherit_previous=true，preserve_scenario=true。"
                        "- new_plan：首次规划，或消息明确包含城市+目标+时间等完整出行描述，或没有任何历史上下文。"
                        "- general_chat：纯打招呼、感谢、问天气等与路线规划完全无关。"
                        ""
                        "## 示例"
                        "示例1：用户说"重新生成路线"，输出 planning_mode=full_replan，confidence>=0.8。"
                        "示例2：用户说"只替换这个地点"，输出 intent_type=replan，planning_mode=partial_replan，confidence>=0.8。"
                        "示例3：用户说"换个便宜点的"，可能是全量重规划也可能是局部替换，输出 candidate_planning_modes=[\"full_replan\",\"partial_replan\"]，confidence<0.5。"
                        "示例4：用户说"半日游"，即使没有历史上下文，也应判为 new_plan，confidence>=0.8。"
                        "示例5：用户说"上海一日游拍照"，判为 new_plan，confidence>=0.9。"
                    ),
                }},"""

if old_prompt_start in content:
    content = content.replace(old_prompt_start, new_prompt, 1)
    with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Router prompt enhanced OK")
else:
    print("NOT FOUND")
    idx = content.find('"你是路线规划 Agent 的消息路由器')
    if idx >= 0:
        print(f"Found at {idx}")
        print(content[idx:idx+300])
