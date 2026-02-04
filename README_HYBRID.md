# LinkerHand L10 混合遥操作系统

## 概述

这是一个结合了**手部重定向**和**硬编码抓取姿态**的混合遥操作系统，专为LinkerHand L10机械手设计。

### 核心特性

- **混合控制模式**：自动在重定向和预设姿态之间切换
- **手势识别**：自动检测捏合、抓握等手势
- **平滑过渡**：模式切换时平滑插值
- **手动/自动模式**：支持手动强制切换或自动识别

## 快速开始

### 1. 安装依赖

```bash
pip install numpy opencv-python mediapipe pyyaml scipy
```

### 2. 运行系统

```bash
# 模拟模式（无硬件）
python run_hand_hybrid.py

# 真实硬件
python run_hand_hybrid.py --real

# 禁用自动模式切换（仅手动）
python run_hand_hybrid.py --real --no-auto
```

## 控制模式

系统支持4种控制模式：

### 1. RETARGETING（重定向模式）
- 默认模式
- 使用dex-retargeting进行实时手部映射
- 适用于一般手部运动

### 2. FINE_PINCH（精细捏合）
- 拇指和食指精确捏合
- 用于：拾取小物体、精细操作
- **触发条件**：拇指和食指尖距离 < 阈值

### 3. POWER_GRASP（力量抓握）
- 所有手指弯曲的力量握持
- 用于：握持圆柱物体、力量抓取
- **触发条件**：所有手指弯曲度 > 阈值

### 4. OPEN_HAND（张开手）
- 所有手指完全伸直
- 用于：释放物体、复位
- **触发条件**：所有手指伸展度 > 阈值

## 键盘控制

运行时可用的键盘命令：

- `q` - 退出程序
- `r` - 复位机械手
- `m` - 切换自动/手动模式
- `1` - 强制切换到重定向模式
- `2` - 强制切换到精细捏合模式
- `3` - 强制切换到力量抓握模式
- `4` - 强制切换到张开手模式

## 项目结构

```
VIST/
├── run_hand_hybrid.py              # 主程序入口
├── src/
│   ├── core/
│   │   ├── linker_hand_retargeter.py        # 原始重定向器
│   │   └── linker_hand_retargeter_simple.py # 简化重定向器
│   ├── hand_driver.py              # 硬件驱动
│   └── utils/
│       ├── gesture_detector.py     # 手势检测
│       └── grasp_poses.py          # 硬编码姿态管理
├── configs/
│   └── hand_retargeting_config.yaml  # 重定向配置
└── config/
    ├── linkerhand_l10_right.urdf         # 机械手URDF
    └── linkerhand_l10_right_relaxed.urdf # 放宽限制的URDF
```

## 核心模块说明

### 1. GestureDetector（手势检测器）
- 位置：`src/utils/gesture_detector.py`
- 功能：从MediaPipe关键点检测手势
- 支持的手势：
  - 精细捏合（拇指+食指）
  - 力量抓握（所有手指弯曲）
  - 张开手（所有手指伸展）

### 2. GraspPoseManager（姿态管理器）
- 位置：`src/utils/grasp_poses.py`
- 功能：管理预定义的抓取姿态
- 预设姿态：
  - `fine_pinch` - 精细捏合
  - `power_grasp` - 力量抓握
  - `open_hand` - 张开手
  - `tripod_pinch` - 三指捏合
  - `pointing` - 指向

### 3. HybridTeleoperationSystem（混合遥操作系统）
- 位置：`run_hand_hybrid.py`
- 功能：协调所有模块，实现混合控制
- 特性：
  - 自动模式切换
  - 平滑过渡（blend_progress）
  - 实时可视化反馈

## 自定义姿态

你可以添加自定义抓取姿态：

```python
from src.utils.grasp_poses import GraspPoseManager
import numpy as np

manager = GraspPoseManager()

# 定义自定义姿态（SDK值：0-255）
custom_pose = np.array([
    100,  # thumb_cmc_pitch
    150,  # thumb_cmc_yaw
    200,  # index_mcp_pitch
    # ... 共10个值
])

manager.add_custom_pose("my_custom_grasp", custom_pose)
```

## 参数调整

### 手势检测阈值

在 `run_hand_hybrid.py` 中修改：

```python
self.gesture_detector = GestureDetector(
    pinch_threshold=0.05,  # 捏合距离阈值（越小越敏感）
    curl_threshold=0.7     # 弯曲度阈值（0-1）
)
```

### 过渡速度

```python
TRANSITION_SPEED = 0.15  # 模式切换速度（0-1）
```

## 故障排除

### 问题：手势检测不灵敏
**解决**：调整 `pinch_threshold` 和 `curl_threshold` 参数

### 问题：模式切换太快/太慢
**解决**：调整 `TRANSITION_SPEED` 参数

### 问题：硬编码姿态不准确
**解决**：在 `src/utils/grasp_poses.py` 中调整对应姿态的SDK值

### 问题：摄像头无法打开
**解决**：使用 `--camera` 参数指定正确的摄像头ID

## 开发说明

### 保留的重定向模块

虽然主要使用硬编码姿态，但重定向模块仍然保留：
- `src/core/linker_hand_retargeter.py` - 原始版本
- `src/core/linker_hand_retargeter_simple.py` - 简化版本

这些模块用于RETARGETING模式，提供基础的手部映射功能。

### 添加新的控制模式

1. 在 `ControlMode` 枚举中添加新模式
2. 在 `GraspPoseManager` 中定义对应姿态
3. 在 `_update_mode_from_gestures()` 中添加触发逻辑
4. 在 `_get_command_for_mode()` 中添加处理逻辑

## 许可证

[根据你的项目添加许可证信息]

## 联系方式

[根据你的项目添加联系方式]
