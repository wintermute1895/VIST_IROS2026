import time
import numpy as np
import sys
import os
import threading
from abc import ABC, abstractmethod

# ==========================================
# 1. 尝试导入 LinkerArm SDK (安全导入)
# ==========================================
SDK_LOADED = False
try:
    # 构造 SDK 路径: external_sdk/linkerarm
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    sdk_path = os.path.join(project_root, "external_sdk", "linkerarm")

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

    def disconnect(self):
        print("🛠️ [MockDriver] Virtual Connection Closed.")

# ==========================================
# 4. 真机驱动 (LinkerArm)
# ==========================================
class RealArmDriver(BaseArmDriver):
    """
    LinkerArm真机驱动

    SDK关节顺序（基于LinkerArm lkls73_o2，Web控制器验证）：
    SDK[0]: Shoulder Pitch (肩部俯仰)
    SDK[1]: Shoulder Roll  (肩部侧摆)
    SDK[2]: Shoulder Yaw   (肩部旋转)
    SDK[3]: Elbow Pitch    (肘部俯仰)
    SDK[4]: Wrist Yaw      (腕部旋转)
    SDK[5]: Wrist Pitch    (腕部俯仰)
    SDK[6]: Wrist Roll     (腕部翻转)

    URDF关节顺序：
    URDF[0]: Shoulder Pitch (肩部俯仰)
    URDF[1]: Shoulder Roll  (肩部侧摆)
    URDF[2]: Shoulder Yaw   (肩部旋转)
    URDF[3]: Elbow Pitch    (肘部俯仰)
    URDF[4]: Wrist Yaw      (腕部旋转)
    URDF[5]: Wrist Pitch    (腕部俯仰)
    URDF[6]: Wrist Roll     (腕部翻转)
    """

    # 映射关系：URDF索引 → SDK索引
    # Web控制器验证：SDK顺序正确，直接对应即可
    URDF_TO_SDK = [
        0,  # URDF[0] Shoulder_Pitch → SDK[0]
        1,  # URDF[1] Shoulder_Roll  → SDK[1]
        2,  # URDF[2] Shoulder_Yaw   → SDK[2]
        3,  # URDF[3] Elbow_Pitch    → SDK[3]
        4,  # URDF[4] Wrist_Yaw      → SDK[4]
        5,  # URDF[5] Wrist_Pitch    → SDK[5]
        6   # URDF[6] Wrist_Roll     → SDK[6]
    ]

    # 映射关系：SDK索引 → URDF索引
    SDK_TO_URDF = [
        0,  # SDK[0] Shoulder_Pitch → URDF[0]
        1,  # SDK[1] Shoulder_Roll  → URDF[1]
        2,  # SDK[2] Shoulder_Yaw   → URDF[2]
        3,  # SDK[3] Elbow_Pitch    → URDF[3]
        4,  # SDK[4] Wrist_Yaw      → URDF[4]
        5,  # SDK[5] Wrist_Pitch    → URDF[5]
        6   # SDK[6] Wrist_Roll     → URDF[6]
    ]

    # 关节符号翻转（按URDF顺序）
    # 根据实际测试结果修正：
    # - URDF[0] Shoulder_Pitch: 不需要翻转
    # - URDF[1] Shoulder_Roll: 不需要翻转（映射已经交换了）
    # - URDF[2] Shoulder_Yaw: 需要翻转
    # - URDF[4] Wrist_Yaw: 需要翻转
    JOINT_SIGN_FLIP = [
        False,  # URDF[0] Shoulder_Pitch - 不需要翻转
        True,  # URDF[1] Shoulder_Roll - 不需要翻转
        True,   # URDF[2] Shoulder_Yaw - 需要翻转
        False,  # URDF[3] Elbow_Pitch
        True,   # URDF[4] Wrist_Yaw - 需要翻转
        False,  # URDF[5] Wrist_Pitch
        False   # URDF[6] Wrist_Roll
    ]

    def __init__(self, ip="192.168.1.183", dof=7, arm_side="left", config=None):
        """
        初始化真机驱动
        :param ip: 机器人控制器 IP 地址
        :param dof: 自由度数量（默认7）
        :param arm_side: 使用哪个手臂，"left" 或 "right"
        :param config: VISTConfig 配置对象（可选，用于读取映射关系）
        """
        if not SDK_LOADED:
            raise RuntimeError("Cannot initialize RealArmDriver: SDK not loaded!")

        self.ip = ip
        self.dof = dof
        self.config = config

        # 从配置读取映射关系（如果提供了配置）
        if config is not None:
            self.URDF_TO_SDK = config.hardware_urdf_to_sdk_mapping
            self.SDK_TO_URDF = config.hardware_sdk_to_urdf_mapping
            self.JOINT_SIGN_FLIP = config.hardware_joint_sign_flip
        else:
            # 使用类默认值
            self.URDF_TO_SDK = RealArmDriver.URDF_TO_SDK
            self.SDK_TO_URDF = RealArmDriver.SDK_TO_URDF
            self.JOINT_SIGN_FLIP = RealArmDriver.JOINT_SIGN_FLIP

        # 确定使用左臂还是右臂
        if arm_side.lower() == "left":
            self.arm_enum = LbotArm.LEFT_ARM
        elif arm_side.lower() == "right":
            self.arm_enum = LbotArm.RIGHT_ARM
        else:
            raise ValueError(f"Invalid arm_side: {arm_side}. Must be 'left' or 'right'")

        # 实例化 SDK 高级接口对象（IP 在构造函数中传入）
        self.robot = LbotRobot(tcp_host=ip)

        # TCP 健康监控（工业标准方案）
        self._connection_healthy = False
        self._last_successful_read = 0
        self._heartbeat_thread = None
        self._heartbeat_running = False
        self._connection_failures = 0
        self._max_failures_before_reconnect = 5
        self._heartbeat_interval = 1.0  # 1秒检查一次

        print(f"🦾 [RealDriver] Initialized for {arm_side.upper()} arm")

    def connect(self, use_safety_checks=True):
        """
        建立连接并使能机械臂

        Args:
            use_safety_checks: 是否使用安全检查（默认True，强烈推荐）
        """
        print(f"🦾 [RealDriver] Connecting to {self.ip}...")

        # SDK 的连接函数是 connect()，返回 bool
        success = self.robot.connect(timeout=10.0)

        if not success:
            error_msg = self.robot.get_last_error()
            print(f"❌ Connection Failed! Error: {error_msg}")
            return False

        print("✅ Connected.")

        # 使能机械臂（使用安全检查）
        if use_safety_checks:
            # 导入安全检查模块
            from src.robot.safety_checks import safe_enable_arm

            print("\n⚠️  使用安全检查模式（推荐）")
            print("   如需跳过安全检查，请在代码中设置 use_safety_checks=False")

            # 执行安全使能
            enable_success = safe_enable_arm(self, self.config)
            if not enable_success:
                print("❌ 安全使能失败")
                self.robot.disconnect()
                return False
        else:
            # 直接使能（不推荐，仅用于调试）
            print("⚠️  跳过安全检查，直接使能（不推荐）")
            self.robot.enable_arm(self.arm_enum, enable=True)
            time.sleep(2)

        # 验证能否读取状态
        print("\n⏳ 验证状态读取...")
        for attempt in range(5):
            joint_pos = self.robot.get_joint_positions(self.arm_enum)
            if joint_pos is not None and len(joint_pos) >= self.dof:
                print(f"✅ Robot ready! Joint positions: {joint_pos[:self.dof]}")
                # 启动心跳监控
                self._start_heartbeat_monitor()
                return True
            print(f"   尝试 {attempt+1}/5: 等待状态数据...")
            time.sleep(0.5)

        print("⚠️ Warning: Robot enabled but state data not available yet")
        # 即使数据未就绪，也启动心跳监控
        self._start_heartbeat_monitor()
        return True  # 仍然返回成功，可能数据会稍后到达

    def _start_heartbeat_monitor(self):
        """启动心跳监控线程（工业标准方案）"""
        if self._heartbeat_running:
            return

        self._heartbeat_running = True
        self._connection_healthy = True
        self._last_successful_read = time.time()

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="RobotHeartbeat",
            daemon=True
        )
        self._heartbeat_thread.start()
        print("✅ [RealDriver] TCP 健康监控已启动")

    def _heartbeat_loop(self):
        """心跳监控循环"""
        while self._heartbeat_running:
            try:
                # 检查连接健康状态
                current_time = time.time()
                time_since_last_read = current_time - self._last_successful_read

                # 如果超过3秒没有成功读取，认为连接不健康
                if time_since_last_read > 3.0:
                    if self._connection_healthy:
                        print(f"⚠️ [RealDriver] TCP 连接不健康: {time_since_last_read:.1f}秒无数据")
                        self._connection_healthy = False
                        self._connection_failures += 1

                    # 如果失败次数过多，尝试重连
                    if self._connection_failures >= self._max_failures_before_reconnect:
                        print(f"🔄 [RealDriver] 尝试自动重连 (失败次数: {self._connection_failures})")
                        self._attempt_reconnect()

                # 定期尝试读取状态（心跳检测）
                joint_pos = self.robot.get_joint_positions(self.arm_enum)
                if joint_pos is not None and len(joint_pos) >= self.dof:
                    if not self._connection_healthy:
                        print("✅ [RealDriver] TCP 连接已恢复")
                        self._connection_healthy = True
                        self._connection_failures = 0
                    self._last_successful_read = current_time

            except Exception as e:
                print(f"⚠️ [RealDriver] 心跳检测错误: {e}")

            time.sleep(self._heartbeat_interval)

    def _attempt_reconnect(self):
        """尝试重新连接"""
        try:
            print("🔄 [RealDriver] 断开旧连接...")
            self.robot.disconnect()
            time.sleep(1.0)

            print(f"🔄 [RealDriver] 重新连接到 {self.ip}...")
            success = self.robot.connect(timeout=10.0)

            if success:
                print("✅ [RealDriver] 重连成功")
                self._connection_healthy = True
                self._connection_failures = 0
                self._last_successful_read = time.time()
            else:
                print("❌ [RealDriver] 重连失败")
                self._connection_failures += 1

        except Exception as e:
            print(f"❌ [RealDriver] 重连异常: {e}")
            self._connection_failures += 1

    def is_connection_healthy(self) -> bool:
        """检查连接是否健康"""
        return self._connection_healthy

    def get_connection_statistics(self):
        """获取连接统计信息"""
        return {
            'healthy': self._connection_healthy,
            'failures': self._connection_failures,
            'time_since_last_read': time.time() - self._last_successful_read
        }

    def get_state(self):
        """
        获取机器人状态
        注意：SDK 返回的已经是弧度制，无需转换

        使用两种方法尝试读取状态：
        1. 通过回调机制的缓存状态（robot.get_joint_positions）
        2. 直接调用底层API（api.get_current_state）
        """
        # 方法1：尝试从回调缓存读取（快速但可能为空）
        joint_positions = self.robot.get_joint_positions(self.arm_enum)

        # 方法2：如果回调缓存为空，直接调用底层API
        if joint_positions is None:
            # 局部导入api（避免模块级导入影响SDK初始化）
            from lbot import api as lbot_api
            state = lbot_api.get_current_state()
            if state:
                if self.arm_enum.value == 0:  # LEFT_ARM
                    joint_positions = state.left_arm.get_joints_list()
                else:  # RIGHT_ARM
                    joint_positions = state.right_arm.get_joints_list()

        # 检查是否成功获取数据
        if joint_positions is None:
            print("⚠️ [RealDriver] Failed to get joint positions (both methods)")
            return time.time(), np.zeros(self.dof), np.zeros(self.dof)

        if len(joint_positions) < self.dof:
            print(f"⚠️ [RealDriver] Incomplete joint data: got {len(joint_positions)}, expected {self.dof}")
            return time.time(), np.zeros(self.dof), np.zeros(self.dof)

        # 更新最后成功读取时间（用于心跳监控）
        self._last_successful_read = time.time()

        # SDK 返回的已经是弧度，直接使用
        q_sdk = np.array(joint_positions[:self.dof])

        # ==========================================
        # 应用SDK→URDF映射（不再使用符号翻转）
        # 符号控制统一由 robot.joint_directions 处理
        # ==========================================
        q_urdf = np.zeros(self.dof)
        for sdk_idx in range(self.dof):
            urdf_idx = self.SDK_TO_URDF[sdk_idx]
            value = q_sdk[sdk_idx]
            # 不再应用 JOINT_SIGN_FLIP - 统一使用 joint_directions
            q_urdf[urdf_idx] = value

        q_pos = q_urdf

        # 检查是否全为零（可能表示数据未就绪）
        if np.allclose(q_pos, 0.0, atol=1e-6):
            print("⚠️ [RealDriver] Warning: All joint positions are zero (robot may not be ready)")

        q_vel = np.zeros(self.dof)  # SDK 暂不提供速度，给 0

        return time.time(), q_pos, q_vel

    def send_command(self, q_cmd_rad, use_smooth_mode=True, blocking=False):
        """
        发送关节控制指令（遥操作模式）
        注意：SDK 的 joint_follow 接受弧度制参数，无需转换

        Args:
            q_cmd_rad: 目标关节角度（弧度）
            use_smooth_mode: True=平滑模式（慢速，有轨迹平滑），False=高速模式（快速响应）
            blocking: 是否阻塞等待指令执行完成（默认False，遥操作模式建议True避免指令堆积）

        支持多种输入格式：
        1. 7维数组：直接发送（手臂关节）
        2. 更多维度：取前7个（假设是手臂关节）
        """
        q_cmd_rad = np.array(q_cmd_rad)

        # 1. 安全检查：NaN 检查
        if np.isnan(q_cmd_rad).any():
            print("🚨 ERROR: NaN detected in command! Stopping.")
            return

        # 2. 维度处理：提取手臂关节
        if len(q_cmd_rad) == self.dof:
            # 直接手臂指令（7维）
            q_urdf = q_cmd_rad.copy()
        elif len(q_cmd_rad) > self.dof:
            # 如果维度更多，取前7个（假设是手臂关节）
            q_urdf = q_cmd_rad[:self.dof].copy()
            print(f"🔧 [RealDriver] 提取前{self.dof}个关节: {len(q_cmd_rad)}维 → {self.dof}维")
        else:
            print(f"❌ [RealDriver] 无效的指令维度: {len(q_cmd_rad)} (期望至少{self.dof})")
            return

        # ==========================================
        # 应用URDF→SDK映射（不再使用符号翻转）
        # 符号控制统一由 robot.joint_directions 处理
        # ==========================================
        q_sdk = np.zeros(self.dof)
        for urdf_idx in range(self.dof):
            sdk_idx = self.URDF_TO_SDK[urdf_idx]
            value = q_urdf[urdf_idx]
            # 不再应用 JOINT_SIGN_FLIP - 统一使用 joint_directions
            q_sdk[sdk_idx] = value

        # 3. 转换为列表格式
        q_cmd_list = q_sdk.tolist()

        # 4. 发送指令
        # ⚠️ 重要：使用 move_joint 而不是 joint_follow
        # 原因：joint_follow API 有严重的控制错乱bug（详见 docs/SDK_BUG_REPORT_joint_follow.md）
        # move_joint 经过测试，控制精度 ±0.03°，完全可靠
        from lbot import api as lbot_api

        # 从配置读取速度和加速度参数
        if self.config is not None:
            speed = self.config.hardware_move_joint_speed
            accel = self.config.hardware_move_joint_accel
        else:
            # 默认值（如果没有配置）
            speed = 1.0
            accel = 2.0

        success = lbot_api.move_joint(
            self.arm_enum,
            q_cmd_list,
            speed=speed,   # 使用配置的速度
            accel=accel,   # 使用配置的加速度
            block=blocking # 阻塞模式可选（True可避免指令堆积导致的振荡）
        )

        if not success:
            print("⚠️ [RealDriver] Failed to send command")

    def move_joint_controlled(self, q_target_rad, speed=0.1, accel=0.1, block=True):
        """
        受控关节运动（带速度和加速度限制）
        适用于测试和安全运动

        Args:
            q_target_rad: 目标关节角度（弧度）
            speed: 运动速度 (rad/s)，默认0.1（非常慢，安全）
            accel: 加速度 (rad/s²)，默认0.1
            block: 是否阻塞等待运动完成

        Returns:
            bool: 运动是否成功启动
        """
        q_target_rad = np.array(q_target_rad)

        # 安全检查
        if np.isnan(q_target_rad).any():
            print("🚨 ERROR: NaN detected in command!")
            return False

        # 维度处理
        if len(q_target_rad) == self.dof:
            q_arm = q_target_rad
        elif len(q_target_rad) > self.dof:
            q_arm = q_target_rad[:self.dof]
            print(f"🔧 [RealDriver] 提取前{self.dof}个关节")
        else:
            print(f"❌ [RealDriver] 无效的指令维度: {len(q_target_rad)}")
            return False

        # 转换为列表
        q_cmd_list = q_arm.tolist()

        # 使用SDK的move_joint方法（带速度控制）
        from lbot import api as lbot_api
        success = lbot_api.move_joint(self.arm_enum, q_cmd_list, speed, accel, block)

        if not success:
            print("⚠️ [RealDriver] Controlled movement failed")
            return False

        return True

    def disconnect(self):
        """
        断开与机器人的连接
        """
        try:
            print("🦾 [RealDriver] Disconnecting from robot...")

            # 停止心跳监控
            if self._heartbeat_running:
                print("   停止心跳监控...")
                self._heartbeat_running = False
                if self._heartbeat_thread is not None:
                    self._heartbeat_thread.join(timeout=2.0)

            # 重要：先发送停止指令（当前位置），避免机器人继续运动
            try:
                current_pos = self.robot.get_joint_positions(self.arm_enum)
                if current_pos is not None and len(current_pos) >= self.dof:
                    print("   发送停止指令（保持当前位置）...")
                    # 使用 move_to_joint_target 而不是 set_joint_positions
                    self.robot.move_to_joint_target(
                        self.arm_enum,
                        current_pos[:self.dof],
                        speed=0.1,
                        accel=0.1,
                        block=False
                    )
                    import time
                    time.sleep(0.1)  # 等待指令发送
            except Exception as e:
                print(f"   ⚠️ 发送停止指令失败: {e}")

            # SDK 的 disconnect 方法
            if hasattr(self.robot, 'disconnect'):
                self.robot.disconnect()
            print("✅ [RealDriver] Disconnected successfully")
        except Exception as e:
            print(f"⚠️ [RealDriver] Disconnect error: {e}")
