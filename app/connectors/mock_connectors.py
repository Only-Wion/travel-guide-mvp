from copy import deepcopy
from typing import Dict, List

from app.schemas import TravelPlanGenerateRequest


CITY_FIXTURES: Dict[str, Dict[str, object]] = {
    "杭州": {
        "weather": {
            "summary": "白天 20-26℃，局部阵雨，西湖周边体感舒适，夜间略潮。",
            "packing": "薄外套、轻便鞋、随身雨具。",
            "confidence": 0.83,
            "updated_at": "2026-04-14T09:00:00+08:00",
        },
        "attractions": [
            ("西湖断桥", "citywalk"),
            ("灵隐寺", "culture"),
            ("小河直街", "local_life"),
            ("西溪湿地", "nature"),
        ],
        "food": [
            ("新白鹿", "杭帮菜，排队高峰明显"),
            ("知味观", "本地游客都认，出餐稳定"),
            ("德明饭店", "口味重，评价两极"),
        ],
        "hotel_area": "武林广场/凤起路",
    },
    "厦门": {
        "weather": {
            "summary": "白天 24-29℃，海风明显，午后紫外线偏强。",
            "packing": "防晒、轻薄外套、拖鞋或凉鞋。",
            "confidence": 0.82,
            "updated_at": "2026-04-14T09:00:00+08:00",
        },
        "attractions": [
            ("鼓浪屿", "beach"),
            ("沙坡尾", "citywalk"),
            ("曾厝垵", "food"),
            ("植物园雨林世界", "family_friendly"),
        ],
        "food": [
            ("八市海鲜", "新鲜但价格浮动大"),
            ("黄则和", "游客多，口味稳定"),
            ("乌糖沙茶面", "口碑强，但排队长"),
        ],
        "hotel_area": "中山路/平码头",
    },
    "成都": {
        "weather": {
            "summary": "白天 21-27℃，早晚温差小，湿度偏高。",
            "packing": "薄衫、雨伞、肠胃药。",
            "confidence": 0.8,
            "updated_at": "2026-04-14T09:00:00+08:00",
        },
        "attractions": [
            ("宽窄巷子", "citywalk"),
            ("杜甫草堂", "museum"),
            ("人民公园", "slow_travel"),
            ("东郊记忆", "nightlife"),
        ],
        "food": [
            ("饕林餐厅", "川菜标杆，需提前排队"),
            ("马旺子", "口味稳，适合外地游客"),
            ("建设路小吃", "选择多，但踩雷概率高"),
        ],
        "hotel_area": "春熙路/太古里",
    },
}


class MockTravelConnectors:
    def load_city_bundle(self, request: TravelPlanGenerateRequest) -> Dict[str, object]:
        city_data = deepcopy(CITY_FIXTURES.get(request.destination_city))
        if city_data:
            return city_data
        return {
            "weather": {
                "summary": "天气数据暂未接入真实源，建议出发前 24 小时复核。",
                "packing": "轻便外套、舒适步行鞋。",
                "confidence": 0.62,
                "updated_at": "2026-04-14T09:00:00+08:00",
            },
            "attractions": [
                (f"{request.destination_city}老城区", "citywalk"),
                (f"{request.destination_city}博物馆", "museum"),
                (f"{request.destination_city}主城区夜景", "nightlife"),
            ],
            "food": [
                (f"{request.destination_city}本地小馆", "评价稳定"),
                (f"{request.destination_city}热门商圈餐厅", "高峰期需排队"),
            ],
            "hotel_area": f"{request.destination_city}市中心",
        }

    def transport_candidates(self, request: TravelPlanGenerateRequest) -> List[Dict[str, object]]:
        return [
            {
                "transport_id": "budget-route",
                "label": "晚班高铁 + 地铁",
                "positioning": "省钱优先",
                "mode": "high_speed_rail",
                "depart_at": f"{request.departure_date} 17:20",
                "arrive_at": f"{request.departure_date} 22:35",
                "duration_minutes": 315,
                "cost_cny": 420 * request.travelers,
                "arrival_is_night": True,
                "transfer_buffer_minutes": 40,
                "reliability": 0.7,
                "summary": "票价最低，但到达偏晚，接驳窗口窄。",
            },
            {
                "transport_id": "balanced-route",
                "label": "早班高铁直达",
                "positioning": "平衡方案",
                "mode": "high_speed_rail",
                "depart_at": f"{request.departure_date} 08:10",
                "arrive_at": f"{request.departure_date} 11:18",
                "duration_minutes": 188,
                "cost_cny": 560 * request.travelers,
                "arrival_is_night": False,
                "transfer_buffer_minutes": 75,
                "reliability": 0.84,
                "summary": "时间和成本较平衡，适合多数用户。",
            },
            {
                "transport_id": "peace-route",
                "label": "上午航班 + 机场快线",
                "positioning": "省心优先",
                "mode": "flight",
                "depart_at": f"{request.departure_date} 09:05",
                "arrive_at": f"{request.departure_date} 12:10",
                "duration_minutes": 185,
                "cost_cny": 930 * request.travelers,
                "arrival_is_night": False,
                "transfer_buffer_minutes": 120,
                "reliability": 0.91,
                "summary": "到达时间稳，后续接驳余量充足。",
            },
        ]
