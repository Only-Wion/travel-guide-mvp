import json
import logging
from typing import Dict, List, Optional

from openai import OpenAI

from app.config import DS_API_KEY, DS_BASE_URL, DS_MODEL, LLM_ENABLED
from app.schemas import TravelPlanGenerateRequest

logger = logging.getLogger(__name__)


class DeepSeekTravelConnectors:
    """Generate travel data (city info, transport options) via DeepSeek LLM instead of mock data."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    @property
    def available(self) -> bool:
        return LLM_ENABLED

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=DS_API_KEY,
                base_url=DS_BASE_URL,
            )
        return self._client

    def load_city_bundle(self, request: TravelPlanGenerateRequest) -> Dict[str, object]:
        """Generate city info (weather, attractions, restaurants, hotel area) via DeepSeek."""
        if not self.available:
            logger.warning("DeepSeek not available, return empty city bundle")
            return self._default_city_bundle(request.destination_city)

        # Build desired places section
        desired_places_section = ""
        if request.desired_places:
            desired_list = "\n".join([f"  - {place}" for place in request.desired_places])
            desired_places_section = f"""
用户想去的地方（优先级最高，必须融入景点列表）：
{desired_list}

要求：必须优先将用户想去的地方融入 attractions 列表中，尽可能匹配这些地点。"""

        prompt = f"""你是一个旅行信息生成助手。根据目的地城市生成真实、有用的旅行信息。

目的地：{request.destination_city}
出发日期：{request.departure_date}
返回日期：{request.return_date}
出行人数：{request.travelers} 人{desired_places_section}

请按 JSON 格式返回该城市的旅行信息：

{{
  "weather": {{
    "summary": "该时期天气摘要，包含温度范围和可能的天气状况",
    "packing": "根据天气建议的行李清单",
    "confidence": 0.8,
    "updated_at": "2026-04-14T09:00:00+08:00"
  }},
  "attractions": [
    ["景点名称1", "类型，如citywalk/culture/nature"],
    ["景点名称2", "类型"],
    ["景点名称3", "类型"],
    ["景点名称4", "类型"]
  ],
  "food": [
    ["餐厅1或美食特色", "特色描述，如地方菜系或评价"],
    ["餐厅2或美食特色", "特色描述"],
    ["餐厅3或美食特色", "特色描述"]
  ],
  "hotel_area": "推荐酒店所在区域"
}}

要求：
1. attractions 至少 4 条，每条包含名称和类型
2. food 至少 3 条，包含真实存在的餐厅或当地美食
3. hotel_area 选择交通便利、旅游集中的区域
{"4. 必须优先使用用户想去的地方中的地点，确保至少 50% 的 attractions 来自用户的想去清单。" if request.desired_places else "4. "}
5. 只返回 JSON，不要任何解释文字"""

        try:
            response = self.client.chat.completions.create(
                model=DS_MODEL,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            raw = response.choices[0].message.content or ""
            result = self._parse_city_bundle(raw)
            if result:
                logger.info(
                    "Generated city bundle for %s via DeepSeek",
                    request.destination_city,
                )
                return result
        except Exception as exc:
            logger.error("DeepSeek city bundle generation failed: %s", exc)

        return self._default_city_bundle(request.destination_city)

    def transport_candidates(
        self, request: TravelPlanGenerateRequest
    ) -> List[Dict[str, object]]:
        """Generate transport options via DeepSeek."""
        if not self.available:
            logger.warning(
                "DeepSeek not available, return default transport candidates"
            )
            return self._default_transport_candidates(request)

        prompt = f"""你是一个交通规划助手。根据出发地、目的地和出行日期，生成 3 个真实可行的交通方案。

出发地：{request.origin_city}
目的地：{request.destination_city}
出发日期：{request.departure_date}
返回日期：{request.return_date}
出行人数：{request.travelers} 人
预算：¥{request.budget_cny}

请按 JSON 数组格式返回 3 个方案。每个方案包含：

[
  {{
    "transport_id": "budget-route",
    "label": "具体交通方式描述，如晚班高铁+地铁",
    "positioning": "定位，如省钱优先",
    "mode": "交通方式类型，如high_speed_rail/flight/driving",
    "depart_at": "2026-MM-DD HH:MM 格式出发时间",
    "arrive_at": "2026-MM-DD HH:MM 格式到达时间",
    "duration_minutes": 耗时分钟数,
    "cost_cny": 总成本(已乘以人数),
    "arrival_is_night": true/false,
    "transfer_buffer_minutes": 中转缓冲分钟数,
    "reliability": 可靠度 0.0-1.0,
    "summary": "优缺点简述"
  }},
  ...
]

