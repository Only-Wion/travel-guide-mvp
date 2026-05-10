import pytest
import os

# 确保测试环境使用 Mock Connector
os.environ["USE_DEEPSEEK_CONNECTORS"] = "false"
