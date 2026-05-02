from typing import Dict, List

from app.schemas import TravelPlanGenerateRequest


class ScoringEngine:
    def score_candidates(
        self,
        request: TravelPlanGenerateRequest,
        candidates: List[Dict[str, object]],
        risk_counts: Dict[str, int],
    ) -> List[Dict[str, object]]:
        scored: List[Dict[str, object]] = []

        for candidate in candidates:
            cost_ratio = candidate["cost_cny"] / max(request.budget_cny, 1)
            reliability_score = int(candidate["reliability"] * 100)
            buffer_score = min(int(candidate["transfer_buffer_minutes"]), 120)
            risk_penalty = risk_counts.get(candidate["transport_id"], 0) * 12

            budget_score = 100 - int(cost_ratio * 75) + (buffer_score // 12) - risk_penalty
            peace_score = reliability_score + (buffer_score // 3) - int(cost_ratio * 20) - risk_penalty

            candidate_with_scores = dict(candidate)
            candidate_with_scores["budget_score"] = budget_score
            candidate_with_scores["peace_score"] = peace_score
            scored.append(candidate_with_scores)

        return scored
