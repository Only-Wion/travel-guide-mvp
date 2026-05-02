from fastapi.testclient import TestClient

from app.api import source_importer_service
from app.main import app


client = TestClient(app)


def payload(**overrides):
    base = {
        "origin_city": "南京",
        "destination_city": "杭州",
        "departure_date": "2026-05-01",
        "return_date": "2026-05-03",
        "budget_cny": 2800,
        "preference_mode": "balanced",
        "allow_night_arrival": False,
        "min_transfer_buffer_minutes": 60,
        "travelers": 2,
        "preferences": ["citywalk", "local_food"],
    }
    base.update(overrides)
    return base


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_cases():
    response = client.get("/api/v1/demo-cases")
    assert response.status_code == 200
    assert len(response.json()["cases"]) == 3


def test_generate_two_distinct_plans():
    response = client.post("/api/v1/plans/generate", json=payload())
    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) == 2
    assert data["plans"][0]["label"] != data["plans"][1]["label"]
    assert data["execution_card"]["title"] == "一页式行前执行卡"


def test_night_arrival_rule_filters_risky_route():
    response = client.post(
        "/api/v1/plans/generate",
        json=payload(allow_night_arrival=False, min_transfer_buffer_minutes=60),
    )
    data = response.json()
    transport_titles = [
        segment["leg_title"]
        for plan in data["plans"]
        for segment in plan["route_segments"]
        if segment["mode"] in {"high_speed_rail", "flight"}
    ]
    assert "晚班高铁 + 地铁" not in transport_titles


def test_transfer_buffer_rule_and_sources_are_exposed():
    response = client.post(
        "/api/v1/plans/generate",
        json=payload(min_transfer_buffer_minutes=100, preference_mode="peace_of_mind"),
    )
    assert response.status_code == 200
    data = response.json()
    assert any(
        source["source"] == "Mock 交通数据源"
        for plan in data["plans"]
        for source in plan["source_references"]
    )
    assert any(
        "updated_at" in source
        for plan in data["plans"]
        for source in plan["source_references"]
    )


def test_fallback_city_still_generates_with_uncertainty():
    response = client.post(
        "/api/v1/plans/generate",
        json=payload(destination_city="苏州"),
    )
    assert response.status_code == 200
    data = response.json()
    weather_notes = [
        risk["title"]
        for plan in data["plans"]
        for risk in plan["risks"]
    ]
    assert "天气可信度偏低" in weather_notes


