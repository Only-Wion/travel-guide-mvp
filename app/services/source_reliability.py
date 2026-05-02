from typing import List

from app.schemas import SourceReference, TravelPlanGenerateRequest


class SourceReliabilityService:
    def build_references(
        self,
        request: TravelPlanGenerateRequest,
        transport_id: str,
        weather_confidence: float,
        fallback_weather: bool,
    ) -> List[SourceReference]:
        refs = [
            SourceReference(
                source_id="rule-arrival-window",
                source="系统规则",
                source_type="rule",
                title="夜间到达限制",
                updated_at="2026-04-14T09:00:00+08:00",
                confidence=0.95,
                note="由用户输入的出行限制直接生成。",
            ),
            SourceReference(
                source_id="rule-transfer-buffer",
                source="系统规则",
                source_type="rule",
                title="最小中转缓冲",
                updated_at="2026-04-14T09:00:00+08:00",
                confidence=0.95,
                note="用于判断接驳链路是否稳妥。",
            ),
            SourceReference(
                source_id=f"transport-{transport_id}",
                source="Mock 交通数据源",
                source_type="transport",
                title=f"{request.origin_city} -> {request.destination_city} 交通候选",
                updated_at="2026-04-14T09:00:00+08:00",
                confidence=0.78,
                note="V0 原型使用模拟数据，正式出发前需复核真实时刻。",
            ),
            SourceReference(
                source_id="weather-forecast",
                source="Mock 天气数据源",
                source_type="weather",
                title=f"{request.destination_city} 旅行天气摘要",
                updated_at="2026-04-14T09:00:00+08:00",
                confidence=weather_confidence,
                conflict_status="warning" if fallback_weather else "none",
                note="天气仅用于提醒，不替代出发前 24 小时复查。",
            ),
            SourceReference(
                source_id="food-local",
                source="Mock 餐饮汇总",
                source_type="food",
                title=f"{request.destination_city} 餐饮建议",
                updated_at="2026-04-14T09:00:00+08:00",
                confidence=0.72,
                conflict_status="warning",
                note="餐厅评价存在主观差异，已保留争议提示。",
            ),
        ]
        return refs