要求：
1. 三个方案分别定位于：省钱优先、平衡方案、省心优先
2. 出发时间要考虑实际车次/航班，避免离谱的时间
3. 成本必须乘以 {request.travelers} 人
4. 可靠度反映该方案的稳定性和风险
5. 只返回 JSON 数组，不要任何解释"""

        try:
            response = self.client.chat.completions.create(
                model=DS_MODEL,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content or ""
            result = self._parse_transport_candidates(raw)
            if result and len(result) >= 2:
                logger.info(
                    "Generated %d transport candidates via DeepSeek", len(result)
                )
                return result
        except Exception as exc:
            logger.error("DeepSeek transport generation failed: %s", exc)

        return self._default_transport_candidates(request)

    def _parse_city_bundle(self, raw: str) -> Optional[Dict[str, object]]:
        """Parse city bundle JSON response."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            # Validate structure
            if not isinstance(data, dict):
                return None
            if "weather" not in data or "attractions" not in data:
                return None
            # Ensure arrays are properly typed
            if not isinstance(data["attractions"], list):
                return None
            if not isinstance(data.get("food"), list):
                data["food"] = []
            return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse city bundle JSON: %.200s", raw)
            return None

    def _parse_transport_candidates(
        self, raw: str
    ) -> Optional[List[Dict[str, object]]]:
        """Parse transport candidates JSON response."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if not isinstance(data, list):
                return None
            # Validate each candidate has required fields
            for item in data:
                if not isinstance(item, dict) or "transport_id" not in item:
                    return None
            return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse transport candidates JSON: %.200s", raw)
            return None

    @staticmethod
    def _default_city_bundle(destination_city: str) -> Dict[str, object]:
        """Fallback city bundle if DeepSeek fails."""
        return {
            "weather": {
                "summary": f"{destination_city}天气数据暂未生成，建议出发前 24 小时复核。",
                "packing": "轻便外套、舒适步行鞋。",
                "confidence": 0.5,
                "updated_at": "2026-04-14T09:00:00+08:00",
            },
            "attractions": [
                (f"{destination_city}老城区", "citywalk"),
                (f"{destination_city}博物馆", "museum"),
                (f"{destination_city}主城区夜景", "nightlife"),
            ],
            "food": [
                (f"{destination_city}本地小馆", "评价稳定"),
            ],
            "hotel_area": f"{destination_city}市中心",
        }

    @staticmethod
    def _default_transport_candidates(
        request: TravelPlanGenerateRequest,
    ) -> List[Dict[str, object]]:
        """Fallback transport candidates if DeepSeek fails."""
        return [
            {
                "transport_id": "budget-route",
                "label": "经济方案",
                "positioning": "省钱优先",
                "mode": "high_speed_rail",
                "depart_at": f"{request.departure_date} 17:20",
                "arrive_at": f"{request.departure_date} 22:35",
                "duration_minutes": 315,
                "cost_cny": 420 * request.travelers,
                "arrival_is_night": True,
                "transfer_buffer_minutes": 40,
                "reliability": 0.7,
                "summary": "票价最低，但到达偏晚。",
            },
            {
                "transport_id": "balanced-route",
                "label": "平衡方案",
                "positioning": "平衡方案",
                "mode": "high_speed_rail",
                "depart_at": f"{request.departure_date} 08:10",
                "arrive_at": f"{request.departure_date} 11:18",
                "duration_minutes": 188,
                "cost_cny": 560 * request.travelers,
                "arrival_is_night": False,
                "transfer_buffer_minutes": 75,
                "reliability": 0.84,
                "summary": "时间和成本较平衡。",
            },
            {
                "transport_id": "peace-route",
                "label": "舒适方案",
                "positioning": "省心优先",
                "mode": "flight",
                "depart_at": f"{request.departure_date} 09:05",
                "arrive_at": f"{request.departure_date} 12:10",
                "duration_minutes": 185,
                "cost_cny": 930 * request.travelers,
                "arrival_is_night": False,
                "transfer_buffer_minutes": 120,
                "reliability": 0.91,
                "summary": "到达时间稳，接驳余量充足。",
            },
        ]


# Singleton for easy injection
deepseek_connectors = DeepSeekTravelConnectors()
