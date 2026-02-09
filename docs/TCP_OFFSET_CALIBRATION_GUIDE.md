# TCP 偏置和补偿完整指南

## 📋 概述

本指南介绍如何测量和补偿机器人系统中的各种物理偏置，包括中间件、法兰盘、灵巧手等。

---

## 🎯 需要补偿的偏置类型

### 1. TCP（Tool Center Point）偏置

**定义**：末端执行器的实际工具中心点相对于机器人法兰盘的偏移。

```
机器人法兰盘 → 中间件 → 法兰盘适配器 → 灵巧手基座 → 工具中心点
    ↓            ↓           ↓              ↓            ↓
  (0,0,0)      +5mm        +10mm          +50mm       +100mm
```

**组成部分**：

| 组件 | 典型尺寸 | 测量精度 | 影响 |
|------|---------|---------|------|
| 中间件 | 5-10mm | ±1mm | 小 |
| 法兰盘适配器 | 10-20mm | ±1mm | 中 |
| 灵巧手基座 | 50-100mm | ±2mm | 大 |
| 手指到工具点 | 50-150mm | ±3mm | 很大 |

### 2. 手眼标定偏置

**定义**：相机相对于末端执行器的偏移（已在手眼标定中处理）。

### 3. 抓握姿态偏置

**定义**：灵巧手抓取物体后，物体中心相对于手掌中心的偏移。

```
手掌中心 → 抓握点 → 物体中心
   ↓         ↓         ↓
 (0,0,0)   +30mm     +50mm
```

### 4. 任务相关偏置

**定义**：不同任务需要不同的工具中心点。

| 任务 | TCP 位置 | 示例 |
|------|---------|------|
| USB 插入 | USB 插头尖端 | 手指尖端 + 20mm |
| 抓取 | 手掌中心 | 手指中点 |
| 推动 | 接触点 | 手指尖端 |

---

## 📐 测量方法

### 方法 1: 直接测量（最简单）

**工具**：
- 游标卡尺（精度 ±0.1mm）
- 卷尺（精度 ±1mm）
- 3D 扫描仪（精度 ±0.5mm，可选）

**步骤**：

1. **测量法兰盘到手基座的距离**：
```python
# 测量 Z 轴偏移（高度）
flange_to_hand_base_z = 0.065  # 65mm（示例）

# 测量 X, Y 偏移（如果有偏心）
flange_to_hand_base_x = 0.0
flange_to_hand_base_y = 0.0
```

2. **测量手基座到工具中心点的距离**：
```python
# 对于灵巧手，工具中心点通常在手指中点
hand_base_to_tcp_z = 0.120  # 120mm（示例）
hand_base_to_tcp_x = 0.0
hand_base_to_tcp_y = 0.0
```

3. **计算总偏移**：
```python
tcp_offset = np.array([
    flange_to_hand_base_x + hand_base_to_tcp_x,
    flange_to_hand_base_y + hand_base_to_tcp_y,
    flange_to_hand_base_z + hand_base_to_tcp_z
])
# 示例结果: [0.0, 0.0, 0.185]  # 185mm
```

**精度**：±2-3mm

---

### 方法 2: 示教测量（推荐）

**原理**：移动机器人到已知位置，反推 TCP 偏移。

**步骤**：

1. **准备标定块**：
   - 在桌面上放置一个已知高度的标定块（如 100mm）
   - 标记标定块的中心位置

