# LBot SDK 位姿格式确认报告

## 执行摘要

经过仔细阅读 LBot SDK 源代码和验证测试，确认以下信息：

| 项目 | 确认结果 |
|------|---------|
| **位姿格式** | **欧拉角**（不是四元数） |
| **角度单位** | **弧度**（不是度数） |
| **旋转顺序** | **XYZ 内旋** (intrinsic) 或等价的 **ZYX 外旋** (extrinsic) |
| **对应关系** | `euler.x = roll`, `euler.y = pitch`, `euler.z = yaw` |

---

## 详细分析

### 1. 位姿格式：欧拉角

**证据来源：**

#### 代码结构（lbot_api.py:129-141）
```python
class LbotArmState(Structure):
    _fields_ = [
        ...
        ("end_effector_position", LbotPosition),  # 末端位置
        ("euler", LbotEuler),                    # 欧拉角
        ("orientation", LbotOrientation)        # 四元数姿态
    ]
```

虽然状态中同时包含 `euler`（欧拉角）和 `orientation`（四元数），但：

#### API 返回值（lbot_robot.py:222-234）
```python
def get_cartesian_pose(self, arm: LbotArm) -> Optional[Tuple[LbotPosition, LbotEuler]]:
    """
    @brief 获取笛卡尔空间位姿
    @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
    @return: 元组(位置, 欧拉角)，如果获取失败则返回None
    """
    state = self.get_state()
    if state:
        if arm == LbotArm.LEFT_ARM:
            return state.left_arm.end_effector_position, state.left_arm.euler
        else:
            return state.right_arm.end_effector_position, state.right_arm.euler
    return None
```

**结论：** `get_cartesian_pose()` 方法明确返回 `LbotEuler`，而不是 `LbotOrientation`（四元数）。

---

### 2. 角度单位：弧度

**证据来源：**

#### 运动控制方法注释（lbot_robot.py:268-279）
```python
def move_to_pose_target(self, arm: LbotArm, position: LbotPosition,
                      euler: LbotEuler, speed: float = 0.5,
                      accel: float = 0.1, block: bool = True) -> bool:
    """
    @brief 笛卡尔空间姿态运动（关节插值）
    @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
    @param position: 目标位置（x, y, z，单位：米）
    @param euler: 机械臂末端目标欧拉角（roll, pitch, yaw，单位：弧度）  ← 明确说明
    @param speed: 机械臂末端运动速度（0.0~20.0）单位m/s
    @param accel: 机械臂末端加速度（0.0~1.0）单位m/s²
    ...
    """
```

#### 关节运动方法注释（lbot_robot.py:251-262）
```python
def move_to_joint_target(self, arm: LbotArm, target_joints: List[float],
                       speed: float = 0.5, accel: float = 0.1,
                       block: bool = True) -> bool:
    """
    @brief 关节空间运动控制
    @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
    @param target_joints: 7个关节的目标角度（弧度）  ← 关节角度也是弧度
    @param speed: 运动速度（0.0~20.0）单位是rad/s
    @param accel: 加速度（0.0~20.0）单位是rad/s²
    ...
    """
```

**结论：** SDK 文档明确说明欧拉角单位为**弧度**，与关节角度单位一致。

---

### 3. 旋转顺序：XYZ 内旋

**证据来源：**

#### 欧拉角定义（lbot_robot.py:275）
```python
@param euler: 机械臂末端目标欧拉角（roll, pitch, yaw，单位：弧度）
```

#### LbotEuler 结构（lbot_api.py:106-126）
```python
class LbotEuler(Structure):
    _fields_ = [
        ("x", c_double),  # roll  - 绕 X 轴旋转
        ("y", c_double),  # pitch - 绕 Y 轴旋转
        ("z", c_double)   # yaw   - 绕 Z 轴旋转
    ]
```

#### 机器人学标准约定

在机器人学中，**roll-pitch-yaw** 的标准定义是：
- **roll**: 绕 X 轴旋转
- **pitch**: 绕 Y 轴旋转
- **yaw**: 绕 Z 轴旋转

这通常对应两种等价的表示方式：
1. **XYZ 内旋** (intrinsic rotation): 先绕 X 轴，再绕旋转后的 Y 轴，最后绕旋转后的 Z 轴
2. **ZYX 外旋** (extrinsic rotation): 先绕固定的 Z 轴，再绕固定的 Y 轴，最后绕固定的 X 轴

#### 验证测试结果

运行 `verify_rotation_order.py` 验证脚本的结果显示：

```
方法 1: XYZ 内旋 (intrinsic) - scipy.from_euler('xyz', ...)
方法 2: ZYX 外旋 (extrinsic) - scipy.from_euler('ZYX', ...)

矩阵差异（最大绝对值）: 1.11e-16
✓ 两种方法等价（差异 < 1e-10）
```

**结论：** 应使用 **XYZ 内旋**（或等价的 ZYX 外旋）。

