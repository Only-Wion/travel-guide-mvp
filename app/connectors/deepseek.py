from copy import deepcopy
import json
import logging
from typing import List, Optional

from openai import OpenAI

from app.config import DS_API_KEY, DS_BASE_URL, DS_MODEL, LLM_ENABLED

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个旅游信息提取助手。用户会给你一段小红书/旅行笔记的文本。
请从中提取以下结构化信息，严格按 JSON 格式返回：

{
  "locations": ["地点1", "地点2", ...],
  "restaurants": ["餐厅1", "餐厅2", ...],
  "risk_tips": [
    {"level": "high|medium|low", "content": "风险描述"}
  ]
}

规则：
1. locations: 提取文中提到的景点、打卡地、地标、街区等具体地点名称。去重，保持原文中的中文名称。
2. restaurants: 提取文中提到的餐厅、饭馆、小吃店、咖啡馆等餐饮场所名称。去重。
3. risk_tips: 提取文中提到的风险、警告、避雷提示。
   - level 用 "high"（强烈避雷/千万别去/宰客/诈骗/关门）、"medium"（注意/排队/预约/堵车/限流）、"low"（建议/早点去/带伞/蚊虫）
   - content 用一句话总结该风险
4. 如果某类信息找不到，返回空数组 []。
5. 只返回 JSON，不要加任何解释文字，不要加 markdown 代码块标记。"""


class DeepSeekNoteParser:
    """Use DeepSeek API to parse travel note text into structured data."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None
        self._last_parse_result: Optional[dict] = None

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

    def parse_note(
        self,
        note_text: str,
    ) -> dict:
        """Parse note text and return structured data.

        Returns a dict with keys: locations, restaurants, risk_tips.
        On failure, returns empty dict.
        """
        if not self.available:
            logger.warning("DeepSeek API key not configured, skip LLM parsing")
            return {}

        text = note_text.strip()
        if len(text) < 20:
            logger.info("Note text too short for LLM parsing (%d chars)", len(text))
            return {}

        # Truncate very long texts to stay within token limits
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.info("Note text truncated from %d to %d chars", len(note_text), max_chars)

        try:
            response = self.client.chat.completions.create(
                model=DS_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content or ""
            result = self._parse_response(raw)
            if result:
                self.remember_parse_result(result)
            return result

        except Exception as exc:
            logger.error("DeepSeek API call failed: %s", exc)
            return {}

    def _parse_response(self, raw: str) -> dict:
        """Parse the LLM response text into a dict."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            # Remove closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON, raw: %.200s", raw)
            return {}

        # Validate and normalize structure
        result: dict = {}
        if isinstance(data.get("locations"), list):
            result["locations"] = [str(item).strip() for item in data["locations"] if str(item).strip()]
        if isinstance(data.get("restaurants"), list):
            result["restaurants"] = [str(item).strip() for item in data["restaurants"] if str(item).strip()]
        if isinstance(data.get("risk_tips"), list):
            tips = []
            for tip in data["risk_tips"]:
                if isinstance(tip, dict) and tip.get("content"):
                    level = tip.get("level", "low")
                    if level not in ("high", "medium", "low"):
                        level = "low"
                    tips.append({
                        "level": level,
                        "content": str(tip["content"]).strip(),
                    })
            result["risk_tips"] = tips
        return result

    def remember_parse_result(
        self,
        result: dict,
        *,
        destination_city: Optional[str] = None,
        source_type: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> None:
        """Keep the latest useful Xiaohongshu parse result for later planning."""
        if not result:
            return
        stored = deepcopy(result)
        metadata = {
            "destination_city": destination_city,
            "source_type": source_type,
            "source_url": source_url,
        }
        stored["_metadata"] = {
            key: value for key, value in metadata.items() if value
        }
        self._last_parse_result = stored

    def get_last_parse_result(
        self,
        *,
        destination_city: Optional[str] = None,
    ) -> Optional[dict]:
        """Return the latest cached parse result, optionally scoped by city."""
        if not self._last_parse_result:
            return None
        metadata = self._last_parse_result.get("_metadata", {})
        cached_city = metadata.get("destination_city")
        if destination_city and cached_city and cached_city != destination_city:
            return None
        return deepcopy(self._last_parse_result)


# Singleton
deepseek_parser = DeepSeekNoteParser()


FOOD_SEARCH_PROMPT = """你是一个帮助用户查找餐厅信息的助手。给一个餐厅名称和所在城市，请搜索美团/大众点评上的信息，按 JSON 返回：

{
  "name": "餐厅名",
  "phone": "电话或null",
  "rating": "评分(如4.3)或null",
  "avg_price": "人均(如¥68)或null",
  "address": "地址或null",
  "meituan_url": "美团搜索链接或null",
  "dianping_url": "大众点评搜索链接或null",
  "queue_tip": "排队/预约提示或null"
}

规则：
1. meituan_url 格式：https://i.meituan.com/search/poi?q=餐厅名，dianping_url 格式：https://m.dianping.com/search/keyword?keyword=餐厅名
2. 如果找不到信息，对应字段填 null
3. 只返回 JSON，不要任何解释"""


class DeepSeekFoodSearch:
    """Search restaurant info from Meituan/Dianping via DeepSeek web search."""

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

    def search_restaurant(self, name: str, city: str) -> Optional[dict]:
        """Search restaurant details via web search."""
        if not self.available:
            return None
        query = f'在{city}搜索餐厅"{name}"的美团和大众点评信息，包括电话、评分、人均价格、地址、排队情况'
        try:
            response = self.client.chat.completions.create(
                model=DS_MODEL,
                messages=[
                    {"role": "system", "content": FOOD_SEARCH_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.1,
                max_tokens=1000,
                extra_body={"enable_search": True},
            )
            raw = response.choices[0].message.content or ""
            return self._parse(raw)
        except Exception as exc:
            logger.error("Food search failed for %s: %s", name, exc)
            return None

    def _parse(self, raw: str) -> Optional[dict]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and data.get("name"):
                return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse food search result: %.200s", raw)
        return None


deepseek_food_search = DeepSeekFoodSearch()
