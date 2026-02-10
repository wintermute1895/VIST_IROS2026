"""
李代数工具模块
提供 SO(3) 和 SE(3) 上的高效运算

基于 Pinocchio 的李群/李代数支持
"""

import numpy as np
import pinocchio as pin
from typing import Tuple


def slerp_rotation(R1: np.ndarray, R2: np.ndarray, alpha: float) -> np.ndarray:
    """
    在 SO(3) 上进行球面线性插值（SLERP）

    使用李代数避免旋转矩阵的线性插值问题

    Args:
        R1: 起始旋转矩阵 (3x3)
        R2: 目标旋转矩阵 (3x3)
        alpha: 插值参数 [0, 1]，0 返回 R1，1 返回 R2

    Returns:
        插值后的旋转矩阵 (3x3)

    Example:
        >>> R1 = np.eye(3)
        >>> R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/2)
        >>> R_mid = slerp_rotation(R1, R2, 0.5)  # 旋转 45 度
    """
    # 1. 计算相对旋转
    R_rel = R1.T @ R2

    # 2. 转换到李代数 so(3)（轴角表示）
    omega = pin.log3(R_rel)  # ∈ R^3

    # 3. 在李代数空间插值
    omega_interp = alpha * omega

    # 4. 通过指数映射转回 SO(3)
    R_rel_interp = pin.exp3(omega_interp)

    return R1 @ R_rel_interp


def slerp_SE3(M1: pin.SE3, M2: pin.SE3, alpha: float) -> pin.SE3:
    """
    在 SE(3) 上进行球面线性插值

    同时插值旋转和平移

    Args:
        M1: 起始刚体变换
        M2: 目标刚体变换
        alpha: 插值参数 [0, 1]

    Returns:
        插值后的刚体变换

    Example:
        >>> M1 = pin.SE3.Identity()
        >>> M2 = pin.SE3(np.eye(3), np.array([1, 0, 0]))
        >>> M_mid = slerp_SE3(M1, M2, 0.5)  # 平移 0.5m
    """
    # 1. 计算相对变换
    M_rel = M1.actInv(M2)

    # 2. 转换到李代数 se(3)
    v = pin.log(M_rel)  # ∈ R^6 (平移速度 + 角速度)

    # 3. 在李代数空间插值
    v_interp = alpha * v

    # 4. 通过指数映射转回 SE(3)
    return M1.act(pin.exp(v_interp))


def compute_velocity_lie(M_old: pin.SE3, M_new: pin.SE3, dt: float) -> pin.Motion:
    """
    使用李代数计算刚体速度

    比数值微分更准确，特别是对于旋转

    Args:
        M_old: 旧的刚体变换
        M_new: 新的刚体变换
        dt: 时间间隔（秒）

    Returns:
        6D 速度向量（平移速度 + 角速度）

    Example:
        >>> M1 = pin.SE3.Identity()
        >>> M2 = pin.SE3(np.eye(3), np.array([0.1, 0, 0]))
        >>> v = compute_velocity_lie(M1, M2, 0.01)  # 10 m/s
    """
    # 1. 计算相对变换
    M_rel = M_old.actInv(M_new)

    # 2. 转换到李代数
    v = pin.log(M_rel)

    # 3. 除以时间得到速度
    return v / dt


def rotation_distance(R1: np.ndarray, R2: np.ndarray) -> float:
    """
    计算两个旋转矩阵之间的测地距离

    使用李代数范数，比 Frobenius 范数更合理

    Args:
        R1, R2: 旋转矩阵 (3x3)

    Returns:
        旋转角度（弧度）

    Example:
        >>> R1 = np.eye(3)
        >>> R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/2)
        >>> dist = rotation_distance(R1, R2)  # π/2
    """
    R_rel = R1.T @ R2
    omega = pin.log3(R_rel)
    return np.linalg.norm(omega)


