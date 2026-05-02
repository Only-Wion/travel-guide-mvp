# 自动旅行攻略 App（V0 原型）

当前仓库已经落地为一个可运行的 `FastAPI + 静态 H5` 原型，定位是：
`高可靠旅行决策助手`

它不做 OTA 下单，也不做内容社区，只验证这条核心价值链：

`输入旅行需求 -> 生成两套方案 -> 解释风险取舍 -> 导出一页式执行卡`

## 当前已实现
- 4 个原型页面：输入页、结果页、风险解释页、执行卡页
- 输入页新增“小红书内容导入 MVP”：支持贴小红书链接自动导入，也支持直接粘贴手机端分享文本；失败时可手动粘贴笔记文本
- 4 个 V0 API：
  - `GET /api/v1/health`
  - `GET /api/v1/demo-cases`
  - `POST /api/v1/sources/import`
  - `POST /api/v1/plans/generate`
- mock 数据连接器：交通、天气、景点、餐饮
- 规则引擎：夜间到达限制、中转缓冲限制、预算占比提醒
- 软评分：输出 `省钱优先方案` 和 `省心优先方案`
- 来源可信度标注：`source`、`updated_at`、`confidence`、冲突状态
- 小红书导入解析：支持链接导入 / 手机端分享文本导入 / 手动文本导入，提取地点、餐厅、风险提示
- 一页式执行卡：文本版 + HTML 版
- 13 个 API 验收测试

## 快速运行
```bash
cd /Users/gaoboyang/Documents/旅游攻略
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

打开：
- 原型首页：`http://127.0.0.1:8001/`
- API 文档：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/api/v1/health`

## 运行测试
```bash
cd /Users/gaoboyang/Documents/旅游攻略
source .venv/bin/activate
pytest -q
```

## 请求示例
`POST /api/v1/sources/import`

```json
{
  "xiaohongshu_url": "https://www.xiaohongshu.com/explore/demo",
  "note_text": ""
}
```

说明：
- 如果 `note_text` 有内容，优先按手动文本解析
- 如果 `note_text` 为空，会尝试抓取 `xiaohongshu_url`
- `xiaohongshu_url` 和 `note_text` 都支持直接粘贴手机端复制出来的整段小红书分享文本
- 如果链接抓不到正文，会提示改为手动粘贴文本

`POST /api/v1/plans/generate`

```json
{
  "origin_city": "南京",
  "destination_city": "杭州",
  "departure_date": "2026-05-01",
  "return_date": "2026-05-03",
  "budget_cny": 2800,
  "preference_mode": "balanced",
  "allow_night_arrival": false,
  "min_transfer_buffer_minutes": 60,
  "travelers": 2,
  "preferences": ["citywalk", "local_food", "light_pace"]
}
```

返回内容包含：
- 两套方案
- 每套方案的风险解释
- 来源可信度列表
- 一页式执行卡
- 导入接口可返回地点、餐厅、风险提示解析结果

## 项目结构
- `app/main.py`：FastAPI 入口和静态首页挂载
- `app/api.py`：V0 API 路由
- `app/schemas.py`：输入输出模型
- `app/demo_cases.py`：3 组演示案例
- `app/connectors/mock_connectors.py`：mock 数据源
- `app/services/constraint_engine.py`：硬约束规则
- `app/services/scoring_engine.py`：方案评分
- `app/services/source_reliability.py`：来源可信度标注
- `app/services/exporter.py`：执行卡导出
- `app/services/planner.py`：主编排逻辑
- `app/static/`：原型页面静态资源
- `tests/test_api.py`：API 测试

## 当前边界
- 只做 `V0 国内单城市验证原型`
- 不接真实交通/天气 API
- 不做抓取、账号体系、数据库持久化
- 不做交易闭环和社区
- 所有关键事实仍需用户在出发前二次确认
