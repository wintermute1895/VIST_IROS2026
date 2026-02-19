#!/usr/bin/env python3
"""
查看URDF中定义的零位姿态

这个脚本会加载URDF并显示所有关节在0角度时的姿态
"""
import numpy as np
import pinocchio as pin
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def show_zero_pose():
    """显示URDF零位姿态"""

    # 加载URDF
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    # 处理URDF路径
    with open(urdf_path, 'r') as f:
        urdf_content = f.read()

    # 替换package路径
    urdf_content = urdf_content.replace(
        'package://my_robot/',
        os.path.join(project_root, 'config') + '/'
    )

    # 保存临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False) as tmp:
        tmp.write(urdf_content)
        tmp_urdf_path = tmp.name

    try:
        # 加载模型
        model = pin.buildModelFromUrdf(tmp_urdf_path)
        data = model.createData()

        print("="*80)
        print("URDF零位姿态分析")
        print("="*80)

        # 设置所有关节为0
        q_zero = pin.neutral(model)

        print(f"\n零位关节角度（所有关节 = 0）:")
        print(f"  q_zero = {q_zero}")

        # 正运动学
        pin.forwardKinematics(model, data, q_zero)
        pin.updateFramePlacements(model, data)

        # 查找右臂关节
        right_arm_joints = [
            'Right_Shoulder_Pitch_Joint',
            'Right_Shoulder_Roll_Joint',
            'Right_Shoulder_Yaw_Joint',
            'Right_Elbow_Pitch_Joint',
            'Right_Wrist_Yaw_Joint',
            'Right_Wrist_Pitch_Joint',
            'Right_Wrist_Roll_Joint'
        ]

        print(f"\n右臂关节信息:")
        print("="*80)

        for joint_name in right_arm_joints:
            if model.existJointName(joint_name):
                joint_id = model.getJointId(joint_name)
                joint = model.joints[joint_id]

                print(f"\n{joint_name}:")
                print(f"  关节ID: {joint_id}")
                print(f"  关节类型: {joint.shortname()}")

                # 获取关节的placement
                placement = data.oMi[joint_id]
                pos = placement.translation
                rot = placement.rotation

                print(f"  零位位置: [{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]")

                # 转换为欧拉角
                from scipy.spatial.transform import Rotation
                euler = Rotation.from_matrix(rot).as_euler('xyz', degrees=True)
                print(f"  零位姿态(欧拉角): [{euler[0]:.2f}°, {euler[1]:.2f}°, {euler[2]:.2f}°]")

        # 查找末端执行器
        ee_frame_name = "Right_Wrist_Roll_Link"
        if model.existFrame(ee_frame_name):
            ee_frame_id = model.getFrameId(ee_frame_name)
            ee_placement = data.oMf[ee_frame_id]
            ee_pos = ee_placement.translation

            print(f"\n末端执行器（{ee_frame_name}）:")
            print(f"  零位位置: [{ee_pos[0]:.4f}, {ee_pos[1]:.4f}, {ee_pos[2]:.4f}]")

        # 测试不同的肘部角度
        print(f"\n" + "="*80)
        print("测试不同肘部角度的末端位置")
        print("="*80)

        # 找到肘部关节的索引
        elbow_joint_id = model.getJointId('Right_Elbow_Pitch_Joint')
        # 获取速度索引
        elbow_v_idx = model.joints[elbow_joint_id].idx_v

        test_angles = [0, 45, 90, 135, 180, -45, -90]

        for angle_deg in test_angles:
            angle_rad = np.radians(angle_deg)
            q_test = q_zero.copy()
            q_test[elbow_v_idx] = angle_rad

            pin.forwardKinematics(model, data, q_test)
            pin.updateFramePlacements(model, data)

            ee_placement = data.oMf[ee_frame_id]
            ee_pos = ee_placement.translation

            print(f"  肘部角度 = {angle_deg:4.0f}° → 末端位置: [{ee_pos[0]:.4f}, {ee_pos[1]:.4f}, {ee_pos[2]:.4f}]")

    finally:
        # 清理临时文件
        os.unlink(tmp_urdf_path)

if __name__ == "__main__":
    show_zero_pose()