from typing import Dict, List, Tuple

from app.connectors.mock_connectors import MockTravelConnectors
from app.schemas import (
    DailyStop,
    PlanMetrics,
    PlanOption,
    RiskItem,
    RouteSegment,
    TravelPlanGenerateRequest,
    TravelPlanGenerateResponse,
)
from app.services.constraint_engine import ConstraintEngine
from app.services.exporter import ExecutionCardExporter
from app.services.scoring_engine import ScoringEngine
from app.services.source_reliability import SourceReliabilityService


class TravelPlannerService:
    def __init__(self) -> None:
        self.connectors = MockTravelConnectors()
        self.constraint_engine = ConstraintEngine()
        self.scoring_engine = ScoringEngine()
        self.source_service = SourceReliabilityService()
        self.exporter = ExecutionCardExporter()

    def generate(self, request: TravelPlanGenerateRequest) -> TravelPlanGenerateResponse:
        city_bundle = self.connectors.load_city_bundle(request)
        transport_candidates = self.connectors.transport_candidates(request)
        viable_candidates, risks_by_candidate = self.constraint_engine.evaluate_transport(
            request, transport_candidates
        )
        fallback_weather = city_bundle["weather"]["confidence"] < 0.7

        if not viable_candidates:
            viable_candidates = [candidate for candidate in transport_candidates if candidate["transport_id"] != "budget-route"]

        scored_candidates = self.scoring_engine.score_candidates(
            request,
            viable_candidates,
            {
                transport_id: len(candidate_risks)
                for transport_id, candidate_risks in risks_by_candidate.items()
            },
        )

        budget_candidate = max(scored_candidates, key=lambda item: item["budget_score"])
        peace_candidate = max(scored_candidates, key=lambda item: item["peace_score"])

        if budget_candidate["transport_id"] == peace_candidate["transport_id"] and len(scored_candidates) > 1:
            peace_candidate = sorted(scored_candidates, key=lambda item: item["peace_score"], reverse=True)[1]

        plans = [
            self._build_plan_option(
                request,
                budget_candidate,
                city_bundle,
                risks_by_candidate.get(budget_candidate["transport_id"], []),
                fallback_weather,
                option_id="budget-first",
                label="省钱优先方案",
                positioning="控制预算，但保留基本稳妥性",
            ),
            self._build_plan_option(
                request,
                peace_candidate,
                city_bundle,
                risks_by_candidate.get(peace_candidate["transport_id"], []),
                fallback_weather,
                option_id="peace-first",
                label="省心优先方案",
                positioning="优先保证到达稳定和接驳冗余",
            ),
        ]

        recommended_plan = plans[1] if request.preference_mode == "peace_of_mind" else plans[0]
        if request.preference_mode == "balanced":
            recommended_plan = min(plans, key=lambda item: abs(item.metrics.total_cost_cny - request.budget_cny // 2))

        execution_card = self.exporter.build(request, recommended_plan)

        return TravelPlanGenerateResponse(
            request_echo=request,
            product_positioning="V0 国内单城市验证原型：高可靠旅行决策助手",
            recommended_action=f"默认先看《{recommended_plan.label}》，再对比另一套方案的风险取舍。",
            plans=plans,
            execution_card=execution_card,
        )

    def _build_plan_option(
        self,
        request: TravelPlanGenerateRequest,
        candidate: Dict[str, object],
        city_bundle: Dict[str, object],
        existing_risks: List[RiskItem],
        fallback_weather: bool,
        option_id: str,
        label: str,
        positioning: str,
    ) -> PlanOption:
        source_refs = self.source_service.build_references(
            request,
            candidate["transport_id"],
            city_bundle["weather"]["confidence"],
            fallback_weather,
        )
        risk_items = list(existing_risks)
        food_tip = city_bundle["food"][-1]
        risk_items.append(
            RiskItem(
                level="medium",
                title="热门餐饮评价分歧",
                description=f"{food_tip[0]} 存在明显评价分歧，需要按排队成本和口味接受度取舍。",
                user_tradeoff="保留本地特色，但不保证所有人都满意。",
                source_ids=["food-local"],
            )
        )
        if fallback_weather:
            risk_items.append(
                RiskItem(
                    level="medium",
                    title="天气可信度偏低",
                    description="当前天气为原型模拟源，只能提供穿搭提醒，不能替代真实预报。",
                    user_tradeoff="先用于规划节奏，出发前必须二次确认。",
                    source_ids=["weather-forecast"],
                )
            )

        route_segments = [
            RouteSegment(
                mode=str(candidate["mode"]),
                leg_title=str(candidate["label"]),
                depart_at=str(candidate["depart_at"]),
                arrive_at=str(candidate["arrive_at"]),
                duration_minutes=int(candidate["duration_minutes"]),
                cost_cny=int(candidate["cost_cny"]),
                transfer_buffer_minutes=int(candidate["transfer_buffer_minutes"]),
                summary=str(candidate["summary"]),
                source_ids=[f"transport-{candidate['transport_id']}"],
            ),
            RouteSegment(
                mode="hotel_transfer",
                leg_title="站点/机场 -> 酒店片区",
                depart_at=str(candidate["arrive_at"]),
                arrive_at="到达后 45 分钟内",
                duration_minutes=45,
                cost_cny=60,
                transfer_buffer_minutes=None,
                summary=f"建议直接前往 {city_bundle['hotel_area']} 办理入住，避免首日折返。",
                source_ids=["rule-transfer-buffer"],
            ),
        ]

        daily_stops = self._build_daily_stops(request, city_bundle, label)

        metrics = PlanMetrics(
            total_cost_cny=int(candidate["cost_cny"]) + 1080,
            total_duration_minutes=int(candidate["duration_minutes"]) + 45,
            risk_score=max(20, 70 - len(risk_items) * 12),
            confidence_score=int((candidate["reliability"] * 100 + city_bundle["weather"]["confidence"] * 100) / 2),
        )

        summary = (
            f"{label} 适合希望{positioning}的用户。"
            f" 首段采用 {candidate['label']}，落地后优先入住 {city_bundle['hotel_area']}，"
            "其余行程集中在同一片区，减少往返。"
        )

        why_this_plan = (
            f"系统优先保留了 {candidate['label']} 这条主线路，"
            f"因为它在成本、到达时间和接驳余量之间更符合“{label}”的目标。"
        )
        decision_hint = (
            "如果你最怕出发当天翻车，优先看中转和到达窗口；"
            "如果你预算紧，则看交通成本占比和餐饮争议提示。"
        )

        return PlanOption(
            option_id=option_id,
            label=label,
            positioning=positioning,
            summary=summary,
            why_this_plan=why_this_plan,
            decision_hint=decision_hint,
            metrics=metrics,
            route_segments=route_segments,
            daily_stops=daily_stops,
            risks=risk_items,
            source_references=source_refs,
        )

    def _build_daily_stops(
        self,
        request: TravelPlanGenerateRequest,
        city_bundle: Dict[str, object],
        label: str,
    ) -> List[DailyStop]:
        attractions: List[Tuple[str, str]] = city_bundle["attractions"]
        food: List[Tuple[str, str]] = city_bundle["food"]
        pace_hint = "慢节奏收拢动线" if label == "省心优先方案" else "压缩停留时间，优先控制成本"

        return [
            DailyStop(
                day=1,
                time_range="上午",
                title="到达并办理入住",
                category="hotel",
                highlight=f"酒店建议落在 {city_bundle['hotel_area']}，先把后续动线收拢。",
                source_ids=["rule-transfer-buffer"],
            ),
            DailyStop(
                day=1,
                time_range="下午",
                title=attractions[0][0],
                category="attraction",
                highlight=f"首日用 {pace_hint} 的方式进入城市状态。",
                source_ids=["transport-balanced-route"],
            ),
            DailyStop(
                day=1,
                time_range="晚上",
                title=food[0][0],
                category="food",
                highlight=food[0][1],
                source_ids=["food-local"],
            ),
            DailyStop(
                day=2,
                time_range="上午",
                title=attractions[1][0],
                category="attraction",
                highlight="放在第二天核心时段，避免首日交通扰动。",
                source_ids=["transport-peace-route"],
            ),
            DailyStop(
                day=2,
                time_range="下午",
                title=attractions[2][0],
                category="attraction",
                highlight="与上午景点在同一片区，减少折返。",
                source_ids=["rule-transfer-buffer"],
            ),
            DailyStop(
                day=2,
                time_range="晚上",
                title=food[1][0],
                category="food",
                highlight=food[1][1],
                source_ids=["food-local"],
            ),
            DailyStop(
                day=3,
                time_range="上午",
                title=attractions[min(3, len(attractions) - 1)][0],
                category="attraction",
                highlight="离开前只放一个主要点位，给返程留缓冲。",
                source_ids=["weather-forecast"],
            ),
        ]
