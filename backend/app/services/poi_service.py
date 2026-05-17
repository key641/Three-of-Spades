from app.schemas.intent import Intent
from app.schemas.poi import POI


class POIService:
    """B-owned module: filters POI candidates by intent and strategy tags."""

    def search(self, intent: Intent, limit: int = 20) -> list[POI]:
        # TODO(B): replace sample list with SQLite-backed POI search.
        sample_pois = [
            POI(
                id="poi_001",
                name="武康路街区",
                city="上海",
                category="citywalk",
                lat=31.213,
                lng=121.445,
                avg_price=0,
                rating=4.6,
                queue_minutes=0,
                visit_duration_minutes=80,
                open_hours="00:00-24:00",
                tags=["拍照", "citywalk", "朋友出游"],
                negative_tags=["周末人多"],
                family_friendly=0.6,
                indoor=False,
            ),
            POI(
                id="poi_002",
                name="安静咖啡馆",
                city="上海",
                category="cafe",
                lat=31.216,
                lng=121.449,
                avg_price=45,
                rating=4.5,
                queue_minutes=5,
                visit_duration_minutes=50,
                open_hours="10:00-22:00",
                tags=["安静", "适合聊天", "少排队"],
                negative_tags=[],
                family_friendly=0.5,
                indoor=True,
            ),
            POI(
                id="poi_003",
                name="弄堂本帮菜",
                city="上海",
                category="restaurant",
                lat=31.219,
                lng=121.452,
                avg_price=135,
                rating=4.7,
                queue_minutes=20,
                visit_duration_minutes=90,
                open_hours="11:00-21:30",
                tags=["吃好", "朋友聚餐", "本帮菜"],
                negative_tags=[],
                family_friendly=0.7,
                indoor=True,
            ),
            POI(
                id="poi_004",
                name="衡山路夜景步道",
                city="上海",
                category="scenic",
                lat=31.207,
                lng=121.446,
                avg_price=0,
                rating=4.4,
                queue_minutes=0,
                visit_duration_minutes=60,
                open_hours="00:00-24:00",
                tags=["夜景", "散步", "拍照"],
                negative_tags=[],
                family_friendly=0.6,
                indoor=False,
            ),
        ]
        return [poi for poi in sample_pois if poi.city == intent.city][:limit]

