"""
demo_mock.py — Demo 演示专用 Mock 数据层

当检测到特定 demo 场景时，绕过真实的 POI 召回 + 路线生成，
直接流式推送预设的 agent_trace（10秒内完成），再返回 mock 路线。

触发条件（任意一个）：
  - 消息中包含 demo 关键词（见 DEMO_TRIGGER_KEYWORDS）
  - ChatRequest.event_type == "demo"

注意：
  - 第一轮命中触发词但无 target_district → 直接返回预设区域追问卡片（build_demo_clarification）
  - 第二轮用户回答了区域后 → 触发 mock，流式推送 agent_trace + mock 路线
  - mock 路线仅限"北京聚餐/夜生活"场景，其他场景不拦截

各步骤延迟分布（总计约 10s）：
  route_message       0.4s
  parse_intent        1.2s  （模拟 LLM 解析耗时）
  apply_query_delta   0.6s
  apply_gps_start     0.3s
  get_user_profile    0.5s
  derive_strategy_tags 0.6s
  build_strategy_weights 0.5s
  search_pois         2.0s  （模拟召回耗时）
  generate_routes     3.0s  （模拟路线生成最耗时）
  summarize_routes    0.9s
"""

import asyncio
from collections.abc import Awaitable, Callable
from app.schemas.chat import AgentTraceStep, ChatResponse, ClarificationGroup, ClarificationOption
from app.schemas.intent import Intent
from app.schemas.route import Route, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile, StrategyWeights


# ── 总开关：False = 完全关闭所有 mock 拦截，走真实 Agent 流程 ─────────────────
DEMO_MOCK_ENABLED: bool = False

# ── 每步推送前的延迟（秒），总计约 10s ───────────────────────────────────────
TRACE_STEP_DELAYS: dict[str, float] = {
    "route_message":        0.4,
    "parse_intent":         1.2,
    "apply_query_delta":    0.6,
    "apply_gps_start":      0.3,
    "get_user_profile":     0.5,
    "derive_strategy_tags": 0.6,
    "build_strategy_weights": 0.5,
    "search_pois":          2.0,
    "generate_routes":      3.0,
    "summarize_routes":     0.9,
}


# ── Demo 触发关键词（命中任意一个即激活 mock 路线） ────────────────────────────
DEMO_TRIGGER_KEYWORDS: list[str] = [
    # 聚餐/美食
    "聚餐", "吃饭", "餐厅", "火锅", "烧烤", "海鲜", "大餐", "饭局",
    "朋友吃", "一起吃", "请客", "订餐", "美食探店",
    # 夜生活/烟火气
    "夜生活", "烟火气", "夜宵", "夜游", "夜晚", "晚上玩", "夜间",
    "酒吧", "livehouse", "LiveHouse", "夜市", "宵夜", "夜景",
    "城市烟火", "感受城市", "烟火",
]

# ── 检测是否命中 demo 触发词 ─────────────────────────────────────────────────
def is_demo_trigger(message: str) -> bool:
    if not DEMO_MOCK_ENABLED:
        return False
    return any(kw in message for kw in DEMO_TRIGGER_KEYWORDS)


# ── Mock RouteStop 构建器 ─────────────────────────────────────────────────────
def _stop(
    poi_id: str,
    name: str,
    category: str,
    address: str,
    lat: float,
    lng: float,
    start_time: str,
    end_time: str,
    cost: int,
    queue: int,
    tags: list[str],
    cover: str,
    highlight: str,
    ugc: str,
    travel_min: int | None = None,
    dist_km: float | None = None,
    transport: str | None = None,
    reason: str | None = None,
) -> RouteStop:
    return RouteStop(
        poi_id=poi_id,
        name=name,
        category=category,
        primary_category="food",
        secondary_categories=["food", "indoor"],
        route_roles=["meal"],
        experience_tags=["本地感", "老字号"],
        district="西城区",
        business_area="西单" if "西单" in address else "什刹海",
        address=address,
        lat=lat,
        lng=lng,
        start_time=start_time,
        end_time=end_time,
        estimated_cost=cost,
        queue_minutes=queue,
        tags=tags,
        meal_type="fine_dining",
        open_hours="11:00-22:00",
        last_entry_time="21:30",
        walking_intensity="low",
        cover_image_url=cover,
        highlight_text=highlight,
        ugc_tip=ugc,
        indoor=True,
        recommended_transport=["地铁", "步行"],
        travel_minutes_from_previous=travel_min,
        distance_km_from_previous=dist_km,
        transport_mode_from_previous=transport,
        reason=reason,
    )


