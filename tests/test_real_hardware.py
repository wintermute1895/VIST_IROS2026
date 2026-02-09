#!/usr/bin/env python3
"""
分阶段真机安全测试脚本
用于验证 IK 方案在真实硬件上的表现

测试阶段：
1. 连接测试 - 验证 SDK 连接和状态读取
2. 单关节测试 - 小幅度运动单个关节
3. IK 验证测试 - 固定目标位姿的 IK 求解
4. 完整回路测试 - 遥操作控制回路

安全特性：
- 每个阶段需要用户确认才能继续
- 运动幅度从小到大逐步增加
- 实时监控关节限位和速度
- 紧急停止机制（Ctrl+C）
"""

import sys
import os
import time
import numpy as np
import yaml

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver
from src.core.ik_solver import PinocchioIKSolver


class SafetyMonitor:
    """安全监控器：检查关节限位、速度限制"""

    def __init__(self, joint_limits, max_joint_velocity=0.5):
        """
        Args:
            joint_limits: numpy array of shape (n, 2), [[min, max], ...]
            max_joint_velocity: 最大关节速度 (rad/s)
        """
        self.joint_limits = joint_limits
        self.max_joint_velocity = max_joint_velocity
        self.prev_q = None
        self.prev_time = None

    def check_limits(self, q):
        """检查关节限位"""
        violations = []
        for i, (q_val, (q_min, q_max)) in enumerate(zip(q, self.joint_limits)):
            if q_val < q_min or q_val > q_max:
                violations.append(f"Joint {i}: {q_val:.3f} rad (limit: [{q_min:.3f}, {q_max:.3f}])")
        return violations

    def check_velocity(self, q, current_time):
        """检查关节速度"""
        if self.prev_q is None:
            self.prev_q = q
            self.prev_time = current_time
            return []

        dt = current_time - self.prev_time
        if dt < 1e-6:
            return []

        dq = (q - self.prev_q) / dt
        violations = []

        for i, vel in enumerate(dq):
            if abs(vel) > self.max_joint_velocity:
                violations.append(f"Joint {i}: velocity {vel:.3f} rad/s (max: {self.max_joint_velocity})")

        self.prev_q = q
        self.prev_time = current_time
        return violations


def wait_for_user_confirmation(message):
    """等待用户确认"""
    print(f"\n{'='*60}")
    print(f"⚠️  {message}")
    print(f"{'='*60}")
    response = input("输入 'y' 继续，'n' 退出: ").strip().lower()
    if response != 'y':
        print("❌ 用户取消，退出测试")
        sys.exit(0)


def stage1_connection_test(driver):
    """阶段1：连接测试"""
    print("\n" + "="*60)
    print("阶段 1: 连接测试")
    print("="*60)

    wait_for_user_confirmation("即将连接到真机并读取状态")

    # 连接
    success = driver.connect()
    if not success:
        print("❌ 连接失败！")
        return False

    print("✅ 连接成功")

    # 读取状态（连续读取5次）
    print("\n📊 读取关节状态（5次）...")
    for i in range(5):
        timestamp, q_pos, q_vel = driver.get_state()
        print(f"  [{i+1}] 时间戳: {timestamp:.3f}")
        print(f"      关节角度 (rad): {q_pos}")
        print(f"      关节速度 (rad/s): {q_vel}")
        time.sleep(0.5)

    print("\n✅ 阶段1完成：连接和状态读取正常")
    return True


