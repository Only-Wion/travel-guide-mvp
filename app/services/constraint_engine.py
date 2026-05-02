from typing import Dict, List, Tuple

from app.schemas import RiskItem, TravelPlanGenerateRequest


class ConstraintEngine:
    def evaluate_transport(
        self,
        request: TravelPlanGenerateRequest,
        candidates: List[Dict[str, object]],
    ) -> Tuple[List[Dict[str, object]], Dict[str, List[RiskItem]]]:
        viable: List[Dict[str, object]] = []
        risks_by_candidate: Dict[str, List[RiskItem]] = {}

        for candidate in candidates:
            candidate_risks: List[RiskItem] = []

            if candidate["arrival_is_night"] and not request.allow_night_arrival:
                candidate_risks.append(
                    RiskItem(
                        level="high",
                        title="夜间到达被规则拦截",
                        description="该方案在 22:00 后到达，不符合“禁止夜间到达”的硬约束。",
                        user_tradeoff="除非放宽规则，否则不建议采用该方案。",
                        source_ids=["rule-arrival-window"],
                    )
                )

            if candidate["transfer_buffer_minutes"] < request.min_transfer_buffer_minutes:
                candidate_risks.append(
                    RiskItem(
                        level="high",
                        title="中转缓冲不足",
                        description=(
                            f"当前缓冲仅 {candidate['transfer_buffer_minutes']} 分钟，"
                            f"低于你设置的 {request.min_transfer_buffer_minutes} 分钟。"
                        ),
                        user_tradeoff="更省钱，但误点后几乎没有补救空间。",
                        source_ids=["rule-transfer-buffer"],
                    )
                )

            if candidate["cost_cny"] > request.budget_cny * 0.55:
                candidate_risks.append(
                    RiskItem(
                        level="medium",
                        title="交通成本占比偏高",
                        description="单交通方案已占去总预算的大头，会压缩住宿和餐饮空间。",
                        user_tradeoff="适合重视稳妥的用户，不适合极限控预算。",
                        source_ids=["rule-budget-share"],
                    )
                )

            risks_by_candidate[candidate["transport_id"]] = candidate_risks

            blocked = any(
                risk.title in {"夜间到达被规则拦截", "中转缓冲不足"} and risk.level == "high"
                for risk in candidate_risks
            )
            if not blocked:
                viable.append(candidate)

        return viable, risks_by_candidate
