# SDK 路径配置修复

## 问题描述

在运行 data_collection.py 时遇到导入错误：
```
ModuleNotFoundError: No module named 'lbot'
```

## 根本原因

SDK 路径配置错误。原配置将 `lbot` 目录本身添加到 sys.path：
```python
sdk_relative_path: str = "src/robot/sdk/linkerarm/lbot"
```

但实际上 `lbot` 是一个 Python 包，应该将其父目录添加到 sys.path。

## SDK 目录结构

```
/home/ilex/Dev/VIST/src/robot/sdk/linkerarm/
└── lbot/                    # Python 包
    ├── __init__.py
    ├── lbot_api.py
    ├── lbot_robot.py
    └── libs/
```

## 修复方案

修改 config.py 中的 RobotConfig：

**修改前**：
```python
sdk_relative_path: str = "src/robot/sdk/linkerarm/lbot"
sdk_search_paths: list = field(default_factory=lambda: [
    "src/robot/sdk/linkerarm/lbot",
    "../src/robot/sdk/linkerarm/lbot",
    "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm",
])
```

**修改后**：
```python
sdk_relative_path: str = "src/robot/sdk/linkerarm"
sdk_search_paths: list = field(default_factory=lambda: [
    "src/robot/sdk/linkerarm",
    "../src/robot/sdk/linkerarm",
    "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm",
])
```

## 验证结果

✅ SDK 路径正确：`/home/ilex/Dev/VIST/src/robot/sdk/linkerarm`
✅ LBot SDK 导入成功
✅ 配置文件模板已更新

## 正确的导入方式

```python
import sys
sys.path.insert(0, "/home/ilex/Dev/VIST/src/robot/sdk/linkerarm")

from lbot.lbot_robot import LbotRobot
from lbot.lbot_api import LbotArm
```

## 修复时间

2026-02-10

## 修复状态

✅ 已完成并验证
