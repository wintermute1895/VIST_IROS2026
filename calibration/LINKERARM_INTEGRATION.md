# LinkerArm (LBot) SDK 集成说明

本文档说明如何使用 `LinkerArmInterface` 类集成 LinkerArm 机械臂 SDK。

## 概述

`LinkerArmInterface` 类实现了 `RobotInterface` 抽象接口，提供了与 LinkerArm (LBot) 双臂机器人的标准化交互方式。

## 主要功能

### 1. 辅助函数：`lbot_pose_to_matrix()`

这是专门为 LBot SDK 设计的静态辅助函数，用于将 SDK 返回的位姿数据转换为标准的 4x4 齐次变换矩阵。

**输入：**
- `position`: `LbotPosition` 对象，包含 `x, y, z`（单位：米）
- `euler`: `LbotEuler` 对象，包含 `x, y, z`（对应 roll, pitch, yaw，单位：弧度）

**输出：**
- `np.ndarray`: 4x4 齐次变换矩阵

**使用示例：**
```python
from robot_interface import RobotInterface

# 假设从 LBot SDK 获取了位姿
position, euler = robot.get_cartesian_pose(LbotArm.LEFT_ARM)

# 转换为标准矩阵格式
matrix = RobotInterface.lbot_pose_to_matrix(position, euler)
```

### 2. LinkerArmInterface 类

完整的 LinkerArm 机械臂接口实现。

#### 初始化

```python
from robot_interface import LinkerArmInterface

robot = LinkerArmInterface(
    tcp_host="192.168.10.21",  # 机器人控制器 IP 地址
    arm_side="left",            # 使用的机械臂："left" 或 "right"
    sdk_path=None               # SDK 路径（可选，会自动查找）
)
```

**参数说明：**
- `tcp_host`: 机器人控制器的 IP 地址（默认：`"192.168.10.21"`）
- `arm_side`: 选择使用的机械臂，`"left"` 或 `"right"`（默认：`"left"`）
- `sdk_path`: LBot SDK 的路径（可选）。如果不提供，会自动尝试以下路径：
  - `/home/luka/.ssh/VIST/src/robot/sdk/linkerarm`
  - `../VIST/src/robot/sdk/linkerarm`（相对于当前文件）
  - `VIST/src/robot/sdk/linkerarm`（相对于当前文件）

#### 主要方法

##### `get_current_pose()` - 获取当前位姿

返回机械臂末端执行器相对于基座的位姿（4x4 齐次变换矩阵）。

```python
pose_matrix = robot.get_current_pose()
print(pose_matrix)
# 输出：
# [[R11, R12, R13, tx],
#  [R21, R22, R23, ty],
#  [R31, R32, R33, tz],
#  [0,   0,   0,   1 ]]
```

##### `move_to(target_pose)` - 移动到目标位姿

移动机械臂到指定的目标位姿。

```python
# 创建目标位姿（例如：在当前位置基础上沿 Z 轴移动 5cm）
target_pose = current_pose.copy()
target_pose[2, 3] += 0.05  # Z 轴移动 5cm

# 执行移动
success = robot.move_to(target_pose)
if success:
    print("移动成功")
else:
    print("移动失败")
```

**运动参数：**
- 速度：0.3 m/s
- 加速度：0.1 m/s²
- 阻塞模式：等待运动完成后返回

##### `disconnect()` - 断开连接

断开与机器人的连接。

```python
robot.disconnect()
```

## 完整使用示例

### 示例 1：基本使用

```python
from robot_interface import LinkerArmInterface
import numpy as np

# 1. 连接到机器人
robot = LinkerArmInterface(
    tcp_host="192.168.10.21",
    arm_side="left"
)

# 2. 获取当前位姿
current_pose = robot.get_current_pose()
print("当前位姿矩阵:")
print(current_pose)

# 3. 提取位置和欧拉角
from robot_interface import RobotInterface
x, y, z, rx, ry, rz = RobotInterface.matrix_to_pose(current_pose)
print(f"位置: x={x:.3f}, y={y:.3f}, z={z:.3f}")
print(f"欧拉角: roll={rx:.3f}, pitch={ry:.3f}, yaw={rz:.3f}")

# 4. 断开连接
robot.disconnect()
```

### 示例 2：移动机械臂