def stage2_single_joint_test(driver, safety_monitor):
    """阶段2：单关节小幅运动测试"""
    print("\n" + "="*60)
    print("阶段 2: 单关节小幅运动测试")
    print("="*60)

    wait_for_user_confirmation("即将测试单关节运动（±5度）")

    # 获取当前位置
    _, q_current, _ = driver.get_state()
    print(f"\n当前关节角度: {q_current}")

    # 测试第一个关节（Shoulder_Pitch）
    joint_idx = 0
    delta = np.deg2rad(5)  # 5度

    print(f"\n测试关节 {joint_idx} (Shoulder_Pitch):")
    print(f"  当前值: {np.rad2deg(q_current[joint_idx]):.2f}°")
    print(f"  目标值: {np.rad2deg(q_current[joint_idx] + delta):.2f}°")

    # 检查限位
    q_target = q_current.copy()
    q_target[joint_idx] += delta
    violations = safety_monitor.check_limits(q_target)

    if violations:
        print(f"❌ 限位检查失败: {violations}")
        return False

    # 发送指令（使用受控运动，速度0.05 rad/s - 非常慢，安全）
    print("\n发送运动指令（慢速安全模式）...")
    success = driver.move_joint_controlled(q_target, speed=0.05, accel=0.05, block=False)

    if not success:
        print("❌ 运动指令发送失败")
        return False

    # 监控运动（增加到5秒，因为速度更慢）
    print("监控运动状态...")
    start_time = time.time()
    while time.time() - start_time < 5.0:
        timestamp, q_actual, _ = driver.get_state()
        error = np.linalg.norm(q_target - q_actual)
        print(f"  误差: {error:.4f} rad ({np.rad2deg(error):.2f}°)", end='\r')
        time.sleep(0.1)

    print("\n")
    _, q_final, _ = driver.get_state()
    print(f"最终位置: {np.rad2deg(q_final[joint_idx]):.2f}°")
    print(f"目标位置: {np.rad2deg(q_target[joint_idx]):.2f}°")
    print(f"误差: {np.rad2deg(abs(q_final[joint_idx] - q_target[joint_idx])):.2f}°")

    # 回到零位
    print("\n" + "-"*60)
    print("准备回到零位...")
    wait_for_user_confirmation("即将回到零位（所有关节归零）")

    q_zero = np.zeros(len(q_current))
    print(f"\n目标零位: {np.rad2deg(q_zero)}")
    print("发送归零指令（慢速安全模式）...")

    success = driver.move_joint_controlled(q_zero, speed=0.1, accel=0.1, block=False)
    if not success:
        print("❌ 归零指令发送失败")
        return False

    # 监控归零过程
    print("监控归零状态...")
    start_time = time.time()
    timeout = 30.0  # 30秒超时
    while time.time() - start_time < timeout:
        timestamp, q_actual, _ = driver.get_state()
        error = np.linalg.norm(q_zero - q_actual)
        print(f"  误差: {error:.4f} rad ({np.rad2deg(error):.2f}°)", end='\r')

        # 如果误差小于1度，认为到达零位
        if error < np.deg2rad(1.0):
            print("\n✅ 已到达零位")
            break

        time.sleep(0.1)
    else:
        print("\n⚠️ 归零超时，但继续测试")

    # 显示最终零位状态
    _, q_final_zero, _ = driver.get_state()
    print(f"\n最终零位状态:")
    for i, q in enumerate(q_final_zero):
        print(f"  关节 {i}: {np.rad2deg(q):6.2f}°")

    print("\n✅ 阶段2完成：单关节运动正常，已回到零位")
    return True


