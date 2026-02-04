"""
LinkerHand Retargeter - 10个主动关节优化
策略：优化器使用10个主动关节，mimic关节由URDF自动处理
"""

import numpy as np
import yaml
import os
from scipy.spatial.transform import Rotation as R
from dex_retargeting.retargeting_config import RetargetingConfig


class LinkerHandRetargeter:
    """
    LinkerHand 重定向器 - 10个主动关节优化

    工作流程：
    1. 优化器使用10个主动关节进行优化
    2. Mimic关节（PIP/DIP）由dex-retargeting自动从URDF检测并处理
    3. 输出10维主动关节角度数组，按LinkerHand SDK顺序排列
    """

    # LinkerHand SDK 要求的10个主动关节顺序（严格按照硬件电机编号）
    # 顺序必须与 LinkerHand SDK 的 finger_move() 期望的顺序一致
    ACTIVE_JOINT_NAMES = [
        "thumb_cmc_pitch",    # 0: 拇指根部俯仰
        "thumb_cmc_yaw",      # 1: 拇指根部偏航/内收外展
        "index_mcp_pitch",    # 2: 食指MCP弯曲
        "middle_mcp_pitch",   # 3: 中指MCP弯曲
        "ring_mcp_pitch",     # 4: 无名指MCP弯曲
        "pinky_mcp_pitch",    # 5: 小指MCP弯曲
        "index_mcp_roll",     # 6: 食指MCP侧摆/内收外展
        "ring_mcp_roll",      # 7: 无名指MCP侧摆/内收外展
        "pinky_mcp_roll",     # 8: 小指MCP侧摆/内收外展
        "thumb_cmc_roll",     # 9: 拇指根部滚转
    ]

    def __init__(self, config_path, project_root):
        """
        初始化重定向器

        Args:
            config_path: YAML配置文件路径
            project_root: 项目根目录（用于解析相对路径）
        """
        print(f"🚀 初始化 LinkerHandRetargeter (配置14个，提取10个)...")

        self.project_root = project_root

        # 1. 加载YAML配置
        with open(config_path, 'r') as f:
            cfg_data = yaml.safe_load(f)

        # 2. 修正URDF绝对路径
        rel_urdf = cfg_data['retargeting']['urdf_path']
        abs_urdf = os.path.join(project_root, rel_urdf)
        cfg_data['retargeting']['urdf_path'] = abs_urdf

        # 3. 构建Retargeting优化器（使用10个主动关节）
        # 注意：dex-retargeting会自动从URDF检测mimic关节并创建适配器
        self.retargeting = RetargetingConfig.from_dict(cfg_data['retargeting']).build()

        # 4. 建立索引映射：从优化器输出 -> 10维主动关节
        # 由于只配置了10个主动关节，优化器输出就是10维，映射是1:1的
        self._build_index_mapping()

        # 5. 准备固定关节位置（用于优化器）
        # 优化器需要固定关节（arm joints）的位置，设为0即可
        self.fixed_qpos = np.zeros(len(self.retargeting.optimizer.fixed_joint_names))
        print(f"📌 固定关节数量: {len(self.fixed_qpos)} (arm joints)")

        # 6. 坐标系转换参数（保留原有逻辑）
        self.thumb_rot = R.from_euler('xyz', [0, 0, 180], degrees=True).as_matrix()
        self.thumb_offset_vec = np.array([0.02, 0.0, 0.0])
        self.operator2mano = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])

        print(f"✅ 优化器配置：{len(self.retargeting.optimizer.target_joint_names)} 个关节")
        print(f"✅ 主动关节：{len(self.ACTIVE_JOINT_NAMES)} 个")
        print(f"✅ 索引映射：{self.active_joint_indices}")

    def _build_index_mapping(self):
        """
        建立索引映射：从14维优化器输出提取10个主动关节

        优化器输出顺序由target_joint_names决定（14个）
        我们需要找到10个主动关节在14维数组中的索引位置
        """
        optimizer_joint_names = self.retargeting.optimizer.target_joint_names

        # 为每个主动关节找到在优化器输出中的索引
        self.active_joint_indices = []
        for active_name in self.ACTIVE_JOINT_NAMES:
            try:
                idx = optimizer_joint_names.index(active_name)
                self.active_joint_indices.append(idx)
            except ValueError:
                raise ValueError(
                    f"主动关节 '{active_name}' 未在优化器的 target_joint_names 中找到！"
                    f"\n优化器关节列表：{optimizer_joint_names}"
                )

        print(f"📊 索引映射构建完成：")
        for i, (name, idx) in enumerate(zip(self.ACTIVE_JOINT_NAMES, self.active_joint_indices)):
            print(f"   SDK[{i}] = Optimizer[{idx}] ({name})")

    def process(self, mediapipe_landmarks):
        """
        核心处理函数：MediaPipe关键点 -> 10个主动关节角度

        Args:
            mediapipe_landmarks: MediaPipe手部关键点 (21, 3) numpy数组

        Returns:
            active_qpos: 10个主动关节的角度 (10,) numpy数组，按SDK顺序排列
        """
        # 1. 坐标系对齐（Canonical Frame）
        rot_mat = self._compute_canonical_frame(mediapipe_landmarks)
        kp_aligned = (mediapipe_landmarks - mediapipe_landmarks[0]) @ rot_mat

        # 2. 提取指尖向量并转换到MANO坐标系
        # MediaPipe索引：4=拇指尖, 8=食指尖, 12=中指尖, 16=无名指尖, 20=小指尖
        vectors = kp_aligned[[4, 8, 12, 16, 20]]
        vectors = vectors @ self.operator2mano.T

        # 3. 拇指特殊修正（旋转+偏移）
        vectors[0] = vectors[0] @ self.thumb_rot.T
        vectors[0] += self.thumb_offset_vec

        # 4. Dex-Retargeting优化求解（输出10维主动关节）
        # 需要提供固定关节位置（arm joints）
        qpos = self.retargeting.retarget(vectors, fixed_qpos=self.fixed_qpos)  # shape: (10,)

        # 5. 提取10个主动关节（按索引映射）
        active_qpos = qpos[self.active_joint_indices]  # shape: (10,)

        return active_qpos

    def _compute_canonical_frame(self, kp):
        """
        计算手部规范坐标系

        使用手腕、食指MCP、中指MCP三点构建正交坐标系
        """
        wrist = kp[0]          # 手腕
        index_mcp = kp[5]      # 食指MCP
        middle_mcp = kp[9]     # 中指MCP

        # 构建正交基
        vec_palm = middle_mcp - wrist
        vec_side = index_mcp - wrist

        y_axis = vec_palm / (np.linalg.norm(vec_palm) + 1e-6)
        z_axis = np.cross(vec_side, y_axis)
        z_axis /= (np.linalg.norm(z_axis) + 1e-6)
        x_axis = np.cross(y_axis, z_axis)

        return np.stack([x_axis, y_axis, z_axis], axis=1)

    def get_full_joint_dict(self, active_qpos):
        """
        将10个主动关节扩展为完整的关节字典（包含耦合关节）

        Args:
            active_qpos: 10个主动关节角度 (10,) numpy数组

        Returns:
            joints: 完整关节字典，包含主动+耦合关节
        """
        # 构建主动关节字典
        joints = dict(zip(self.ACTIVE_JOINT_NAMES, active_qpos))

        # 手动计算耦合关节（用于可视化或调试）
        joints["thumb_mcp"] = joints["thumb_cmc_pitch"] * 1.3898
        joints["thumb_ip"] = joints["thumb_cmc_pitch"] * 1.508

        for name, pip_factor in [("index", 1.3), ("middle", 1.2462),
                                  ("ring", 1.2462), ("pinky", 1.2462)]:
            mcp_angle = joints.get(f"{name}_mcp_pitch", 0.0)
            joints[f"{name}_pip"] = mcp_angle * pip_factor
            joints[f"{name}_dip"] = mcp_angle * 0.4616

        return joints