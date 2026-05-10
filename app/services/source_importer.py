import html
import json
import logging
import re
from collections import OrderedDict
from typing import Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.connectors.deepseek import deepseek_parser
from app.schemas import ParsedRiskTip, SourceImportRequest, SourceImportResponse

logger = logging.getLogger(__name__)


PLACE_SUFFIXES = (
    "景区|公园|寺|塔|湖|山|博物馆|广场|码头|古镇|古城|村|市场|乐园|天地|口岸|"
    "机场|高铁站|火车站|地铁站|商场|中心|江|河|桥|街|路|巷|里|站|阁|坊|弄"
)
RESTAURANT_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9·()（）\-]{2,24}"
    r"(?:餐厅|饭店|饭馆|小馆|食堂|酒家|火锅|烧烤|烤肉|料理|咖啡馆|咖啡店|茶馆|甜品店|面馆|粉店|菜馆|酒吧|大排档|小吃店|私房菜|早餐店|美食街|美食一条街|小吃街|夜市)"
)
LOCATION_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9·()（）\-]{2,24}"
    rf"(?:{PLACE_SUFFIXES})"
)
LOCATION_SUFFIX_PATTERN = re.compile(
    rf"({PLACE_SUFFIXES})$"
)
LOCATION_SPLIT_PATTERN = re.compile(r"(?:从|再去|然后去|步行到|走到|前往|去|到|逛|打卡)")
ROUTE_SEQUENCE_PATTERN = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9·()（）]{2,20}(?:[-—–－][\u4e00-\u9fffA-Za-z0-9·()（）]{2,20}){2,})"
)
COMPOUND_LOCATION_PATTERN = re.compile(
    rf"([\u4e00-\u9fffA-Za-z0-9·()（）]{{1,12}}?(?:{PLACE_SUFFIXES}))"
)
RESTAURANT_CONTEXT_PATTERN = re.compile(
    r"(?:早餐吃|午饭吃|午餐吃|晚饭吃|晚餐吃|夜宵吃|吃|喝)"
    r"([\u4e00-\u9fffA-Za-z0-9·()（）\-]{2,24})"
)
RISK_KEYWORDS = {
    "high": ["避雷", "别去", "不要", "千万别", "踩雷", "黑车", "宰客", "黄牛", "诈骗", "关门", "闭馆"],
    "medium": ["注意", "排队", "限流", "预约", "堵车", "绕路", "打车难", "暴雨", "台风", "大风", "售罄"],
    "low": ["建议", "早点", "提前", "现金", "辣", "蚊虫", "晒", "带伞"],
}
SUPPORTED_HOSTS = {
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "xhslink.com",
    "www.xhslink.com",
}
META_CONTENT_PATTERNS = [
    re.compile(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
]
JSON_TEXT_PATTERNS = [
    re.compile(r'"desc"\s*:\s*"((?:\\.|[^"])*)"', re.DOTALL),
    re.compile(r'"content"\s*:\s*"((?:\\.|[^"])*)"', re.DOTALL),
]
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
SCRIPT_PATTERN = re.compile(r"<script[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
DETAIL_TITLE_PATTERN = re.compile(
    r'<div[^>]+id="detail-title"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
DETAIL_DESC_PATTERN = re.compile(
    r'<div[^>]+id="detail-desc"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
INITIAL_STATE_PATTERN = re.compile(
    r"window\.__INITIAL_STATE__=(\{.*?\})</script>",
    re.IGNORECASE | re.DOTALL,
)
URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
SHARE_TEXT_MARKERS = [
    "复制后打开【小红书】查看笔记",
    "打开【小红书】查看笔记",
    "复制本条信息",
    "查看笔记",
]
GENERIC_LOCATION_TOKENS = {
    "地铁站",
    "火车站",
    "高铁站",
    "机场",
    "博物馆",
    "广场",
    "公园",
    "古镇",
    "古城",
    "市场",
    "商场",
    "中心",
}


class SourceImportError(ValueError):
    pass


class SourceImporterService:
    def import_manual_note(self, request: SourceImportRequest) -> SourceImportResponse:
        text, source_type, source_url = self._resolve_note_text(request)

        # Try LLM-based parsing first (DeepSeek), fall back to regex
        llm_result = self._try_llm_parse(text)
        if llm_result:
            locations = llm_result.get("locations", [])
            restaurants = llm_result.get("restaurants", [])
            risk_tips = [
                ParsedRiskTip(level=tip["level"], content=tip["content"])
                for tip in llm_result.get("risk_tips", [])
            ]
            logger.info("Using DeepSeek LLM parse result: %d locations, %d restaurants, %d tips",
                        len(locations), len(restaurants), len(risk_tips))
        else:
            locations = self._extract_locations(text)
            restaurants = self._extract_restaurants(text)
            risk_tips = self._extract_risk_tips(text)
            logger.info("Using regex parse result (LLM unavailable or failed): %d locations, %d restaurants, %d tips",
                        len(locations), len(restaurants), len(risk_tips))

        return SourceImportResponse(
            source_type=source_type,
            source_url=source_url,
            locations=locations,
            restaurants=restaurants,
            risk_tips=risk_tips,
        )

    @staticmethod
    def _try_llm_parse(text: str) -> Optional[dict]:
        """Try to parse note text using DeepSeek LLM.
        Returns None if parsing fails or LLM is unavailable.
        """
        if not deepseek_parser.available:
            return None
        try:
            result = deepseek_parser.parse_note(text)
            # Only accept result if it contains at least some useful data
            if result and (result.get("locations") or result.get("restaurants") or result.get("risk_tips")):
                return result
        except Exception:
            logger.exception("LLM parse failed, falling back to regex")
        return None

    def _resolve_note_text(self, request: SourceImportRequest) -> tuple[str, str, Optional[str]]:
        source_url = self._extract_source_url(request.xiaohongshu_url) if request.xiaohongshu_url else None
        note_text = request.note_text

        if note_text and self._looks_like_share_text(note_text):
            source_url = source_url or self._extract_source_url(note_text)
            note_text = None

        if note_text:
            return note_text, "xiaohongshu_manual", source_url
        if not source_url and request.xiaohongshu_url:
            if URL_PATTERN.search(request.xiaohongshu_url):
                raise SourceImportError("当前只支持小红书或 xhslink 链接")
            raise SourceImportError("未识别到有效的小红书链接，请粘贴完整分享内容或标准 URL")
        if not source_url:
            raise SourceImportError("缺少可导入的笔记文本或小红书链接")
        return self._fetch_remote_note_text(source_url), "xiaohongshu_link", source_url

    def _fetch_remote_note_text(self, source_url: str) -> str:
        self._validate_source_url(source_url)
        html_content = self._fetch_html(source_url)
        note_text = self._extract_note_text_from_html(html_content)
        if not note_text:
            raise SourceImportError("链接可访问，但未提取到正文，请改为手动粘贴笔记文本")
        return note_text

    def _validate_source_url(self, source_url: str) -> None:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise SourceImportError("只支持 http 或 https 的小红书链接")
        if parsed.netloc.lower() not in SUPPORTED_HOSTS:
            raise SourceImportError("当前只支持小红书或 xhslink 链接")

    def _extract_source_url(self, raw_text: Optional[str]) -> Optional[str]:
        if not raw_text:
            return None
        candidate = raw_text.strip()
        if candidate.startswith(("http://", "https://")):
            parsed = urlparse(candidate)
            if parsed.netloc.lower() in SUPPORTED_HOSTS:
                return candidate
        for match in URL_PATTERN.findall(raw_text):
            sanitized = match.rstrip("，。；;！!）)]】>\"'")
            parsed = urlparse(sanitized)
            if parsed.netloc.lower() in SUPPORTED_HOSTS:
                return sanitized
        return None

    def _looks_like_share_text(self, text: str) -> bool:
        source_url = self._extract_source_url(text)
        if not source_url:
            return False
        return any(marker in text for marker in SHARE_TEXT_MARKERS) or "xhslink.com" in source_url

    def _fetch_html(self, source_url: str) -> str:
        request = Request(
            source_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="ignore")
        except HTTPError as exc:
            raise SourceImportError(f"抓取失败，远端返回 HTTP {exc.code}") from exc
        except URLError as exc:
            raise SourceImportError("抓取失败，请检查链接是否可访问") from exc

    def _extract_note_text_from_html(self, html_content: str) -> str:
        initial_state_note = self._extract_note_from_initial_state(html_content)
        if initial_state_note:
            return initial_state_note

        dom_note = self._extract_note_from_dom(html_content)
        if dom_note:
            return dom_note

        candidates: List[str] = []
        for pattern in META_CONTENT_PATTERNS:
            candidates.extend(pattern.findall(html_content))
        for pattern in JSON_TEXT_PATTERNS:
            candidates.extend(pattern.findall(html_content))
        title_match = TITLE_PATTERN.search(html_content)
        if title_match:
            candidates.append(title_match.group(1))

        for candidate in candidates:
            normalized = self._normalize_html_candidate(candidate)
            if self._is_meaningful_note_text(normalized):
                return normalized

        body_text = self._extract_body_text(html_content)
        if self._is_meaningful_note_text(body_text):
            return body_text
        return ""

    def _extract_note_from_initial_state(self, html_content: str) -> str:
        match = INITIAL_STATE_PATTERN.search(html_content)
        if not match:
            return ""
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return ""

        note_map = payload.get("note", {}).get("noteDetailMap", {})
        if not isinstance(note_map, dict) or not note_map:
            return ""

        first_entry = next(iter(note_map.values()), {})
        note = first_entry.get("note", {}) if isinstance(first_entry, dict) else {}
        title = self._normalize_html_candidate(str(note.get("title", "")))
        desc = self._normalize_html_candidate(str(note.get("desc", "")))
        combined = "\n".join(part for part in [title, desc] if part)
        return combined if self._is_meaningful_note_text(combined or desc) else ""

    def _extract_note_from_dom(self, html_content: str) -> str:
        title_match = DETAIL_TITLE_PATTERN.search(html_content)
        desc_match = DETAIL_DESC_PATTERN.search(html_content)
        title = self._normalize_html_candidate(self._strip_tags(title_match.group(1))) if title_match else ""
        desc = self._normalize_html_candidate(self._strip_tags(desc_match.group(1))) if desc_match else ""
        combined = "\n".join(part for part in [title, desc] if part)
        return combined if self._is_meaningful_note_text(combined or desc) else ""

    def _normalize_html_candidate(self, candidate: str) -> str:
        candidate = self._decode_json_escaped_text(candidate)
        candidate = html.unescape(candidate)
        candidate = self._strip_tags(candidate)
        candidate = candidate.replace("[话题]", "")
        candidate = re.sub(r"\s+", " ", candidate).strip()
        candidate = candidate.replace("小红书", "").strip(" -|")
        return candidate

    def _decode_json_escaped_text(self, raw: str) -> str:
        try:
            return json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            return raw

    def _extract_body_text(self, html_content: str) -> str:
        content = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_content, flags=re.IGNORECASE | re.DOTALL)
        content = SCRIPT_PATTERN.sub(" ", content)
        content = TAG_PATTERN.sub(" ", content)
        content = html.unescape(content)
        content = re.sub(r"\s+", " ", content).strip()
        return content[:2000]

    def _is_meaningful_note_text(self, text: str) -> bool:
        if not text or len(text) < 12:
            return False
        blocked_signals = ["验证码", "登录后查看更多", "打开 app", "服务条款", "隐私政策"]
        if any(signal in text for signal in blocked_signals):
            return False
        return True

    def _extract_restaurants(self, text: str) -> List[str]:
        matches = [self._normalize_restaurant(item.group(0)) for item in RESTAURANT_PATTERN.finditer(text)]
        context_matches: List[str] = []
        for line in self._split_lines(text):
            context_matches.extend(
                self._normalize_restaurant(item.group(1))
                for item in RESTAURANT_CONTEXT_PATTERN.finditer(line)
            )
        matches.extend(context_matches)
        return self._dedupe(matches)

    def _extract_locations(self, text: str) -> List[str]:
        matches: List[str] = []
        for line in self._split_lines(text):
            matches.extend(self._extract_location_candidates_from_line(line))
        matches.extend(self._extract_route_locations(text))
        expanded_matches: List[str] = []
        for item in matches:
            expanded_matches.extend(self._split_compound_location(item))
        return self._dedupe(expanded_matches)

    def _extract_route_locations(self, text: str) -> List[str]:
        locations: List[str] = []
        for route in ROUTE_SEQUENCE_PATTERN.findall(text):
            for part in re.split(r"[-—–－]", route):
                value = self._normalize_location_chunk(part)
                if not value:
                    continue
                if LOCATION_PATTERN.fullmatch(value) or LOCATION_SUFFIX_PATTERN.search(value):
                    locations.append(value)
        return locations

    def _extract_risk_tips(self, text: str) -> List[ParsedRiskTip]:
        tips: List[ParsedRiskTip] = []
        for sentence in self._split_sentences(text):
            normalized = self._clean_sentence(sentence)
            if not normalized:
                continue
            level = self._infer_risk_level(normalized)
            if level:
                tips.append(ParsedRiskTip(level=level, content=normalized))
        return self._dedupe_risks(tips)

    def _extract_location_candidates_from_line(self, line: str) -> List[str]:
        candidates = []
        for segment in re.split(r"[，。,；;、/→\-｜|]", line):
            for chunk in LOCATION_SPLIT_PATTERN.split(segment):
                value = self._normalize_location_chunk(chunk)
                if not value:
                    continue
                if LOCATION_PATTERN.fullmatch(value) or LOCATION_SUFFIX_PATTERN.search(value):
                    candidates.append(value)
        return candidates

    def _normalize_location_chunk(self, value: str) -> str:
        cleaned = self._clean_entity(value)
        cleaned = re.sub(
            r"^(注意[:：]?|避雷[:：]?|建议[:：]?|路线|推荐|周边|附近|沿线|citywalk|Citywalk|上午|中午|下午|晚上|早上|周末|工作日|先|再)+",
            "",
            cleaned,
        )
        cleaned = re.sub(
            r"(排队很久.*|最好提前预约.*|坐坐.*|打车.*|黑车.*|不要.*|这段很适合.*|很适合.*|适合.*|"
            r"这条citywalk路线.*|这条路线.*|外围.*|历史人文景观.*|美食一条街.*)$",
            "",
            cleaned,
        )
        if len(cleaned) < 2 or len(cleaned) > 24:
            return ""
        if any(keyword in cleaned for keyword in ["餐厅", "饭", "咖啡", "火锅", "料理", "酒吧", "甜品"]):
            return ""
        return cleaned

    def _normalize_restaurant(self, value: str) -> str:
        cleaned = self._clean_entity(value)
        cleaned = re.sub(
            r"^(早餐吃|午饭吃|午餐吃|晚饭吃|晚餐吃|夜宵吃|吃|喝|饭可以去|下午去|饭后去|午饭后去|晚饭后去|去|再去|打卡)+",
            "",
            cleaned,
        )
        if any(keyword in cleaned for keyword in ["杭帮菜", "价格", "路线"]):
            return ""
        return cleaned

    def _infer_risk_level(self, sentence: str) -> Optional[str]:
        for level, keywords in RISK_KEYWORDS.items():
            if any(keyword in sentence for keyword in keywords):
                return level
        return None

    def _split_lines(self, text: str) -> List[str]:
        return [line.strip(" -•\t") for line in text.splitlines() if line.strip()]

    def _split_sentences(self, text: str) -> List[str]:
        chunks = re.split(r"[\n。！？!?\r]+", text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _clean_entity(self, value: str) -> str:
        return re.sub(r"\s+", "", value).strip("，。,；;：:（）()[]【】")

    def _clean_sentence(self, value: str) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        return compact.strip("，。,；;")

    def _strip_tags(self, value: str) -> str:
        return TAG_PATTERN.sub(" ", value)

    def _split_compound_location(self, value: str) -> List[str]:
        matches = [item.group(1) for item in COMPOUND_LOCATION_PATTERN.finditer(value)]
        if len(matches) >= 2 and "".join(matches) == value and not any(
            item in GENERIC_LOCATION_TOKENS for item in matches
        ):
            return matches
        return [value]

    def _dedupe(self, items: Iterable[str]) -> List[str]:
        ordered = OrderedDict()
        for item in items:
            if item:
                ordered[item] = None
        return list(ordered.keys())

    def _dedupe_risks(self, items: List[ParsedRiskTip]) -> List[ParsedRiskTip]:
        ordered = OrderedDict()
        for item in items:
            ordered[(item.level, item.content)] = item
        return list(ordered.values())