# ── 预设 Mock 路线（西城区聚餐，3条） ──────────────────────────────────────────
def build_mock_routes(district: str = "西城区") -> list[Route]:
    """
    返回 3 条风格各异的西城区聚餐路线。
    district 参数预留，未来可按区域切换数据。
    """
    score_bd = RouteScoreBreakdown(quality=88, queue=82, budget=78, distance=90, preference=85)

    # ── 路线一：什刹海老字号聚餐 ──────────────────────────────────
    route1 = Route(
        route_id="demo_mock_route_001",
        title="什刹海老字号聚餐",
        objective="food_first",
        summary="以什刹海为核心，串联春山、旧庭两家老字号餐厅，人均 80-120，适合 6 人轻松聚餐，餐后可沿后海散步。",
        total_duration_minutes=150,
        total_cost_per_person=120,
        total_queue_minutes=15,
        total_travel_minutes=20,
        total_distance_km=1.8,
        score=88,
        score_breakdown=score_bd,
        stops=[
            _stop(
                poi_id="poi_bj_restaurant_001",
                name="春山餐厅",
                category="restaurant",
                address="烟袋斜街58号",
                lat=39.9197, lng=116.3726,
                start_time="12:00", end_time="13:30",
                cost=90, queue=10,
                tags=["什刹海", "老字号", "朋友聚餐", "本地感"],
                cover="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80",
                highlight="什刹海老字号，招牌老北京炸酱面，环境古朴雅致，适合6人聚餐",
                ugc="来了必点铜锅涮肉，服务很好，等位一般不超过10分钟",
                reason="老字号口碑稳，适合多人聚餐，人均90左右很划算",
            ),
            _stop(
                poi_id="poi_bj_restaurant_041",
                name="旧庭食社",
                category="restaurant",
                address="西城区护国寺街21号",
                lat=39.9369, lng=116.3703,
                start_time="13:50", end_time="15:00",
                cost=80, queue=5,
                tags=["西城区", "京味", "聚餐", "大包厢"],
                cover="https://images.unsplash.com/photo-1569050467447-ce54b3bbc37d?w=600&q=80",
                highlight="旧庭食社，北京传统风味，大包厢适合6-10人聚餐",
                ugc="环境超有感觉，可以提前预约包厢",
                travel_min=18, dist_km=1.7, transport="步行",
                reason="餐后步行可接后海散步，路线衔接自然",
            ),
        ],
        reasons=["什刹海周边老字号密集，人均适中", "步行路线串联，省去换乘烦恼", "餐后后海散步，体验完整"],
    )

    # ── 路线二：西单精致聚餐 ──────────────────────────────────────
    route2 = Route(
        route_id="demo_mock_route_002",
        title="西单精致聚餐",
        objective="balanced",
        summary="以西单商圈为核心，青苔西单食社 + 半日餐厅两家人气餐厅，人均 100-150，环境精致，适合节日聚餐或商务宴请。",
        total_duration_minutes=180,
        total_cost_per_person=150,
        total_queue_minutes=10,
        total_travel_minutes=15,
        total_distance_km=1.2,
        score=85,
        score_breakdown=RouteScoreBreakdown(quality=92, queue=80, budget=72, distance=92, preference=86),
        stops=[
            _stop(
                poi_id="poi_bj_restaurant_057",
                name="青苔西单食社",
                category="restaurant",
                address="西单北大街100号",
                lat=39.9012, lng=116.3754,
                start_time="12:00", end_time="13:30",
                cost=130, queue=8,
                tags=["西单", "精致", "聚餐", "朋友", "拍照"],
                cover="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80",
                highlight="青苔系餐厅西单旗舰店，主打创意本帮菜，环境时髦，出片率极高",
                ugc="装修超级好看，菜品颜值和口味都在线，建议提前预约",
                reason="西单旗舰店，适合6人精致聚餐，环境好有格调",
            ),
            _stop(
                poi_id="poi_bj_restaurant_065",
                name="半日餐厅",
                category="restaurant",
                address="金融街购物中心B1",
                lat=39.9022, lng=116.3595,
                start_time="14:00", end_time="15:30",
                cost=120, queue=5,
                tags=["金融街", "精致", "午后", "聚餐"],
                cover="https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=600&q=80",
                highlight="半日餐厅主打慢食文化，原材料精选，适合下午茶后续续餐",
                ugc="环境很安静舒服，适合慢慢聊，不会催翻台",
                travel_min=12, dist_km=1.1, transport="步行",
                reason="距西单步行12分钟，可衔接饭后散步逛街",
            ),
        ],
        reasons=["西单商圈交通便利", "两家餐厅风格互补，体验层次丰富", "餐后可延伸至西单大悦城消化消化"],
    )

    # ── 路线三：金融街商务聚餐 ────────────────────────────────────
    route3 = Route(
        route_id="demo_mock_route_003",
        title="金融街商务聚餐",
        objective="low_walking",
        summary="金融街核心地段，春山+金融街南窗两家餐厅，环境正式，适合商务请客，人均 100-160，无需长途步行。",
        total_duration_minutes=160,
        total_cost_per_person=160,
        total_queue_minutes=8,
        total_travel_minutes=10,
        total_distance_km=0.9,
        score=82,
        score_breakdown=RouteScoreBreakdown(quality=90, queue=85, budget=68, distance=95, preference=80),
        stops=[
            _stop(
                poi_id="poi_bj_restaurant_009",
                name="金融街南窗餐厅",
                category="restaurant",
                address="金融街购物中心5F",
                lat=39.9113, lng=116.3703,
                start_time="12:00", end_time="13:30",
                cost=150, queue=8,
                tags=["金融街", "商务", "请客", "包厢"],
                cover="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80",
                highlight="金融街高端餐厅，商务包厢齐全，主打精品粤菜，适合请客接待",
                ugc="有专属停车位，包厢需提前3天预约，服务一流",
                reason="商务氛围强，有独立包厢，6人请客首选",
            ),
            _stop(
                poi_id="poi_bj_restaurant_017",
                name="金融街云边餐厅",
                category="restaurant",
                address="金融街西区B座L1",
                lat=39.8800, lng=116.3644,
                start_time="13:45", end_time="15:00",
                cost=100, queue=5,
                tags=["金融街", "休闲", "下午茶", "聚餐"],
                cover="https://images.unsplash.com/photo-1552566626-52f8b828add9?w=600&q=80",
                highlight="云边餐厅主打轻食与创意川菜，氛围轻松，适合饭后续茶",
                ugc="午餐后来这喝茶聊天很舒服，不催客",
                travel_min=10, dist_km=0.8, transport="步行",
                reason="步行10分钟即可抵达，无需换乘，适合餐后续聊",
            ),
        ],
        reasons=["全程步行串联，交通负担最低", "适合不想走太多路的聚餐场景", "金融街停车方便，自驾来也ok"],
    )

    return [route1, route2, route3]


