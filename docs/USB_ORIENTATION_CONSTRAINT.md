# USB 插头姿态约束实现

## 📋 问题

**关键约束**：抓握 USB U 盘时，必须保证插头水平向下（垂直于地面）。

---

## 🎯 解决方案

### 方案 1: 固定姿态约束（推荐）

**原理**：在运动映射或 IK 求解中，强制末端执行器保持固定姿态。

```python
# src/core/orientation_constraint.py

import numpy as np
from scipy.spatial.transform import Rotation


class OrientationConstraint:
    """
    姿态约束

    用于保证末端执行器保持特定姿态（如 USB 插头水平向下）。
    """

    def __init__(self, constraint_type='usb_downward'):
        """
        Args:
            constraint_type: 约束类型
                - 'usb_downward': USB 插头水平向下
                - 'horizontal': 水平姿态
                - 'custom': 自定义姿态
        """
        self.constraint_type = constraint_type
        self.target_orientation = self._get_target_orientation(constraint_type)

        print(f"🔒 [OrientationConstraint] 初始化姿态约束")
        print(f"   约束类型: {constraint_type}")
        print(f"   目标姿态: {self.target_orientation.as_euler('xyz', degrees=True)} deg")

    def _get_target_orientation(self, constraint_type: str) -> Rotation:
        """获取目标姿态"""
        if constraint_type == 'usb_downward':
            # USB 插头水平向下
            # 假设：
            # - 机器人基座坐标系：X=forward, Y=left, Z=up
            # - USB 插头方向：沿 -Z 轴（向下）
            # - 手指方向：沿 -Z 轴
            #
            # 目标姿态：无旋转（或根据实际情况调整）
            return Rotation.identity()

        elif constraint_type == 'horizontal':
            # 水平姿态（Roll=0, Pitch=0）
            return Rotation.from_euler('xyz', [0, 0, 0])

        elif constraint_type == 'custom':
            # 自定义姿态（需要手动设置）
            return Rotation.identity()

        else:
            raise ValueError(f"未知的约束类型: {constraint_type}")

    def apply_constraint(
        self,
        target_pos: np.ndarray,
        target_quat: np.ndarray = None
    ) -> tuple:
        """
        应用姿态约束

        Args:
            target_pos: 目标位置 [x, y, z]
            target_quat: 目标姿态（四元数，可选）

        Returns:
            constrained_pos: 约束后的位置（不变）
            constrained_quat: 约束后的姿态（固定）
        """
        # 位置不变
        constrained_pos = target_pos

        # 姿态固定为目标姿态
        constrained_quat = self.target_orientation.as_quat()

        return constrained_pos, constrained_quat

    def check_constraint_violation(
        self,
        current_quat: np.ndarray,
        tolerance_deg: float = 5.0
    ) -> bool:
        """
        检查姿态约束是否被违反

        Args:
            current_quat: 当前姿态（四元数）
            tolerance_deg: 容差（度）

        Returns:
            is_violated: 是否违反约束
        """
        current_rot = Rotation.from_quat(current_quat)
        target_rot = self.target_orientation

        # 计算旋转差异
        rotation_diff = target_rot.inv() * current_rot
        angle_diff = rotation_diff.magnitude()  # 弧度

        # 转换为度
        angle_diff_deg = np.rad2deg(angle_diff)

        is_violated = angle_diff_deg > tolerance_deg

        if is_violated:
            print(f"⚠️ [OrientationConstraint] 姿态约束违反")
            print(f"   当前姿态: {current_rot.as_euler('xyz', degrees=True)} deg")
            print(f"   目标姿态: {target_rot.as_euler('xyz', degrees=True)} deg")
            print(f"   角度差异: {angle_diff_deg:.2f} deg (容差: {tolerance_deg} deg)")

        return is_violated
```

---

### 方案 2: 手部姿态检测（可选）

**原理**：检测人类手部姿态，确保抓握时手部保持正确姿态。

