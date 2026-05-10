#!/usr/bin/env python
"""
Demonstration script showing how to switch between mock and DeepSeek connectors.
"""

import os
import json

# Example 1: Using mock connectors (default)
print("=" * 80)
print("EXAMPLE 1: Mock Connectors (Default)")
print("=" * 80)
print()

# Make sure we use mock connectors
os.environ["USE_DEEPSEEK_CONNECTORS"] = "false"

from app.services.planner import TravelPlannerService
from app.schemas import TravelPlanGenerateRequest

# Need to reimport after setting env var
import importlib
import app.services.planner

importlib.reload(app.services.planner)
from app.services.planner import TravelPlannerService as TravelPlannerService1

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

planner1 = TravelPlannerService1()
print(f"Planner connectors class: {planner1.connectors.__class__.__name__}")
print()

# Show mock connector data
city_bundle = planner1.connectors.load_city_bundle(request)
print("City Bundle (Mock):")
print(f"  - Weather: {city_bundle['weather']['summary']}")
print(f"  - Attractions: {len(city_bundle['attractions'])} items")
print(f"  - Food: {len(city_bundle['food'])} items")
print()

# Example 2: Switching to DeepSeek connectors
print("=" * 80)
print("EXAMPLE 2: DeepSeek Connectors (With Environment Variable)")
print("=" * 80)
print()
print("To enable DeepSeek connectors, set these environment variables:")
print()
print("  PowerShell:")
print('    $env:USE_DEEPSEEK_CONNECTORS = "true"')
print('    $env:DS_API_KEY = "sk-your-deepseek-api-key"')
print('    $env:DS_BASE_URL = "https://api.deepseek.com/v1"')
print()
print("  Linux/Mac (bash):")
print("    export USE_DEEPSEEK_CONNECTORS=true")
print("    export DS_API_KEY=sk-your-deepseek-api-key")
print("    export DS_BASE_URL=https://api.deepseek.com/v1")
print()
print("Then start the server:")
print("    .\\venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8001")
print()
print("Key points:")
print("  ✓ Both connectors implement the same interface")
print("  ✓ No code changes needed, just environment variables")
print("  ✓ DeepSeek generates dynamic, context-aware travel data")
print("  ✓ Falls back to mock if DeepSeek is unavailable")
print("  ✓ All tests pass with both implementations")
print()

# Summary
print("=" * 80)
print("SUMMARY: Switching Strategy")
print("=" * 80)
print()
print("┌─────────────────────────────────────────────────────────────────────┐")
print("│ Environment Variable: USE_DEEPSEEK_CONNECTORS                      │")
print("├─────────────────────────────────┬─────────────────────────────────┤")
print('│ Value (default: "false")        │ Connector Used                  │')
print("├─────────────────────────────────┼─────────────────────────────────┤")
print('│ "false" or unset                │ MockTravelConnectors            │')
print('│ "true"                          │ DeepSeekTravelConnectors        │')
print("│ (if DS_API_KEY is set)          │                                 │")
print('│ "true"                          │ MockTravelConnectors (fallback) │')
print("│ (if DS_API_KEY is NOT set)      │                                 │")
print("└─────────────────────────────────┴─────────────────────────────────┘")
print()
