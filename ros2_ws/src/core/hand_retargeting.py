import numpy as np
import yaml
import os
import sys
import json
import socket
import time
from scipy.spatial.transform import Rotation as R

# 添加external_sdk路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
dex_retargeting_path = os.path.join(project_root, "external_sdk", "dex_retargeting")
if dex_retargeting_path not in sys.path:
    sys.path.insert(0, dex_retargeting_path)

from dex_retargeting.retargeting_config import RetargetingConfig
from dex_retargeting.kinematics_adaptor import MimicJointKinematicAdaptor

class VectorHandController:
    def __init__(self, config_path, project_root):
        print(f"🚀 启动灵巧手重定向器 (Config: {os.path.basename(config_path)})...")
        
        self.project_root = project_root
        
        # 1. 加载 YAML 配置
        with open(config_path, 'r') as f:
            cfg_data = yaml.safe_load(f)
            
        # 2. 修正 URDF 绝对路径 (关键步骤)
        # 配置文件里写的是相对路径 "config/...", 这里要拼成绝对路径
        rel_urdf = cfg_data['retargeting']['urdf_path']
        abs_urdf = os.path.join(project_root, rel_urdf)
        cfg_data['retargeting']['urdf_path'] = abs_urdf
        
        # 3. 构建 Retargeting (dex-retargeting 核心)
        # 注意：from_dict 需要直接传入包含 type, urdf_path 等键的字典
        self.retargeting = RetargetingConfig.from_dict(cfg_data['retargeting']).build()
        
        # 4. 注入 Mimic 关节规则 (保留你原来的逻辑)
        # LinkerHand 有很多耦合关节，必须告诉优化器
        self._inject_mimic_adaptor(cfg_data['retargeting']['target_joint_names'])
        
        # 5. 手动参数 (缩指/旋转修正)
        # 这些也可以考虑放入 yaml，但暂时硬编码没问题
        self.thumb_rot = R.from_euler('xyz', [0, 0, 180], degrees=True).as_matrix()
        self.thumb_offset_vec = np.array([0.02, 0.0, 0.0])
        self.operator2mano = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])

    def _inject_mimic_adaptor(self, target_joint_names):
        """
        Linker Hand L10 特有的耦合关节规则
        """
        mimic_rules = [
            ("thumb_cmc_pitch", "thumb_mcp", 1.3898, 0), ("thumb_cmc_pitch", "thumb_ip", 1.508, 0),
            ("index_mcp_pitch", "index_pip", 1.3, 0), ("index_mcp_pitch", "index_dip", 0.4616, 0),
            ("middle_mcp_pitch", "middle_pip", 1.2462, 0), ("middle_mcp_pitch", "middle_dip", 0.4616, 0),
            ("ring_mcp_pitch", "ring_pip", 1.2462, 0), ("ring_mcp_pitch", "ring_dip", 0.4616, 0),
            ("pinky_mcp_pitch", "pinky_pip", 1.2462, 0), ("pinky_mcp_pitch", "pinky_dip", 0.4616, 0),
        ]
        source, mimic, mul, off = zip(*mimic_rules)
        
        # 这是一个补丁，dex-retargeting 有时需要手动注入耦合关系
        adaptor = MimicJointKinematicAdaptor(
            self.retargeting.optimizer.robot, 
            target_joint_names, 
            list(source), list(mimic), list(mul), list(off)
        )
        self.retargeting.optimizer.set_kinematic_adaptor(adaptor)

    def process(self, kp):
        """
        核心处理函数：输入关键点 -> 输出全关节角度
        """
        # 1. 坐标系对齐 (Canonical Frame)
        rot_mat = self._compute_canonical_frame(kp)
        kp_aligned = (kp - kp[0]) @ rot_mat 
        
        # 2. 提取向量并转换到 MANO 坐标系
        vectors = kp_aligned[[4, 8, 12, 16, 20]] 
        vectors = vectors @ self.operator2mano.T
        
        # 3. 大拇指特殊修正
        vectors[0] = vectors[0] @ self.thumb_rot.T
        vectors[0] += self.thumb_offset_vec

        # 4. Dex-Retargeting 求解
        retarget_qpos = self.retargeting.retarget(vectors)
        
        # 5. 扩展耦合关节 (Expansion)
        full_joints = self._expand_to_full(retarget_qpos)
        
        return full_joints

    def _compute_canonical_frame(self, kp):
        wrist, index_mcp, middle_mcp = kp[0], kp[5], kp[9]
        vec_palm = middle_mcp - wrist
        vec_side = index_mcp - wrist
        y_axis = vec_palm / (np.linalg.norm(vec_palm) + 1e-6)
        z_axis = np.cross(vec_side, y_axis)
        z_axis /= (np.linalg.norm(z_axis) + 1e-6)
        x_axis = np.cross(y_axis, z_axis)
        return np.stack([x_axis, y_axis, z_axis], axis=1)

    def _expand_to_full(self, active_qpos):
        # 从优化器的输出映射回所有关节名称
        # idx_pin2target 是 dex-retargeting 内部记录的索引映射
        joints = dict(zip(self.retargeting.optimizer.target_joint_names, active_qpos))
        
        # 手动计算耦合关节 (为了发送给机器人)
        d = joints.get("thumb_cmc_pitch", 0.0)
        joints["thumb_mcp"], joints["thumb_ip"] = d*1.3898, d*1.508
        for name, factor in [("index", 1.3), ("middle", 1.2462), ("ring", 1.2462), ("pinky", 1.2462)]:
            d = joints.get(f"{name}_mcp_pitch", 0.0)
            joints[f"{name}_pip"], joints[f"{name}_dip"] = d*factor, d*0.4616
            
        return joints