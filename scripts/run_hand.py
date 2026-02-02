import numpy as np
import socket
import json
import time
import os
from scipy.spatial.transform import Rotation as R

try:
    from dex_retargeting.retargeting_config import RetargetingConfig
    from dex_retargeting.kinematics_adaptor import MimicJointKinematicAdaptor
except ImportError:
    print("❌ dex-retargeting not found")

# ================= 配置 =================
HAND_URDF = "/home/ilex/Dev/IROS_teleop/config/l10/right/linkerhand_l10_right.urdf"
HAND_PKG_DIR = "/home/ilex/Dev/IROS_teleop/config/l10/right"

TARGET_ORIGIN_LINKS = ["hand_base_link"] * 5
TARGET_TASK_LINKS = ["thumb_distal", "index_distal", "middle_distal", "ring_distal", "pinky_distal"]

# 🔴 修复点：必须是 2行 N列 的 List，不能是 Numpy 数组
VECTOR_INDICES = [
    [0, 0, 0, 0, 0],      # 起点 (全是手腕 0)
    [4, 8, 12, 16, 20]    # 终点 (五个指尖)
]

TARGET_JOINT_NAMES = [
    "thumb_cmc_roll", "thumb_cmc_yaw", "thumb_cmc_pitch",
    "index_mcp_roll", "index_mcp_pitch",
    "middle_mcp_pitch", 
    "ring_mcp_roll", "ring_mcp_pitch",
    "pinky_mcp_roll", "pinky_mcp_pitch"
]

RETARGETING_PARAMS = {"low_pass_alpha": 0.2, "norm_delta": 1e-3}
SERVER_ADDR = ("127.0.0.1", 6000)
OPERATOR2MANO_RIGHT = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])

MIRROR_LEFT_TO_RIGHT = True
THUMB_ROTATION_EULER = [0, 0, 180] 
THUMB_OFFSET_VEC = [0.02, 0.0, 0.0] 

class VectorHandController:
    def __init__(self):
        print("🚀 启动手部控制器 (Vector 模式)...")
        
        config_dict = {
            "type": "vector",
            "urdf_path": HAND_URDF,
            "target_joint_names": TARGET_JOINT_NAMES,
            "target_origin_link_names": TARGET_ORIGIN_LINKS,
            "target_task_link_names": TARGET_TASK_LINKS,
            "target_link_human_indices": VECTOR_INDICES, # 使用修复后的列表
            "scaling_factor": 1.0, 
            "huber_delta": 2e-2,
            "normal_delta": RETARGETING_PARAMS["norm_delta"], 
            "low_pass_alpha": RETARGETING_PARAMS["low_pass_alpha"] 
        }
        self.retargeting = RetargetingConfig.from_dict(config_dict).build()
        self._inject_mimic_adaptor()
        
        self.thumb_rot = R.from_euler('xyz', THUMB_ROTATION_EULER, degrees=True).as_matrix()
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 5006)) 
        self.sock.setblocking(False)

        self.full_joint_names = self._get_full_joints()

    def _inject_mimic_adaptor(self):
        mimic_rules = [
            ("thumb_cmc_pitch", "thumb_mcp", 1.3898, 0), ("thumb_cmc_pitch", "thumb_ip", 1.508, 0),
            ("index_mcp_pitch", "index_pip", 1.3, 0), ("index_mcp_pitch", "index_dip", 0.4616, 0),
            ("middle_mcp_pitch", "middle_pip", 1.2462, 0), ("middle_mcp_pitch", "middle_dip", 0.4616, 0),
            ("ring_mcp_pitch", "ring_pip", 1.2462, 0), ("ring_mcp_pitch", "ring_dip", 0.4616, 0),
            ("pinky_mcp_pitch", "pinky_pip", 1.2462, 0), ("pinky_mcp_pitch", "pinky_dip", 0.4616, 0),
        ]
        source, mimic, mul, off = zip(*mimic_rules)
        adaptor = MimicJointKinematicAdaptor(
            self.retargeting.optimizer.robot, TARGET_JOINT_NAMES, list(source), list(mimic), list(mul), list(off)
        )
        self.retargeting.optimizer.set_kinematic_adaptor(adaptor)

    def _get_full_joints(self):
        return [
            "thumb_cmc_roll", "thumb_cmc_yaw", "thumb_cmc_pitch", "thumb_mcp", "thumb_ip",
            "index_mcp_roll", "index_mcp_pitch", "index_pip", "index_dip",
            "middle_mcp_pitch", "middle_pip", "middle_dip",
            "ring_mcp_roll", "ring_mcp_pitch", "ring_pip", "ring_dip",
            "pinky_mcp_roll", "pinky_mcp_pitch", "pinky_pip", "pinky_dip"
        ]
        
    def expand_to_full(self, active_qpos):
        joints = dict(zip(TARGET_JOINT_NAMES, active_qpos))
        d = joints.get("thumb_cmc_pitch", 0.0)
        joints["thumb_mcp"], joints["thumb_ip"] = d*1.3898, d*1.508
        for name, factor in [("index", 1.3), ("middle", 1.2462), ("ring", 1.2462), ("pinky", 1.2462)]:
            d = joints.get(f"{name}_mcp_pitch", 0.0)
            joints[f"{name}_pip"], joints[f"{name}_dip"] = d*factor, d*0.4616
        return joints

    def compute_canonical_frame(self, kp):
        wrist, index_mcp, middle_mcp = kp[0], kp[5], kp[9]
        vec_palm = middle_mcp - wrist
        vec_side = index_mcp - wrist
        y_axis = vec_palm / np.linalg.norm(vec_palm)
        z_axis = np.cross(vec_side, y_axis)
        z_axis /= np.linalg.norm(z_axis)
        x_axis = np.cross(y_axis, z_axis)
        return np.stack([x_axis, y_axis, z_axis], axis=1)

    def run(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
                kp = np.array(json.loads(data.decode())["hand_keypoints_21"])
            except: time.sleep(0.001); continue

            if MIRROR_LEFT_TO_RIGHT: kp[:, 0] = -kp[:, 0]
            rot_mat = self.compute_canonical_frame(kp)
            kp_aligned = (kp - kp[0]) @ rot_mat 
            
            vectors = kp_aligned[ [4, 8, 12, 16, 20] ] 
            vectors = vectors @ OPERATOR2MANO_RIGHT.T
            
            vectors[0] = vectors[0] @ self.thumb_rot.T
            vectors[0] += THUMB_OFFSET_VEC 

            retarget_qpos = self.retargeting.retarget(vectors)
            
            full_joints = self.expand_to_full(retarget_qpos[self.retargeting.optimizer.idx_pin2target])
            packet = {"type": "hand", "joints": full_joints}
            self.sock.sendto(json.dumps(packet).encode(), SERVER_ADDR)

if __name__ == "__main__":
    VectorHandController().run()