```python
from robot_interface import LinkerArmInterface
import numpy as np

robot = LinkerArmInterface(tcp_host="192.168.10.21", arm_side="left")

try:
    # 获取当前位姿
    current_pose = robot.get_current_pose()

    # 创建目标位姿：沿 Z 轴向上移动 5cm
    target_pose = current_pose.copy()
    target_pose[2, 3] += 0.05

    # 移动到目标位姿
    if robot.move_to(target_pose):
        print("移动成功")

        # 移动回原位
        robot.move_to(current_pose)
        print("已返回原位")

finally:
    robot.disconnect()
```

### 示例 3：在标定系统中使用

```python
from robot_interface import LinkerArmInterface

# 在标定系统中使用
def collect_calibration_data():
    # 创建机器人接口
    robot = LinkerArmInterface(
        tcp_host="192.168.10.21",
        arm_side="left"
    )

    try:
        # 采集多个位姿的数据
        poses = []
        for i in range(10):
            input(f"移动机械臂到位置 {i+1}，然后按回车...")

            # 获取当前位姿（自动转换为标准矩阵格式）
            pose = robot.get_current_pose()
            poses.append(pose)

            print(f"已记录位置 {i+1}")

        return poses

    finally:
        robot.disconnect()
```

## 测试脚本

使用提供的测试脚本验证集成是否正常工作：

```bash
cd /home/luka/.ssh/calibration
python3 test_linkerarm.py
```

测试脚本会执行以下测试：
1. 连接到机器人
2. 获取当前位姿并显示详细信息
3. （可选）测试机械臂移动

## 坐标系统说明

### 位姿表示

LinkerArm SDK 使用以下格式表示位姿：
- **位置**：`LbotPosition(x, y, z)`，单位：米
- **姿态**：`LbotEuler(x, y, z)`，对应 roll, pitch, yaw，单位：弧度

### 转换关系

`LinkerArmInterface` 自动处理以下转换：

1. **SDK → 标准矩阵**（在 `get_current_pose()` 中）：
   ```
   LbotPosition + LbotEuler → 4x4 齐次变换矩阵
   ```

2. **标准矩阵 → SDK**（在 `move_to()` 中）：
   ```
   4x4 齐次变换矩阵 → LbotPosition + LbotEuler
   ```

### 欧拉角顺序

- **旋转顺序**：XYZ（内旋）
- **对应关系**：
  - `euler.x` = roll（绕 X 轴旋转）
  - `euler.y` = pitch（绕 Y 轴旋转）
  - `euler.z` = yaw（绕 Z 轴旋转）

## 故障排除

### 问题 1：无法导入 LBot SDK

**错误信息：**
```
ImportError: 无法导入 LBot SDK
```

**解决方法：**
1. 检查 SDK 路径是否正确
2. 手动指定 `sdk_path` 参数：
   ```python
   robot = LinkerArmInterface(
       tcp_host="192.168.10.21",
       arm_side="left",
       sdk_path="/home/luka/.ssh/VIST/src/robot/sdk/linkerarm"
   )
   ```

### 问题 2：无法连接到机器人

**错误信息：**
```
RuntimeError: 无法连接到机器人
```

**解决方法：**
1. 检查机器人是否已开机
2. 检查网络连接
3. 验证 IP 地址是否正确
4. 确认防火墙设置

### 问题 3：移动失败

**可能原因：**
- 目标位姿超出工作空间
- 机械臂未使能
- 存在碰撞风险

**解决方法：**
1. 检查目标位姿是否在工作空间内
2. 确认机械臂已使能
3. 检查错误信息：`robot.get_last_error()`

## API 参考

### RobotInterface 基类方法

所有辅助函数都可以通过 `RobotInterface` 类访问：

```python
from robot_interface import RobotInterface

# 位姿转换
matrix = RobotInterface.pose_to_matrix(x, y, z, rx, ry, rz)
x, y, z, rx, ry, rz = RobotInterface.matrix_to_pose(matrix)

# 四元数转换
matrix = RobotInterface.quaternion_to_matrix(x, y, z, qx, qy, qz, qw)

# LBot SDK 专用转换
matrix = RobotInterface.lbot_pose_to_matrix(position, euler)
```

## 注意事项

1. **安全第一**：在测试移动功能前，确保机械臂周围没有障碍物
2. **单位统一**：所有位置单位为米，角度单位为弧度
3. **坐标系**：位姿矩阵表示从基座到末端执行器的变换
4. **连接管理**：使用完毕后记得调用 `disconnect()` 断开连接
5. **错误处理**：建议使用 try-finally 块确保连接被正确关闭

## 更多信息

- LBot SDK 文档：查看 `/home/luka/.ssh/VIST/src/robot/sdk/linkerarm/lbot/` 目录
- 标定系统文档：查看项目根目录的 README 文件
