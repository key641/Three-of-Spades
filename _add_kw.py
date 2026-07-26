with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    c = f.read()

# Replace the existing citywalk line block with one that includes new keywords
old = """            "citywalk",
            "逛",
            "玩",
            "游","""

new = """            "citywalk",
            "半日游",
            "一日游",
            "半日",
            "一日",
            "周末",
            "今天",
            "明天",
            "今晚",
            "打卡",
            "网红",
            "吃",
            "逛",
            "玩",
            "游","""

if old in c:
    c = c.replace(old, new, 1)
    with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("Keywords added OK")
else:
    print("NOT FOUND, searching...")
    for kw in ["citywalk", "逛", "玩", "游"]:
        idx = c.find(f'"{kw}"')
        if idx >= 0:
            print(f'"{kw}" at {idx}: {c[idx:idx+30]}')