# ── 模拟 agent trace（完整链路版）─────────────────────────────────────────────
def build_mock_trace(
    message: str,
    district: str,
    city: str = "北京",
    people_count: int = 6,
) -> list[AgentTraceStep]:
    return [
        AgentTraceStep(
            step="route_message",
            label="判定为：新规划",
            status="done",
            details={
                "intent_type": "new_plan",
                "intent_type_label": "新规划",
                "turn_type": "new_plan",
                "planning_mode": "new_plan",
                "confidence": 0.95,
                "reason": f"用户明确提出{district}附近聚餐需求，属于全新规划。",
                "evidence": [message[:40]],
            },
        ),
        AgentTraceStep(
            step="parse_intent",
            label="LLM 解析用户意图",
            status="done",
            details={
                "city": city,
                "people_count": people_count,
                "target_district": district,
                "start_time": "12:00",
                "duration_hours": 3,
                "interest_tags": ["美食", "聚餐"],
                "scenario": "foodie",
            },
        ),
        AgentTraceStep(
            step="apply_query_delta",
            label="合并区域偏好到规划意图",
            status="done",
            details={
                "added": [f"目标区域={district}"],
                "source": "clarification_answer",
            },
        ),
        AgentTraceStep(
            step="apply_gps_start",
            label="使用GPS坐标作为起点：(39.9072, 116.3740)",
            status="done",
            details={
                "start_lat": 39.9072,
                "start_lng": 116.374,
                "reason": "使用前端传入的 GPS 坐标作为规划起点。",
            },
        ),
        AgentTraceStep(
            step="get_user_profile",
            label="读取并更新用户画像",
            status="done",
            details={
                "preferences": ["美食"],
                "interest_tags": ["美食", "聚餐"],
                "category_preferences": {"restaurant": 0.85},
                "preferred_route_roles": ["meal"],
            },
        ),
        AgentTraceStep(
            step="derive_strategy_tags",
            label="生成本轮策略标签",
            status="done",
            details={
                "strategy_tags": [
                    {"tag": "food_first", "intensity": 0.75, "polarity": "prefer", "evidence": "聚餐/美食"},
                ]
            },
        ),
        AgentTraceStep(
            step="build_strategy_weights",
            label="生成偏好权重",
            status="done",
            details={
                "weights": {
                    "quality": 0.32,
                    "queue": 0.22,
                    "distance": 0.18,
                    "budget": 0.16,
                    "preference": 0.12,
                }
            },
        ),
        AgentTraceStep(
            step="search_pois",
            label=f"召回 {district} 附近 38 个候选 POI",
            status="done",
            details={
                "count": 38,
                "city": city,
                "names": ["春山餐厅", "青苔西单食社", "半日餐厅", "旧庭食社", "金融街南窗餐厅"],
            },
        ),
        AgentTraceStep(
            step="generate_routes",
            label="生成 3 条多目标聚餐路线",
            status="done",
            details={
                "count": 3,
                "route_titles": ["什刹海老字号聚餐", "西单精致聚餐", "金融街商务聚餐"],
                "objectives": ["food_first", "balanced", "low_walking"],
                "final_candidate_poi_count": 38,
            },
        ),
        AgentTraceStep(
            step="summarize_routes",
            label="输出路线方案",
            status="done",
            details={},
        ),
    ]


