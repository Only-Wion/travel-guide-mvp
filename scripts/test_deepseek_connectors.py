#!/usr/bin/env python
"""
Test script to demonstrate DeepSeek-powered travel data generation.
Replaces mock data with AI-generated dynamic data.
"""

import json
from app.connectors.deepseek_connectors import deepseek_connectors
from app.schemas import TravelPlanGenerateRequest


def test_deepseek_connectors():
    """Test generating city bundle and transport candidates via DeepSeek."""

    # Example request
    request = TravelPlanGenerateRequest(
        origin_city="上海",
        destination_city="杭州",
        departure_date="2026-05-10",
        return_date="2026-05-13",
        budget_cny=3000,
        preference_mode="balanced",
        allow_night_arrival=False,
        min_transfer_buffer_minutes=60,
        travelers=2,
        preferences=["文化", "美食"],
        desired_places=["西湖", "灵隐寺"],
    )

    print("=" * 80)
    print("Test: DeepSeek Connectors")
    print("=" * 80)
    print()

    if not deepseek_connectors.available:
        print("❌ DeepSeek LLM not enabled (DS_API_KEY not set)")
        print("   Set DS_API_KEY environment variable to enable")
        return

    print(f"✅ DeepSeek LLM enabled, model: deepseek-chat")
    print()

    # Test 1: Load city bundle
    print("TEST 1: Load City Bundle (Weather, Attractions, Restaurants, Hotels)")
    print("-" * 80)
    city_bundle = deepseek_connectors.load_city_bundle(request)
    print(json.dumps(city_bundle, ensure_ascii=False, indent=2))
    print()

    # Test 2: Load transport candidates
    print("TEST 2: Generate Transport Candidates")
    print("-" * 80)
    candidates = deepseek_connectors.transport_candidates(request)
    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ City bundle generated with:")
    weather = city_bundle.get("weather", {})
    attractions = city_bundle.get("attractions", [])
    food = city_bundle.get("food", [])
    hotel = city_bundle.get("hotel_area", "")
    print(f"   - Weather: {weather.get('summary', 'N/A')[:50]}...")
    print(f"   - Attractions: {len(attractions)} items")
    print(f"   - Food: {len(food)} items")
    print(f"   - Hotel area: {hotel}")
    print()
    print(f"✅ Generated {len(candidates)} transport options:")
    for idx, cand in enumerate(candidates, 1):
        print(
            f"   {idx}. {cand.get('label')} (¥{cand.get('cost_cny')} for {request.travelers} people, "
            f"reliability: {cand.get('reliability'):.2f})"
        )
    print()


if __name__ == "__main__":
    test_deepseek_connectors()