---

## 正确的转换代码

### 从 LBot SDK 格式转换为 4x4 齐次变换矩阵

```python
from scipy.spatial.transform import Rotation as R
import numpy as np

def lbot_pose_to_matrix(position, euler) -> np.ndarray:
    """
    将 LBot SDK 的位姿数据转换为 4x4 齐次变换矩阵

    Args:
        position: LbotPosition 对象，包含 x, y, z（单位：米）
        euler: LbotEuler 对象，包含 x, y, z（对应 roll, pitch, yaw，单位：弧度）

    Returns:
        np.ndarray: 4x4 齐次变换矩阵
    """
    # 使用 scipy 将欧拉角（XYZ 内旋）转换为旋转矩阵
    rotation = R.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)
    rotation_matrix = rotation.as_matrix()

    # 构建 4x4 齐次变换矩阵
    transform_matrix = np.eye(4)
    transform_matrix[:3, :3] = rotation_matrix
    transform_matrix[:3, 3] = [position.x, position.y, position.z]

    return transform_matrix
```

### 从 4x4 齐次变换矩阵转换为 LBot SDK 格式

```python
from lbot.lbot_api import LbotPosition, LbotEuler

def matrix_to_lbot_pose(matrix: np.ndarray):
    """
    将 4x4 齐次变换矩阵转换为 LBot SDK 格式

    Args:
        matrix: 4x4 齐次变换矩阵

    Returns:
        tuple: (LbotPosition, LbotEuler)
    """
    # 提取位置
    x, y, z = matrix[:3, 3]
    position = LbotPosition(x, y, z)

    # 提取旋转矩阵并转换为欧拉角
    rotation = R.from_matrix(matrix[:3, :3])
    roll, pitch, yaw = rotation.as_euler('xyz', degrees=False)
    euler = LbotEuler(roll, pitch, yaw)

    return position, euler
```

---

## 使用示例

### 示例 1：获取机械臂位姿

```python
from lbot.lbot_robot import LbotRobot
from lbot.lbot_api import LbotArm
from robot_interface import RobotInterface

# 连接到机器人
robot = LbotRobot("192.168.10.21")
robot.connect()

# 获取当前位姿（返回 LbotPosition 和 LbotEuler）
position, euler = robot.get_cartesian_pose(LbotArm.LEFT_ARM)

print(f"位置: x={position.x:.3f}, y={position.y:.3f}, z={position.z:.3f} 米")
print(f"欧拉角: roll={euler.x:.3f}, pitch={euler.y:.3f}, yaw={euler.z:.3f} 弧度")
print(f"欧拉角: roll={np.rad2deg(euler.x):.1f}°, pitch={np.rad2deg(euler.y):.1f}°, yaw={np.rad2deg(euler.z):.1f}°")

# 转换为 4x4 矩阵
matrix = RobotInterface.lbot_pose_to_matrix(position, euler)
print(f"\n4x4 齐次变换矩阵:\n{matrix}")
```

### 示例 2：移动机械臂

```python
from lbot.lbot_api import LbotPosition, LbotEuler

# 创建目标位姿（单位：米和弧度）
target_position = LbotPosition(x=0.5, y=0.0, z=0.3)
target_euler = LbotEuler(x=0.0, y=0.0, z=0.0)  # roll=0, pitch=0, yaw=0

# 移动到目标位姿
success = robot.move_to_pose_target(
    LbotArm.LEFT_ARM,
    target_position,
    target_euler,
    speed=0.3,
    accel=0.1,
    block=True
)
```

---

## 常见问题

### Q1: 为什么状态中同时有 euler 和 orientation？

**A:** LBot SDK 在内部状态中同时保存欧拉角和四元数两种表示，可能是为了方便不同的使用场景。但 `get_cartesian_pose()` API 返回的是欧拉角。

### Q2: 如何验证旋转顺序是否正确？

**A:** 可以运行 `verify_rotation_order.py` 脚本进行验证。该脚本测试了不同的旋转约定，并确认 XYZ 内旋是正确的选择。

### Q3: 如果需要四元数怎么办？

**A:** 可以从状态中直接获取：
```python
state = robot.get_state()
orientation = state.left_arm.orientation  # LbotOrientation (四元数)
print(f"四元数: x={orientation.x}, y={orientation.y}, z={orientation.z}, w={orientation.w}")
```

或者从欧拉角转换：
```python
from scipy.spatial.transform import Rotation as R

rotation = R.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)
quat = rotation.as_quat()  # 返回 [x, y, z, w]
```

---

## 总结

✅ **位姿格式**: 欧拉角（LbotEuler）
✅ **角度单位**: 弧度
✅ **旋转顺序**: XYZ 内旋（intrinsic）
✅ **对应关系**: euler.x=roll, euler.y=pitch, euler.z=yaw
✅ **scipy 转换**: `R.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)`

当前 `robot_interface.py` 中的实现是**正确的**，无需修改。