# ── 流式推送 mock trace（逐步 emit，带延迟，总计约 10s）────────────────────────
async def stream_mock_trace(
    steps: list[AgentTraceStep],
    emit: Callable[[AgentTraceStep], Awaitable[None] | None],
    routes_at_step: str = "generate_routes",
    routes: list[Route] | None = None,
    emit_routes: Callable[[list[Route]], Awaitable[None] | None] | None = None,
) -> None:
    """
    逐步推送 mock trace steps，每步按 TRACE_STEP_DELAYS 延迟。
    在 routes_at_step 步骤之后立即推送路线（让前端尽早渲染卡片）。
    """
    import inspect as _inspect
    for step in steps:
        delay = TRACE_STEP_DELAYS.get(step.step, 0.4)
        await asyncio.sleep(delay)
        if emit is not None:
            result = emit(step)
            if _inspect.isawaitable(result):
                await result
        # 在 generate_routes 步骤完成后推送路线
        if step.step == routes_at_step and routes and emit_routes is not None:
            r = emit_routes(routes)
            if _inspect.isawaitable(r):
                await r


# ── 构建完整 mock ChatResponse ────────────────────────────────────────────────
def build_mock_response(
    session_id: str,
    message: str,
    district: str,
    city: str = "北京",
    people_count: int = 6,
) -> ChatResponse:
    routes = build_mock_routes(district)
    trace = build_mock_trace(message, district, city, people_count)

    reply = (
        f"好的！根据你在**{city}{district}**附近的需求，"
        f"我为你规划了 3 条适合 {people_count} 人聚餐的路线，"
        f"从轻松老字号到精致宴请都有覆盖，你看哪条更符合心意？"
    )

    intent = Intent(
        city=city,
        people_count=people_count,
        start_location_name="北京市西城区西单",
        target_district=district,
        start_lat=39.9072,
        start_lng=116.374,
        start_time="12:00",
        duration_hours=3,
        budget_per_person=150,
        preferences=["美食", "室内为主"],
        interest_tags=["美食", "聚餐"],
        scenario="foodie",
        need_clarification=False,
        city_from_message=False,
    )

    return ChatResponse(
        session_id=session_id,
        message=reply,
        need_clarification=False,
        clarifying_question=None,
        intent=intent,
        user_profile=None,
        routes=routes,
        agent_trace=trace,
    )


# ── Demo 追问卡片：第一轮命中触发词但还没有 target_district 时返回 ──────────────
def build_demo_clarification(
    session_id: str,
    message: str,
    city: str = "北京",
    current_district: str = "西城区",
    trace: list[AgentTraceStep] | None = None,
) -> ChatResponse:
    """
    返回预设的区域追问卡片。
    current_district：根据 GPS 推断的当前区，作为"附近"选项。
    """
    city_districts = {
        "北京": ["朝阳区", "海淀区", "东城区", "西城区", "丰台区"],
        "上海": ["黄浦区", "静安区", "徐汇区", "浦东新区", "长宁区"],
    }
    all_districts = city_districts.get(city, ["朝阳区", "海淀区", "东城区", "丰台区"])
    other_districts = [d for d in all_districts if d != current_district][:3]

    options = [
        ClarificationOption(
            id="current_district",
            label=f"就在{current_district}附近",
            value={"city": city, "target_district": current_district},
        ),
        *[
            ClarificationOption(
                id=f"district_{d}",
                label=d,
                value={"city": city, "target_district": d},
            )
            for d in other_districts
        ],
    ]

    group = ClarificationGroup(
        id="city",
        title=f"你想在{current_district}附近玩，还是去{city}其他地方？",
        required=True,
        options=options,
    )

    clarify_trace = list(trace or [])
    clarify_trace.append(AgentTraceStep(
        step="clarify_intent",
        label="需要确认游玩区域",
        status="done",
        details={"missing_field": "target_district", "city": city},
    ))

    return ChatResponse(
        session_id=session_id,
        message=f"我已经理解了，想体验{city}的夜生活氛围！先确认一下你想在哪个区域玩？",
        need_clarification=True,
        clarifying_question=f"你想在{current_district}附近，还是去{city}其他地方？",
        clarification_type="missing_required_field",
        clarification_groups=[group],
        inferred_context={"city": city, "trip_goal": "夜生活"},
        intent=None,
        user_profile=None,
        routes=[],
        agent_trace=clarify_trace,
    )
