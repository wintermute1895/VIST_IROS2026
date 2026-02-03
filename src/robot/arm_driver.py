import time
import numpy as np
import sys
import os
from abc import ABC, abstractmethod

# ==========================================
# 1. 尝试导入 LinkerArm SDK (安全导入)
# ==========================================
SDK_LOADED = False
try:
    # 构造 SDK 路径: src/robot/sdk/linkerarm
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sdk_path = os.path.join(current_dir, "sdk", "linkerarm")

    # 把 SDK 路径加入 Python 搜索路径，确保能找到 libs/ 下的 .so
    if sdk_path not in sys.path:
        sys.path.append(sdk_path)

    # 引用 lbot 包（从 __init__.py 导入）
    from lbot import LbotRobot, LbotArm
    SDK_LOADED = True
except ImportError as e:
    print(f"⚠️ [ArmDriver] Warning: LinkerArm SDK not found or failed to load. Real hardware mode unavailable.")
    print(f"   Debug Info: {e}")
except Exception as e:
    print(f"⚠️ [ArmDriver] SDK Load Error: {e}")

# ==========================================
# 2. 定义抽象基类 (接口约束)
# ==========================================
class BaseArmDriver(ABC):
    """所有驱动必须遵守的标准接口"""
    
    @abstractmethod
    def connect(self):
        """建立连接"""
        pass

    @abstractmethod
    def get_state(self):
        """
        获取机器人状态
        :return: (timestamp, q_pos_rad, q_vel_rad)
        必须统一为【弧度】单位！
        """
        pass

    @abstractmethod
    def send_command(self, q_cmd_rad):
        """
        发送控制指令
        :param q_cmd_rad: 目标关节角 【弧度】
        """
        pass

# ==========================================
# 3. 仿真驱动 (Mock / PyBullet)
# ==========================================
class MockArmDriver(BaseArmDriver):
    def __init__(self, dof=7):
        self.dof = dof
        self.q = np.zeros(dof)
        self.start_time = time.time()
        print("🛠️ [MockDriver] Initialized in Simulation Mode")

    def connect(self):
        print("🛠️ [MockDriver] Virtual Connection Established.")
        return True

    def get_state(self):
        # 模拟：当前状态 = 上次设定的目标 (假设瞬间到达)
        # 加一点微小的噪声模拟真实传感器
        noise = np.random.normal(0, 0.0001, self.dof)
        return time.time(), self.q + noise, np.zeros(self.dof)

    def send_command(self, q_cmd_rad):
        # 在仿真里，我们直接更新内部状态
        self.q = np.array(q_cmd_rad)

# ==========================================
# 4. 真机驱动 (LinkerArm)
# ==========================================
class RealArmDriver(BaseArmDriver):
    def __init__(self, ip="192.168.1.183", dof=7, arm_side="left"):
        """
        初始化真机驱动
        :param ip: 机器人控制器 IP 地址
        :param dof: 自由度数量（默认7）
        :param arm_side: 使用哪个手臂，"left" 或 "right"
        """
        if not SDK_LOADED:
            raise RuntimeError("Cannot initialize RealArmDriver: SDK not loaded!")

        self.ip = ip
        self.dof = dof

        # 确定使用左臂还是右臂
        if arm_side.lower() == "left":
            self.arm_enum = LbotArm.LEFT_ARM
        elif arm_side.lower() == "right":
            self.arm_enum = LbotArm.RIGHT_ARM
        else:
            raise ValueError(f"Invalid arm_side: {arm_side}. Must be 'left' or 'right'")

        # 实例化 SDK 高级接口对象（IP 在构造函数中传入）
        self.robot = LbotRobot(tcp_host=ip)
        print(f"🦾 [RealDriver] Initialized for {arm_side.upper()} arm")

    def connect(self):
        """建立连接并使能机械臂"""
        print(f"🦾 [RealDriver] Connecting to {self.ip}...")

        # SDK 的连接函数是 connect()，返回 bool
        success = self.robot.connect(timeout=10.0)

        if not success:
            error_msg = self.robot.get_last_error()
            print(f"❌ Connection Failed! Error: {error_msg}")
            return False

        print("✅ Connected. Enabling Robot...")
        # 使能机械臂（需要指定左臂或右臂）
        self.robot.enable_arm(self.arm_enum, enable=True)
        time.sleep(1)  # 等待就绪
        return True

    def get_state(self):
        """
        获取机器人状态
        注意：SDK 返回的已经是弧度制，无需转换
        """
        # SDK 方法：get_joint_positions(arm) 返回 List[float] 弧度制
        joint_positions = self.robot.get_joint_positions(self.arm_enum)

        if joint_positions is None or len(joint_positions) < self.dof:
            # 读取失败时返回空状态
            print("⚠️ [RealDriver] Failed to get joint positions")
            return time.time(), np.zeros(self.dof), np.zeros(self.dof)

        # SDK 返回的已经是弧度，直接使用
        q_pos = np.array(joint_positions[:self.dof])
        q_vel = np.zeros(self.dof)  # SDK 暂不提供速度，给 0

        return time.time(), q_pos, q_vel

    def send_command(self, q_cmd_rad):
        """
        发送关节控制指令
        注意：SDK 的 joint_follow 接受弧度制参数，无需转换
        """
        # 1. 安全检查：NaN 检查
        if np.isnan(q_cmd_rad).any():
            print("🚨 ERROR: NaN detected in command! Stopping.")
            return

        # 2. 转换为列表格式
        q_cmd_list = q_cmd_rad.tolist()

        # 3. 发送指令（SDK 的 joint_follow 用于遥操作，参数是弧度制）
        # follow=True 表示高跟随模式（低延迟，实时映射）
        success = self.robot.joint_follow(self.arm_enum, q_cmd_list, follow=True)

        if not success:
            print("⚠️ [RealDriver] Failed to send command")