```python
def detect_hand_orientation(hand_keypoints: dict) -> Rotation:
    """
    检测手部姿态

    Args:
        hand_keypoints: 手部关键点
            - 'wrist': 手腕位置
            - 'index_mcp': 食指掌指关节
            - 'pinky_mcp': 小指掌指关节

    Returns:
        hand_orientation: 手部姿态（Rotation 对象）
    """
    wrist = hand_keypoints['wrist']
    index_mcp = hand_keypoints['index_mcp']
    pinky_mcp = hand_keypoints['pinky_mcp']

    # 计算手部坐标系
    # Z 轴：手腕到手指方向（前臂延伸方向）
    z_axis = (index_mcp + pinky_mcp) / 2 - wrist
    z_axis = z_axis / np.linalg.norm(z_axis)

    # Y 轴：小指到食指方向（手掌宽度方向）
    y_axis = index_mcp - pinky_mcp
    y_axis = y_axis / np.linalg.norm(y_axis)

    # X 轴：叉乘
    x_axis = np.cross(y_axis, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)

    # 重新正交化 Y 轴
    y_axis = np.cross(z_axis, x_axis)

    # 构建旋转矩阵
    R = np.column_stack([x_axis, y_axis, z_axis])

    return Rotation.from_matrix(R)


def check_usb_grip_orientation(hand_orientation: Rotation) -> bool:
    """
    检查 USB 抓握姿态是否正确

    要求：手部应该保持垂直（手指向下）

    Args:
        hand_orientation: 手部姿态

    Returns:
        is_correct: 姿态是否正确
    """
    # 提取 Roll, Pitch, Yaw
    roll, pitch, yaw = hand_orientation.as_euler('xyz')

    # 检查手部是否垂直
    # 假设：手指向下时，Pitch ≈ -90°
    target_pitch = -np.pi / 2  # -90°
    pitch_error = abs(pitch - target_pitch)

    # 容差：±10°
    tolerance = np.deg2rad(10)

    is_correct = pitch_error < tolerance

    if not is_correct:
        print(f"⚠️ [USB Grip] 手部姿态不正确")
        print(f"   当前 Pitch: {np.rad2deg(pitch):.1f}°")
        print(f"   目标 Pitch: {np.rad2deg(target_pitch):.1f}°")
        print(f"   误差: {np.rad2deg(pitch_error):.1f}° (容差: ±10°)")

    return is_correct
```

---

### 方案 3: IK 求解中的姿态约束

**原理**：在 IK 求解时，只优化位置，固定姿态。

```python
# 修改 VIST 卡尔曼滤波器

class VISTKalmanFilter:
    def __init__(self, ..., orientation_constraint=None):
        # ...
        self.orientation_constraint = orientation_constraint

    def solve(self, target_pos, target_quat=None, ...):
        # 应用姿态约束
        if self.orientation_constraint is not None:
            target_pos, target_quat = self.orientation_constraint.apply_constraint(
                target_pos, target_quat
            )

        # 继续正常的 VIST 求解
        # ...
```

---

## 🔧 集成到 VIST 系统

### 1. 初始化姿态约束

```python
from src.core.orientation_constraint import OrientationConstraint

# 创建 USB 插头向下的姿态约束
orientation_constraint = OrientationConstraint(constraint_type='usb_downward')

# 集成到 VIST 滤波器
vist_filter = VISTKalmanFilter(
    ik_solver=ik_solver,
    config=config,
    orientation_constraint=orientation_constraint
)
```

### 2. 在运动映射中应用约束

```python
# 在 ArmMotionMapper 中
def human_to_robot(self, human_kps):
    # 正常的运动映射
    target_pos, target_quat, debug_info = self._compute_target_pose(human_kps)

    # 应用姿态约束
    if self.orientation_constraint is not None:
        target_pos, target_quat = self.orientation_constraint.apply_constraint(
            target_pos, target_quat
        )

    return target_pos, target_quat, debug_info
```

### 3. 实时监测姿态