def test_import_manual_source_extracts_locations_restaurants_and_risks():
    response = client.post(
        "/api/v1/sources/import",
        json={
            "xiaohongshu_url": "https://www.xiaohongshu.com/explore/demo",
            "note_text": "\n".join(
                [
                    "西湖周边 citywalk：从龙翔桥地铁站走到西湖，再去灵隐寺。",
                    "早餐吃老李面馆，下午去山野咖啡馆坐坐。",
                    "注意：周末灵隐寺排队很久，最好提前预约。",
                    "避雷：西湖边黑车很多，不要随便上车。",
                    "建议带伞，杭州下午容易下雨。",
                ]
            ),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "xiaohongshu_manual"
    assert "龙翔桥地铁站" in data["locations"]
    assert "灵隐寺" in data["locations"]
    assert "老李面馆" in data["restaurants"]
    assert "山野咖啡馆" in data["restaurants"]
    assert any(item["level"] == "high" for item in data["risk_tips"])
    assert any(item["level"] == "medium" for item in data["risk_tips"])
    assert any(item["level"] == "low" for item in data["risk_tips"])


def test_import_link_source_extracts_content(monkeypatch):
    def fake_fetch_remote_note_text(source_url: str) -> str:
        assert source_url == "https://www.xiaohongshu.com/explore/demo"
        return "\n".join(
            [
                "从龙翔桥地铁站走到西湖，晚上再去河坊街。",
                "午饭吃老头儿油爆虾，饭后去山野咖啡馆。",
                "注意周末西湖边很堵，建议早点出发。",
            ]
        )

    monkeypatch.setattr(source_importer_service, "_fetch_remote_note_text", fake_fetch_remote_note_text)

    response = client.post(
        "/api/v1/sources/import",
        json={"xiaohongshu_url": "https://www.xiaohongshu.com/explore/demo", "note_text": ""},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "xiaohongshu_link"
    assert "龙翔桥地铁站" in data["locations"]
    assert "西湖" in data["locations"]
    assert "河坊街" in data["locations"]
    assert "老头儿油爆虾" in data["restaurants"]
    assert "山野咖啡馆" in data["restaurants"]
    assert any(item["level"] == "medium" for item in data["risk_tips"])


def test_import_accepts_mobile_share_text_in_link_field(monkeypatch):
    def fake_fetch_remote_note_text(source_url: str) -> str:
        assert source_url == "http://xhslink.com/o/34TR1P9l8lF"
        return "\n".join(
            [
                "吴山广场到杭州博物馆这段很适合 citywalk。",
                "路上可以吃方老大面馆。",
                "注意下午人会变多，建议上午去。",
            ]
        )

    monkeypatch.setattr(source_importer_service, "_fetch_remote_note_text", fake_fetch_remote_note_text)

    response = client.post(
        "/api/v1/sources/import",
        json={
            "xiaohongshu_url": (
                "杭州citywalk 杭州除了去西湖灵隐寺，推荐吴山广场-杭... "
                "http://xhslink.com/o/34TR1P9l8lF 复制后打开【小红书】查看笔记！"
            ),
            "note_text": "",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "xiaohongshu_link"
    assert data["source_url"] == "http://xhslink.com/o/34TR1P9l8lF"
    assert "吴山广场" in data["locations"]
    assert "杭州博物馆" in data["locations"]
    assert "方老大面馆" in data["restaurants"]


def test_import_accepts_mobile_share_text_in_note_text(monkeypatch):
    def fake_fetch_remote_note_text(source_url: str) -> str:
        assert source_url == "http://xhslink.com/o/34TR1P9l8lF"
        return "从吴山广场走到河坊街，注意周末很挤。"

    monkeypatch.setattr(source_importer_service, "_fetch_remote_note_text", fake_fetch_remote_note_text)

    response = client.post(
        "/api/v1/sources/import",
        json={
            "xiaohongshu_url": "",
            "note_text": (
                "杭州citywalk 杭州除了去西湖灵隐寺，推荐吴山广场-杭... "
                "http://xhslink.com/o/34TR1P9l8lF 复制后打开【小红书】查看笔记！"
            ),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "xiaohongshu_link"
    assert data["source_url"] == "http://xhslink.com/o/34TR1P9l8lF"
    assert "吴山广场" in data["locations"]
    assert "河坊街" in data["locations"]


def test_import_parses_realistic_xiaohongshu_ssr_html(monkeypatch):
    realistic_html = """
    <html>
      <head>
        <meta name="description" content="杭州除了去西湖灵隐寺，推荐吴山广场-杭州博物馆-城隍阁-晓霞弄-南宋御街-清河坊这条citywalk路线，历史人文景观都有了，吃饭可以去清河坊外围的美食一条街，杭帮菜美味可口价格也不贵，太好逛了。">
      </head>
      <body>
        <div id="detail-title">杭州citywalk</div>
        <div id="detail-desc"><span>杭州除了去西湖灵隐寺，推荐吴山广场-杭州博物馆-城隍阁-晓霞弄-南宋御街-清河坊这条citywalk路线，历史人文景观都有了，吃饭可以去清河坊外围的美食一条街，杭帮菜美味可口价格也不贵，太好逛了。</span></div>
        <script>
          window.__INITIAL_STATE__={"note":{"noteDetailMap":{"6843":{"note":{"title":"杭州citywalk","desc":"杭州除了去西湖灵隐寺，推荐吴山广场-杭州博物馆-城隍阁-晓霞弄-南宋御街-清河坊这条citywalk路线，历史人文景观都有了，吃饭可以去清河坊外围的美食一条街，杭帮菜美味可口价格也不贵，太好逛了。#杭州citywalk[话题]#"}}}}}
        </script>
      </body>
    </html>
    """

    monkeypatch.setattr(source_importer_service, "_fetch_html", lambda source_url: realistic_html)

    response = client.post(
        "/api/v1/sources/import",
        json={"xiaohongshu_url": "http://xhslink.com/o/34TR1P9l8lF", "note_text": ""},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "xiaohongshu_link"
    for location in ["西湖", "灵隐寺", "吴山广场", "杭州博物馆", "城隍阁", "晓霞弄", "南宋御街", "清河坊"]:
        assert location in data["locations"]
    assert "清河坊外围的美食一条街" in data["restaurants"]


def test_import_rejects_non_xiaohongshu_url():
    response = client.post(
        "/api/v1/sources/import",
        json={"xiaohongshu_url": "https://example.com/post/1", "note_text": ""},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "当前只支持小红书或 xhslink 链接"


def test_import_requires_url_or_note_text():
    response = client.post(
        "/api/v1/sources/import",
        json={"xiaohongshu_url": "", "note_text": ""},
    )
    assert response.status_code == 422
