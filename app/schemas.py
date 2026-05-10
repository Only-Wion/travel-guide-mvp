from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


PreferenceMode = Literal["balanced", "budget_first", "peace_of_mind"]
RiskLevel = Literal["low", "medium", "high"]


class HealthResponse(BaseModel):
    status: str
    version: str
    mode: str
    message: str


class SourceImportRequest(BaseModel):
    xiaohongshu_url: Optional[str] = None
    note_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_source_input(self) -> "SourceImportRequest":
        self.xiaohongshu_url = (self.xiaohongshu_url or "").strip() or None
        self.note_text = (self.note_text or "").strip() or None
        if not self.xiaohongshu_url and not self.note_text:
            raise ValueError("小红书链接和笔记文本至少填写一项")
        return self


class ParsedRiskTip(BaseModel):
    level: RiskLevel
    content: str


class RestaurantDetail(BaseModel):
    name: str
    phone: Optional[str] = None
    rating: Optional[str] = None
    avg_price: Optional[str] = None
    address: Optional[str] = None
    meituan_url: Optional[str] = None
    dianping_url: Optional[str] = None
    queue_tip: Optional[str] = None


class SourceImportResponse(BaseModel):
    source_type: Literal["xiaohongshu_manual", "xiaohongshu_link"]
    source_url: Optional[str] = None
    locations: List[str] = Field(default_factory=list)
    restaurants: List[str] = Field(default_factory=list)
    restaurant_details: List[RestaurantDetail] = Field(default_factory=list)
    risk_tips: List[ParsedRiskTip] = Field(default_factory=list)


class TravelPlanGenerateRequest(BaseModel):
    origin_city: str = Field(..., min_length=1)
    destination_city: str = Field(..., min_length=1)
    departure_date: str
    return_date: str
    budget_cny: int = Field(..., gt=0)
    preference_mode: PreferenceMode = "balanced"
    allow_night_arrival: bool = False
    min_transfer_buffer_minutes: int = Field(60, ge=0, le=720)
    travelers: int = Field(1, ge=1, le=9)
    preferences: List[str] = Field(default_factory=list)
    desired_places: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cities(self) -> "TravelPlanGenerateRequest":
        if self.origin_city == self.destination_city:
            raise ValueError("出发地和目的地不能相同")
        return self


class SourceReference(BaseModel):
    source_id: str
    source: str
    source_type: Literal["transport", "weather", "food", "attraction", "rule", "system"]
    title: str
    updated_at: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    conflict_status: Literal["none", "warning", "conflict"] = "none"
    note: Optional[str] = None


class RiskItem(BaseModel):
    level: RiskLevel
    title: str
    description: str
    user_tradeoff: str
    source_ids: List[str] = Field(default_factory=list)


class RouteSegment(BaseModel):
    mode: str
    leg_title: str
    depart_at: str
    arrive_at: str
    duration_minutes: int
    cost_cny: int
    transfer_buffer_minutes: Optional[int] = None
    summary: str
    source_ids: List[str] = Field(default_factory=list)


class DailyStop(BaseModel):
    day: int
    time_range: str
    title: str
    category: Literal["transport", "attraction", "food", "hotel", "rest"]
    highlight: str
    source_ids: List[str] = Field(default_factory=list)


class PlanMetrics(BaseModel):
    total_cost_cny: int
    total_duration_minutes: int
    risk_score: int = Field(..., ge=0, le=100)
    confidence_score: int = Field(..., ge=0, le=100)


class PlanOption(BaseModel):
    option_id: str
    label: str
    positioning: str
    summary: str
    why_this_plan: str
    decision_hint: str
    metrics: PlanMetrics
    route_segments: List[RouteSegment]
    daily_stops: List[DailyStop]
    risks: List[RiskItem]
    source_references: List[SourceReference]


class ExecutionCard(BaseModel):
    title: str
    trip_window: str
    traveler_summary: str
    final_checklist: List[str]
    day_brief: List[str]
    risk_brief: List[str]
    text_version: str
    html_version: str


class TravelPlanGenerateResponse(BaseModel):
    request_echo: TravelPlanGenerateRequest
    product_positioning: str
    recommended_action: str
    plans: List[PlanOption]
    execution_card: ExecutionCard
