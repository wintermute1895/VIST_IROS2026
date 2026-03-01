# src/utils/transformations.py

import numpy as np
from scipy.spatial.transform import Rotation as R

def to_homogeneous(pos, quat):
    """将位置和四元数转换为 4x4 齐次变换矩阵"""
    T = np.eye(4)
    T[:3, 3] = pos
    r = R.from_quat(quat) # expected [x, y, z, w]
    T[:3, :3] = r.as_matrix()
    return T

def from_homogeneous(T):
    """从 4x4 矩阵提取位置和四元数"""
    pos = T[:3, 3]
    quat = R.from_matrix(T[:3, :3]).as_quat()
    return pos, quat

def pose_diff(pose1, pose2):
    """计算两个位姿之间的误差（位置距离 + 角度距离）"""
    # 这里的 pose 是 [x,y,z, qx,qy,qz,qw]
    pos_err = np.linalg.norm(pose1[:3] - pose2[:3])
    
    r1 = R.from_quat(pose1[3:])
    r2 = R.from_quat(pose2[3:])
    # 计算旋转差的角度
    rel = r1.inv() * r2
    rot_err = rel.magnitude()
    
    return pos_err, rot_err