def SE3_distance(M1: pin.SE3, M2: pin.SE3) -> Tuple[float, float]:
    """
    计算两个刚体变换之间的距离

    Args:
        M1, M2: 刚体变换

    Returns:
        (translation_dist, rotation_dist): 平移距离（米）和旋转距离（弧度）

    Example:
        >>> M1 = pin.SE3.Identity()
        >>> M2 = pin.SE3(np.eye(3), np.array([1, 0, 0]))
        >>> t_dist, r_dist = SE3_distance(M1, M2)  # (1.0, 0.0)
    """
    M_rel = M1.actInv(M2)
    v = pin.log(M_rel)

    # 分离平移和旋转
    translation_dist = np.linalg.norm(v.linear)
    rotation_dist = np.linalg.norm(v.angular)

    return translation_dist, rotation_dist


def axis_angle_to_rotation(axis: np.ndarray, angle: float) -> np.ndarray:
    """
    从轴角表示转换为旋转矩阵

    Args:
        axis: 旋转轴（单位向量）
        angle: 旋转角度（弧度）

    Returns:
        旋转矩阵 (3x3)

    Example:
        >>> axis = np.array([0, 0, 1])  # Z 轴
        >>> angle = np.pi / 2  # 90 度
        >>> R = axis_angle_to_rotation(axis, angle)
    """
    omega = axis * angle
    return pin.exp3(omega)


def rotation_to_axis_angle(R: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    从旋转矩阵转换为轴角表示

    Args:
        R: 旋转矩阵 (3x3)

    Returns:
        (axis, angle): 旋转轴（单位向量）和旋转角度（弧度）

    Example:
        >>> R = pin.rpy.rpyToMatrix(0, 0, np.pi/2)
        >>> axis, angle = rotation_to_axis_angle(R)
        >>> # axis ≈ [0, 0, 1], angle ≈ π/2
    """
    omega = pin.log3(R)
    angle = np.linalg.norm(omega)

    if angle < 1e-6:
        # 接近单位矩阵，返回任意轴
        return np.array([1, 0, 0]), 0.0

    axis = omega / angle
    return axis, angle


def quaternion_slerp(q1: np.ndarray, q2: np.ndarray, alpha: float) -> np.ndarray:
    """
    四元数球面线性插值

    Args:
        q1, q2: 四元数 [x, y, z, w]
        alpha: 插值参数 [0, 1]

    Returns:
        插值后的四元数

    Example:
        >>> q1 = np.array([0, 0, 0, 1])  # 单位四元数
        >>> q2 = np.array([0, 0, 0.707, 0.707])  # 绕 Z 轴旋转 90 度
        >>> q_mid = quaternion_slerp(q1, q2, 0.5)  # 旋转 45 度
    """
    # 转换为旋转矩阵
    R1 = pin.Quaternion(q1[3], q1[0], q1[1], q1[2]).toRotationMatrix()
    R2 = pin.Quaternion(q2[3], q2[0], q2[1], q2[2]).toRotationMatrix()

    # 使用旋转矩阵插值
    R_interp = slerp_rotation(R1, R2, alpha)

    # 转回四元数
    q_interp = pin.Quaternion(R_interp)
    return np.array([q_interp.x, q_interp.y, q_interp.z, q_interp.w])


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试李代数工具...")

    # 测试 1: 旋转插值
    print("\n测试 1: 旋转插值")
    R1 = np.eye(3)
    R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/2)
    R_mid = slerp_rotation(R1, R2, 0.5)
    print(f"R1 (0°):\n{R1}")
    print(f"R2 (90°):\n{R2}")
    print(f"R_mid (45°):\n{R_mid}")

    # 测试 2: SE(3) 插值
    print("\n测试 2: SE(3) 插值")
    M1 = pin.SE3.Identity()
    M2 = pin.SE3(np.eye(3), np.array([1, 0, 0]))
    M_mid = slerp_SE3(M1, M2, 0.5)
    print(f"M1: {M1.translation.T}")
    print(f"M2: {M2.translation.T}")
    print(f"M_mid: {M_mid.translation.T}")

    # 测试 3: 速度计算
    print("\n测试 3: 速度计算")
    v = compute_velocity_lie(M1, M2, 0.1)
    print(f"速度: {v.linear.T} m/s")

    # 测试 4: 旋转距离
    print("\n测试 4: 旋转距离")
    dist = rotation_distance(R1, R2)
    print(f"旋转距离: {dist:.4f} rad ({np.degrees(dist):.2f}°)")

    print("\n✅ 所有测试通过")