2. **示教 4 个点**：
```python
def calibrate_tcp_offset():
    """
    通过示教 4 个点标定 TCP 偏移

    原理：
    - 移动机器人到标定块的 4 个角
    - 记录每个位置的关节角度
    - 通过正运动学计算法兰盘位置
    - 反推 TCP 偏移
    """
    import numpy as np
    from scipy.optimize import least_squares

    # 1. 示教 4 个点（标定块的 4 个角）
    print("请移动机器人末端到标定块的 4 个角...")

    taught_points = []
    for i in range(4):
        input(f"移动到第 {i+1} 个角，按回车继续...")

        # 记录当前关节角度
        joint_angles = robot.get_joint_angles()

        # 计算法兰盘位置（正运动学）
        flange_pos = robot.forward_kinematics(joint_angles)

        taught_points.append(flange_pos)

    # 2. 已知的标定块 4 个角的位置（世界坐标系）
    known_points = np.array([
        [0.5, 0.0, 0.1],    # 角 1
        [0.6, 0.0, 0.1],    # 角 2
        [0.6, 0.1, 0.1],    # 角 3
        [0.5, 0.1, 0.1]     # 角 4
    ])

    # 3. 优化求解 TCP 偏移
    def residual(tcp_offset):
        """残差函数"""
        errors = []
        for flange_pos, known_pos in zip(taught_points, known_points):
            # 假设 TCP = 法兰盘位置 + 偏移
            tcp_pos = flange_pos + tcp_offset
            error = np.linalg.norm(tcp_pos - known_pos)
            errors.append(error)
        return errors

    # 初始猜测：[0, 0, 150mm]
    x0 = np.array([0.0, 0.0, 0.15])

    # 最小二乘优化
    result = least_squares(residual, x0)
    tcp_offset = result.x

    print(f"标定结果: TCP 偏移 = {tcp_offset}")
    print(f"残差: {np.mean(result.fun):.3f}mm")

    return tcp_offset
```

**精度**：±1-2mm

---

### 方法 3: 视觉测量（最精确）

**原理**：使用相机和 AprilTag 标记精确测量。

**步骤**：

1. **在末端执行器上贴 AprilTag 标记**：
   - 标记尺寸：5cm x 5cm
   - 标记位置：尽量靠近工具中心点

2. **使用外部相机检测标记**：
```python
def calibrate_tcp_with_vision():
    """
    使用视觉测量 TCP 偏移
    """
    import cv2

    # 1. 检测 AprilTag 标记
    marker_pos_camera = detect_apriltag(camera_image)

    # 2. 转换到机器人基座坐标系
    marker_pos_base = transform_camera_to_base(marker_pos_camera)

    # 3. 获取当前法兰盘位置
    joint_angles = robot.get_joint_angles()
    flange_pos = robot.forward_kinematics(joint_angles)

    # 4. 计算标记相对于法兰盘的偏移
    marker_offset = marker_pos_base - flange_pos

    # 5. 手动测量标记到 TCP 的距离
    marker_to_tcp = np.array([0.0, 0.0, 0.05])  # 50mm（手动测量）

    # 6. 计算 TCP 偏移
    tcp_offset = marker_offset + marker_to_tcp

    return tcp_offset
```

**精度**：±0.5-1mm

---

## 🔧 补偿实现

### 1. 在 URDF 中定义 TCP

**方法 A：修改 URDF 文件**（推荐）

```xml
<!-- config/lkls73_o2_dual_arm_description.urdf -->

<!-- 添加 TCP frame -->
<link name="Right_TCP">
  <visual>
    <geometry>
      <sphere radius="0.01"/>
    </geometry>
    <material name="red"/>
  </visual>
</link>

<joint name="Right_Wrist_to_TCP" type="fixed">
  <parent link="Right_Wrist_Roll_Link"/>
  <child link="Right_TCP"/>
  <!-- TCP 偏移：根据测量结果填写 -->
  <origin xyz="0.0 0.0 0.185" rpy="0 0 0"/>
</joint>
```

**方法 B：在代码中动态补偿**

