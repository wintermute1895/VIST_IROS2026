# LinkerHand L10 键盘控制使用说明

## 概述

`hand_control.py` 是一个键盘控制程序，用于通过按键控制 LinkerHand L10 灵巧手的状态。

## 功能特点

- **键盘控制**：通过按键 1、2、3 控制手的三种状态
- **模拟模式**：支持无硬件测试
- **多种抓取预设**：支持小、中、大物体的抓取配置
- **实时状态切换**：即时响应按键输入

## 按键说明

| 按键 | 功能 | 说明 |
|------|------|------|
| `1` | IDLE | 空闲状态，手完全张开 |
| `2` | PRE-GRASP | 预抓取状态，手部分闭合 |
| `3` | GRASP | 抓取状态，手完全闭合 |
| `h` | 帮助 | 显示帮助信息 |
| `q` | 退出 | 退出程序 |

## 使用方法

### 1. 模拟模式（无硬件测试）

```bash
python3 scripts/hand_control.py --mock
```

### 2. 真实硬件模式

```bash
python3 scripts/hand_control.py
```

### 3. 指定抓取预设

```bash
# 小物体预设（如硬币、螺丝）
python3 scripts/hand_control.py --preset small

# 中等物体预设（如杯子、瓶子）- 默认
python3 scripts/hand_control.py --preset medium

# 大物体预设（如球、盒子）
python3 scripts/hand_control.py --preset large
```

## 配置说明

程序启动时会显示当前配置：

```
======================================================================
当前配置:
======================================================================
摄像头类型: realsense
控制频率: 30 Hz
CAN ID: 0x27
CAN通道: can0
模拟模式: False
默认抓取预设: medium
日志级别: INFO
======================================================================
```

## 文件结构

```
scripts/
  └── hand_control.py          # 主控制程序（包含配置和控制逻辑）

src/robot/hand/
  └── hand_driver.py           # LinkerHand 驱动（封装 SDK 调用）

external_sdk/
  └── linkerhand-ros2-sdk/     # LinkerHand SDK
```

## 技术细节

### 驱动特性

- **CAN 总线通信**：通过 CAN 接口与手部硬件通信
- **错误处理**：包含缓冲区溢出检测和重试机制
- **变化过滤**：减少不必要的命令发送，提高稳定性
- **帧间延迟**：防止 CAN 总线拥塞

### 关节角度

手部有 10 个自由度：

1. 拇指俯仰 (Thumb Pitch)
2. 拇指偏航 (Thumb Yaw)
3. 食指俯仰 (Index Pitch)
4. 中指俯仰 (Middle Pitch)
5. 无名指俯仰 (Ring Pitch)
6. 小指俯仰 (Pinky Pitch)
7. 食指侧摆 (Index Roll)
8. 无名指侧摆 (Ring Roll)
9. 小指侧摆 (Pinky Roll)
10. 拇指侧摆 (Thumb Roll)

角度范围：0-255 度

## 故障排除

### 1. SDK 导入失败

**错误信息**：`ModuleNotFoundError: No module named 'LinkerHand'`

**解决方法**：确保 SDK 路径正确，检查 `external_sdk/linkerhand-ros2-sdk/` 目录是否存在。

### 2. CAN 接口错误

**错误信息**：`Failed to initialize SDK`

**解决方法**：
- 检查 CAN 接口是否正常：`ip link show can0`
- 确保 CAN 接口已启动：`sudo ip link set can0 up type can bitrate 1000000`
- 使用模拟模式测试：`python3 scripts/hand_control.py --mock`

### 3. 缓冲区溢出

**错误信息**：`CAN buffer full`

**解决方法**：驱动已包含自动重试机制，偶尔出现此警告是正常的。如果频繁出现，可以：
- 降低控制频率
- 增加帧间延迟
- 启用变化过滤

## 开发说明

### 修改抓取预设

编辑 `hand_control.py` 中的 `JointAnglesConfig` 类：

```python
JOINT_ANGLES_IDLE = [255.0, 255.0, ...]  # 空闲状态
JOINT_ANGLES_PRE_GRASP = [188.0, 51.0, ...]  # 预抓取状态
JOINT_ANGLES_GRASP = [138.0, 60.0, ...]  # 抓取状态
```

### 添加新状态

1. 在 `HandState` 枚举中添加新状态
2. 在 `JointAnglesConfig` 中定义对应的关节角度
3. 在 `KeyboardHandController.set_state()` 中添加处理逻辑
4. 在 `KeyboardHandController.run()` 中添加按键映射

## 许可证

请参考项目根目录的 LICENSE 文件。
