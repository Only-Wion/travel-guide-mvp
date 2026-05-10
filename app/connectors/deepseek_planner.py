import json
import logging
from typing import Dict, List, Optional

from openai import OpenAI

from app.config import DS_API_KEY, DS_BASE_URL, DS_MODEL, LLM_ENABLED
from app.schemas import DailyStop, TravelPlanGenerateRequest

logger = logging.getLogger(__name__)


class DeepSeekDailyStopPlanner:
    """Use DeepSeek to turn ranked planning inputs into DailyStop items."""

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

    def build_daily_stops(
        self,
        request: TravelPlanGenerateRequest,
        city_bundle: Dict[str, object],
        label: str,
        xiaohongshu_result: Optional[dict] = None,
    ) -> Optional[List[DailyStop]]:
        if not self.available:
            return None

        prompt = self._build_prompt(request, city_bundle, label, xiaohongshu_result)
        try:
            response = self.client.chat.completions.create(
                model=DS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.35,
                max_tokens=2200,
            )
            raw = response.choices[0].message.content or ""
            return self._parse_daily_stops(raw)
        except Exception as exc:
            logger.error("DeepSeek daily stop planning failed: %s", exc)
            return None

    def _build_prompt(
        self,
        request: TravelPlanGenerateRequest,
        city_bundle: Dict[str, object],
        label: str,
        xiaohongshu_result: Optional[dict],
    ) -> str:
        desired_places = request.desired_places or []
        xhs_locations = []
        xhs_restaurants = []
        xhs_risks = []
        if xiaohongshu_result:
            xhs_locations = xiaohongshu_result.get("locations", []) or []
            xhs_restaurants = xiaohongshu_result.get("restaurants", []) or []
            xhs_risks = xiaohongshu_result.get("risk_tips", []) or []

        payload = {
            "trip": {
                "origin_city": request.origin_city,
                "destination_city": request.destination_city,
                "departure_date": request.departure_date,
                "return_date": request.return_date,
                "travelers": request.travelers,
                "plan_label": label,
                "preference_mode": request.preference_mode,
            },
            "priority_1_desired_places": desired_places,
            "priority_2_xiaohongshu": {
                "locations": xhs_locations,
                "restaurants": xhs_restaurants,
                "risk_tips": xhs_risks,
            },
            "priority_3_connector_city_bundle": city_bundle,
        }

        return f"""你是一个旅行日程编排助手。请根据下面 JSON 生成 daily_stops。

优先级必须严格遵守：
1. 用户想去的地方 priority_1_desired_places 最高，能安排就优先安排在景点/餐饮 stop 中。
2. 小红书攻略提取结果 priority_2_xiaohongshu 次高，作为补充景点、餐厅和风险提醒。
3. DeepSeek connectors 生成的 city_bundle priority_3_connector_city_bundle 最低，用来补齐天气、酒店区域、景点和餐饮。

输入：
{json.dumps(payload, ensure_ascii=False, default=str)}

请只返回 JSON 数组，数组元素必须完全符合下面字段：
[
  {{
    "day": 1,
    "time_range": "上午|下午|晚上",
    "title": "地点/餐厅/事项名称",
    "category": "transport|attraction|food|hotel|rest",
    "highlight": "一句简短说明，说明为什么这样安排",
    "source_ids": ["rule-transfer-buffer"]
  }}
]

硬性要求：
1. 保持原系统输出格式：返回可直接转换为 DailyStop 的 JSON 数组。
2. 至少 7 条，覆盖 day=1 的上午/下午/晚上、day=2 的上午/下午/晚上、day=3 的上午。
3. category 只能使用 transport、attraction、food、hotel、rest。
4. 第一条通常是到达并办理入住，酒店区域优先使用 city_bundle.hotel_area。
5. 如果使用用户想去地点，source_ids 包含 "user-desired-place"。
6. 如果使用小红书地点/餐厅，source_ids 包含 "xiaohongshu-import"。
7. 如果使用 connectors 的 attractions/food/hotel_area，source_ids 分别包含 "connector-attraction"、"food-local" 或 "rule-transfer-buffer"。
8. 只返回 JSON，不要 markdown，不要解释。"""

    def _parse_daily_stops(self, raw: str) -> Optional[List[DailyStop]]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse daily stops JSON: %.200s", raw)
            return None

        if not isinstance(data, list):
            return None

        stops: List[DailyStop] = []
        for item in data:
            if not isinstance(item, dict):
                return None
            try:
                stops.append(DailyStop(**item))
            except Exception as exc:
                logger.warning("Invalid DailyStop from DeepSeek: %s", exc)
                return None

        return stops if len(stops) >= 7 else None


deepseek_daily_stop_planner = DeepSeekDailyStopPlanner()