```python
# src/core/tcp_compensation.py

import numpy as np
from scipy.spatial.transform import Rotation

class TCPCompensation:
    """TCP 偏移补偿"""

    def __init__(self, tcp_offset=None, tcp_rotation=None):
        """
        Args:
            tcp_offset: TCP 位置偏移 [x, y, z] (米)
            tcp_rotation: TCP 姿态偏移（四元数 [x, y, z, w]）
        """
        self.tcp_offset = np.array(tcp_offset or [0.0, 0.0, 0.185])
        self.tcp_rotation = Rotation.from_quat(tcp_rotation or [0, 0, 0, 1])

    def compensate_target_pose(self, target_pos, target_quat=None):
        """
        补偿目标位姿

        将目标 TCP 位姿转换为法兰盘位姿

        Args:
            target_pos: 目标 TCP 位置 [x, y, z]
            target_quat: 目标 TCP 姿态（四元数）

        Returns:
            flange_pos: 法兰盘位置
            flange_quat: 法兰盘姿态
        """
        # 1. 位置补偿
        # 法兰盘位置 = TCP 位置 - TCP 偏移（在法兰盘坐标系中）
        if target_quat is not None:
            # 考虑姿态的影响
            R_target = Rotation.from_quat(target_quat)
            offset_world = R_target.apply(self.tcp_offset)
            flange_pos = target_pos - offset_world
        else:
            # 简化：假设姿态为零
            flange_pos = target_pos - self.tcp_offset

        # 2. 姿态补偿
        if target_quat is not None:
            R_target = Rotation.from_quat(target_quat)
            R_flange = R_target * self.tcp_rotation.inv()
            flange_quat = R_flange.as_quat()
        else:
            flange_quat = None

        return flange_pos, flange_quat

    def compensate_current_pose(self, flange_pos, flange_quat=None):
        """
        补偿当前位姿

        将法兰盘位姿转换为 TCP 位姿

        Args:
            flange_pos: 法兰盘位置
            flange_quat: 法兰盘姿态

        Returns:
            tcp_pos: TCP 位置
            tcp_quat: TCP 姿态
        """
        # 1. 位置补偿
        if flange_quat is not None:
            R_flange = Rotation.from_quat(flange_quat)
            offset_world = R_flange.apply(self.tcp_offset)
            tcp_pos = flange_pos + offset_world
        else:
            tcp_pos = flange_pos + self.tcp_offset

        # 2. 姿态补偿
        if flange_quat is not None:
            R_flange = Rotation.from_quat(flange_quat)
            R_tcp = R_flange * self.tcp_rotation
            tcp_quat = R_tcp.as_quat()
        else:
            tcp_quat = None

        return tcp_pos, tcp_quat
```

### 2. 集成到 VIST 系统

```python
# 在 VIST 控制器中使用 TCP 补偿

from src.core.tcp_compensation import TCPCompensation

class VISTPerceptionController:
    def __init__(self, ..., tcp_offset=None):
        # ...

        # 初始化 TCP 补偿
        self.tcp_compensation = TCPCompensation(tcp_offset=tcp_offset)

    def process_frame(self, human_kps):
        # 1. 运动映射（人体 → 机器人目标位姿）
        target_pos, target_quat, _ = self.motion_mapper.human_to_robot(human_kps)

        # 2. TCP 补偿（TCP 位姿 → 法兰盘位姿）
        flange_pos, flange_quat = self.tcp_compensation.compensate_target_pose(
            target_pos, target_quat
        )

        # 3. VIST 卡尔曼滤波（使用法兰盘位姿）
        joint_angles, success, error = self.vist_filter.solve(
            target_pos=flange_pos,
            target_quat=flange_quat,
            ...
        )

        return joint_angles, ...
```

---

## 📊 精度分析

### 1. 误差来源

| 误差来源 | 典型值 | 累积方式 |
|---------|--------|---------|
| 测量误差 | ±2mm | 直接累加 |
| 机器人重复精度 | ±1mm | 随机误差 |
| 运动学模型误差 | ±3mm | 累积 |
| 手眼标定误差 | ±2mm | 累积 |
| TCP 标定误差 | ±2mm | 累积 |

### 2. 累积误差计算

**线性累积**（最坏情况）：
```
总误差 = Σ 各项误差
       = 2 + 1 + 3 + 2 + 2
       = 10mm
```

**均方根累积**（统计平均）：
```
总误差 = √(Σ 误差²)
       = √(2² + 1² + 3² + 2² + 2²)
       = √(4 + 1 + 9 + 4 + 4)
       = √22
       ≈ 4.7mm
```

**实际经验**：
- 良好标定：±3-5mm
- 一般标定：±5-10mm
- 粗略标定：±10-20mm

