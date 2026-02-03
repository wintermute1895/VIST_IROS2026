#!/usr/bin/env python3
"""
快速测试脚本：验证坐标轴可视化是否正确
"""
import numpy as np
from scipy.spatial.transform import Rotation

# 测试几个典型的旋转矩阵
test_cases = [
    ("单位矩阵（无旋转）", np.eye(3)),
    ("绕Z轴旋转90度", Rotation.from_euler('z', 90, degrees=True).as_matrix()),
    ("绕Y轴旋转90度", Rotation.from_euler('y', 90, degrees=True).as_matrix()),
    ("绕X轴旋转90度", Rotation.from_euler('x', 90, degrees=True).as_matrix()),
]

print("🔍 测试旋转矩阵的正交性和轴向量\n")

for name, R in test_cases:
    print(f"测试: {name}")
    print(f"旋转矩阵:\n{R}")

    # 提取轴向量
    x_axis = R[:, 0]
    y_axis = R[:, 1]
    z_axis = R[:, 2]

    print(f"X轴: {x_axis}")
    print(f"Y轴: {y_axis}")
    print(f"Z轴: {z_axis}")

    # 检查正交性
    dot_xy = np.dot(x_axis, y_axis)
    dot_xz = np.dot(x_axis, z_axis)
    dot_yz = np.dot(y_axis, z_axis)

    print(f"X·Y = {dot_xy:.6f} (应该≈0)")
    print(f"X·Z = {dot_xz:.6f} (应该≈0)")
    print(f"Y·Z = {dot_yz:.6f} (应该≈0)")

    # 检查模长
    print(f"|X| = {np.linalg.norm(x_axis):.6f} (应该≈1)")
    print(f"|Y| = {np.linalg.norm(y_axis):.6f} (应该≈1)")
    print(f"|Z| = {np.linalg.norm(z_axis):.6f} (应该≈1)")

    # 检查行列式（应该是1）
    det = np.linalg.det(R)
    print(f"det(R) = {det:.6f} (应该≈1)")

    print("-" * 60)
    print()
