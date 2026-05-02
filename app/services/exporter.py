from typing import List

from app.schemas import ExecutionCard, PlanOption, TravelPlanGenerateRequest


class ExecutionCardExporter:
    def build(
        self,
        request: TravelPlanGenerateRequest,
        recommended_plan: PlanOption,
    ) -> ExecutionCard:
        risk_brief = [f"{risk.level.upper()} | {risk.title}：{risk.description}" for risk in recommended_plan.risks]
        day_brief = [
            f"Day {stop.day} {stop.time_range} | {stop.title} | {stop.highlight}"
            for stop in recommended_plan.daily_stops
        ]
        final_checklist = [
            "出发前 24 小时复核交通和天气。",
            "将酒店、车站、景点地址截图保存到手机。",
            "若接驳涉及末班车，至少提前 20 分钟到达。",
            "把执行卡转发给同行人，统一集合时间和风险预案。",
        ]

        text_version = "\n".join(
            [
                f"{request.origin_city} -> {request.destination_city} 行前执行卡",
                f"推荐方案：{recommended_plan.label}",
                f"时间：{request.departure_date} 至 {request.return_date}",
                f"预算：¥{request.budget_cny}",
                "",
                "关键行程：",
                *day_brief,
                "",
                "风险提醒：",
                *risk_brief,
                "",
                "出发前检查：",
                *final_checklist,
            ]
        )

        html_version = """
<section class="execution-card">
  <h1>自动旅行攻略 App 行前执行卡</h1>
  <p><strong>路线：</strong>{route}</p>
  <p><strong>推荐方案：</strong>{plan}</p>
  <p><strong>时间：</strong>{window}</p>
  <p><strong>预算上限：</strong>¥{budget}</p>
  <h2>关键行程</h2>
  <ul>{day_items}</ul>
  <h2>风险提醒</h2>
  <ul>{risk_items}</ul>
  <h2>出发前检查</h2>
  <ul>{check_items}</ul>
</section>
""".strip().format(
            route=f"{request.origin_city} -> {request.destination_city}",
            plan=recommended_plan.label,
            window=f"{request.departure_date} 至 {request.return_date}",
            budget=request.budget_cny,
            day_items="".join(f"<li>{item}</li>" for item in day_brief),
            risk_items="".join(f"<li>{item}</li>" for item in risk_brief),
            check_items="".join(f"<li>{item}</li>" for item in final_checklist),
        )

        return ExecutionCard(
            title="一页式行前执行卡",
            trip_window=f"{request.departure_date} 至 {request.return_date}",
            traveler_summary=f"{request.travelers} 人同行，偏好：{', '.join(request.preferences) or '未填写'}",
            final_checklist=final_checklist,
            day_brief=day_brief,
            risk_brief=risk_brief,
            text_version=text_version,
            html_version=html_version,
        )
