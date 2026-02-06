"""
坐标转换工具：视觉坐标系 → 机器人基座坐标系

使用方法：
在 motion_mapper.py 中添加此转换矩阵
"""
import numpy as np


def get_vision_to_robot_transform():
    """
    获取从视觉坐标系到机器人基座坐标系的转换矩阵

    视觉坐标系（Shoulder Frame）：
    - X: 向上
    - Y: 向右
    - Z: 向前
    - 原点：肩部

    机器人基座坐标系（body_base_link）：
    - X: 向前
    - Y: 向左
    - Z: 向上
    - 原点：body_base_link

    Returns:
        R: 3x3 旋转矩阵
    """
    R = np.array([
        [0,  0,  1],  # X_robot = Z_vision (向前 = 视觉向前，同向)
        [0, -1,  0],  # Y_robot = -Y_vision (向左 = -视觉向右)
        [1,  0,  0]   # Z_robot = X_vision (向上)
    ], dtype=np.float64)
    return R


def vision_to_robot_coords(P_vision, T_shoulder_to_base):
    """
    将视觉坐标系的点转换到机器人基座坐标系

    Args:
        P_vision: 视觉坐标系中的点 [x, y, z]
        T_shoulder_to_base: 肩部在机器人基座坐标系中的位置 [x, y, z]

    Returns:
        P_robot: 机器人基座坐标系中的点 [x, y, z]
    """
    R = get_vision_to_robot_transform()
    P_vision = np.array(P_vision, dtype=np.float64)
    T_shoulder_to_base = np.array(T_shoulder_to_base, dtype=np.float64)
    P_robot = R @ P_vision + T_shoulder_to_base
    return P_robot


def test_transform():
    """测试坐标转换"""
    print("=" * 60)
    print("坐标转换测试")
    print("=" * 60)

    R = get_vision_to_robot_transform()
    T_shoulder = np.array([0.0, -0.096, 1.217])  # 右臂肩部位置（从URDF提取）

    print("\n旋转矩阵 R:")
    print(R)

    print("\n肩部位置 T_shoulder:")
    print(T_shoulder)

    # 测试用例
    test_cases = [
        ("向前伸手", np.array([0.0, 0.0, 0.5]), "X_robot 应该增大"),
        ("向右移动", np.array([0.0, 0.3, 0.0]), "Y_robot 应该减小"),
        ("向上抬手", np.array([0.4, 0.0, 0.0]), "Z_robot 应该增大"),
    ]

    print("\n" + "=" * 60)
    print("测试用例")
    print("=" * 60)

    for name, P_vision, expected in test_cases:
        P_robot = vision_to_robot_coords(P_vision, T_shoulder)
        print(f"\n{name}:")
        print(f"  视觉坐标: {P_vision}")
        print(f"  机器人坐标: {P_robot}")
        print(f"  预期: {expected}")

        # 验证
        if name == "向前伸手":
            assert P_robot[0] > T_shoulder[0], "X_robot 应该增大"
            print("  ✓ 验证通过")
        elif name == "向右移动":
            assert P_robot[1] < T_shoulder[1], "Y_robot 应该减小"
            print("  ✓ 验证通过")
        elif name == "向上抬手":
            assert P_robot[2] > T_shoulder[2], "Z_robot 应该增大"
            print("  ✓ 验证通过")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_transform()
