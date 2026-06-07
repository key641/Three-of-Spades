#!/usr/bin/env python3
"""Build mock POI, interaction, CF, and two-tower recall assets.

The project intentionally avoids heavyweight ML dependencies. The two-tower
artifact generated here is a deterministic trainable retrieval prototype:
feature-hashed user/item towers plus interaction-driven embedding updates.
It gives the online recall layer real persisted user/item vectors while keeping
the demo reproducible and easy to run in a small environment.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "seed"
MODEL_DIR = ROOT / "data" / "models"
POI_PATH = SEED_DIR / "pois.json"
PROFILE_PATH = SEED_DIR / "user_profiles.json"
INTERACTION_PATH = SEED_DIR / "interaction_events.json"
TWO_TOWER_DIR = MODEL_DIR / "two_tower"
CF_DIR = MODEL_DIR / "cf"

EMBEDDING_DIM = 64
RNG = random.Random(20260604)

TARGET_CATEGORY_COUNTS = {
    "restaurant": 140,
    "cafe": 120,
    "market": 80,
    "shopping": 80,
    "boutique": 40,
    "bookstore": 40,
    "lifestyle_store": 40,
    "toy_collectible": 40,
    "sports_outdoor": 40,
    "beauty_retail": 40,
    "design_store": 40,
    "landmark": 80,
    "museum": 70,
    "gallery": 70,
    "park": 70,
    "night_view": 70,
    "theater": 60,
}

STORE_CATEGORIES = {
    "shopping",
    "boutique",
    "bookstore",
    "lifestyle_store",
    "toy_collectible",
    "sports_outdoor",
    "beauty_retail",
    "design_store",
}

CATEGORY_BASE = {
    "boutique": "shopping",
    "bookstore": "shopping",
    "lifestyle_store": "shopping",
    "toy_collectible": "shopping",
    "sports_outdoor": "shopping",
    "beauty_retail": "shopping",
    "design_store": "shopping",
}

CITY_CODES = {"上海": "sh", "北京": "bj"}

BUSINESS_AREAS = {
    "上海": {
        "徐汇区": ["武康路-安福路", "衡山路", "西岸"],
        "静安区": ["静安寺", "南京西路", "愚园路"],
        "黄浦区": ["外滩-南京东路", "新天地", "淮海中路"],
        "浦东新区": ["陆家嘴", "前滩", "世纪公园"],
        "长宁区": ["中山公园", "新华路", "古北"],
        "虹口区": ["北外滩", "鲁迅公园", "甜爱路"],
        "普陀区": ["长风公园", "真如", "曹杨"],
        "杨浦区": ["大学路", "五角场", "滨江"],
    },
    "北京": {
        "朝阳区": ["三里屯", "亮马河", "国贸"],
        "东城区": ["雍和宫", "南锣鼓巷", "王府井"],
        "西城区": ["什刹海", "西单", "金融街"],
        "海淀区": ["五道口", "中关村", "学院路"],
        "丰台区": ["丽泽", "方庄", "花乡"],
        "石景山区": ["首钢园", "古城", "苹果园"],
        "昌平区": ["回龙观", "天通苑", "沙河"],
        "通州区": ["运河商务区", "宋庄", "北关"],
    },
}

STREET_NAMES = {
    "上海": {
        "武康路-安福路": ["安福路", "武康路", "湖南路"],
        "静安寺": ["愚园路", "万航渡路", "南京西路"],
        "外滩-南京东路": ["圆明园路", "南京东路", "四川中路"],
        "陆家嘴": ["陆家嘴环路", "银城中路", "东泰路"],
    },
    "北京": {
        "三里屯": ["三里屯路", "太古里西街", "工体北路"],
        "雍和宫": ["五道营胡同", "国子监街", "雍和宫大街"],
        "什刹海": ["烟袋斜街", "地安门外大街", "前海北沿"],
        "五道口": ["成府路", "学院路", "中关村东路"],
    },
}

NAME_PREFIXES = [
    "春山",
    "梧桐里",
    "慢岛",
    "里弄",
    "晴野",
    "南窗",
    "白石",
    "有光",
    "半日",
    "旧庭",
    "青苔",
    "云边",
]

EVENT_WEIGHTS = {
    "view": 0.5,
    "click": 1.0,
    "save": 2.0,
    "like": 3.0,
    "selected_in_route": 4.0,
    "completed_visit": 5.0,
    "skip": -1.5,
    "replace": -2.0,
    "dislike": -3.0,
}
POSITIVE_EVENTS = ["view", "click", "save", "like", "selected_in_route", "completed_visit"]
NEGATIVE_EVENTS = ["skip", "replace", "dislike"]


TAG_VARIANTS = {
    "restaurant": [
        ["吃好", "老字号", "本地感", "朋友聚餐"],
        ["精致", "餐厅环境", "拍照", "约会"],
        ["小吃", "高性价比", "市井", "轻松"],
        ["轻食", "预算友好", "雨天", "室内"],
    ],
    "cafe": [
        ["咖啡", "安静", "办公", "休息"],
        ["下午茶", "拍照", "文艺", "雨天"],
        ["咖啡", "小众", "低步行", "室内"],
        ["咖啡馆", "朋友", "休息", "交通方便"],
    ],
    "market": [
        ["小吃", "市井", "本地感", "citywalk"],
        ["拍照", "热闹", "朋友", "高性价比"],
        ["轻食", "街区", "散步", "本地"],
    ],
    "shopping": [
        ["室内", "雨天", "购物", "休息"],
        ["夜间", "低步行", "交通方便", "朋友"],
        ["亲子", "餐饮附近", "室内休息", "预算友好"],
    ],
    "boutique": [
        ["买手店", "潮流", "逛街", "小众"],
        ["设计师品牌", "拍照", "朋友", "citywalk"],
        ["服饰", "生活方式", "低步行", "室内"],
    ],
    "bookstore": [
        ["书店", "安静", "文艺", "休息"],
        ["独立出版", "展览", "小众", "雨天"],
        ["阅读", "咖啡附近", "低步行", "室内"],
    ],
    "lifestyle_store": [
        ["生活方式", "家居", "香氛", "逛街"],
        ["杂货", "设计", "拍照", "小众"],
        ["礼物", "预算友好", "朋友", "室内"],
    ],
    "toy_collectible": [
        ["潮玩", "手办", "拍照", "朋友"],
        ["盲盒", "收藏", "亲子", "室内"],
        ["玩具", "小众", "逛街", "低步行"],
    ],
    "sports_outdoor": [
        ["运动户外", "装备", "轻松", "朋友"],
        ["跑步", "骑行", "城市运动", "交通方便"],
        ["户外生活", "预算友好", "逛街", "低步行"],
    ],
    "beauty_retail": [
        ["美妆", "香氛", "试妆", "室内"],
        ["护肤", "礼物", "朋友", "逛街"],
        ["集合店", "拍照", "低步行", "雨天"],
    ],
    "design_store": [
        ["设计商店", "文创", "展览", "小众"],
        ["艺术周边", "拍照", "文艺", "citywalk"],
        ["器物", "家居", "安静", "室内"],
    ],
    "landmark": [
        ["citywalk", "拍照", "经典", "交通方便"],
        ["街区", "散步", "文艺", "本地"],
        ["地标", "出片", "朋友", "低步行"],
    ],
    "museum": [
        ["展览", "室内", "雨天", "亲子"],
        ["文艺", "小众", "安静", "文化"],
        ["博物馆", "经典", "低步行", "交通方便"],
    ],
    "gallery": [
        ["艺术展", "文艺", "小众", "室内"],
        ["拍照", "展览", "雨天", "安静"],
        ["画廊", "出片", "朋友", "低步行"],
    ],
    "park": [
        ["公园", "自然", "散步", "低强度"],
        ["江景", "亲子", "拍照", "轻松"],
        ["自然风景", "安静", "预算友好", "citywalk"],
    ],
    "night_view": [
        ["夜景", "夜游", "拍照", "经典"],
        ["晚上", "江景", "出片", "交通方便"],
        ["夜间", "朋友", "低步行", "地标"],
    ],
    "theater": [
        ["剧场", "室内", "夜间", "文艺"],
        ["演出", "雨天", "约会", "低步行"],
        ["小众", "休息", "交通方便", "朋友"],
    ],
}

NAME_SUFFIXES = {
    "restaurant": ["风味馆", "小馆", "食社", "餐厅"],
    "cafe": ["咖啡", "咖啡馆", "烘焙咖啡", "下午茶室"],
    "market": ["市集", "食集", "街区小吃", "集市"],
    "shopping": ["商场", "生活广场", "购物中心", "室内街区"],
    "boutique": ["买手集合", "衣橱", "选品店", "服饰廊"],
    "bookstore": ["书局", "书店", "阅读室", "书房"],
    "lifestyle_store": ["生活研究所", "杂货社", "家居店", "生活馆"],
    "toy_collectible": ["潮玩局", "收藏社", "玩具仓", "手办店"],
    "sports_outdoor": ["运动户外", "跑步社", "骑行仓", "装备店"],
    "beauty_retail": ["香氛店", "美妆集合", "护肤间", "试妆室"],
    "design_store": ["设计商店", "文创社", "器物店", "艺术商店"],
    "landmark": ["地标", "街区", "步道", "城市客厅"],
    "museum": ["博物馆", "展馆", "文化馆", "陈列馆"],
    "gallery": ["画廊", "美术空间", "艺术馆", "展览空间"],
    "park": ["公园", "绿地", "滨水公园", "自然花园"],
    "night_view": ["夜景台", "观景点", "夜游步道", "江景平台"],
    "theater": ["剧场", "演艺空间", "小剧院", "文化剧院"],
}


def main() -> None:
    payload = _read_json(POI_PATH)
    raw_pois = payload["pois"]
    print("building pois...")
    expanded = expand_pois(raw_pois)
    print("refreshing nearby...")
    _refresh_nearby(expanded)
    payload["pois"] = expanded
    payload.update(_poi_metadata(expanded))
    _write_json(POI_PATH, payload)

    profiles_payload = _read_json(PROFILE_PATH)
    users = profiles_payload.get("users", [])
    print("building interactions...")
    events = generate_interactions(users, expanded)
    _write_json(INTERACTION_PATH, events)

    print("building cf...")
    build_cf_model(events)
    print("building two tower...")
    build_two_tower_artifacts(users, expanded, events)

    print(f"pois={len(expanded)} events={len(events)}")


def expand_pois(raw_pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_city_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for poi in raw_pois:
        by_city_category[(poi["location"]["city"], poi["category"])].append(poi)

    expanded = list(raw_pois)
    existing_ids = {poi["poi_id"] for poi in raw_pois}
    existing_names = {poi["name"] for poi in raw_pois}

    cities = sorted({poi["location"]["city"] for poi in raw_pois})
    for city in cities:
        for category, target in TARGET_CATEGORY_COUNTS.items():
            pois = by_city_category.get((city, category), [])
            base_category = CATEGORY_BASE.get(category, category)
            base_pois = pois or by_city_category.get((city, base_category), [])
            if not base_pois:
                continue
            current_count = len(pois)
            needed = target - current_count
            if needed <= 0:
                continue
            prefix = base_pois[0]["poi_id"].rsplit("_", 1)[0] if pois else f"poi_{CITY_CODES.get(city, stable_int(city) % 1000)}_{category}"
            for index in range(needed):
                base = base_pois[index % len(base_pois)]
                serial = current_count + index + 1
                new_poi = _mutate_poi(base, city, category, prefix, serial, existing_ids, existing_names)
                expanded.append(new_poi)
                by_city_category[(city, category)].append(new_poi)
                existing_ids.add(new_poi["poi_id"])
                existing_names.add(new_poi["name"])

    normalized: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for poi in expanded:
        normalized_poi = _normalize_poi(poi, seen_names)
        normalized.append(normalized_poi)
        seen_names.add(normalized_poi["name"])
    return normalized


def _poi_metadata(pois: list[dict[str, Any]]) -> dict[str, Any]:
    by_city: dict[str, Counter[str]] = defaultdict(Counter)
    for poi in pois:
        by_city[poi["location"]["city"]][poi["category"]] += 1
    city_lines = []
    for city, counts in sorted(by_city.items()):
        category_counts = ", ".join(f"{category}:{count}" for category, count in sorted(counts.items()))
        city_lines.append(f"{city}: {sum(counts.values())}条；{category_counts}。")
    return {
        "mock_poi_intro": [f"Mock POI: 上海、北京，共{len(pois)}条。", *city_lines],
        "schema_version": "1.2.0",
        "description": "Curated Shanghai/Beijing mock POI data for route recall, with realistic fictional names, district and business_area fields, and expanded shopping/lifestyle store categories.",
    }


def _legacy_expand_pois(raw_pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_city_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for poi in raw_pois:
        by_city_category[(poi["location"]["city"], poi["category"])].append(poi)

    expanded = list(raw_pois)
    existing_ids = {poi["poi_id"] for poi in raw_pois}
    existing_names = {poi["name"] for poi in raw_pois}

    for (city, category), pois in sorted(by_city_category.items()):
        target = TARGET_CATEGORY_COUNTS[category]
        needed = target - len(pois)
        if needed <= 0:
            continue
        prefix = pois[0]["poi_id"].rsplit("_", 1)[0]
        for index in range(needed):
            base = pois[index % len(pois)]
            serial = len(pois) + index + 1
            new_poi = _mutate_poi(base, city, category, prefix, serial, existing_ids, existing_names)
            expanded.append(new_poi)
            existing_ids.add(new_poi["poi_id"])
            existing_names.add(new_poi["name"])

    return expanded


def _mutate_poi(
    base: dict[str, Any],
    city: str,
    category: str,
    prefix: str,
    serial: int,
    existing_ids: set[str],
    existing_names: set[str],
) -> dict[str, Any]:
    poi = copy.deepcopy(base)
    poi_id = f"{prefix}_{serial:03d}"
    while poi_id in existing_ids:
        serial += 1
        poi_id = f"{prefix}_{serial:03d}"

    district = poi["location"]["district"]
    poi["category"] = category
    poi["primary_category"] = _primary_category(category, poi["planning_features"].get("meal_type", "non_meal"))
    poi["map_category"] = category
    poi["map_category_code"] = f"mock_{category}"
    suffix = NAME_SUFFIXES[category][serial % len(NAME_SUFFIXES[category])]
    variant_tags = TAG_VARIANTS[category][serial % len(TAG_VARIANTS[category])]
    theme = variant_tags[0]
    name = f"{city}{district}{theme}{suffix}{serial:02d}"
    while name in existing_names:
        serial += 1
        name = f"{city}{district}{theme}{suffix}{serial:02d}"

    poi["poi_id"] = poi_id
    poi["name"] = name
    poi["canonical_poi_id"] = poi_id
    poi["external_place_ids"] = {"mock": f"mock_{poi_id}"}
    poi["source_provider"] = "mock_expanded"
    poi["source_updated_at"] = "2026-06-04"
    poi["geohash"] = f"mock_{poi_id}"

    lat_delta = ((serial % 9) - 4) * 0.0027 + RNG.uniform(-0.0012, 0.0012)
    lng_delta = (((serial * 2) % 9) - 4) * 0.0029 + RNG.uniform(-0.0012, 0.0012)
    poi["location"]["lat"] = round(float(base["location"]["lat"]) + lat_delta, 6)
    poi["location"]["lng"] = round(float(base["location"]["lng"]) + lng_delta, 6)
    poi["location"]["address"] = f"{district}推荐路{100 + serial}号"

    price_min = max(0, int(base["visit_info"]["price_min"]) + ((serial % 7) - 3) * 8)
    price_max = max(price_min, int(base["visit_info"]["price_max"]) + ((serial % 5) - 2) * 10)
    poi["visit_info"]["price_min"] = price_min
    poi["visit_info"]["price_max"] = price_max
    poi["visit_info"]["avg_visit_duration_min"] = max(25, int(base["visit_info"]["avg_visit_duration_min"]) + ((serial % 5) - 2) * 6)

    quality = poi["quality"]
    quality["rating"] = round(min(4.9, max(3.8, float(base["quality"]["rating"]) + ((serial % 7) - 3) * 0.04)), 2)
    quality["review_count"] = max(80, int(base["quality"]["review_count"]) + (serial % 13) * 37)
    quality["popularity"] = round(min(0.98, max(0.25, float(base["quality"]["popularity"]) + ((serial % 9) - 4) * 0.025)), 3)
    quality["crowd_level"] = round(min(0.95, max(0.05, float(base["quality"]["crowd_level"]) + ((serial % 7) - 3) * 0.035)), 3)
    quality["queue_time_min"] = max(0, min(90, int(base["quality"]["queue_time_min"]) + ((serial % 9) - 4) * 3))
    quality["live_crowd_level"] = round(min(0.95, max(0.03, float(base["quality"].get("live_crowd_level", 0.2)) + ((serial % 5) - 2) * 0.03)), 3)
    quality["live_queue_time_min"] = max(0, min(90, int(base["quality"].get("live_queue_time_min", quality["queue_time_min"])) + ((serial % 7) - 3) * 2))

    suitability = poi["suitability"]
    for key in ["family", "couple", "friends", "solo", "elderly", "rainy_day", "budget_friendly", "photo_friendly", "food_nearby", "night_activity"]:
        value = float(suitability.get(key, 0.5)) + ((serial % 5) - 2) * 0.035
        suitability[key] = round(min(0.98, max(0.05, value)), 3)
    if "拍照" in variant_tags:
        suitability["photo_friendly"] = max(suitability["photo_friendly"], 0.78)
    if "雨天" in variant_tags or "室内" in variant_tags:
        suitability["rainy_day"] = max(suitability["rainy_day"], 0.78)
    if "夜间" in variant_tags or "夜景" in variant_tags:
        suitability["night_activity"] = max(suitability["night_activity"], 0.78)
    if "预算友好" in variant_tags or "高性价比" in variant_tags:
        suitability["budget_friendly"] = max(suitability["budget_friendly"], 0.82)

    planning = poi["planning_features"]
    planning["nearby_poi_ids"] = []
    planning["walking_intensity"] = _walking_intensity(category, variant_tags, serial)
    planning["indoor"] = category in {"restaurant", "cafe", "shopping", "museum", "gallery", "theater"} or "室内" in variant_tags
    planning["recommended_transport"] = _transport_modes(category, variant_tags, serial)
    planning["transit_hub_nearby"] = "交通方便" in variant_tags or serial % 4 == 0
    planning["parking_available"] = category in {"shopping", "restaurant", "theater"} and serial % 3 == 0
    planning["meal_type"] = _meal_type(category, variant_tags, serial)

    poi["secondary_categories"] = _unique([*poi.get("secondary_categories", []), *_secondary_categories(category, variant_tags, planning, suitability)])
    poi["route_roles"] = _unique([*_route_roles(category, variant_tags, planning), *poi.get("route_roles", [])])
    poi["experience_tags"] = _unique([*poi.get("experience_tags", []), *_experience_tags(variant_tags)])
    poi["tags"] = _unique([*variant_tags, *poi.get("tags", [])])
    poi["highlight_text_tags"] = _unique([*variant_tags[:2], *poi.get("highlight_text_tags", [])])
    poi["cover_image_url"] = f"https://picsum.photos/seed/{poi_id}/640/360"
    poi["highlight_text"] = f"{name}，适合{ '、'.join(variant_tags[:3]) }需求。"
    poi["ugc_tip"] = f"用户常提到{variant_tags[0]}和{variant_tags[min(1, len(variant_tags)-1)]}，适合与周边点位组合。"
    return poi


def _normalize_poi(poi: dict[str, Any], seen_names: set[str]) -> dict[str, Any]:
    poi = copy.deepcopy(poi)
    location = poi.setdefault("location", {})
    city = str(location.get("city") or poi.get("city") or "上海")
    district = str(poi.get("district") or location.get("district") or _fallback_district(city))
    business_area = str(poi.get("business_area") or location.get("business_area") or _business_area(city, district, poi["poi_id"]))
    serial = stable_int(poi["poi_id"])
    category = str(poi.get("category") or "landmark")
    variant_tags = TAG_VARIANTS.get(category, TAG_VARIANTS["shopping"])[serial % len(TAG_VARIANTS.get(category, TAG_VARIANTS["shopping"]))]

    location["district"] = district
    location["business_area"] = business_area
    poi["district"] = district
    poi["business_area"] = business_area
    poi["name"] = _realistic_name(city, district, business_area, category, serial, seen_names)
    location["address"] = _realistic_address(city, business_area, serial)
    poi["source_updated_at"] = "2026-06-06"
    poi["map_category"] = category
    poi["map_category_code"] = f"mock_{category}"
    poi["primary_category"] = _primary_category(category, poi.get("planning_features", {}).get("meal_type", "non_meal"))

    planning = poi.setdefault("planning_features", {})
    planning["walking_intensity"] = _walking_intensity(category, variant_tags, serial)
    planning["indoor"] = category in {"restaurant", "cafe", "shopping", "museum", "gallery", "theater", *STORE_CATEGORIES} or "室内" in variant_tags
    planning["recommended_transport"] = _transport_modes(category, variant_tags, serial)
    planning["transit_hub_nearby"] = "交通方便" in variant_tags or serial % 4 == 0
    planning["parking_available"] = category in {"shopping", "restaurant", "theater", "sports_outdoor"} and serial % 3 == 0
    planning["meal_type"] = _meal_type(category, variant_tags, serial)

    poi["secondary_categories"] = _unique([*poi.get("secondary_categories", []), *_secondary_categories(category, variant_tags, planning, poi.get("suitability", {})), business_area])
    poi["route_roles"] = _unique([*_route_roles(category, variant_tags, planning), *poi.get("route_roles", [])])
    poi["experience_tags"] = _unique([*poi.get("experience_tags", []), *_experience_tags(variant_tags)])
    poi["tags"] = _unique([business_area, district, *variant_tags, *poi.get("tags", [])])
    poi["highlight_text_tags"] = _unique([business_area, *variant_tags[:2], *poi.get("highlight_text_tags", [])])
    poi["highlight_text"] = f"{poi['name']}位于{business_area}，适合{ '、'.join(variant_tags[:3]) }需求。"
    poi["ugc_tip"] = f"{business_area}周边可步行串联，用户常提到{variant_tags[0]}和{variant_tags[min(1, len(variant_tags)-1)]}。"
    poi["cover_image_url"] = f"https://picsum.photos/seed/{poi['poi_id']}/640/360"
    return poi


def _fallback_district(city: str) -> str:
    areas = BUSINESS_AREAS.get(city) or BUSINESS_AREAS["上海"]
    return next(iter(areas))


def _business_area(city: str, district: str, poi_id: str) -> str:
    areas = (BUSINESS_AREAS.get(city) or {}).get(district)
    if not areas:
        areas = ["城市中心", "老街区", "滨水片区"]
    return areas[stable_int(poi_id) % len(areas)]


def _realistic_name(city: str, district: str, business_area: str, category: str, serial: int, seen_names: set[str]) -> str:
    prefix = NAME_PREFIXES[serial % len(NAME_PREFIXES)]
    suffixes = NAME_SUFFIXES.get(category, NAME_SUFFIXES["shopping"])
    suffix = suffixes[(serial // 7) % len(suffixes)]
    area_hint = business_area.split("-")[0].split("/")[0]
    if category in STORE_CATEGORIES:
        candidates = [
            f"{area_hint}{prefix}{suffix}",
            f"{prefix}{suffix}{area_hint}店",
            f"{prefix}{business_area}{suffix}",
        ]
    elif category in {"landmark", "night_view", "park"}:
        candidates = [
            f"{area_hint}{suffix}",
            f"{prefix}{area_hint}{suffix}",
            f"{business_area}{suffix}",
        ]
    else:
        candidates = [
            f"{prefix}{suffix}",
            f"{area_hint}{prefix}{suffix}",
            f"{prefix}{business_area}{suffix}",
        ]
    fallback_marks = ["别馆", "东馆", "西馆", "南馆", "北馆", "小楼", "里间", "新馆"]
    for candidate in candidates:
        if candidate not in seen_names:
            return candidate
    for offset, mark in enumerate(fallback_marks):
        candidate = f"{candidates[0]}{mark}"
        if candidate not in seen_names:
            return candidate
    chinese_marks = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    return f"{candidates[0]}{chinese_marks[serial % len(chinese_marks)]}馆"


def _realistic_address(city: str, business_area: str, serial: int) -> str:
    city_streets = STREET_NAMES.get(city, {})
    streets = city_streets.get(business_area) or ["梧桐路", "春山路", "云锦街", "南窗巷"]
    street = streets[serial % len(streets)]
    lane = 12 + serial % 86
    return f"{street}{lane}号"


def _primary_category(category: str, meal_type: str) -> str:
    if category == "cafe" or meal_type == "cafe":
        return "cafe"
    if category in {"restaurant", "market"} or meal_type in {"local_food", "fine_dining", "light_meal", "fast_food"}:
        return "food"
    if category in {"museum", "gallery", "theater"}:
        return "culture"
    if category in {"landmark", "night_view"}:
        return "landmark"
    if category in {"park", "nature"}:
        return "nature"
    if category in STORE_CATEGORIES:
        return "shopping"
    return category or "activity"


def _refresh_nearby(pois: list[dict[str, Any]]) -> None:
    by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for poi in pois:
        by_city[poi["location"]["city"]].append(poi)

    for city_pois in by_city.values():
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in city_pois:
            by_category[candidate["category"]].append(candidate)
        for poi in city_pois:
            candidate_pool: list[dict[str, Any]] = []
            salt = stable_int(poi["poi_id"])
            for category, category_pois in by_category.items():
                if category == poi["category"]:
                    continue
                if len(category_pois) <= 18:
                    candidate_pool.extend(category_pois)
                    continue
                start = salt % len(category_pois)
                candidate_pool.extend(category_pois[(start + offset) % len(category_pois)] for offset in range(18))
            scored = []
            for other in candidate_pool:
                if other["poi_id"] == poi["poi_id"]:
                    continue
                distance = _distance(poi, other)
                role_bonus = -0.04 * len(set(poi.get("route_roles", [])) & set(other.get("route_roles", [])))
                scored.append((distance + role_bonus, other["poi_id"]))
            poi["planning_features"]["nearby_poi_ids"] = [poi_id for _, poi_id in sorted(scored)[:3]]


def generate_interactions(users: list[dict[str, Any]], pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for poi in pois:
        by_city[poi["location"]["city"]].append(poi)

    events: list[dict[str, Any]] = []
    event_index = 1
    poi_touch_count: Counter[str] = Counter()
    user_positive_counts: Counter[str] = Counter()
    user_negative_counts: Counter[str] = Counter()

    def add_event(user: dict[str, Any], poi: dict[str, Any], event_type: str, day_offset: int) -> None:
        nonlocal event_index
        timestamp = datetime(2026, 5, 1, 9, 0, tzinfo=timezone(timedelta(hours=8))) + timedelta(
            days=day_offset % 28,
            minutes=(event_index * 17) % 720,
        )
        preferences = _user_preferences(user)
        events.append(
            {
                "event_id": f"evt_{event_index:06d}",
                "user_id": user["user_id"],
                "poi_id": poi["poi_id"],
                "event_type": event_type,
                "event_value": EVENT_WEIGHTS[event_type],
                "city": poi["location"]["city"],
                "timestamp": timestamp.isoformat(),
                "context": {
                    "scenario": "friends_citywalk",
                    "weather": _weather_for_event(poi, event_index),
                    "time_slot": _time_slot_for_event(poi, event_index),
                    "budget_per_person": int(user.get("current_trip", {}).get("budget_total") or 300),
                    "preferences": preferences[:5],
                    "route_objective": _objective_for_poi(poi, preferences),
                },
            }
        )
        poi_touch_count[poi["poi_id"]] += 1
        if EVENT_WEIGHTS[event_type] > 0:
            user_positive_counts[user["user_id"]] += 1
        else:
            user_negative_counts[user["user_id"]] += 1
        event_index += 1

    initial_cursor = 0
    for poi in pois:
        for i in range(4):
            user = users[initial_cursor % len(users)]
            initial_cursor += 1
            event_type = _sample_event_type(_affinity(user, poi), i)
            add_event(user, poi, event_type, i)

    per_user_target = 160
    by_user_count = Counter(event["user_id"] for event in events)
    for user in users:
        city = _user_city(user)
        pool = by_city.get(city) or pois
        while by_user_count[user["user_id"]] < per_user_target:
            poi = _weighted_choice(pool, lambda item: max(0.03, _affinity(user, item)))
            affinity = _affinity(user, poi)
            negative_needed = user_negative_counts[user["user_id"]] < 10
            positive_needed = user_positive_counts[user["user_id"]] < 30
            event_type = _sample_event_type(affinity, event_index)
            if negative_needed and affinity < 0.55:
                event_type = NEGATIVE_EVENTS[event_index % len(NEGATIVE_EVENTS)]
            if positive_needed and affinity >= 0.45:
                event_type = POSITIVE_EVENTS[1 + event_index % (len(POSITIVE_EVENTS) - 1)]
            add_event(user, poi, event_type, event_index)
            by_user_count[user["user_id"]] += 1

    user_cursor = 0
    while len(events) < 16000:
        user = users[user_cursor % len(users)]
        user_cursor += 1
        pool = by_city.get(_user_city(user)) or pois
        poi = _weighted_choice(pool, lambda item: max(0.05, _affinity(user, item)))
        add_event(user, poi, _sample_event_type(_affinity(user, poi), len(events)), len(events))
        by_user_count[user["user_id"]] += 1

    return events


def build_cf_model(events: list[dict[str, Any]]) -> None:
    user_items: dict[str, dict[str, float]] = defaultdict(dict)
    for event in events:
        value = float(event["event_value"])
        user_items[event["user_id"]][event["poi_id"]] = user_items[event["user_id"]].get(event["poi_id"], 0) + value

    item_users: dict[str, dict[str, float]] = defaultdict(dict)
    for user_id, items in user_items.items():
        for poi_id, value in items.items():
            item_users[poi_id][user_id] = value

    pair_candidates: dict[str, set[str]] = defaultdict(set)
    for items in user_items.values():
        positive_items = [poi_id for poi_id, value in items.items() if value > 0]
        positive_items = sorted(positive_items, key=lambda poi_id: items[poi_id], reverse=True)[:80]
        for index, poi_id in enumerate(positive_items):
            for other_id in positive_items[index + 1 :]:
                pair_candidates[poi_id].add(other_id)
                pair_candidates[other_id].add(poi_id)

    similarity: dict[str, list[dict[str, float | str]]] = {}
    norms = {poi_id: math.sqrt(sum(value * value for value in users.values())) or 1 for poi_id, users in item_users.items()}
    for poi_id, users in item_users.items():
        sims = []
        for other_id in pair_candidates.get(poi_id, set()):
            common = set(users) & set(item_users[other_id])
            if not common:
                continue
            dot = sum(users[user_id] * item_users[other_id][user_id] for user_id in common)
            score = dot / (norms[poi_id] * norms[other_id])
            if score > 0:
                sims.append({"poi_id": other_id, "score": round(score, 6)})
        similarity[poi_id] = sorted(sims, key=lambda item: item["score"], reverse=True)[:40]

    CF_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(CF_DIR / "item_similarity.json", {"version": "1.0", "items": similarity})


def build_two_tower_artifacts(users: list[dict[str, Any]], pois: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    poi_by_id = {poi["poi_id"]: poi for poi in pois}
    user_by_id = {user["user_id"]: user for user in users}
    poi_vectors = {poi_id: _poi_vector(poi) for poi_id, poi in poi_by_id.items()}
    user_vectors = {user_id: _user_vector(user, poi_vectors, events) for user_id, user in user_by_id.items()}

    # Interaction-driven prototype training: pull positive user/item vectors
    # together and push negative pairs apart with a small deterministic step.
    for event in events:
        user_id = event["user_id"]
        poi_id = event["poi_id"]
        if user_id not in user_vectors or poi_id not in poi_vectors:
            continue
        weight = min(abs(float(event["event_value"])) / 5, 1)
        sign = 1 if float(event["event_value"]) > 0 else -1
        step = 0.018 * weight
        user_vec = user_vectors[user_id]
        poi_vec = poi_vectors[poi_id]
        for index in range(EMBEDDING_DIM):
            delta = step * sign * poi_vec[index]
            user_vec[index] += delta
            poi_vec[index] += step * sign * user_vec[index] * 0.35

    user_vectors = {key: _normalize(vec) for key, vec in user_vectors.items()}
    poi_vectors = {key: _normalize(vec) for key, vec in poi_vectors.items()}

    TWO_TOWER_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(TWO_TOWER_DIR / "user_embeddings.json", {"version": "1.0", "dimension": EMBEDDING_DIM, "embeddings": user_vectors})
    _write_json(TWO_TOWER_DIR / "poi_embeddings.json", {"version": "1.0", "dimension": EMBEDDING_DIM, "embeddings": poi_vectors})
    _write_json(
        TWO_TOWER_DIR / "model_metadata.json",
        {
            "version": "1.0",
            "dimension": EMBEDDING_DIM,
            "training_events": len(events),
            "poi_count": len(pois),
            "user_count": len(users),
            "loss": "weighted_binary_interaction_prototype",
            "built_at": "2026-06-04T00:00:00+08:00",
        },
    )


def _user_vector(user: dict[str, Any], poi_vectors: dict[str, list[float]], events: list[dict[str, Any]]) -> list[float]:
    features = [f"user:{user['user_id']}", f"city:{_user_city(user)}"]
    features.extend(f"pref:{pref}" for pref in _user_preferences(user))
    for category, score in (user.get("category_preferences") or {}).items():
        if float(score) >= 0.35:
            features.append(f"category:{category}")
    profile = user.get("preference_profile", {})
    numeric = [
        float(profile.get("budget_sensitivity", 0.5)),
        float(profile.get("walking_tolerance", 0.5)),
        float(profile.get("crowd_tolerance", 0.5)),
        float(profile.get("novelty_preference", 0.5)),
        float(profile.get("comfort_preference", 0.5)),
    ]
    vec = _features_to_vector(features, numeric)
    positives = [event["poi_id"] for event in events if event["user_id"] == user["user_id"] and event["event_value"] > 0]
    negatives = [event["poi_id"] for event in events if event["user_id"] == user["user_id"] and event["event_value"] < 0]
    vec = _add_pool(vec, positives, poi_vectors, 0.35)
    vec = _add_pool(vec, negatives, poi_vectors, -0.18)
    return _normalize(vec)


def _poi_vector(poi: dict[str, Any]) -> list[float]:
    features = [
        f"poi:{poi['poi_id']}",
        f"city:{poi['location']['city']}",
        f"category:{poi['category']}",
        f"primary:{poi.get('primary_category', '')}",
        f"walk:{poi['planning_features'].get('walking_intensity', '')}",
        f"indoor:{poi['planning_features'].get('indoor', False)}",
    ]
    for key in ["secondary_categories", "route_roles", "experience_tags", "tags", "highlight_text_tags"]:
        features.extend(f"{key}:{value}" for value in poi.get(key, []))
    for slot in poi["visit_info"].get("suitable_time_slots", []):
        features.append(f"slot:{slot}")
    quality = poi["quality"]
    suitability = poi["suitability"]
    price = (int(poi["visit_info"]["price_min"]) + int(poi["visit_info"]["price_max"])) / 2
    numeric = [
        min(price / 800, 1),
        float(quality.get("rating", 4.2)) / 5,
        min(float(quality.get("review_count", 0)) / 10000, 1),
        float(quality.get("popularity", 0.5)),
        min(float(quality.get("queue_time_min", 0)) / 90, 1),
        float(quality.get("crowd_level", 0.4)),
        float(suitability.get("rainy_day", 0.5)),
        float(suitability.get("budget_friendly", 0.5)),
        float(suitability.get("photo_friendly", 0.5)),
        float(suitability.get("night_activity", 0.5)),
    ]
    return _normalize(_features_to_vector(features, numeric))


def _features_to_vector(features: list[str], numeric: list[float]) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1 if digest[4] % 2 == 0 else -1
        vec[index] += sign * 1.0
    for index, value in enumerate(numeric):
        vec[index % EMBEDDING_DIM] += float(value)
    return _normalize(vec)


def _add_pool(base: list[float], poi_ids: list[str], poi_vectors: dict[str, list[float]], weight: float) -> list[float]:
    if not poi_ids:
        return base
    selected = [poi_vectors[poi_id] for poi_id in poi_ids if poi_id in poi_vectors]
    if not selected:
        return base
    pooled = [sum(vec[index] for vec in selected) / len(selected) for index in range(EMBEDDING_DIM)]
    return [base[index] + pooled[index] * weight for index in range(EMBEDDING_DIM)]


def _affinity(user: dict[str, Any], poi: dict[str, Any]) -> float:
    category_preferences = user.get("category_preferences") or {}
    score = 0.25 + float(category_preferences.get(poi["category"], 0.2)) * 0.55
    poi_text = _poi_text(poi)
    for pref in _user_preferences(user):
        if pref and pref in poi_text:
            score += 0.08
    profile = user.get("preference_profile", {})
    if float(profile.get("crowd_tolerance", 0.5)) < 0.4:
        score += max(0, 0.5 - float(poi["quality"].get("crowd_level", 0.5))) * 0.18
    if float(profile.get("walking_tolerance", 0.5)) < 0.4 and poi["planning_features"].get("walking_intensity") == "low":
        score += 0.12
    if float(profile.get("budget_sensitivity", 0.5)) > 0.6 and float(poi["suitability"].get("budget_friendly", 0.5)) > 0.75:
        score += 0.1
    history = user.get("history_behavior", {})
    if poi["poi_id"] in history.get("liked_poi_ids", []):
        score += 0.25
    if poi["poi_id"] in history.get("disliked_poi_ids", []):
        score -= 0.35
    return max(0.02, min(0.98, score))


def _sample_event_type(affinity: float, salt: int) -> str:
    if RNG.random() < max(0.12, min(0.88, affinity)):
        return POSITIVE_EVENTS[(salt + int(affinity * 10)) % len(POSITIVE_EVENTS)]
    return NEGATIVE_EVENTS[salt % len(NEGATIVE_EVENTS)]


def _weighted_choice(items: list[dict[str, Any]], scorer) -> dict[str, Any]:
    if len(items) > 140:
        start = RNG.randrange(len(items))
        sampled = [items[(start + offset * 7) % len(items)] for offset in range(140)]
    else:
        sampled = items
    weights = [scorer(item) for item in sampled]
    total = sum(weights) or 1
    cursor = RNG.random() * total
    for item, weight in zip(sampled, weights):
        cursor -= weight
        if cursor <= 0:
            return item
    return sampled[-1]


def _user_city(user: dict[str, Any]) -> str:
    return str(user.get("basic_profile", {}).get("home_city") or "上海")


def _user_preferences(user: dict[str, Any]) -> list[str]:
    soft = user.get("current_trip", {}).get("soft_preferences", {})
    values = list(soft.get("prefer_tags") or [])
    values.extend((user.get("history_behavior", {}) or {}).get("common_adjust_actions", []))
    return _unique([str(value) for value in values])


def _weather_for_event(poi: dict[str, Any], salt: int) -> str:
    if poi["suitability"].get("rainy_day", 0) >= 0.75:
        return "rainy" if salt % 3 == 0 else "cloudy"
    if poi["suitability"].get("night_activity", 0) >= 0.75:
        return "night"
    return ["sunny", "cloudy", "hot"][salt % 3]


def _time_slot_for_event(poi: dict[str, Any], salt: int) -> str:
    slots = poi["visit_info"].get("suitable_time_slots") or ["afternoon"]
    return slots[salt % len(slots)]


def _objective_for_poi(poi: dict[str, Any], preferences: list[str]) -> str:
    text = " ".join([*_as_list(poi.get("tags")), *_as_list(poi.get("route_roles")), *preferences])
    if "夜景" in text or "night_end" in text:
        return "night_friendly"
    if "室内" in text or "雨天" in text:
        return "indoor_rainy"
    if "吃好" in text or "meal" in text:
        return "food_first"
    if "自然" in text or poi["category"] == "park":
        return "nature_relax"
    if "拍照" in text or "citywalk" in text:
        return "photo_citywalk"
    return "balanced"


def _walking_intensity(category: str, tags: list[str], serial: int) -> str:
    if "低步行" in tags or "低强度" in tags or category in {"museum", "gallery", "theater", *STORE_CATEGORIES}:
        return "low"
    if category in {"park", "landmark"} and serial % 3 == 0:
        return "high"
    return "medium" if serial % 4 else "low"


def _transport_modes(category: str, tags: list[str], serial: int) -> list[str]:
    modes = ["metro"] if "交通方便" in tags or serial % 4 == 0 else ["walk"]
    if category in {"restaurant", "theater", "sports_outdoor"}:
        modes.append("taxi")
    if category in {"park", "market", "landmark", *STORE_CATEGORIES}:
        modes.append("bus")
    return _unique(modes)


def _meal_type(category: str, tags: list[str], serial: int) -> str:
    if category == "restaurant":
        if "轻食" in tags:
            return "light_meal"
        if "小吃" in tags:
            return "fast_food"
        return "fine_dining" if "精致" in tags else "local_food"
    if category == "cafe":
        return "cafe"
    if category == "market":
        return "light_meal"
    return "non_meal"


def _secondary_categories(category: str, tags: list[str], planning: dict[str, Any], suitability: dict[str, Any]) -> list[str]:
    values = []
    if "拍照" in tags or "出片" in tags:
        values.append("photo")
    if planning.get("indoor"):
        values.append("indoor")
    if "夜间" in tags or "夜景" in tags or suitability.get("night_activity", 0) >= 0.75:
        values.append("night")
    if "雨天" in tags or suitability.get("rainy_day", 0) >= 0.75:
        values.append("rainy")
    if "预算友好" in tags or "高性价比" in tags:
        values.append("budget")
    if category in {"restaurant", "market"}:
        values.append("food")
    if category == "park":
        values.append("nature")
    if category in STORE_CATEGORIES:
        values.extend(["shopping", "retail", "citywalk"])
    return values


def _route_roles(category: str, tags: list[str], planning: dict[str, Any]) -> list[str]:
    roles = []
    if category in {"restaurant"}:
        roles.extend(["meal", "rest_stop"])
    if category == "market":
        roles.extend(["meal", "photo_stop", "main_activity"])
    if category == "cafe":
        roles.extend(["coffee_break", "rest_stop"])
    if category in {"landmark", "museum", "gallery", "park", "night_view", "theater", *STORE_CATEGORIES}:
        roles.append("main_activity")
    if "拍照" in tags or "出片" in tags or "citywalk" in tags:
        roles.append("photo_stop")
    if planning.get("transit_hub_nearby"):
        roles.append("transit_anchor")
    if category == "night_view" or "夜间" in tags or "夜景" in tags:
        roles.append("night_end")
    if "休息" in tags:
        roles.append("rest_stop")
    return roles or ["main_activity"]


def _experience_tags(tags: list[str]) -> list[str]:
    candidates = ["老字号", "安静", "市井", "展览", "江景", "亲子", "文艺", "小众", "经典", "夜景", "本地", "雨天", "免费", "高性价比", "买手店", "书店", "生活方式", "潮玩", "运动户外", "美妆", "设计"]
    return [tag for tag in candidates if tag in tags]


def _poi_text(poi: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in [
            poi.get("name"),
            poi.get("district"),
            poi.get("business_area"),
            poi.get("location", {}).get("district"),
            poi.get("location", {}).get("business_area"),
            poi.get("category"),
            poi.get("primary_category"),
            poi.get("highlight_text"),
            poi.get("ugc_tip"),
            *_as_list(poi.get("secondary_categories")),
            *_as_list(poi.get("route_roles")),
            *_as_list(poi.get("experience_tags")),
            *_as_list(poi.get("tags")),
        ]
        if part
    )


def _as_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.hypot(
        (float(left["location"]["lat"]) - float(right["location"]["lat"])) * 111,
        (float(left["location"]["lng"]) - float(right["location"]["lng"])) * 95,
    )


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vec)) or 1
    return [round(value / norm, 6) for value in vec]


def stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
