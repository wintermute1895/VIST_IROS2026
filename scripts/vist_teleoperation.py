#!/usr/bin/env python3
"""
VIST Framework Teleoperation
基于VIST框架的遥操作实现

核心特点：
1. 微分IK（Differential IK）- 不求全局解，只求增量
2. 速度控制（Velocity Control）- 关节空间直接控制
3. 平滑滤波（Smoothing）- One Euro Filter
4. 无迭代优化 - 每步计算时间 < 1ms
"""

import os
import sys
import time
import socket
import json
import numpy as np
import yaml

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver
from src.core.differential_ik_solver import DifferentialIKSolver
from src.core.motion_mapper import ArmMotionMapper
from src.core.one_euro_filter import OneEuroFilter
from src.core.safety_monitor import SafetyMonitor
from src.config import get_config


def countdown(seconds):
    """倒计时"""
    print(f"\n⏱️  {seconds}秒后开始遥操作...")
    for i in range(seconds, 0, -1):
        print(f"   {i}...", end='\r')
        time.sleep(1)
    print("   🚀 开始！" + " "*20)


def main():
    print("="*80)
    print("🎮 VIST框架遥操作 (Differential IK)")
    print("="*80)

    # 1. 加载统一配置
    print("\n📁 加载系统配置...")
    config = get_config()
    print("✅ 系统配置加载完成")

    # 2. 加载硬件配置（设备特定参数）
    config_path = os.path.join(project_root, "config", "hardware.yaml")
    print(f"\n📁 加载硬件配置: {config_path}")

    with open(config_path, 'r') as f:
        hw_config = yaml.safe_load(f)

    arm_config = hw_config['arm']
    print(f"  IP: {arm_config['ip']}")
    print(f"  Side: {arm_config['side']}")
    print(f"  DoF: {arm_config['dof']}")

    # 3. 初始化真机驱动器
    print("\n🦾 初始化真机驱动器...")
    driver = RealArmDriver(
        ip=arm_config['ip'],
        dof=arm_config['dof'],
        arm_side=arm_config['side']
    )

    # 4. 初始化微分IK求解器
    print("\n🧠 初始化微分IK求解器...")
    ik_solver = DifferentialIKSolver()
    print("✅ 微分IK求解器初始化完成")

    # 5. 初始化运动映射器（从配置文件自动加载参数）
    print("\n🗺️  初始化运动映射器...")
    mapper = ArmMotionMapper()  # 自动从配置文件加载
    mapper.set_filter_alpha(config.filter_alpha)
    print("✅ 运动映射器初始化完成")

    # 6. 初始化安全监控器（使用配置参数）
    print("\n🛡️  初始化安全监控器...")
    safety_monitor = SafetyMonitor(
        config.robot_joint_limits,
        max_joint_velocity=config.max_joint_velocity,
        max_joint_acceleration=config.max_joint_acceleration
    )
    print("✅ 安全监控器初始化完成")

    try:
        # 7. 连接机器人
        print("\n🔌 连接机器人...")
        driver.connect()
        print("✅ 连接成功")

        # 8. 获取当前状态
        print("\n📊 读取当前关节状态...")
        timestamp, q_current, _ = driver.get_state()
        print(f"当前关节角度: {np.round(np.rad2deg(q_current), 2)}°")

        # 9. 设置 UDP 接收（使用配置参数）
        print("\n📡 设置 UDP 接收...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((config.udp_host, config.udp_port))
        sock.setblocking(False)
        print(f"✅ UDP 接收器就绪 ({config.udp_host}:{config.udp_port})")

        # 10. 初始化滤波器（使用配置参数）
        pos_filter = OneEuroFilter(min_cutoff=config.filter_min_cutoff, beta=config.filter_beta)
        quat_filter = OneEuroFilter(min_cutoff=config.filter_min_cutoff, beta=config.filter_beta)

        # 11. 倒计时
        countdown(10)

        # 12. 遥操作循环
        q_cmd = q_current.copy()
        q_cmd_prev = q_cmd.copy()

        # 使用配置参数
        frequency = config.control_frequency
        dt = config.control_dt
        max_joint_velocity = config.max_joint_velocity
        duration = config.control_duration
        ik_gain = config.ik_gain
        max_data_timeout = config.max_data_timeout
        joint_limits = config.robot_joint_limits  # 用于后续的 clip 操作

        data_timeout_count = 0
        success_count = 0
        total_count = 0

        print(f"\n🎮 开始遥操作（{duration}秒）...")
        print("提示：按 Ctrl+C 可随时停止")
        print("\n💡 VIST框架特点：")
        print("  - 微分IK：每步只计算增量，无需迭代")
        print("  - 速度控制：关节空间直接控制")
        print("  - 天然平滑：不会跳变或卡住\n")

        start_time = time.time()

        while time.time() - start_time < duration:
            loop_start = time.time()
            total_count += 1

            # 接收人体关键点数据
            try:
                data, _ = sock.recvfrom(config.udp_buffer_size)
                packet = json.loads(data.decode('utf-8'))

                if 'keypoints' in packet:
                    human_kps = packet['keypoints']
                else:
                    human_kps = packet

                data_timeout_count = 0
            except BlockingIOError:
                data_timeout_count += 1
                if data_timeout_count >= max_data_timeout:
                    print(f"\n⚠️ 超过 1 秒未收到数据，停止测试")
                    break
                time.sleep(dt)
                continue
            except Exception as e:
                print(f"\n❌ 数据接收错误: {e}")
                break

            # 提取右手关键点
            if 'wrist' not in human_kps or 'elbow' not in human_kps:
                time.sleep(dt)
                continue

            # 运动映射：视觉坐标 → 机器人坐标
            map_start_time = time.time()
            result = mapper.human_to_robot(human_kps)
            map_time = (time.time() - map_start_time) * 1000  # ms

            if result is None:
                time.sleep(dt)
                continue

            target_pos_robot, target_quat, debug_info = result

            # 提取肘部位置（关键！）
            target_elbow_pos = debug_info.get('elbow_pos', None)

            # One Euro 滤波
            filter_start_time = time.time()
            target_pos_filtered = pos_filter(target_pos_robot, time.time())
            target_elbow_filtered = pos_filter(target_elbow_pos, time.time()) if target_elbow_pos is not None else None
            filter_time = (time.time() - filter_start_time) * 1000  # ms

            # 单目标微分IK求解（VIST核心）
            # 暂时禁用双目标优化，先测试单目标效果
            ik_start_time = time.time()
            q_solution, success, ik_error = ik_solver.solve(
                target_pos_filtered,
                q_init=q_cmd,
                position_only=True,
                gain=ik_gain
            )
            ik_time = (time.time() - ik_start_time) * 1000  # ms

            # ==========================================
            # 综合安全检查（使用 SafetyMonitor 的完整功能）
            # ==========================================
            # 检查：关节限位 + 速度限制 + 加速度限制
            is_safe, violations = safety_monitor.check_command(
                q_solution,
                time.time(),
                end_effector_pos=target_pos_filtered  # 可选：工作空间检查
            )

            if is_safe:
                success_count += 1

                # 速度限制（关节空间）- 作为额外保护层
                q_velocity = (q_solution - q_cmd_prev) / dt
                q_velocity_limited = np.clip(q_velocity, -max_joint_velocity, max_joint_velocity)
                q_cmd = q_cmd_prev + q_velocity_limited * dt

                # 再次检查限位（双重保护）
                q_cmd = np.clip(q_cmd, joint_limits[:, 0], joint_limits[:, 1])

                # 发送指令
                driver.send_command(q_cmd)

                # 更新状态
                q_cmd_prev = q_cmd.copy()

                # 显示状态（每10帧显示一次）
                if success_count % 10 == 0:
                    # 检查关节1（Shoulder_Roll）是否接近限位
                    joint1_deg = np.rad2deg(q_cmd[1])
                    joint1_warning = ""
                    if joint1_deg > 170:
                        joint1_warning = f" ⚠️ J1接近上限: {joint1_deg:.1f}°"
                    elif joint1_deg < -5:
                        joint1_warning = f" ⚠️ J1接近下限: {joint1_deg:.1f}°"

                    # 计算总延迟
                    total_latency = map_time + filter_time + ik_time
                    print(f"✅ 控制: {success_count}/{total_count} | 误差: {ik_error*1000:.1f}mm | 延迟: {total_latency:.1f}ms (IK:{ik_time:.1f}ms){joint1_warning}", end='\r')
            else:
                # 安全违规：跳过此帧，不发送指令
                if total_count % 50 == 0:
                    print(f"\n⚠️ 安全违规（跳过指令）: {violations}")

            # 控制频率
            elapsed = time.time() - loop_start
            if elapsed < dt:
                time.sleep(dt - elapsed)

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    finally:
        sock.close()
        driver.disconnect()
        print("\n✅ 已断开连接")

    print(f"\n📊 统计:")
    print(f"  总帧数: {total_count}")
    print(f"  成功帧数: {success_count}")
    print(f"  成功率: {success_count/total_count*100:.1f}%")


if __name__ == "__main__":
    main()