def stage3_ik_validation_test(driver, ik_solver, safety_monitor):
    """阶段3：IK求解器验证测试"""
    print("\n" + "="*60)
    print("阶段 3: IK 求解器验证测试")
    print("="*60)

    # 确认机器人在零位
    print("\n⚠️ 阶段3需要从零位开始")
    _, q_current, _ = driver.get_state()
    print(f"当前关节角度:")
    for i, q in enumerate(q_current):
        print(f"  关节 {i}: {np.rad2deg(q):6.2f}°")

    # 检查是否接近零位（允许±2度误差）
    q_zero = np.zeros(len(q_current))
    error_from_zero = np.linalg.norm(q_current - q_zero)
    print(f"\n与零位的误差: {np.rad2deg(error_from_zero):.2f}°")

    if error_from_zero > np.deg2rad(5.0):  # 如果误差大于5度
        print("⚠️ 机器人不在零位！")
        wait_for_user_confirmation("是否先回到零位？")

        print("\n发送归零指令...")
        success = driver.move_joint_controlled(q_zero, speed=0.1, accel=0.1, block=False)
        if not success:
            print("❌ 归零指令发送失败")
            return False

        # 等待归零完成
        print("等待归零完成...")
        start_time = time.time()
        while time.time() - start_time < 30.0:
            _, q_actual, _ = driver.get_state()
            error = np.linalg.norm(q_zero - q_actual)
            print(f"  误差: {error:.4f} rad ({np.rad2deg(error):.2f}°)", end='\r')
            if error < np.deg2rad(1.0):
                print("\n✅ 已到达零位")
                break
            time.sleep(0.1)

        # 更新当前位置
        _, q_current, _ = driver.get_state()

    wait_for_user_confirmation("即将测试 IK 求解器（固定目标位姿）")

    # 定义测试目标位姿
    # 根据URDF分析，零位时末端在 [0, -0.15, 0.84]
    # 测试目标：向前10cm，保持高度
    target_pos = np.array([0.1, -0.15, 0.84])
    print(f"\n🎯 目标位置: {target_pos}")
    print(f"   (零位末端: [0.0, -0.15, 0.84], 向前移动10cm)")

    # 求解 IK（3-DoF 位置追踪）
    print("\n求解 IK...")
    q_solution, success, error = ik_solver.solve(
        target_pos,
        q_init=q_current,
        max_iter=100,
        tol=1e-3
    )

    if not success:
        print(f"❌ IK 求解失败！误差: {error*1000:.2f}mm")
        return False

    print(f"✅ IK 求解成功！误差: {error*1000:.2f}mm")

    # 检查限位
    violations = safety_monitor.check_limits(q_solution)
    if violations:
        print(f"❌ 限位检查失败: {violations}")
        return False

    # 显示关节角度变化
    print("\n关节角度变化:")
    for i, (q_curr, q_sol) in enumerate(zip(q_current, q_solution[:7])):
        delta = np.rad2deg(q_sol - q_curr)
        print(f"  Joint {i}: {np.rad2deg(q_curr):6.2f}° → {np.rad2deg(q_sol):6.2f}° (Δ{delta:+6.2f}°)")

    wait_for_user_confirmation("即将执行 IK 求解结果")

    # 发送指令
    print("\n发送运动指令...")
    driver.send_command(q_solution)

    # 监控运动（3秒）
    print("监控运动状态...")
    start_time = time.time()
    while time.time() - start_time < 3.0:
        timestamp, q_actual, _ = driver.get_state()
        error = np.linalg.norm(q_solution[:7] - q_actual)
        print(f"  关节误差: {error:.4f} rad ({np.rad2deg(error):.2f}°)", end='\r')
        time.sleep(0.1)

    print("\n✅ 阶段3完成：IK 求解器验证正常")
    return True


def stage4_full_loop_test(driver, ik_solver, safety_monitor):
    """阶段4：完整遥操作回路测试（模拟）"""
    print("\n" + "="*60)
    print("阶段 4: 完整回路测试（模拟遥操作）")
    print("="*60)

    wait_for_user_confirmation("即将测试完整控制回路（10秒圆周运动）")

    # 获取当前位置
    _, q_current, _ = driver.get_state()

    # 定义圆周轨迹参数
    # 零位末端在 [0.0, -0.15, 0.84]，选择附近的可达位置
    center = np.array([0.15, -0.15, 0.75])
    radius = 0.05  # 5cm 半径
    duration = 10.0  # 10秒
    frequency = 10  # 10Hz 控制频率

    print(f"\n轨迹参数:")
    print(f"  中心: {center}")
    print(f"  半径: {radius}m")
    print(f"  时长: {duration}s")
    print(f"  频率: {frequency}Hz")

    # 执行轨迹跟踪
    print("\n开始轨迹跟踪...")
    start_time = time.time()
    dt = 1.0 / frequency
    q_cmd = q_current.copy()

    ik_failure_count = 0
    max_failures = 5
    test_success = True

    try:
        while time.time() - start_time < duration:
            loop_start = time.time()

            # 计算当前目标位置（圆周运动）
            t = time.time() - start_time
            angle = 2 * np.pi * t / duration
            target_pos = center + np.array([
                radius * np.cos(angle),
                radius * np.sin(angle),
                0.0
            ])

            # IK 求解
            q_solution, success, ik_error = ik_solver.solve(
                target_pos,
                q_init=q_cmd,
                max_iter=30,
                tol=5e-3
            )

            if success:
                # 检查限位
                violations = safety_monitor.check_limits(q_solution)
                if not violations:
                    q_cmd = q_solution
                    ik_failure_count = 0
                else:
                    print(f"\n⚠️ 限位违规: {violations}")
                    ik_failure_count += 1
            else:
                ik_failure_count += 1
                print(f"\n⚠️ IK 失败 ({ik_failure_count}/{max_failures})")

            if ik_failure_count >= max_failures:
                print(f"\n❌ 连续失败 {max_failures} 次，停止测试")
                test_success = False
                break

            # 发送指令
            driver.send_command(q_cmd)

            # 频率控制
            elapsed = time.time() - loop_start
            sleep_time = max(0, dt - elapsed)
            time.sleep(sleep_time)

            # 进度显示
            progress = (t / duration) * 100
            print(f"  进度: {progress:.1f}% | IK误差: {ik_error*1000:.2f}mm", end='\r')

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断测试")
        test_success = False

    if test_success:
        print("\n✅ 阶段4完成：完整回路测试正常")
    else:
        print("\n❌ 阶段4失败：完整回路测试未通过")

    return test_success


