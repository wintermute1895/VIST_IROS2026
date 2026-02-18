#!/usr/bin/env python3
"""
VIST滤波过程动画演示

创建动态动画展示：
1. 三维轨迹的实时演化
2. 意图因子的实时变化
3. 协方差调度的实时变化
4. 原始轨迹 vs 滤波后轨迹的对比
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from mpl_toolkits.mplot3d import Axes3D
from src.config.config_loader import VISTConfig


class VISTAnimator:
    """VIST滤波动画生成器"""

    def __init__(self, trajectory, filtered_trajectory, alpha, R_human, R_virtual,
                 hole_position, hole_radius, t):
        self.trajectory = trajectory
        self.filtered_trajectory = filtered_trajectory
        self.alpha = alpha
        self.R_human = R_human
        self.R_virtual = R_virtual
        self.hole_position = hole_position
        self.hole_radius = hole_radius
        self.t = t
        self.n_steps = len(t)

        # 创建图形
        self.fig = plt.figure(figsize=(16, 9))
        self.setup_subplots()

    def setup_subplots(self):
        """设置子图布局"""
        # 3D轨迹图（左上，占2x2）
        self.ax_3d = self.fig.add_subplot(2, 3, (1, 4), projection='3d')

        # XY平面投影（右上）
        self.ax_xy = self.fig.add_subplot(2, 3, 2)

        # 意图因子曲线（右中）
        self.ax_alpha = self.fig.add_subplot(2, 3, 3)

        # 协方差调度曲线（右下）
        self.ax_cov = self.fig.add_subplot(2, 3, 6)

        # 距离误差曲线（左下）
        self.ax_error = self.fig.add_subplot(2, 3, 5)

    def init_animation(self):
        """初始化动画"""
        # 3D轨迹图
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        self.ax_3d.set_title('三维轨迹演化', fontsize=12, fontweight='bold')

        # 绘制目标点
        self.ax_3d.scatter(*self.hole_position, c='g', s=200, marker='*',
                          label='目标插孔', zorder=10)

        # 初始化轨迹线
        self.line_raw, = self.ax_3d.plot([], [], [], 'r-', alpha=0.3,
                                         linewidth=1, label='原始轨迹（带抖动）')
        self.line_filtered, = self.ax_3d.plot([], [], [], 'b-',
                                              linewidth=2, label='VIST滤波后')
        self.point_current, = self.ax_3d.plot([], [], [], 'ro',
                                              markersize=8, label='当前位置')

        self.ax_3d.legend(loc='upper right', fontsize=8)
        self.ax_3d.grid(True, alpha=0.3)

        # 设置固定的视角范围
        all_points = np.vstack([self.trajectory, self.filtered_trajectory])
        margin = 0.1
        self.ax_3d.set_xlim(all_points[:, 0].min() - margin,
                           all_points[:, 0].max() + margin)
        self.ax_3d.set_ylim(all_points[:, 1].min() - margin,
                           all_points[:, 1].max() + margin)
        self.ax_3d.set_zlim(all_points[:, 2].min() - margin,
                           all_points[:, 2].max() + margin)

        # XY平面投影
        self.ax_xy.set_xlabel('X (m)')
        self.ax_xy.set_ylabel('Y (m)')
        self.ax_xy.set_title('XY平面投影', fontsize=10)
        self.ax_xy.scatter(*self.hole_position[:2], c='g', s=200, marker='*')
        circle = plt.Circle((self.hole_position[0], self.hole_position[1]),
                           self.hole_radius, color='g', fill=False, linewidth=2)
        self.ax_xy.add_patch(circle)
        self.line_xy_raw, = self.ax_xy.plot([], [], 'r-', alpha=0.3, linewidth=1)
        self.line_xy_filtered, = self.ax_xy.plot([], [], 'b-', linewidth=2)
        self.ax_xy.grid(True, alpha=0.3)
        self.ax_xy.axis('equal')

        # 意图因子曲线
        self.ax_alpha.set_xlabel('时间 (s)')
        self.ax_alpha.set_ylabel('意图因子 α')
        self.ax_alpha.set_title('意图因子实时变化', fontsize=10)
        self.ax_alpha.set_xlim(0, self.t[-1])
        self.ax_alpha.set_ylim(0, 1)
        self.line_alpha, = self.ax_alpha.plot([], [], 'b-', linewidth=2)
        self.ax_alpha.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        self.ax_alpha.grid(True, alpha=0.3)

        # 协方差调度曲线
        self.ax_cov.set_xlabel('时间 (s)')
        self.ax_cov.set_ylabel('协方差 (对数尺度)')
        self.ax_cov.set_title('协方差调度', fontsize=10)
        self.ax_cov.set_xlim(0, self.t[-1])
        self.ax_cov.set_yscale('log')
        self.line_R_human, = self.ax_cov.plot([], [], 'r-', linewidth=2, label='R_human')
        self.line_R_virtual, = self.ax_cov.plot([], [], 'b-', linewidth=2, label='R_virtual')
        self.ax_cov.legend(fontsize=8)
        self.ax_cov.grid(True, alpha=0.3)

        # 距离误差曲线
        self.ax_error.set_xlabel('时间 (s)')
        self.ax_error.set_ylabel('距离误差 (mm)')
        self.ax_error.set_title('距离误差实时变化', fontsize=10)
        self.ax_error.set_xlim(0, self.t[-1])
        distance_raw = np.linalg.norm(self.trajectory - self.hole_position, axis=1) * 1000
        distance_filtered = np.linalg.norm(self.filtered_trajectory - self.hole_position, axis=1) * 1000
        self.ax_error.set_ylim(0, max(distance_raw.max(), distance_filtered.max()) * 1.1)
        self.line_error_raw, = self.ax_error.plot([], [], 'r-', alpha=0.5, linewidth=1, label='原始')
        self.line_error_filtered, = self.ax_error.plot([], [], 'b-', linewidth=2, label='滤波后')
        self.ax_error.axhline(y=self.hole_radius * 1000, color='g', linestyle='--', label='插孔半径')
        self.ax_error.legend(fontsize=8)
        self.ax_error.grid(True, alpha=0.3)

        plt.tight_layout()

        return (self.line_raw, self.line_filtered, self.point_current,
                self.line_xy_raw, self.line_xy_filtered,
                self.line_alpha, self.line_R_human, self.line_R_virtual,
                self.line_error_raw, self.line_error_filtered)

    def update_frame(self, frame):
        """更新每一帧"""
        # 更新3D轨迹
        self.line_raw.set_data(self.trajectory[:frame, 0], self.trajectory[:frame, 1])
        self.line_raw.set_3d_properties(self.trajectory[:frame, 2])

        self.line_filtered.set_data(self.filtered_trajectory[:frame, 0],
                                    self.filtered_trajectory[:frame, 1])
        self.line_filtered.set_3d_properties(self.filtered_trajectory[:frame, 2])

        if frame > 0:
            self.point_current.set_data([self.filtered_trajectory[frame-1, 0]],
                                       [self.filtered_trajectory[frame-1, 1]])
            self.point_current.set_3d_properties([self.filtered_trajectory[frame-1, 2]])

        # 更新XY投影
        self.line_xy_raw.set_data(self.trajectory[:frame, 0], self.trajectory[:frame, 1])
        self.line_xy_filtered.set_data(self.filtered_trajectory[:frame, 0],
                                       self.filtered_trajectory[:frame, 1])

        # 更新意图因子
        self.line_alpha.set_data(self.t[:frame], self.alpha[:frame])

        # 更新协方差
        self.line_R_human.set_data(self.t[:frame], self.R_human[:frame])
        self.line_R_virtual.set_data(self.t[:frame], self.R_virtual[:frame])

        # 更新距离误差
        distance_raw = np.linalg.norm(self.trajectory[:frame] - self.hole_position, axis=1) * 1000
        distance_filtered = np.linalg.norm(self.filtered_trajectory[:frame] - self.hole_position, axis=1) * 1000
        self.line_error_raw.set_data(self.t[:frame], distance_raw)
        self.line_error_filtered.set_data(self.t[:frame], distance_filtered)

        # 更新标题显示当前状态
        current_alpha = self.alpha[frame-1] if frame > 0 else 0
        current_error = distance_filtered[-1] if len(distance_filtered) > 0 else 0
        self.fig.suptitle(f'VIST滤波实时演示 | 时间: {self.t[frame-1]:.2f}s | α: {current_alpha:.3f} | 误差: {current_error:.1f}mm',
                         fontsize=14, fontweight='bold')

        return (self.line_raw, self.line_filtered, self.point_current,
                self.line_xy_raw, self.line_xy_filtered,
                self.line_alpha, self.line_R_human, self.line_R_virtual,
                self.line_error_raw, self.line_error_filtered)

    def create_animation(self, output_path='/tmp/vist_animation.gif', fps=20, skip_frames=2):
        """创建动画"""
        print(f"\n正在生成动画...")
        print(f"  总帧数: {self.n_steps}")
        print(f"  跳帧: {skip_frames} (实际帧数: {self.n_steps // skip_frames})")
        print(f"  帧率: {fps} fps")

        # 创建动画（跳帧以减小文件大小）
        frames = range(0, self.n_steps, skip_frames)
        anim = FuncAnimation(self.fig, self.update_frame, init_func=self.init_animation,
                           frames=frames, interval=1000/fps, blit=False, repeat=True)

        # 保存为GIF
        writer = PillowWriter(fps=fps)
        anim.save(output_path, writer=writer)

        print(f"✅ 动画已保存至: {output_path}")
        print(f"  文件大小: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")

        return anim


def main():
    """主函数"""
    print("="*60)
    print("VIST滤波过程动画生成")
    print("="*60)

    # 导入模拟器
    from simulate_peg_in_hole_task import PegInHoleSimulator

    # 加载配置
    config = VISTConfig()

    # 创建模拟器
    simulator = PegInHoleSimulator(config)

    # 生成轨迹
    print("\n1. 生成模拟轨迹...")
    t, trajectory, velocity, intent_phase = simulator.generate_human_trajectory()
    print(f"   ✅ 生成 {len(t)} 个时间步")

    # 计算意图因子
    print("\n2. 计算意图因子...")
    alpha = simulator.compute_intent_factor(trajectory, velocity)
    print(f"   ✅ 意图因子范围: [{alpha.min():.3f}, {alpha.max():.3f}]")

    # 应用VIST滤波
    print("\n3. 应用VIST滤波...")
    filtered_trajectory = simulator.apply_vist_filtering(trajectory, velocity, alpha)
    print(f"   ✅ 滤波完成")

    # 计算协方差
    R_human, R_virtual = simulator.compute_covariance_scheduling(alpha)

    # 创建动画
    print("\n4. 创建动画...")
    animator = VISTAnimator(
        trajectory=trajectory,
        filtered_trajectory=filtered_trajectory,
        alpha=alpha,
        R_human=R_human,
        R_virtual=R_virtual,
        hole_position=simulator.hole_position,
        hole_radius=simulator.hole_radius,
        t=t
    )

    # 生成动画（跳帧以减小文件大小）
    anim = animator.create_animation(
        output_path='/tmp/vist_animation.gif',
        fps=20,
        skip_frames=5  # 每5帧取1帧
    )

    print("\n" + "="*60)
    print("✅ 动画生成完成！")
    print("="*60)
    print("\n你可以查看以下文件：")
    print("  - /tmp/vist_animation.gif - 动态演示动画")
    print("  - /tmp/peg_in_hole_simulation.png - 静态结果图表")


if __name__ == "__main__":
    main()