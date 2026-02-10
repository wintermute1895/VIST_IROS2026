# Logging 系统使用指南

## 快速开始

### 1. 在模块中使用 logging

```python
from src.utils.logger import setup_logger

# 创建 logger（通常在文件开头）
logger = setup_logger(__name__)

# 使用 logger
logger.debug("调试信息")
logger.info("正常信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

### 2. 配置日志级别

```python
# 只输出到控制台
logger = setup_logger(__name__, level="DEBUG", file=False)

# 只输出到文件
logger = setup_logger(__name__, level="INFO", console=False)

# 自定义日志目录
logger = setup_logger(__name__, log_dir="experiments/logs")
```

## 日志格式

```
2026-02-10 14:30:45 | VISTController      | INFO     | VIST 控制器初始化完成
2026-02-10 14:30:46 | IKSolver            | WARNING  | IK 求解未收敛
2026-02-10 14:30:47 | SafetyController    | ERROR    | 关节速度超限
```

## 日志文件

- 位置: `logs/vist_YYYYMMDD.log`
- 按日期自动分割
- UTF-8 编码

## 迁移指南

### 替换 print 语句

**之前:**
```python
print("✅ 初始化完成")
print(f"⚠️ 警告: {message}")
print(f"❌ 错误: {error}")
```

**之后:**
```python
logger.info("初始化完成")
logger.warning(f"警告: {message}")
logger.error(f"错误: {error}")
```

### 调试信息

**之前:**
```python
if DEBUG:
    print(f"Debug: x={x}, y={y}")
```

**之后:**
```python
logger.debug(f"x={x}, y={y}")
```

## 已迁移的模块

- ✅ `src/control/vist_controller.py` - 核心控制器
- ⏳ 其他模块待迁移

## 注意事项

1. **不要删除所有 print**：用户交互信息（如进度条、提示）仍使用 print
2. **日志级别选择**：
   - DEBUG: 详细调试信息
   - INFO: 正常运行信息
   - WARNING: 警告但不影响运行
   - ERROR: 错误但程序可继续
   - CRITICAL: 严重错误，程序可能崩溃
3. **性能考虑**：DEBUG 级别日志在生产环境会被自动过滤
