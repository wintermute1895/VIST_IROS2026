"""
VIST 仿真验证框架

在无法上真机的情况下，通过仿真测试验证算法设计是否能实现实验目标。

核心功能：
1. 模拟完整的 VIST 工作流程
2. 可视化 α、β、α_eff 的动态变化
3. 测试各种场景（标定误差、人类微调、紧急退出等）
4. 生成性能指标报告

Author: VIST Team
Date: 2026-02-09
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import sys
import os
from typing import List, Tuple, Dict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.intent_detector import (
    EnhancedIntentDetector,
    IntentState,
    compute_human_command,
    compute_algorithm_expectation
)


class VISTSimulator:
    """
    VIST 系统仿真器

    模拟完整的 VIST 工作流程，包括：
    - 人类操作员的手部运动
    - 机器人的响应
    - 意图检测和冲突检测
    - 状态转换
    """

    def __init__(self, config=None):
        """初始化仿真器"""
        self.intent_detector = EnhancedIntentDetector(config)

        # 仿真参数
        self.dt = 1.0 / 30.0  # 30Hz 采样
        self.time = 0.0

        # 目标位置（USB 插孔）
        self.target_socket_pos = np.array([0.5, 0.0, 0.3])

        # 机器人当前状态
        self.robot_pos = np.array([0.0, 0.0, 0.5])
        self.robot_velocity = np.zeros(3)

        # 人类手部位置
        self.human_hand_pos = np.array([0.0, 0.0, 0.5])

        # 记录数据（用于可视化）
        self.history = {
            'time': [],
            'distance': [],
            'velocity': [],
            'alpha': [],
            'beta': [],
            'alpha_eff': [],
            'state': [],
            'robot_pos': [],
            'human_pos': [],
            'target_pos': []
        }

    def simulate_human_motion(
        self,
        scenario: str,
        t: float
    ) -> np.ndarray:
        """
        模拟人类手部运动

        Args:
            scenario: 场景类型
            t: 当前时间

        Returns:
            human_hand_pos: 人类手部位置
        """
        if scenario == "normal_approach":
            # 场景 1: 正常接近（人类主导）
            # 从起点平滑移动到目标附近
            progress = min(t / 3.0, 1.0)  # 3秒到达
            self.human_hand_pos = (
                np.array([0.0, 0.0, 0.5]) * (1 - progress) +
                (self.target_socket_pos + np.array([0.0, 0.0, 0.08])) * progress
            )

        elif scenario == "calibration_error":
            # 场景 2: 标定误差（算法引导偏离 3mm）
            # 人类接近后，算法引导到错误位置，人类微调修正
            if t < 3.0:
                # 接近阶段
                progress = t / 3.0
                self.human_hand_pos = (
                    np.array([0.0, 0.0, 0.5]) * (1 - progress) +
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.08])) * progress
                )
            elif t < 5.0:
                # 算法主导阶段（但位置偏离）
                # 人类手部保持静止，让算法引导
                self.human_hand_pos = self.target_socket_pos + np.array([0.0, 0.0, 0.05])
            else:
                # 微调阶段（人类发现偏离，开始修正）
                # 慢速移动修正位置
                correction_progress = min((t - 5.0) / 2.0, 1.0)
                offset = np.array([0.003, 0.0, 0.0]) * (1 - correction_progress)  # 修正 3mm 偏差
                self.human_hand_pos = self.target_socket_pos + np.array([0.0, 0.0, 0.05]) + offset

        elif scenario == "emergency_pullback":
            # 场景 3: 紧急回拉（插入时发现问题）
            if t < 3.0:
                # 接近阶段
                progress = t / 3.0
                self.human_hand_pos = (
                    np.array([0.0, 0.0, 0.5]) * (1 - progress) +
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.02])) * progress
                )
            elif t < 4.0:
                # 插入阶段
                progress = (t - 3.0) / 1.0
                self.human_hand_pos = (
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.02])) * (1 - progress) +
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.005])) * progress
                )
            else:
                # 紧急回拉（发现插歪了）
                pullback_progress = min((t - 4.0) / 0.5, 1.0)
                self.human_hand_pos = (
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.005])) * (1 - pullback_progress) +
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.1])) * pullback_progress
                )

        elif scenario == "conflict_test":
            # 场景 4: 冲突测试（人类故意反向移动）
            if t < 2.0:
                # 接近阶段
                progress = t / 2.0
                self.human_hand_pos = (
                    np.array([0.0, 0.0, 0.5]) * (1 - progress) +
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.04])) * progress
                )
            elif t < 4.0:
                # 算法主导阶段
                self.human_hand_pos = self.target_socket_pos + np.array([0.0, 0.0, 0.04])
            else:
                # 人类故意反向移动（测试冲突检测）
                conflict_progress = min((t - 4.0) / 1.0, 1.0)
                self.human_hand_pos = (
                    (self.target_socket_pos + np.array([0.0, 0.0, 0.04])) * (1 - conflict_progress) +
                    (self.target_socket_pos + np.array([0.1, 0.0, 0.04])) * conflict_progress
                )

        return self.human_hand_pos

    def simulate_robot_response(
        self,
        alpha_eff: float,
        beta: float
    ):
        """
        模拟机器人响应（带阻尼补偿）

        Args:
            alpha_eff: 有效意图因子
            beta: 冲突因子
        """
        # 阻尼补偿参数
        K_BASE = 100.0
        D_BASE = 20.0
        K_DAMP = 50.0

        # 计算动态刚度和阻尼
        k_stiffness = K_BASE * alpha_eff
        d_damping = D_BASE + (K_DAMP * beta)

        # 混合目标位置
        target_pos = (1 - alpha_eff) * self.human_hand_pos + alpha_eff * self.target_socket_pos

        # 计算位置误差
        pos_error = target_pos - self.robot_pos

        # 计算控制力（带阻尼）
        F_cmd = k_stiffness * pos_error - d_damping * self.robot_velocity

        # 简化的动力学模型（质量 = 1kg）
        m = 1.0
        acceleration = F_cmd / m

        # 更新速度和位置
        self.robot_velocity += acceleration * self.dt
        self.robot_pos += self.robot_velocity * self.dt

    def run_simulation(
        self,
        scenario: str,
        duration: float = 10.0
    ) -> Dict:
        """
        运行仿真

        Args:
            scenario: 场景类型
            duration: 仿真时长（秒）

        Returns:
            history: 仿真历史数据
        """
        print(f"\n{'='*60}")
        print(f"运行仿真场景: {scenario}")
        print(f"{'='*60}\n")

        # 重置状态
        self.time = 0.0
        self.robot_pos = np.array([0.0, 0.0, 0.5])
        self.robot_velocity = np.zeros(3)
        self.intent_detector.reset()
        self.history = {
            'time': [],
            'distance': [],
            'velocity': [],
            'alpha': [],
            'beta': [],
            'alpha_eff': [],
            'state': [],
            'robot_pos': [],
            'human_pos': [],
            'target_pos': []
        }

        # 仿真循环
        steps = int(duration / self.dt)
        for step in range(steps):
            self.time = step * self.dt

            # 1. 模拟人类手部运动
            self.simulate_human_motion(scenario, self.time)

            # 2. 计算距离和速度
            distance = np.linalg.norm(self.target_socket_pos - self.robot_pos)
            velocity = np.linalg.norm(self.robot_velocity)

            # 3. 计算人类指令和算法期望
            human_command = compute_human_command(
                self.robot_pos,
                self.human_hand_pos,
                self.robot_velocity
            )
            algorithm_expectation = compute_algorithm_expectation(
                self.robot_pos,
                self.target_socket_pos
            )

            # 4. 意图检测
            alignment_error = distance
            result = self.intent_detector.detect_intent(
                distance=distance,
                velocity=velocity,
                human_command=human_command,
                algorithm_expectation=algorithm_expectation,
                alignment_error=alignment_error
            )

            # 5. 模拟机器人响应
            self.simulate_robot_response(result.alpha_effective, result.beta)

            # 6. 记录数据
            self.history['time'].append(self.time)
            self.history['distance'].append(distance * 1000)  # 转换为 mm
            self.history['velocity'].append(velocity * 100)  # 转换为 cm/s
            self.history['alpha'].append(result.alpha)
            self.history['beta'].append(result.beta)
            self.history['alpha_eff'].append(result.alpha_effective)
            self.history['state'].append(result.state.value)
            self.history['robot_pos'].append(self.robot_pos.copy())
            self.history['human_pos'].append(self.human_hand_pos.copy())
            self.history['target_pos'].append(self.target_socket_pos.copy())

            # 7. 打印关键事件
            if step % 30 == 0:  # 每秒打印一次
                print(f"t={self.time:.1f}s | State: {result.state.value:20s} | "
                      f"d={distance*1000:.1f}mm | v={velocity*100:.1f}cm/s | "
                      f"α={result.alpha:.2f} | β={result.beta:.2f} | α_eff={result.alpha_effective:.2f}")

        print(f"\n{'='*60}")
        print(f"仿真完成")
        print(f"{'='*60}\n")

        return self.history


def plot_simulation_results(history: Dict, scenario: str):
    """
    可视化仿真结果

    Args:
        history: 仿真历史数据
        scenario: 场景名称
    """
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle(f'VIST Simulation Results - {scenario}', fontsize=16)

    time = history['time']

    # 1. 距离和速度
    ax = axes[0, 0]
    ax.plot(time, history['distance'], 'b-', label='Distance to target')
    ax.axhline(y=50, color='r', linestyle='--', label='Align threshold (50mm)')
    ax.axhline(y=2, color='g', linestyle='--', label='Insertion threshold (2mm)')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Distance (mm)')
    ax.set_title('Distance to Target')
    ax.legend()
    ax.grid(True)

    # 2. 意图因子
    ax = axes[0, 1]
    ax.plot(time, history['alpha'], 'b-', label='α (base)', linewidth=2)
    ax.plot(time, history['alpha_eff'], 'r-', label='α_eff (effective)', linewidth=2)
    ax.fill_between(time, 0, history['alpha_eff'], alpha=0.3, color='red')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Intent Factor')
    ax.set_title('Intent Factor (α)')
    ax.legend()
    ax.grid(True)
    ax.set_ylim([-0.1, 1.1])

    # 3. 冲突因子
    ax = axes[1, 0]
    ax.plot(time, history['beta'], 'r-', label='β (conflict)', linewidth=2)
    ax.fill_between(time, 0, history['beta'], alpha=0.3, color='red')
    ax.axhline(y=0.3, color='orange', linestyle='--', label='Conflict threshold')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Conflict Factor')
    ax.set_title('Conflict Factor (β)')
    ax.legend()
    ax.grid(True)
    ax.set_ylim([-0.1, 1.1])

    # 4. 速度
    ax = axes[1, 1]
    ax.plot(time, history['velocity'], 'g-', label='Velocity')
    ax.axhline(y=0.5, color='r', linestyle='--', label='Deadband (0.5cm/s)')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Velocity (cm/s)')
    ax.set_title('Robot Velocity')
    ax.legend()
    ax.grid(True)

    # 5. 状态转换
    ax = axes[2, 0]
    states = history['state']
    state_map = {
        'approaching': 0,
        'visual_admittance': 1,
        'correction_override': 2,
        'constrained_insertion': 3,
        'release': 4
    }
    state_values = [state_map.get(s, 0) for s in states]
    ax.plot(time, state_values, 'k-', linewidth=2)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('State')
    ax.set_title('State Machine')
    ax.set_yticks([0, 1, 2, 3, 4])
    ax.set_yticklabels(['APPROACHING', 'VISUAL_ADMITTANCE', 'CORRECTION_OVERRIDE', 'CONSTRAINED_INSERTION', 'RELEASE'])
    ax.grid(True)

    # 6. 3D 轨迹
    ax = axes[2, 1]
    ax.remove()
    ax = fig.add_subplot(3, 2, 6, projection='3d')

    robot_pos = np.array(history['robot_pos'])
    human_pos = np.array(history['human_pos'])
    target_pos = history['target_pos'][0]

    ax.plot(robot_pos[:, 0], robot_pos[:, 1], robot_pos[:, 2], 'b-', label='Robot', linewidth=2)
    ax.plot(human_pos[:, 0], human_pos[:, 1], human_pos[:, 2], 'g--', label='Human', linewidth=1)
    ax.scatter(*target_pos, color='r', s=200, marker='*', label='Target')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title('3D Trajectory')
    ax.legend()

    plt.tight_layout()
    plt.savefig(f'simulation_{scenario}.png', dpi=150)
    print(f"✅ 图表已保存: simulation_{scenario}.png")
    plt.show()


def main():
    """主函数"""
    print("\n" + "="*60)
    print("VIST 仿真验证框架")
    print("="*60)

    simulator = VISTSimulator()

    # 场景列表
    scenarios = [
        ("normal_approach", "正常接近场景"),
        ("calibration_error", "标定误差场景"),
        ("emergency_pullback", "紧急回拉场景"),
        ("conflict_test", "冲突测试场景")
    ]

    # 运行所有场景
    for scenario_name, scenario_desc in scenarios:
        print(f"\n{'='*60}")
        print(f"场景: {scenario_desc}")
        print(f"{'='*60}")

        history = simulator.run_simulation(scenario_name, duration=8.0)
        plot_simulation_results(history, scenario_name)

        input("\n按 Enter 继续下一个场景...")

    print("\n✅ 所有仿真场景完成！")


if __name__ == "__main__":
    main()
