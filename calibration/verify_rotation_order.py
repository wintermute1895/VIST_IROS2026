#!/usr/bin/env python3
"""
验证 LBot SDK 的欧拉角旋转顺序

这个脚本用于验证 LBot SDK 返回的欧拉角使用的是什么旋转顺序。
"""

import numpy as np
from scipy.spatial.transform import Rotation as R


def test_rotation_conventions():
    """
    测试不同的旋转约定

    在机器人学中，roll-pitch-yaw 有两种常见的解释：
    1. XYZ 内旋（intrinsic）：先绕 X 轴，再绕旋转后的 Y 轴，最后绕旋转后的 Z 轴
    2. ZYX 外旋（extrinsic）：先绕固定的 Z 轴，再绕固定的 Y 轴，最后绕固定的 X 轴

    这两种方式在数学上是等价的（ZYX 外旋 = xyz 内旋）
    """

    print("=" * 70)
    print("欧拉角旋转顺序验证")
    print("=" * 70)

    # 测试角度（弧度）
    roll = 0.1   # 绕 X 轴
    pitch = 0.2  # 绕 Y 轴
    yaw = 0.3    # 绕 Z 轴

    print(f"\n测试角度（弧度）:")
    print(f"  roll  (绕 X 轴) = {roll:.4f} rad = {np.rad2deg(roll):.2f}°")
    print(f"  pitch (绕 Y 轴) = {pitch:.4f} rad = {np.rad2deg(pitch):.2f}°")
    print(f"  yaw   (绕 Z 轴) = {yaw:.4f} rad = {np.rad2deg(yaw):.2f}°")

    # 方法 1: XYZ 内旋（小写）
    print("\n" + "-" * 70)
    print("方法 1: XYZ 内旋 (intrinsic) - scipy.from_euler('xyz', ...)")
    print("-" * 70)
    rot_xyz_intrinsic = R.from_euler('xyz', [roll, pitch, yaw], degrees=False)
    matrix_xyz_intrinsic = rot_xyz_intrinsic.as_matrix()
    print("旋转矩阵:")
    print(matrix_xyz_intrinsic)

    # 方法 2: ZYX 外旋（大写）
    print("\n" + "-" * 70)
    print("方法 2: ZYX 外旋 (extrinsic) - scipy.from_euler('ZYX', ...)")
    print("-" * 70)
    # 注意：ZYX 外旋时，角度顺序是 [yaw, pitch, roll]
    rot_zyx_extrinsic = R.from_euler('ZYX', [yaw, pitch, roll], degrees=False)
    matrix_zyx_extrinsic = rot_zyx_extrinsic.as_matrix()
    print("旋转矩阵:")
    print(matrix_zyx_extrinsic)

    # 验证两种方法是否等价
    print("\n" + "-" * 70)
    print("验证: XYZ 内旋 vs ZYX 外旋")
    print("-" * 70)
    diff = np.max(np.abs(matrix_xyz_intrinsic - matrix_zyx_extrinsic))
    print(f"矩阵差异（最大绝对值）: {diff:.2e}")
    if diff < 1e-10:
        print("✓ 两种方法等价（差异 < 1e-10）")
    else:
        print("✗ 两种方法不等价")

    # 方法 3: XYZ 外旋（大写）- 这是不同的
    print("\n" + "-" * 70)
    print("方法 3: XYZ 外旋 (extrinsic) - scipy.from_euler('XYZ', ...)")
    print("-" * 70)
    rot_xyz_extrinsic = R.from_euler('XYZ', [roll, pitch, yaw], degrees=False)
    matrix_xyz_extrinsic = rot_xyz_extrinsic.as_matrix()
    print("旋转矩阵:")
    print(matrix_xyz_extrinsic)

    diff_with_intrinsic = np.max(np.abs(matrix_xyz_intrinsic - matrix_xyz_extrinsic))
    print(f"\n与 XYZ 内旋的差异: {diff_with_intrinsic:.2e}")
    if diff_with_intrinsic < 1e-10:
        print("✓ 与 XYZ 内旋相同")
    else:
        print("✗ 与 XYZ 内旋不同")

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print("""
在机器人学中，roll-pitch-yaw 通常指：
- roll:  绕 X 轴旋转
- pitch: 绕 Y 轴旋转
- yaw:   绕 Z 轴旋转

常见的两种等价表示：
1. XYZ 内旋 (intrinsic): scipy.from_euler('xyz', [roll, pitch, yaw])
2. ZYX 外旋 (extrinsic): scipy.from_euler('ZYX', [yaw, pitch, roll])

根据 LBot SDK 的文档注释：
- euler: 机械臂末端目标欧拉角（roll, pitch, yaw，单位：弧度）
- LbotEuler.x = roll, LbotEuler.y = pitch, LbotEuler.z = yaw

推荐使用: scipy.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)
    """)


def test_with_simple_rotations():
    """
    使用简单的旋转测试，帮助理解旋转顺序
    """
    print("\n" + "=" * 70)
    print("简单旋转测试")
    print("=" * 70)

    # 测试 1: 只绕 X 轴旋转 90 度
    print("\n测试 1: 只绕 X 轴旋转 90°")
    roll_90 = np.pi / 2
    rot = R.from_euler('xyz', [roll_90, 0, 0], degrees=False)
    print(f"输入: roll={np.rad2deg(roll_90):.0f}°, pitch=0°, yaw=0°")
    print("旋转矩阵:")
    print(rot.as_matrix())
    print("预期: Y 轴 → Z 轴, Z 轴 → -Y 轴")

    # 测试 2: 只绕 Y 轴旋转 90 度
    print("\n测试 2: 只绕 Y 轴旋转 90°")
    pitch_90 = np.pi / 2
    rot = R.from_euler('xyz', [0, pitch_90, 0], degrees=False)
    print(f"输入: roll=0°, pitch={np.rad2deg(pitch_90):.0f}°, yaw=0°")
    print("旋转矩阵:")
    print(rot.as_matrix())
    print("预期: X 轴 → -Z 轴, Z 轴 → X 轴")

    # 测试 3: 只绕 Z 轴旋转 90 度
    print("\n测试 3: 只绕 Z 轴旋转 90°")
    yaw_90 = np.pi / 2
    rot = R.from_euler('xyz', [0, 0, yaw_90], degrees=False)
    print(f"输入: roll=0°, pitch=0°, yaw={np.rad2deg(yaw_90):.0f}°")
    print("旋转矩阵:")
    print(rot.as_matrix())
    print("预期: X 轴 → Y 轴, Y 轴 → -X 轴")


if __name__ == "__main__":
    test_rotation_conventions()
    test_with_simple_rotations()

    print("\n" + "=" * 70)
    print("建议")
    print("=" * 70)
    print("""
基于 LBot SDK 的文档和机器人学的标准约定，建议使用：

    rotation = R.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)

这对应于 XYZ 内旋（intrinsic rotation），也等价于 ZYX 外旋。
这是机器人学中 roll-pitch-yaw 的标准解释。
    """)
