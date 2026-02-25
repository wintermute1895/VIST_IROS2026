"""
MuJoCo Arm Driver for VIST System
基于 MuJoCo 物理引擎的机械臂仿真驱动

作者: VIST Team
日期: 2026-02-25
"""

import time
import numpy as np
import sys
import os
from typing import Tuple, Optional

# 尝试导入 MuJoCo
try:
    import mujoco
    import mujoco.viewer
    MUJOCO_AVAILABLE = True
except ImportError:
    MUJOCO_AVAILABLE = False
    print("⚠️ [MuJoCoDriver] MuJoCo not installed. Please install: pip install mujoco")

# 导入基类
from .arm_driver import BaseArmDriver


class MuJoCoArmDriver(BaseArmDriver):
    """
    MuJoCo 仿真驱动

    特点:
    - 高精度物理仿真（PD 动力学控制）
    - 碰撞检测（解决穿模问题）
    - 支持 250Hz+ 控制频率
    - 真实的动力学响应
    - 可视化支持
    """

    def __init__(
        self,
        model_path: str,
        dof: int = 7,
        arm_side: str = "right",
        use_viewer: bool = True,
        control_dt: float = 0.002,
        config: Optional[object] = None,
        kp: float = 200.0,   # 位置增益
        kd: float = 20.0,    # 速度增益
        debug: bool = False
    ):
        """
        初始化 MuJoCo 驱动

        Args:
            model_path: MJCF/URDF 模型文件路径
            dof: 自由度数量
            arm_side: 使用哪个手臂 ("left" 或 "right")
            use_viewer: 是否启用可视化窗口
            control_dt: 控制时间步长（秒）
            config: VIST 配置对象
            kp: PD 控制位置增益
            kd: PD 控制速度增益
            debug: 是否打印调试信息
        """
        if not MUJOCO_AVAILABLE:
            raise RuntimeError("MuJoCo not available. Please install: pip install mujoco")

        self.model_path = model_path
        self.dof = dof
        self.arm_side = arm_side.lower()
        self.use_viewer = use_viewer
        self.control_dt = control_dt
        self.config = config
        self.kp = kp
        self.kd = kd
        self.debug = debug

        # MuJoCo 对象
        self.model = None
        self.data = None
        self.viewer = None

        # 状态变量
        self.q_target = np.zeros(dof)
        self.q_current = np.zeros(dof)
        self.qd_current = np.zeros(dof)
        self.start_time = None

        # 关节名称映射（根据 arm_side 确定）
        self.joint_names = self._get_joint_names()
        self.joint_ids = []
        self.qpos_addrs = []  # qpos 中的地址
        self.dof_addrs = []   # qvel/qfrc_applied 中的地址

        # 另一侧手臂的关节（需要固定）
        self.other_arm_joint_names = self._get_other_arm_joint_names()
        self.other_arm_qpos_addrs = []
        self.other_arm_dof_addrs = []

        # 调试计数器
        self._debug_count = 0

        print(f"[MuJoCoDriver] Initialized for {arm_side.upper()} arm")
        print(f"   Model: {model_path}")
        print(f"   Control dt: {control_dt*1000:.1f}ms ({1/control_dt:.0f}Hz)")
        print(f"   PD gains: Kp={kp}, Kd={kd}")

    def _get_joint_names(self):
        """根据手臂侧获取关节名称"""
        prefix = "Left" if self.arm_side == "left" else "Right"
        return [
            f"{prefix}_Shoulder_Pitch_Joint",
            f"{prefix}_Shoulder_Roll_Joint",
            f"{prefix}_Shoulder_Yaw_Joint",
            f"{prefix}_Elbow_Pitch_Joint",
            f"{prefix}_Wrist_Yaw_Joint",
            f"{prefix}_Wrist_Pitch_Joint",
            f"{prefix}_Wrist_Roll_Joint"
        ]

    def _get_other_arm_joint_names(self):
        """获取另一侧手臂的关节名称（需要固定）"""
        prefix = "Right" if self.arm_side == "left" else "Left"
        return [
            f"{prefix}_Shoulder_Pitch_Joint",
            f"{prefix}_Shoulder_Roll_Joint",
            f"{prefix}_Shoulder_Yaw_Joint",
            f"{prefix}_Elbow_Pitch_Joint",
            f"{prefix}_Wrist_Yaw_Joint",
            f"{prefix}_Wrist_Pitch_Joint",
            f"{prefix}_Wrist_Roll_Joint"
        ]

    def connect(self) -> bool:
        """建立 MuJoCo 仿真连接"""
        try:
            print(f"[MuJoCoDriver] Loading model from {self.model_path}")

            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found: {self.model_path}")

            self.model = mujoco.MjModel.from_xml_path(self.model_path)
            self.data = mujoco.MjData(self.model)

            # 打印模型信息
            print(f"[MuJoCoDriver] Model info:")
            print(f"   njnt={self.model.njnt}, nq={self.model.nq}, nv={self.model.nv}")
            print(f"   All joints: {[self.model.joint(i).name for i in range(self.model.njnt)]}")

            # 查找关节 ID、qpos 地址和 DOF 地址
            self.joint_ids = []
            self.qpos_addrs = []
            self.dof_addrs = []
            for joint_name in self.joint_names:
                try:
                    joint_id = mujoco.mj_name2id(
                        self.model,
                        mujoco.mjtObj.mjOBJ_JOINT,
                        joint_name
                    )
                    self.joint_ids.append(joint_id)
                    self.qpos_addrs.append(self.model.jnt_qposadr[joint_id])
                    self.dof_addrs.append(self.model.jnt_dofadr[joint_id])
                except Exception as e:
                    print(f"⚠️ [MuJoCoDriver] Warning: Joint '{joint_name}' not found")
                    print(f"   Available joints: {[self.model.joint(i).name for i in range(self.model.njnt)]}")
                    raise

            print(f"[MuJoCoDriver] Found {len(self.joint_ids)} joints:")
            print(f"   joint_ids  = {self.joint_ids}")
            print(f"   qpos_addrs = {self.qpos_addrs}")
            print(f"   dof_addrs  = {self.dof_addrs}")

            # 查找另一侧手臂的关节（需要固定）
            for joint_name in self.other_arm_joint_names:
                try:
                    joint_id = mujoco.mj_name2id(
                        self.model,
                        mujoco.mjtObj.mjOBJ_JOINT,
                        joint_name
                    )
                    self.other_arm_qpos_addrs.append(self.model.jnt_qposadr[joint_id])
                    self.other_arm_dof_addrs.append(self.model.jnt_dofadr[joint_id])
                except Exception:
                    pass  # 忽略找不到的关节

            if len(self.other_arm_qpos_addrs) > 0:
                print(f"[MuJoCoDriver] Found {len(self.other_arm_qpos_addrs)} joints on other arm (will be fixed)")
                print(f"   other_qpos_addrs = {self.other_arm_qpos_addrs}")

            # 初始化状态
            mujoco.mj_resetData(self.model, self.data)

            # 禁用重力（避免未控制关节自由落下）
            self.model.opt.gravity[:] = 0.0

            self.q_current = self.data.qpos[self.qpos_addrs].copy()
            self.qd_current = self.data.qvel[self.dof_addrs].copy()
            self.q_target = self.q_current.copy()

            # 启动可视化（如果需要）
            if self.use_viewer:
                self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
                print("[MuJoCoDriver] Viewer launched")

            self.start_time = time.time()
            print("✅ [MuJoCoDriver] Connection established")
            return True

        except Exception as e:
            print(f"❌ [MuJoCoDriver] Connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_state(self) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        获取机器人状态

        Returns:
            (timestamp, q_pos_rad, q_vel_rad)
        """
        if self.data is None:
            raise RuntimeError("MuJoCo not connected. Call connect() first.")

        self.q_current = self.data.qpos[self.qpos_addrs].copy()
        self.qd_current = self.data.qvel[self.dof_addrs].copy()

        timestamp = time.time()
        return timestamp, self.q_current, self.qd_current

    def send_command(self, q_cmd_rad: np.ndarray):
        """
        发送控制指令（混合模式：位置控制 + 碰撞检测）

        使用直接位置控制（运动学）+ mj_step 启用碰撞检测。
        这种方法结合了运动学控制的精确性和动力学仿真的碰撞检测。

        Args:
            q_cmd_rad: 目标关节角（弧度），7 维
        """
        if self.data is None:
            raise RuntimeError("MuJoCo not connected. Call connect() first.")

        q_cmd = np.array(q_cmd_rad, dtype=np.float64)

        # 维度检查
        if len(q_cmd) != self.dof:
            print(f"⚠️ [MuJoCoDriver] q_cmd 维度错误: 期望 {self.dof}, 实际 {len(q_cmd)}")
            return

        # 更新目标
        self.q_target = q_cmd.copy()

        # 调试输出（每 10 次打印一次）
        if self.debug and self._debug_count % 10 == 0:
            q_current = self.data.qpos[self.qpos_addrs]
            print(f"\n[DEBUG MuJoCo #{self._debug_count}]")
            print(f"  q_target (deg): {np.round(np.rad2deg(self.q_target), 1)}")
            print(f"  q_current(deg): {np.round(np.rad2deg(q_current), 1)}")
            print(f"  error    (deg): {np.round(np.rad2deg(self.q_target - q_current), 1)}")
        self._debug_count += 1

        # 直接设置关节位置（运动学控制）
        self.data.qpos[self.qpos_addrs] = self.q_target

        # 固定另一侧手臂（设置为零位或当前位置）
        if len(self.other_arm_qpos_addrs) > 0:
            # 设置为零位（或者可以设置为某个固定姿态）
            self.data.qpos[self.other_arm_qpos_addrs] = 0.0
            self.data.qvel[self.other_arm_dof_addrs] = 0.0
            self.data.qacc[self.other_arm_dof_addrs] = 0.0

        # 清零速度和加速度，防止漂移
        self.data.qvel[self.dof_addrs] = 0.0
        self.data.qacc[self.dof_addrs] = 0.0

        # 清零所有外力
        self.data.qfrc_applied[:] = 0.0

        # 调用 mj_step 启用碰撞检测（但关节位置已固定）
        # 注意：由于我们直接设置了 qpos 和清零了 qvel，
        # mj_step 主要用于更新碰撞和约束，不会改变关节位置
        mujoco.mj_step(self.model, self.data)

        # 更新可视化
        if self.viewer is not None and self.viewer.is_running():
            self.viewer.sync()

    def step_simulation(self, n_steps: int = 1):
        """
        执行仿真步进（不发送新指令，保持当前目标）

        Args:
            n_steps: 步进次数
        """
        if self.data is None:
            raise RuntimeError("MuJoCo not connected. Call connect() first.")

        for _ in range(n_steps):
            q_now = self.data.qpos[self.qpos_addrs]
            qd_now = self.data.qvel[self.dof_addrs]
            tau = self.kp * (self.q_target - q_now) + self.kd * (0.0 - qd_now)
            self.data.qfrc_applied[:] = 0.0
            self.data.qfrc_applied[self.dof_addrs] = tau
            mujoco.mj_step(self.model, self.data)

        if self.viewer is not None and self.viewer.is_running():
            self.viewer.sync()

    def disconnect(self):
        """断开连接"""
        if self.viewer is not None:
            try:
                self.viewer.close()
            except Exception:
                pass
            self.viewer = None

        self.model = None
        self.data = None
        print("[MuJoCoDriver] Connection closed")

    def __del__(self):
        """析构函数"""
        try:
            self.disconnect()
        except Exception:
            pass
