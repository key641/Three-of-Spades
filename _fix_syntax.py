with open(r"D:\Document\New project\backend\app\agent\message_router.py", "r", encoding="utf-8") as f:
    c = f.read()

# Fix the orphaned lines after the system prompt
old_orphan = """                    ),
                },
                        ensure_ascii=False,
                    ),
                },
            ],
            json_mode=True,
        )
        content = response["choices"][0]["message"]["content"]
        data = self._load_json_object(content)"""

new_correct = """                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": message,
                            "has_previous_intent": state.last_intent is not None,
                            "has_current_routes": bool(state.current_routes),
                            "previous_intent": state.last_intent.model_dump() if state.last_intent else None,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            json_mode=True,
        )
        content = response["choices"][0]["message"]["content"]
        data = self._load_json_object(content)"""

if old_orphan in c:
    c = c.replace(old_orphan, new_correct)
    with open(r"D:\Document\New project\backend\app\agent\message_router.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("Syntax fixed OK")
else:
    print("NOT FOUND")
    idx = c.find("ensure_ascii=False")
    if idx >= 0:
        print(c[idx-200:idx+200])
