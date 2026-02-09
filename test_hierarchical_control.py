#!/usr/bin/env python3
"""
测试分层控制的雅可比计算

目的：隔离测试新的分层控制函数，找出段错误的根源
"""
import os
import sys
import numpy as np
import pinocchio as pin

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from src.core.ik_solver import PinocchioIKSolver
from src.config import get_config

def test_frame_existence():
    """测试 URDF 中是否存在所需的 frame"""
    print("=" * 80)
    print("🔍 测试 1: 检查 URDF Frame 是否存在")
    print("=" * 80)

    config = get_config()
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 检查所需的 frame
    required_frames = [
        "Right_Shoulder_Pitch_Link",
        "Right_Elbow_Pitch_Link",
        "Right_Wrist_Roll_Link"
    ]

    print("\n📋 检查所需 Frame:")
    for frame_name in required_frames:
        exists = ik_solver.model.existFrame(frame_name)
        status = "✅" if exists else "❌"
        print(f"   {status} {frame_name}: {'存在' if exists else '不存在'}")

        if exists:
            frame_id = ik_solver.model.getFrameId(frame_name)
            print(f"      Frame ID: {frame_id}")

    # 列出所有可用的 frame
    print(f"\n📋 所有可用 Frame (共 {ik_solver.model.nframes} 个):")
    for i in range(ik_solver.model.nframes):
        frame = ik_solver.model.frames[i]
        print(f"   [{i:2d}] {frame.name}")

    return ik_solver

def test_jacobian_computation(ik_solver):
    """测试雅可比矩阵计算"""
    print("\n" + "=" * 80)
    print("🔍 测试 2: 雅可比矩阵计算")
    print("=" * 80)

    # 使用中性姿态
    q = pin.neutral(ik_solver.model)

    print(f"\n📊 模型信息:")
    print(f"   总关节数 (nq): {ik_solver.model.nq}")
    print(f"   总速度维度 (nv): {ik_solver.model.nv}")
    print(f"   受控关节索引: {ik_solver.controlled_indices}")

    # 正运动学
    pin.forwardKinematics(ik_solver.model, ik_solver.data, q)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)

    # 测试肘部 frame 的雅可比
    print("\n🧮 测试肘部 Frame 雅可比:")
    try:
        if ik_solver.model.existFrame("Right_Elbow_Pitch_Link"):
            elbow_frame_id = ik_solver.model.getFrameId("Right_Elbow_Pitch_Link")
            print(f"   肘部 Frame ID: {elbow_frame_id}")

            J_elbow = pin.computeFrameJacobian(
                ik_solver.model,
                ik_solver.data,
                q,
                elbow_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            print(f"   ✅ 雅可比矩阵形状: {J_elbow.shape}")
            print(f"   前3行（位置）形状: {J_elbow[:3, :].shape}")

            # 测试索引肩部关节列
            shoulder_indices = ik_solver.controlled_indices[:3]
            print(f"   肩部关节索引: {shoulder_indices}")
            print(f"   最大索引: {max(shoulder_indices)}, 雅可比列数: {J_elbow.shape[1]}")

            if max(shoulder_indices) < J_elbow.shape[1]:
                J_shoulder = J_elbow[:3, shoulder_indices]
                print(f"   ✅ 肩部雅可比形状: {J_shoulder.shape}")
            else:
                print(f"   ❌ 索引超出范围!")
        else:
            print("   ❌ Right_Elbow_Pitch_Link 不存在")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()

    # 测试末端执行器的雅可比
    print("\n🧮 测试末端执行器雅可比:")
    try:
        J_ee = pin.computeFrameJacobian(
            ik_solver.model,
            ik_solver.data,
            q,
            ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        print(f"   ✅ 雅可比矩阵形状: {J_ee.shape}")

        # 测试索引腕部关节列
        wrist_indices = ik_solver.controlled_indices[4:7]
        print(f"   腕部关节索引: {wrist_indices}")
        print(f"   最大索引: {max(wrist_indices)}, 雅可比列数: {J_ee.shape[1]}")

        if max(wrist_indices) < J_ee.shape[1]:
            J_wrist = J_ee[:3, wrist_indices]
            print(f"   ✅ 腕部雅可比形状: {J_wrist.shape}")
        else:
            print(f"   ❌ 索引超出范围!")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()

def test_hierarchical_ik():
    """测试完整的分层 IK 流程"""
    print("\n" + "=" * 80)
    print("🔍 测试 3: 完整分层 IK 流程")
    print("=" * 80)

    try:
        from src.core.vist_kalman_filter import VISTKalmanFilter
        from src.core.geometric_arm_solver import GeometricArmSolver

        config = get_config()
        urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

        ik_solver = PinocchioIKSolver(
            urdf_path=urdf_path,
            end_effector_frame="Right_Wrist_Roll_Link"
        )

        # 初始化几何求解器（如果启用）
        geometric_solver = None
        if config.vist_geometric_solver_enabled:
            geometric_solver = GeometricArmSolver(
                model=ik_solver.model,
                data=ik_solver.data,
                controlled_joints=ik_solver.controlled_indices,
                ee_frame_id=ik_solver.ee_frame_id,
                config=config
            )

        # 初始化 VIST 滤波器
        vist_filter = VISTKalmanFilter(
            ik_solver,
            config,
            geometric_solver=geometric_solver
        )

        print("\n✅ VIST 滤波器初始化成功")

        # 测试一次求解
        print("\n🧪 测试单次求解:")
        shoulder_pos = np.array(config.robot_shoulder_position)
        target_pos = shoulder_pos + np.array([0.2, -0.1, -0.3])
        target_quat = np.array([0, 0, 0, 1])

        print(f"   目标位置: {target_pos}")

        q_init = pin.neutral(ik_solver.model)
        q_init_controlled = q_init[ik_solver.controlled_indices]

        q_solution, success, error = vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            q_init=q_init_controlled,
            elbow_pos=shoulder_pos + np.array([0.15, -0.05, -0.15]),
            shoulder_pos=shoulder_pos
        )

        print(f"   求解结果: {'✅ 成功' if success else '❌ 失败'}")
        print(f"   误差: {error:.6f}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🧪 分层控制诊断测试\n")

    # 测试 1: Frame 存在性
    ik_solver = test_frame_existence()

    # 测试 2: 雅可比计算
    test_jacobian_computation(ik_solver)

    # 测试 3: 完整流程
    test_hierarchical_ik()

    print("\n" + "=" * 80)
    print("✅ 诊断测试完成")
    print("=" * 80)
