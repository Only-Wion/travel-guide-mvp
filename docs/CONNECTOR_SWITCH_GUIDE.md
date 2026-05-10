# 旅行规划器 - Connector 切换指南

## 快速开始

### 场景 1：本地开发（使用 Mock 数据）

Mock 是默认行为，不需要任何配置：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8001
```

输出：
```
[INFO] Using mock travel connectors
```

### 场景 2：启用 DeepSeek 动态生成数据

设置环境变量，然后启动服务器：

```powershell
$env:USE_DEEPSEEK_CONNECTORS = "true"
$env:DS_API_KEY = "sk-your-actual-deepseek-api-key"
$env:DS_BASE_URL = "https://api.deepseek.com/v1"
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8001
```

输出：
```
[INFO] Using DeepSeek-powered travel connectors
```

---

## 工作原理

### 架构图

```
用户请求 (TravelPlanGenerateRequest)
    ↓
TravelPlannerService.__init__()
    ↓
get_travel_connectors() [工厂函数]
    ↓
[检查 USE_DEEPSEEK_CONNECTORS 环境变量]
    ↓
    ├─ "false" (默认) → MockTravelConnectors
    ├─ "true" + DS_API_KEY ✓ → DeepSeekTravelConnectors
    └─ "true" + DS_API_KEY ✗ → MockTravelConnectors (回退)
    ↓
返回 TravelPlannerService，用选定的 connector 生成方案
```

### 核心文件

| 文件 | 作用 |
|------|------|
| `app/connectors/factory.py` | 工厂函数，根据环境变量选择 connector |
| `app/connectors/mock_connectors.py` | 硬编码的城市/交通数据（原有） |
| `app/connectors/deepseek_connectors.py` | 用 DeepSeek LLM 生成动态数据（新增） |
| `app/services/planner.py` | 规划服务，现在通过工厂获取 connector |

---

## 环境变量说明

### `USE_DEEPSEEK_CONNECTORS`

- **默认值**：`"false"`
- **可选值**：`"true"` / `"false"`
- **含义**：是否使用 DeepSeek Connectors

### `DS_API_KEY`

- **默认值**：无（空字符串）
- **需要**：当 `USE_DEEPSEEK_CONNECTORS=true` 时
- **来源**：https://www.deepseek.com/

### `DS_BASE_URL`

- **默认值**：`https://api.deepseek.com/v1`
- **用途**：DeepSeek API 的基础 URL

### `DS_MODEL`

- **默认值**：`deepseek-chat`
- **用途**：使用的模型名称

---

## 数据流对比

### Mock Connectors （快速，固定数据）

```
load_city_bundle(request)
    ↓
在 CITY_FIXTURES 中查找城市数据
    ↓
返回硬编码的数据（如果找不到返回通用数据）
```

**优点**：
- ✓ 速度快（无 API 调用）
- ✓ 不需要 API Key
- ✓ 数据完全可预测

**缺点**：
- ✗ 数据固定，不随实际情况改变
- ✗ 只有 3 个城市的预设数据

---

### DeepSeek Connectors （慢，动态数据）

```
load_city_bundle(request)
    ↓
调用 DeepSeek LLM（通过 OpenAI SDK）
    ↓
    ├─ 发送提示词：生成 {destination_city} 在 {departure_date} 的城市信息
    ├─ LLM 返回 JSON：weather / attractions / food / hotel_area
    └─ 解析并验证 JSON 格式
    ↓
返回真实、上下文感知的数据
```

**优点**：
- ✓ 数据动态生成，针对具体城市/日期
- ✓ 覆盖所有城市（不仅仅 3 个预设）
- ✓ 响应用户偏好（如果扩展了 LLM 提示词）

**缺点**：
- ✗ 速度较慢（HTTP 请求 + LLM 处理，通常 2-5 秒）
- ✗ 需要 DeepSeek API Key
- ✗ 可能产生额外 API 费用

---

## 测试两种模式

### 方式 1：直接在 Python 中测试

```python
# 测试 Mock 模式
import os
os.environ["USE_DEEPSEEK_CONNECTORS"] = "false"

from app.services.planner import TravelPlannerService
planner = TravelPlannerService()
print(f"Connector: {planner.connectors.__class__.__name__}")
# 输出：Connector: MockTravelConnectors
```

### 方式 2：运行演示脚本

```powershell
.\.venv\Scripts\python scripts/demo_connector_switch.py
```

### 方式 3：运行测试套件

```powershell
# 所有测试都是用 Mock 模式（默认）
.\.venv\Scripts\python -m pytest tests/ -v
```

---

## 常见问题

### Q: 怎么完全禁用 Mock，只用 DeepSeek？

A: 修改 `app/connectors/factory.py` 中的 `get_travel_connectors()` 函数，删除回退逻辑。但不建议，因为这样会在 DeepSeek 不可用时导致服务故障。

### Q: DeepSeek Connectors 生成的数据格式和 Mock 一样吗？

A: 是的。两个 Connector 都实现相同的接口，返回相同的数据结构。planner 无感知差异。

### Q: 能否在运行时切换，不重启服务器？

A: 不行。环境变量在进程启动时读取一次，修改后需要重启。但这通常不是问题，因为生产环境一般在容器/进程启动时就固定了配置。

### Q: DeepSeek Connectors 出错会怎样？

A: 自动回退到 Mock 数据。见 `deepseek_connectors.py` 中的 `_default_city_bundle()` 和 `_default_transport_candidates()` 方法。

### Q: 能混合使用吗（比如只用 DeepSeek 生成景点，用 Mock 生成交通）？

A: 可以扩展，但需要修改代码。当前工厂模式是"全有或全无"。如果需要混合，建议创建一个新的 `HybridConnectors` 类。

---

## 性能参考

在笔记本电脑上的典型耗时：

| 操作 | Mock | DeepSeek |
|------|------|----------|
| `load_city_bundle()` | <1ms | 2-4s |
| `transport_candidates()` | <1ms | 3-5s |
| **总规划时间** | <50ms | 5-10s |

建议：
- 本地开发/测试：用 Mock（快速迭代）
- 演示/生产（有预算）：用 DeepSeek（更真实的推荐）

---

## 下一步

### 可能的改进

1. **缓存 LLM 结果**
   ```python
   # 在 deepseek_connectors.py 中加入 @cache
   @functools.lru_cache(maxsize=32)
   def load_city_bundle(self, request):
       ...
   ```

2. **环境变量文件**
   创建 `.env` 文件（如果用 python-dotenv）：
   ```env
   USE_DEEPSEEK_CONNECTORS=true
   DS_API_KEY=sk-xxx
   DS_BASE_URL=https://api.deepseek.com/v1
   ```

3. **条件日志**
   根据 connector 类型输出更详细的日志

4. **Metrics 收集**
   记录每个 connector 的性能数据

---

## 调试

### 检查当前使用的 Connector

```python
from app.services.planner import TravelPlannerService
planner = TravelPlannerService()
print(f"Using: {planner.connectors.__class__.__name__}")
print(f"Available: {planner.connectors.available if hasattr(planner.connectors, 'available') else 'N/A'}")
```

### 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

**最后提醒**：无论选择哪种 Connector，业务逻辑和 API 响应格式完全相同。这就是抽象的力量！
