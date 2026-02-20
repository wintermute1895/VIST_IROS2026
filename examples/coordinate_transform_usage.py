#!/usr/bin/env python3
"""
坐标变换管理器使用示例

演示如何使用CoordinateTransformManager进行坐标系变换
"""

import numpy as np
from src.perception.coordinate_transform_manager import CoordinateTransformManager
from src.config.config_loader import VISTConfig

# ==========================================
# 示例1：基础初始化
# ==========================================
print("=" * 60)
print("示例1：初始化坐标变换管理器")
print("=" * 60)

# 加载配置
config = VISTConfig("config/system_config.yaml")

# 初始化坐标变换管理器
coord_mgr = CoordinateTransformManager(config=config)

# 检查标定状态
print(f"\n标定状态:")
print(f"  手内相机: {coord_mgr.is_hand_camera_calibrated()}")
print(f"  头顶相机: {coord_mgr.is_head_camera_calibrated()}")

# ==========================================
# 示例2：手内相机坐标变换
# ==========================================
print("\n" + "=" * 60)
print("示例2：手内相机检测到的目标 → 基座坐标系")
print("=" * 60)

# 假设手内相机检测到目标在相机坐标系下的位置
target_in_hand_cam = np.array([0.1, 0.05, 0.3])  # [x, y, z] 米
print(f"\n目标在手内相机坐标系: {target_in_hand_cam}")

# 假设当前机器人位姿（从FK或机器人API获取）
T_base_to_end = np.array([
    [1, 0, 0, 0.3],
    [0, 1, 0, 0.2],
    [0, 0, 1, 0.4],
    [0, 0, 0, 1]
])
print(f"机器人当前位姿（基座→末端）:\n{T_base_to_end}")

# 坐标变换
if coord_mgr.is_hand_camera_calibrated():
    target_in_base = coord_mgr.hand_camera_to_base(target_in_hand_cam, T_base_to_end)
    print(f"\n目标在基座坐标系: {target_in_base}")
    print(f"  → 可以直接传给VIST控制器: vist_filter.solve(target_pos={target_in_base})")
else:
    print("\n⚠️ 手内相机未标定，无法进行坐标变换")

# ==========================================
# 示例3：头顶相机坐标变换
# ==========================================
print("\n" + "=" * 60)
print("示例3：头顶相机检测到的目标 → 基座坐标系")
print("=" * 60)

# 假设头顶相机检测到目标在相机坐标系下的位置
target_in_head_cam = np.array([0.2, 0.1, 0.5])  # [x, y, z] 米
print(f"\n目标在头顶相机坐标系: {target_in_head_cam}")

# 坐标变换（头顶相机固定，不需要机器人位姿）
if coord_mgr.is_head_camera_calibrated():
    target_in_base = coord_mgr.head_camera_to_base(target_in_head_cam)
    print(f"目标在基座坐标系: {target_in_base}")
else:
    print("⚠️ 头顶相机未标定，无法进行坐标变换")

# ==========================================
# 示例4：双相机融合
# ==========================================
print("\n" + "=" * 60)
print("示例4：融合双相机观测")
print("=" * 60)

# 两个相机都检测到目标
target_hand = np.array([0.1, 0.05, 0.3])
target_head = np.array([0.2, 0.1, 0.5])

# 置信度（可以根据检测质量动态调整）
confidence_hand = 0.9  # 手内相机更近，置信度更高
confidence_head = 0.7

# 融合观测
fused_target = coord_mgr.fuse_dual_camera_observations(
    point_hand_cam=target_hand,
    point_head_cam=target_head,
    T_base_to_end=T_base_to_end,
    confidence_hand=confidence_hand,
    confidence_head=confidence_head
)

if fused_target is not None:
    print(f"\n融合后的目标位置: {fused_target}")
    print(f"  权重: 手内={confidence_hand}, 头顶={confidence_head}")
else:
    print("\n⚠️ 无法融合观测（两个相机都未标定）")

# ==========================================
# 示例5：获取TCP位姿
# ==========================================
print("\n" + "=" * 60)
print("示例5：获取TCP（USB末端）在基座坐标系下的位姿")
print("=" * 60)

tcp_pos, tcp_quat = coord_mgr.get_tcp_pose_in_base(T_base_to_end)
print(f"\nTCP位置: {tcp_pos}")
print(f"TCP姿态（四元数）: {tcp_quat}")
print(f"  → 这是USB插头尖端的实际位置，考虑了TCP偏移")

# ==========================================
# 示例6：完整的视觉-控制流程
# ==========================================
print("\n" + "=" * 60)
print("示例6：完整的视觉-控制集成流程")
print("=" * 60)

print("""
完整流程：

1. 视觉检测（ArUco/ChArUco/深度学习）
   ↓
   target_in_camera = detect_target(image)

2. 坐标变换（CoordinateTransformManager）
   ↓
   target_in_base = coord_mgr.hand_camera_to_base(target_in_camera, robot_pose)

3. VIST控制（VISTKalmanFilter）
   ↓
   q_target = vist_filter.solve(target_pos=target_in_base)

4. 机器人执行
   ↓
   robot.move_joint(q_target)

关键点：
- 视觉模块只需要输出相机坐标系下的目标位置
- CoordinateTransformManager负责所有坐标变换
- VIST控制器接收基座坐标系下的目标位置
- 各模块完全解耦，可以独立测试和替换
""")

# ==========================================
# 示例7：无视觉的盲操作模式
# ==========================================
print("\n" + "=" * 60)
print("示例7：无视觉盲操作模式（今晚可以测试）")
print("=" * 60)

print("""
无需相机和标定，直接测试VIST核心：

# 手动设置目标位置（基座坐标系）
target_pos = np.array([0.3, 0.2, 0.1])  # 米

# 直接传给VIST
from src.core.vist_kalman_filter import VISTKalmanFilter
vist_filter = VISTKalmanFilter(...)
q_target = vist_filter.solve(target_pos=target_pos)

# 观察机器人是否被"吸引"到目标位置
# 感受流形约束和意图因子的效果
""")

print("\n" + "=" * 60)
print("示例完成！")
print("=" * 60)