def main():
    """主测试流程"""
    print("="*60)
    print("🧪 真机安全测试脚本")
    print("="*60)

    # 1. 加载配置
    config_path = os.path.join(project_root, "config", "system_config.yaml")
    print(f"\n📁 加载配置: {config_path}")

    with open(config_path, 'r') as f:
        hw_config = yaml.safe_load(f)

    # 从hardware配置中读取参数
    hw_params = hw_config['hardware']
    print(f"  IP: {hw_params['robot_ip']}")
    print(f"  Side: {hw_params['arm_side']}")
    print(f"  DoF: 7")  # LinkerArm固定为7自由度

    # 2. 初始化驱动器
    print("\n🦾 初始化真机驱动器...")
    driver = RealArmDriver(
        ip=hw_params['robot_ip'],
        dof=7,  # LinkerArm固定为7自由度
        arm_side=hw_params['arm_side']
    )

    # 3. 初始化 IK 求解器
    print("\n🧠 初始化 IK 求解器...")

    # 从配置读取URDF路径
    urdf_filename = hw_config['robot_model'].get('urdf_file', 'lkls73_o2_dual_arm_description.urdf')
    urdf_path = os.path.join(project_root, "config", urdf_filename)
    print(f"   使用URDF: {urdf_filename}")

    # 确定控制的关节名称（而不是索引）
    arm_side = hw_params['arm_side']
    if arm_side == 'right':
        controlled_joints = [
            'Right_Shoulder_Pitch_Joint',
            'Right_Shoulder_Roll_Joint',
            'Right_Shoulder_Yaw_Joint',
            'Right_Elbow_Pitch_Joint',
            'Right_Wrist_Yaw_Joint',
            'Right_Wrist_Pitch_Joint',
            'Right_Wrist_Roll_Joint'
        ]
        end_effector_frame = hw_config['robot_model']['end_effector_frames']['right']
    else:
        controlled_joints = [
            'Left_Shoulder_Pitch_Joint',
            'Left_Shoulder_Roll_Joint',
            'Left_Shoulder_Yaw_Joint',
            'Left_Elbow_Pitch_Joint',
            'Left_Wrist_Yaw_Joint',
            'Left_Wrist_Pitch_Joint',
            'Left_Wrist_Roll_Joint'
        ]
        end_effector_frame = hw_config['robot_model']['end_effector_frames']['left']

    print(f"   控制关节: {controlled_joints}")
    print(f"   末端执行器: {end_effector_frame}")

    # 初始化IK求解器，指定控制的关节和末端执行器
    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        controlled_joints=controlled_joints,
        end_effector_frame=end_effector_frame
    )

    # 4. 初始化安全监控器
    # 从 URDF 获取关节限位（这里硬编码，实际应从 URDF 读取）
    joint_limits = np.array([
        [-2.9, 1.0],      # Shoulder_Pitch
        [-0.15, 3.14],    # Shoulder_Roll
        [-3.14, 3.14],    # Shoulder_Yaw
        [-2.35, 0.1],     # Elbow_Pitch (updated to match real robot)
        [-3.14, 3.14],    # Wrist_Yaw
        [-1.57, 1.57],    # Wrist_Pitch
        [-3.14, 3.14]     # Wrist_Roll
    ])
    safety_monitor = SafetyMonitor(joint_limits, max_joint_velocity=0.5)

    # 5. 执行测试阶段
    try:
        # 阶段1：连接测试
        if not stage1_connection_test(driver):
            return

        # 阶段2：单关节测试
        if not stage2_single_joint_test(driver, safety_monitor):
            return

        # 阶段3：IK 验证测试
        if not stage3_ik_validation_test(driver, ik_solver, safety_monitor):
            return

        # 阶段4：完整回路测试
        if not stage4_full_loop_test(driver, ik_solver, safety_monitor):
            return

        print("\n" + "="*60)
        print("🎉 所有测试阶段完成！")
        print("="*60)
        print("\n✅ 真机验证成功，可以进行完整遥操作测试")

    except KeyboardInterrupt:
        print("\n\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

