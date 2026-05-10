import os
from typing import Union

from app.connectors.mock_connectors import MockTravelConnectors


def get_travel_connectors() -> Union[MockTravelConnectors, "DeepSeekTravelConnectors"]:
    """Factory function to get travel connectors based on environment variable.

    Returns:
        - DeepSeekTravelConnectors if USE_DEEPSEEK_CONNECTORS=true and DS_API_KEY is set
        - MockTravelConnectors otherwise (default)

    Environment variables:
        - USE_DEEPSEEK_CONNECTORS: Set to "false" to disable DeepSeek-powered connectors (default: true)
        - DS_API_KEY: DeepSeek API key (required if USE_DEEPSEEK_CONNECTORS=true)
    """
    use_deepseek = os.getenv("USE_DEEPSEEK_CONNECTORS", "true").lower() == "true"

    if use_deepseek:
        try:
            # Import here to avoid circular import and lazy loading
            from app.connectors.deepseek_connectors import deepseek_connectors
            from app.config import LLM_ENABLED

            if LLM_ENABLED:
                print("[INFO] Using DeepSeek-powered travel connectors")
                return deepseek_connectors
            else:
                print(
                    "[WARN] DeepSeek not available (DS_API_KEY not set), falling back to mock connectors"
                )
                return MockTravelConnectors()
        except Exception as exc:
            print(
                f"[WARN] Failed to load DeepSeek connectors: {exc}, falling back to mock connectors"
            )
            return MockTravelConnectors()
    else:
        print("[INFO] Using mock travel connectors")
        return MockTravelConnectors()
