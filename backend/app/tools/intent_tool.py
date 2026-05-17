from app.schemas.intent import Intent


def parse_user_intent(message: str) -> Intent:
    # TODO(A): replace with LLM structured output.
    return Intent(
        city="上海",
        people_count=3,
        start_time="14:00",
        duration_hours=6,
        budget_per_person=300,
        preferences=["吃好", "少排队", "拍照"],
        avoid_tags=["排队久", "太贵"],
        scenario="friends_citywalk",
    )