```python
# 在主控制循环中
while True:
    # 获取当前姿态
    current_quat = robot.get_end_effector_orientation()

    # 检查姿态约束
    if orientation_constraint.check_constraint_violation(current_quat):
        print("⚠️ 姿态约束违反，请调整手部姿态！")
        # 可选：触发警告或暂停
```

---

## 📊 姿态约束验证

### 1. 可视化姿态

```python
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def visualize_orientation(orientation: Rotation, title="Orientation"):
    """可视化姿态"""
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # 原点
    origin = np.array([0, 0, 0])

    # 坐标轴
    axes = orientation.as_matrix()

    # 绘制 X, Y, Z 轴
    colors = ['r', 'g', 'b']
    labels = ['X', 'Y', 'Z']

    for i, (axis, color, label) in enumerate(zip(axes.T, colors, labels)):
        ax.quiver(*origin, *axis, color=color, label=label, arrow_length_ratio=0.1)

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_xlim([-1, 1])
    ax.set_ylim([-1, 1])
    ax.set_zlim([-1, 1])
    ax.legend()
    plt.title(title)
    plt.show()
```

### 2. 测试姿态约束

```python
def test_orientation_constraint():
    """测试姿态约束"""
    constraint = OrientationConstraint('usb_downward')

    # 测试 1: 正确姿态
    correct_quat = constraint.target_orientation.as_quat()
    is_violated = constraint.check_constraint_violation(correct_quat, tolerance_deg=5.0)
    assert not is_violated, "正确姿态不应该违反约束"

    # 测试 2: 错误姿态（旋转 20°）
    wrong_rot = constraint.target_orientation * Rotation.from_euler('x', 20, degrees=True)
    wrong_quat = wrong_rot.as_quat()
    is_violated = constraint.check_constraint_violation(wrong_quat, tolerance_deg=5.0)
    assert is_violated, "错误姿态应该违反约束"

    print("✅ 姿态约束测试通过")
```

---

## 🎯 实际应用建议

### 1. 抓握前检查

```python
# 在抓握 USB 前，检查手部姿态
hand_orientation = detect_hand_orientation(hand_keypoints)
if not check_usb_grip_orientation(hand_orientation):
    print("⚠️ 请调整手部姿态，使手指向下")
    # 等待用户调整
    return
```

### 2. 抓握后固定

```python
# 抓握 USB 后，固定末端执行器姿态
robot.grasp_usb()

# 应用姿态约束
orientation_constraint = OrientationConstraint('usb_downward')
vist_filter.set_orientation_constraint(orientation_constraint)

# 后续所有运动都保持姿态固定
```

### 3. 插入前验证

```python
# 在插入前，最后验证姿态
current_quat = robot.get_end_effector_orientation()
if orientation_constraint.check_constraint_violation(current_quat, tolerance_deg=2.0):
    print("⚠️ 姿态不正确，无法插入")
    return

# 开始插入
auto_insertion_control()
```

---

## 📝 配置文件

```yaml
# config/orientation_constraints.yaml

orientation_constraints:
  # USB 插入任务
  usb_insertion:
    type: 'fixed'
    target_orientation: [0.0, 0.0, 0.0, 1.0]  # 四元数 [x, y, z, w]
    tolerance_deg: 5.0  # ±5°
    description: "USB 插头水平向下"

  # 抓取任务
  grasping:
    type: 'adaptive'
    description: "根据物体姿态自适应"

  # 推动任务
  pushing:
    type: 'fixed'
    target_orientation: [0.0, 0.0, 0.0, 1.0]
    tolerance_deg: 10.0
    description: "水平推动"
```

---

## ✅ 总结

**问题**：抓握 USB 时必须保证插头水平向下

**解决方案**：
1. ✅ 固定姿态约束（在 IK 求解中强制固定姿态）
2. ✅ 手部姿态检测（检测人类手部姿态是否正确）
3. ✅ 实时监测（检测姿态约束违反）

**推荐流程**：
1. 抓握前：检查手部姿态
2. 抓握后：应用固定姿态约束
3. 运动中：实时监测姿态
4. 插入前：最后验证姿态

**最后更新**: 2026-02-09