### 3. USB 插入精度要求

```
USB Type-A 插口：
- 宽度：12mm
- 高度：4.5mm
- 所需精度：±5mm（宽度方向）
              ±2mm（高度方向）

结论：良好标定（±3-5mm）足够满足要求 ✅
```

---

## 🔍 验证和调试

### 1. 精度验证

```python
def verify_tcp_calibration():
    """验证 TCP 标定精度"""

    # 1. 移动到已知位置
    known_positions = [
        [0.5, 0.0, 0.1],
        [0.5, 0.1, 0.1],
        [0.6, 0.0, 0.1],
        [0.6, 0.1, 0.1]
    ]

    errors = []
    for known_pos in known_positions:
        # 移动到目标位置
        robot.move_to_position(known_pos)

        # 获取实际位置（通过视觉或其他方式）
        actual_pos = measure_actual_position()

        # 计算误差
        error = np.linalg.norm(actual_pos - known_pos)
        errors.append(error)

        print(f"目标: {known_pos}, 实际: {actual_pos}, 误差: {error*1000:.1f}mm")

    print(f"\n平均误差: {np.mean(errors)*1000:.1f}mm")
    print(f"最大误差: {np.max(errors)*1000:.1f}mm")
    print(f"标准差: {np.std(errors)*1000:.1f}mm")
```

### 2. 可视化调试

```python
def visualize_tcp_offset():
    """可视化 TCP 偏移"""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # 绘制法兰盘
    ax.scatter([0], [0], [0], c='blue', marker='o', s=100, label='Flange')

    # 绘制 TCP
    tcp_offset = [0.0, 0.0, 0.185]
    ax.scatter([tcp_offset[0]], [tcp_offset[1]], [tcp_offset[2]],
               c='red', marker='x', s=100, label='TCP')

    # 绘制连线
    ax.plot([0, tcp_offset[0]], [0, tcp_offset[1]], [0, tcp_offset[2]],
            'k--', linewidth=2)

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.legend()
    plt.title('TCP Offset Visualization')
    plt.show()
```

---

## 📝 配置文件格式

```yaml
# config/tcp_calibration.yaml

tcp_offsets:
  # 默认 TCP（手指中点）
  default:
    position: [0.0, 0.0, 0.185]  # 185mm
    orientation: [0.0, 0.0, 0.0, 1.0]  # 四元数 [x, y, z, w]

  # USB 插入任务
  usb_insertion:
    position: [0.0, 0.0, 0.205]  # 205mm（手指尖端）
    orientation: [0.0, 0.0, 0.0, 1.0]

  # 抓取任务
  grasping:
    position: [0.0, 0.0, 0.150]  # 150mm（手掌中心）
    orientation: [0.0, 0.0, 0.0, 1.0]

# 测量记录
calibration_record:
  date: "2026-02-09"
  method: "teaching"  # 'direct', 'teaching', 'vision'
  accuracy: 0.002  # ±2mm
  verified: true
  notes: "使用示教方法标定，4 点验证"
```

---

## 🚀 快速开始

### Day 1: 测量和标定

```bash
# 1. 直接测量（30分钟）
# 使用游标卡尺测量法兰盘到手指的距离

# 2. 示教标定（1小时）
python scripts/calibrate_tcp_offset.py

# 3. 验证精度（30分钟）
python scripts/verify_tcp_calibration.py
```

### Day 2: 集成和测试

```bash
# 1. 更新配置文件
# 编辑 config/tcp_calibration.yaml

# 2. 集成到 VIST 系统
# 修改 VISTPerceptionController

# 3. 运行完整测试
python examples/vist_perception_control.py
```

---

## 📚 参考资料

- [TCP Calibration Best Practices](https://www.universal-robots.com/articles/ur/application-installation/what-is-tcp/)
- [Hand-Eye Calibration](https://github.com/IFL-CAMP/easy_handeye)
- [Kinematic Calibration](https://ieeexplore.ieee.org/document/8793896)

---

**最后更新**: 2026-02-09
