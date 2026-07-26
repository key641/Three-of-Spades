with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the exact line to insert after
for i, line in enumerate(lines):
    if line.strip() == '"citywalk",':
        # Insert new keywords after citywalk
        new_kws = [
            '            "半日游",\n',
            '            "一日游",\n',
            '            "半日",\n',
            '            "一日",\n',
            '            "周末",\n',
            '            "今天",\n',
            '            "明天",\n',
            '            "今晚",\n',
            '            "打卡",\n',
            '            "网红",\n',
            '            "吃",\n',
            '            "游",\n',
        ]
        for j, kw in enumerate(new_kws):
            lines.insert(i + 1 + j, kw)
        print(f"Inserted {len(new_kws)} keywords after line {i+1}")
        break

with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done")
