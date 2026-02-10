# 如何实现自定义机械臂接口

## 概述

要在手眼标定系统中使用您的机械臂，需要实现 `RobotInterface` 抽象类。本文档将详细说明需要提供的信息和实现步骤。

## 需要提供的信息

### 1. 机械臂基本信息

请提供以下信息：

- **机械臂品牌和型号**: 例如 UR5, ABB IRB, KUKA KR, Franka Emika, 等
- **控制方式**: TCP/IP, USB, ROS, 专有SDK, 等
- **通信协议**: 如果有文档，请提供
- **IP地址和端口**: 如果通过网络连接

### 2. SDK 文档和代码

请提供以下材料（越详细越好）：

#### 必需材料：
1. **SDK 安装包或 Python 库**
   - PyPI 包名（如果有）: `pip install xxx`
   - 或者 SDK 文件/文件夹路径
   - 安装说明

2. **获取位姿的 API 文档**
   - 函数名称
   - 参数说明
   - 返回值格式
   - 示例代码

3. **位姿数据格式**
   - 返回的数据类型和结构
   - 坐标系定义（右手系/左手系）
   - 单位（米/毫米，弧度/度）
   - 旋转表示方式（欧拉角/四元数/旋转矩阵/轴角）

#### 可选但有帮助的材料：
4. **移动控制 API**（用于自动化采集）
   - 移动到指定位姿的函数
   - 参数格式
   - 示例代码

5. **SDK 示例代码**
   - 连接机械臂的示例
   - 读取位姿的示例
   - 任何官方示例代码

6. **坐标系说明**
   - 基座坐标系定义
   - 末端执行器坐标系定义
   - 坐标系示意图（如果有）

## 实现步骤

### 步骤 1: 创建接口类

在 `calibration/robot_interface.py` 中添加您的机械臂接口类：

```python
class YourRobotInterface(RobotInterface):
    """
    您的机械臂接口实现
    """

    def __init__(self, ip_address: str = "192.168.1.100", **kwargs):
        """
        初始化机械臂连接

        Args:
            ip_address: 机械臂IP地址
            **kwargs: 其他参数（根据您的SDK需求）
        """
        # TODO: 初始化SDK连接
        pass

    def get_current_pose(self) -> np.ndarray:
        """
        获取当前机械臂位姿

        Returns:
            np.ndarray: 4x4 齐次变换矩阵
        """
        # TODO: 调用SDK获取位姿
        # TODO: 转换为4x4矩阵格式
        pass

    def move_to(self, target_pose: np.ndarray) -> bool:
        """
        移动到目标位姿（可选）

        Args:
            target_pose: 4x4 齐次变换矩阵

        Returns:
            bool: 是否成功
        """
        # TODO: 实现移动功能（可选）
        pass

    def disconnect(self):
        """
        断开连接（可选但推荐）
        """
        # TODO: 清理资源
        pass
```

### 步骤 2: 实现位姿转换

根据您的SDK返回的位姿格式，选择合适的转换方法：

#### 情况 1: SDK 返回 [x, y, z, rx, ry, rz] 格式

```python
def get_current_pose(self) -> np.ndarray:
    # 从SDK获取位姿
    x, y, z, rx, ry, rz = your_sdk.get_pose()

    # 转换为4x4矩阵
    # 注意：需要确认旋转的表示方式和单位
    return self.pose_to_matrix(
        x, y, z,           # 位置（米）
        rx, ry, rz,        # 旋转（弧度）
        rotation_type="euler_xyz"  # 根据实际情况选择
    )
```

#### 情况 2: SDK 返回四元数 [x, y, z, qx, qy, qz, qw]

```python
def get_current_pose(self) -> np.ndarray:
    # 从SDK获取位姿
    x, y, z, qx, qy, qz, qw = your_sdk.get_pose()

    # 转换为4x4矩阵
    return self.quaternion_to_matrix(x, y, z, qx, qy, qz, qw)
```

#### 情况 3: SDK 直接返回 4x4 矩阵

```python
def get_current_pose(self) -> np.ndarray:
    # 从SDK获取位姿
    matrix = your_sdk.get_pose()

    # 确保是 numpy 数组
    return np.array(matrix, dtype=np.float64)
```

#### 情况 4: SDK 返回自定义对象

```python
def get_current_pose(self) -> np.ndarray:
    # 从SDK获取位姿对象
    pose = your_sdk.get_pose()

    # 提取位置和旋转
    x = pose.position.x
    y = pose.position.y
    z = pose.position.z

    # 根据SDK的旋转表示方式转换
    # 例如，如果是欧拉角：
    rx = pose.rotation.roll
    ry = pose.rotation.pitch
    rz = pose.rotation.yaw

    return self.pose_to_matrix(x, y, z, rx, ry, rz)
```

### 步骤 3: 处理单位转换

**重要**: 确保所有单位正确！

```python
def get_current_pose(self) -> np.ndarray:
    # 从SDK获取位姿
    x, y, z, rx, ry, rz = your_sdk.get_pose()

    # 单位转换
    # 如果SDK返回毫米，转换为米
    x = x / 1000.0
    y = y / 1000.0
    z = z / 1000.0

    # 如果SDK返回度，转换为弧度
    rx = np.deg2rad(rx)
    ry = np.deg2rad(ry)
    rz = np.deg2rad(rz)

    return self.pose_to_matrix(x, y, z, rx, ry, rz)
```

