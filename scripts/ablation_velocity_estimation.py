#!/usr/bin/env python3
"""
速度估计方法消融实验

对比三种速度估计方法：
1. 卡尔曼滤波估计（kalman）
2. 数值微分估计（numerical）
3. 机器人测量值（measured，如果可用）

评估指标：
- 速度估计的平滑度（标准差）
- 加速度估计的准确性
- 安全限制触发次数
- 跟踪误差

Author: VIST Project
Date: 2026-02-22
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


def run_ablation_experiment(method='kalman', duration=30):
    """
    运行消融实验

    Args:
        method: 速度估计方法 ('kalman', 'numerical', 'measured')
        duration: 实验时长（秒）

    Returns:
        metrics: 实验指标字典
    """
    from src.config import get_config
    from src.control.vist_controller import VISTController
    from src.robot.robot_interface import RobotInterface

    # 加载配置
    config = get_config()

    # 设置速度估计方法
    config.velocity_estimation_method = method

    print(f"\n{'='*60}")
    print(f"消融实验: {method.upper()} 方法")
    print(f"{'='*60}\n")

    # 初始化控制器
    controller = VISTController(config)
    robot = RobotInterface(config)

    # 连接真机
    q_init = robot.connect()

    # 收集数据
    metrics = {
        'method': method,
        'velocities': [],
        'accelerations': [],
        'tracking_errors': [],
        'safety_triggers': {
            'velocity': 0,
            'acceleration': 0
        },
        'timestamps': []
    }

    print(f"开始收集数据（{duration}秒）...")

    import time
    start_time = time.time()
    last_q = q_init.copy()
    last_v = np.zeros(7)
    last_time = start_time

    try:
        while time.time() - start_time < duration:
            # 接收关键点
            keypoints = robot.receive_keypoints()
            if keypoints is None:
                continue

            # VIST处理
            q_target, success, debug_info = controller.process(keypoints)
            if not success:
                continue

            # 发送命令
            robot.send_command(q_target)

            # 读取实际状态
            _, q_actual, q_vel_measured = robot.driver.get_state()

            # 计算跟踪误差
            tracking_error = np.linalg.norm(q_target - q_actual)

            # 计算速度和加速度（数值微分）
            current_time = time.time()
            dt = current_time - last_time
            if dt > 0:
                v_numerical = (q_actual - last_q) / dt
                a_numerical = (v_numerical - last_v) / dt

                # 记录数据
                metrics['velocities'].append(v_numerical.copy())
                metrics['accelerations'].append(a_numerical.copy())
                metrics['tracking_errors'].append(tracking_error)
                metrics['timestamps'].append(current_time - start_time)

                # 统计安全触发
                if debug_info.get('safety_status', {}).get('velocity_limited', False):
                    metrics['safety_triggers']['velocity'] += 1
                if debug_info.get('safety_status', {}).get('acceleration_limited', False):
                    metrics['safety_triggers']['acceleration'] += 1

                last_q = q_actual.copy()
                last_v = v_numerical.copy()
                last_time = current_time

    except KeyboardInterrupt:
        print("\n实验被用户中断")

    finally:
        robot.disconnect()

    print(f"✅ 数据收集完成（{len(metrics['timestamps'])}帧）\n")

    return metrics


def analyze_metrics(metrics_list):
    """
    分析和对比多个实验的指标

    Args:
        metrics_list: 实验指标列表
    """
    print(f"\n{'='*60}")
    print("消融实验结果对比")
    print(f"{'='*60}\n")

    for metrics in metrics_list:
        method = metrics['method']
        velocities = np.array(metrics['velocities'])
        accelerations = np.array(metrics['accelerations'])
        tracking_errors = np.array(metrics['tracking_errors'])

        print(f"{method.upper()} 方法:")
        print(f"  速度平滑度（标准差）: {np.std(velocities):.4f} rad/s")
        print(f"  加速度平滑度（标准差）: {np.std(accelerations):.4f} rad/s²")
        print(f"  平均跟踪误差: {np.mean(tracking_errors):.4f} rad")
        print(f"  速度限制触发: {metrics['safety_triggers']['velocity']}次")
        print(f"  加速度限制触发: {metrics['safety_triggers']['acceleration']}次")
        print()


def plot_comparison(metrics_list):
    """
    绘制对比图表

    Args:
        metrics_list: 实验指标列表
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    colors = ['blue', 'red', 'green']
    for i, metrics in enumerate(metrics_list):
        method = metrics['method']
        timestamps = metrics['timestamps']
        velocities = np.array(metrics['velocities'])
        accelerations = np.array(metrics['accelerations'])
        tracking_errors = metrics['tracking_errors']

        # 速度标准差（每个关节）
        ax1 = axes[0]
        velocity_std = np.std(velocities, axis=0)
        ax1.bar(np.arange(7) + i*0.25, velocity_std, width=0.25,
                label=method.upper(), color=colors[i], alpha=0.7)
        ax1.set_xlabel('关节索引')
        ax1.set_ylabel('速度标准差 (rad/s)')
        ax1.set_title('速度平滑度对比（标准差越小越平滑）')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 加速度标准差
        ax2 = axes[1]
        accel_std = np.std(accelerations, axis=0)
        ax2.bar(np.arange(7) + i*0.25, accel_std, width=0.25,
                label=method.upper(), color=colors[i], alpha=0.7)
        ax2.set_xlabel('关节索引')
        ax2.set_ylabel('加速度标准差 (rad/s²)')
        ax2.set_title('加速度平滑度对比（标准差越小越平滑）')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 跟踪误差
        ax3 = axes[2]
        ax3.plot(timestamps, tracking_errors, label=method.upper(),
                 color=colors[i], alpha=0.7, linewidth=2)
        ax3.set_xlabel('时间 (s)')
        ax3.set_ylabel('跟踪误差 (rad)')
        ax3.set_title('跟踪误差对比')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('velocity_estimation_ablation.png', dpi=150)
    print("✅ 对比图表已保存: velocity_estimation_ablation.png")


if __name__ == "__main__":
    print("速度估计方法消融实验")
    print("="*60)
    print("将对比以下方法:")
    print("1. kalman - VIST卡尔曼滤波估计")
    print("2. numerical - 数值微分估计（基线）")
    print("="*60)

    # 运行实验
    methods = ['kalman', 'numerical']
    metrics_list = []

    for method in methods:
        input(f"\n按Enter开始 {method.upper()} 方法实验...")
        metrics = run_ablation_experiment(method=method, duration=30)
        metrics_list.append(metrics)

    # 分析结果
    analyze_metrics(metrics_list)

    # 绘制对比图
    plot_comparison(metrics_list)

    print("\n✅ 消融实验完成！")