### 步骤 4: 测试接口

创建测试脚本 `test_your_robot.py`:

```python
from robot_interface import YourRobotInterface
import numpy as np

def test_connection():
    """测试连接"""
    print("测试机械臂连接...")
    robot = YourRobotInterface(ip_address="192.168.1.100")
    print("✓ 连接成功")
    return robot

def test_get_pose(robot):
    """测试获取位姿"""
    print("\n测试获取位姿...")
    pose = robot.get_current_pose()

    print(f"位姿矩阵:\n{pose}")
    print(f"矩阵形状: {pose.shape}")
    print(f"矩阵类型: {pose.dtype}")

    # 验证矩阵格式
    assert pose.shape == (4, 4), "矩阵形状应该是 4x4"
    assert np.allclose(pose[3, :], [0, 0, 0, 1]), "最后一行应该是 [0, 0, 0, 1]"

    # 验证旋转矩阵
    R = pose[:3, :3]
    det = np.linalg.det(R)
    print(f"旋转矩阵行列式: {det:.6f} (应该接近1)")

    print("✓ 位姿格式正确")

def test_multiple_reads(robot):
    """测试多次读取"""
    print("\n测试多次读取位姿...")
    poses = []
    for i in range(5):
        pose = robot.get_current_pose()
        poses.append(pose)
        print(f"读取 {i+1}: 位置 = {pose[:3, 3]}")

    print("✓ 多次读取成功")

if __name__ == "__main__":
    robot = test_connection()
    test_get_pose(robot)
    test_multiple_reads(robot)
    print("\n所有测试通过！")
```

## 常见问题和解决方案

### 问题 1: 不知道旋转表示方式

**解决方案**:
1. 查看SDK文档中的"坐标系"或"位姿"章节
2. 尝试不同的 `rotation_type` 参数
3. 使用已知位姿测试（例如，机械臂在零位时）

### 问题 2: 坐标系不匹配

**症状**: 标定误差很大，或者坐标轴方向不对

**解决方案**:
```python
def get_current_pose(self) -> np.ndarray:
    pose = your_sdk.get_pose()
    matrix = self.pose_to_matrix(...)

    # 如果需要坐标系转换，可以添加变换
    # 例如，交换 Y 和 Z 轴：
    # transform = np.array([
    #     [1, 0, 0, 0],
    #     [0, 0, 1, 0],
    #     [0, 1, 0, 0],
    #     [0, 0, 0, 1]
    # ])
    # matrix = transform @ matrix

    return matrix
```

### 问题 3: SDK 需要特殊初始化

**解决方案**: 在 `__init__` 中完成所有初始化：

```python
def __init__(self, ip_address: str):
    import sys
    sys.path.append("/path/to/sdk")

    from your_sdk import RobotController

    self.robot = RobotController()
    self.robot.connect(ip_address)
    self.robot.enable()

    print("✓ 机械臂已连接并使能")
```

## 现有实现参考

### LinkerArm (LBot) 实现

您可以参考 `robot_interface.py` 中的 `LinkerArmInterface` 类作为示例：

```python
class LinkerArmInterface(RobotInterface):
    def __init__(self, tcp_host: str, arm_side: str, sdk_path: str = None):
        # 1. 添加SDK路径到Python路径
        import sys
        sys.path.insert(0, sdk_path)

        # 2. 导入SDK
        from lbot import LBot, LbotArm

        # 3. 连接机械臂
        self.robot = LBot(tcp_host)
        self.arm = LbotArm.LEFT_ARM if arm_side == "left" else LbotArm.RIGHT_ARM

    def get_current_pose(self) -> np.ndarray:
        # 1. 调用SDK获取位姿
        pose = self.robot.get_cartesian_pose(self.arm)

        # 2. 提取位置和欧拉角
        position, euler = pose

        # 3. 转换为4x4矩阵
        return self.lbot_pose_to_matrix(position, euler)
```

## 提供信息的模板

请按照以下模板提供信息：

```
机械臂信息：
- 品牌型号: [例如: UR5]
- 控制方式: [例如: TCP/IP]
- IP地址: [例如: 192.168.1.100]
- 端口: [例如: 30003]

SDK信息：
- SDK名称: [例如: ur_rtde]
- 安装方式: [例如: pip install ur-rtde]
- 文档链接: [如果有]

位姿获取API：
- 函数名: [例如: get_actual_tcp_pose()]
- 返回格式: [例如: [x, y, z, rx, ry, rz]]
- 单位: [例如: 米, 弧度]
- 旋转表示: [例如: 轴角表示]

示例代码：
[粘贴您的SDK示例代码]
```

## 下一步

提供上述信息后，我可以帮您：
1. 编写完整的接口实现代码
2. 创建测试脚本
3. 验证接口是否正确工作
4. 集成到标定系统中

请提供尽可能详细的信息，这样我可以为您创建一个可靠的接口实现！
