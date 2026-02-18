#!/usr/bin/env python3
"""
VIST流形约束可视化 - IROS补充材料
Visualizing Intent-Driven Manifold Constraint for Precision Assembly

展示VIST框架的核心数学原理：
1. 意图因子α的演化（从自由空间到约束流形）
2. 协方差调度（Q矩阵从各向同性到各向异性）
3. 轨迹"吸附"效应（Virtual Fixture）
4. 刚度分析（X轴冻结，Z轴自由）
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.patches import Ellipse
import matplotlib.patches as mpatches
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class VISTManifoldVisualizer:
    """VIST流形约束可视化器"""

    def __init__(self):
        # 仿真参数
        self.n_steps = 200
        self.dt = 0.05  # 50ms
        self.time = np.linspace(0, self.n_steps * self.dt, self.n_steps)

        # 目标流形（Z轴上的线）
        self.target_x = 0.0  # X轴目标位置
        self.target_z_start = 0.0
        self.target_z_end = 0.5

        # VIST参数
        self.lambda_r = 3.0  # R增长率
        self.R_base = 0.01

        # 生成数据
        self.generate_trajectory()
        self.compute_intent_factor()
        self.apply_vist_filtering()

    def generate_trajectory(self):
        """生成带噪声的人类输入轨迹"""
        # Z轴：平滑接近
        z_smooth = np.linspace(0, 0.5, self.n_steps)

        # X轴：带抖动的接近
        # 阶段1: 远离时大幅抖动
        # 阶段2: 接近时仍有抖动
        x_base = np.zeros(self.n_steps)

        # 添加生理抖动（5-12Hz）
        tremor_freq = 8.0  # Hz
        tremor_amplitude = 0.02  # 2cm
        tremor = tremor_amplitude * np.sin(2 * np.pi * tremor_freq * self.time)

        # 添加随机噪声
        noise = np.random.normal(0, 0.005, self.n_steps)

        # 人类输入：基准 + 抖动 + 噪声
        self.human_x = x_base + tremor + noise
        self.human_z = z_smooth + np.random.normal(0, 0.002, self.n_steps)

        # 速度（简单差分）
        self.velocity_x = np.gradient(self.human_x, self.dt)
        self.velocity_z = np.gradient(self.human_z, self.dt)

    def compute_intent_factor(self):
        """计算意图因子α（使用论文公式）"""
        self.alpha = np.zeros(self.n_steps)

        # 参数
        W_task_x = 100.0  # X轴权重（高，因为需要约束）
        W_task_z = 1.0    # Z轴权重（低，因为需要自由）
        beta = 50.0       # 速度衰减参数

        for i in range(self.n_steps):
            # Eq. 2: 几何势能（只考虑X轴误差）
            xi_err_x = self.target_x - self.human_x[i]
            mahalanobis_sq = W_task_x * xi_err_x**2
            alpha_geo = np.exp(-0.5 * mahalanobis_sq)

            # Eq. 3: 运动能量
            speed_sq = self.velocity_x[i]**2 + self.velocity_z[i]**2
            alpha_vel = 1.0 / (1.0 + beta * speed_sq)

            # Eq. 4: 方向对齐（简化：朝向目标）
            xi_err = np.array([xi_err_x, 0])
            velocity = np.array([self.velocity_x[i], self.velocity_z[i]])

            xi_err_norm = np.linalg.norm(xi_err)
            velocity_norm = np.linalg.norm(velocity)

            if xi_err_norm > 1e-6 and velocity_norm > 1e-6:
                cos_theta = np.dot(velocity, xi_err) / (velocity_norm * xi_err_norm)
                cos_theta = np.clip(cos_theta, -1.0, 1.0)
                alpha_dir = 0.5 * (1.0 + cos_theta)
            else:
                alpha_dir = 1.0

            # Eq. 5: 意图因子融合
            w_g = 0.7
            w_v = 0.3
            eta = 2.0

            state_prior = w_g * alpha_geo + w_v * alpha_vel
            state_prior_normalized = 1.0 / (1.0 + np.exp(-5.0 * (state_prior - 0.5)))
            active_gating = alpha_dir ** eta

            self.alpha[i] = state_prior_normalized * active_gating

    def apply_vist_filtering(self):
        """应用VIST滤波（简化的Kalman滤波）"""
        self.filtered_x = np.zeros(self.n_steps)
        self.filtered_z = np.zeros(self.n_steps)

        # 初始状态
        self.filtered_x[0] = self.human_x[0]
        self.filtered_z[0] = self.human_z[0]

        # 协方差矩阵演化
        self.Q_xx = np.zeros(self.n_steps)
        self.Q_zz = np.zeros(self.n_steps)
        self.R_values = np.zeros(self.n_steps)

        # 简化的Kalman滤波
        P_x = 0.01  # X轴协方差
        P_z = 0.01  # Z轴协方差

        for i in range(1, self.n_steps):
            alpha = self.alpha[i]

            # Q矩阵（任务空间插值）
            high_gain = 5e-3
            Sigma_free_x = 1.0 * high_gain
            Sigma_free_z = 1.0 * high_gain
            Sigma_cons_x = 0.001 * high_gain  # X轴冻结
            Sigma_cons_z = 1.0 * high_gain    # Z轴自由

            Q_x = (1.0 - alpha) * Sigma_free_x + alpha * Sigma_cons_x
            Q_z = (1.0 - alpha) * Sigma_free_z + alpha * Sigma_cons_z

            self.Q_xx[i] = Q_x
            self.Q_zz[i] = Q_z

            # R矩阵（指数增长）
            R = self.R_base * np.exp(self.lambda_r * alpha)
            self.R_values[i] = R

            # 预测步骤
            x_pred = self.filtered_x[i-1]
            z_pred = self.filtered_z[i-1]
            P_x_pred = P_x + Q_x
            P_z_pred = P_z + Q_z

            # 更新步骤
            # Kalman增益
            K_x = P_x_pred / (P_x_pred + R)
            K_z = P_z_pred / (P_z_pred + R)

            # 状态更新
            self.filtered_x[i] = x_pred + K_x * (self.human_x[i] - x_pred)
            self.filtered_z[i] = z_pred + K_z * (self.human_z[i] - z_pred)

            # 协方差更新
            P_x = (1 - K_x) * P_x_pred
            P_z = (1 - K_z) * P_z_pred

    def create_visualization(self):
        """创建4子图可视化"""
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle('VIST: Intent-Driven Manifold Constraint Visualization',
                     fontsize=16, fontweight='bold', y=0.98)

        # 子图1: 空间轨迹（"管道"效应）
        ax1 = fig.add_subplot(221)
        ax1.set_xlabel('Z-axis (Insertion Direction) [m]', fontsize=11)
        ax1.set_ylabel('X-axis (Constraint Direction) [m]', fontsize=11)
        ax1.set_title('Spatial Trajectory: "Tube" Effect', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.set_xlim([-0.05, 0.55])
        ax1.set_ylim([-0.05, 0.05])

        # 目标流形（红色虚线）
        ax1.axhline(y=self.target_x, color='red', linestyle='--', linewidth=2,
                    label='Task Manifold (Target)', alpha=0.7)

        # 人类输入（灰色，半透明）
        human_line, = ax1.plot([], [], color='gray', linewidth=1.5, alpha=0.4,
                               label='Noisy Human Input')

        # VIST输出（蓝色，实线）
        vist_line, = ax1.plot([], [], color='#2E86AB', linewidth=2.5,
                              label='VIST Filtered Output')

        # 当前位置标记
        human_marker, = ax1.plot([], [], 'o', color='gray', markersize=8, alpha=0.6)
        vist_marker, = ax1.plot([], [], 'o', color='#2E86AB', markersize=10)

        ax1.legend(loc='upper left', fontsize=9)

        # 子图2: 意图因子α演化
        ax2 = fig.add_subplot(222)
        ax2.set_xlabel('Time [s]', fontsize=11)
        ax2.set_ylabel('Intent Factor α', fontsize=11)
        ax2.set_title('Intent Factor Evolution', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.set_xlim([0, self.time[-1]])
        ax2.set_ylim([0, 1.05])

        # 阶段标注
        ax2.axhline(y=0.3, color='orange', linestyle=':', alpha=0.5)
        ax2.axhline(y=0.7, color='green', linestyle=':', alpha=0.5)
        ax2.text(self.time[-1]*0.05, 0.15, 'Free Space', fontsize=9, color='orange')
        ax2.text(self.time[-1]*0.05, 0.85, 'Manifold', fontsize=9, color='green')

        alpha_line, = ax2.plot([], [], color='#06A77D', linewidth=2.5, label='α(t)')
        alpha_fill = None

        ax2.legend(loc='upper left', fontsize=9)

        # 子图3: 协方差椭圆演化
        ax3 = fig.add_subplot(223)
        ax3.set_xlabel('Z-axis [m]', fontsize=11)
        ax3.set_ylabel('X-axis [m]', fontsize=11)
        ax3.set_title('Process Noise Covariance Q Evolution', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3, linestyle='--')
        ax3.set_xlim([-0.1, 0.1])
        ax3.set_ylim([-0.1, 0.1])
        ax3.set_aspect('equal')

        # 目标流形
        ax3.axhline(y=0, color='red', linestyle='--', linewidth=2, alpha=0.7)

        # 协方差椭圆（将动态更新）
        ellipse = None

        # 子图4: 刚度分析
        ax4 = fig.add_subplot(224)
        ax4.set_xlabel('Time [s]', fontsize=11)
        ax4.set_ylabel('Stiffness (Inverse Variance)', fontsize=11)
        ax4.set_title('Anisotropic Stiffness Analysis', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3, linestyle='--')
        ax4.set_xlim([0, self.time[-1]])
        ax4.set_yscale('log')

        stiffness_x_line, = ax4.plot([], [], color='#D62828', linewidth=2,
                                      label='X-axis (Frozen)')
        stiffness_z_line, = ax4.plot([], [], color='#06A77D', linewidth=2,
                                      label='Z-axis (Free)')

        ax4.legend(loc='upper left', fontsize=9)

        # 信息文本
        info_text = fig.text(0.5, 0.01, '', ha='center', fontsize=10,
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout(rect=[0, 0.03, 1, 0.97])

        def init():
            human_line.set_data([], [])
            vist_line.set_data([], [])
            human_marker.set_data([], [])
            vist_marker.set_data([], [])
            alpha_line.set_data([], [])
            stiffness_x_line.set_data([], [])
            stiffness_z_line.set_data([], [])
            return (human_line, vist_line, human_marker, vist_marker,
                    alpha_line, stiffness_x_line, stiffness_z_line)

        def update(frame):
            nonlocal alpha_fill, ellipse

            # 子图1: 更新轨迹
            human_line.set_data(self.human_z[:frame+1], self.human_x[:frame+1])
            vist_line.set_data(self.filtered_z[:frame+1], self.filtered_x[:frame+1])
            human_marker.set_data([self.human_z[frame]], [self.human_x[frame]])
            vist_marker.set_data([self.filtered_z[frame]], [self.filtered_x[frame]])

            # 子图2: 更新意图因子
            alpha_line.set_data(self.time[:frame+1], self.alpha[:frame+1])

            # 填充区域
            if alpha_fill is not None:
                alpha_fill.remove()
            alpha_fill = ax2.fill_between(self.time[:frame+1], 0, self.alpha[:frame+1],
                                          alpha=0.3, color='#06A77D')

            # 子图3: 更新协方差椭圆
            if ellipse is not None:
                ellipse.remove()

            # 计算椭圆参数
            Q_x = self.Q_xx[frame]
            Q_z = self.Q_zz[frame]

            # 椭圆的宽度和高度（标准差的3倍）
            width = 3 * np.sqrt(Q_z) * 100  # 放大100倍以便可视化
            height = 3 * np.sqrt(Q_x) * 100

            ellipse = Ellipse((0, 0), width, height, angle=0,
                             facecolor='#2E86AB', alpha=0.3,
                             edgecolor='#2E86AB', linewidth=2)
            ax3.add_patch(ellipse)

            # 添加文本说明
            phase = "Isotropic" if self.alpha[frame] < 0.3 else \
                   ("Transition" if self.alpha[frame] < 0.7 else "Anisotropic")
            ax3.text(0.05, 0.08, f'Phase: {phase}\nα={self.alpha[frame]:.3f}',
                    fontsize=9, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

            # 子图4: 更新刚度
            stiffness_x = 1.0 / (self.Q_xx[:frame+1] + 1e-6)
            stiffness_z = 1.0 / (self.Q_zz[:frame+1] + 1e-6)

            stiffness_x_line.set_data(self.time[:frame+1], stiffness_x)
            stiffness_z_line.set_data(self.time[:frame+1], stiffness_z)

            # 更新Y轴范围
            all_stiffness = np.concatenate([stiffness_x, stiffness_z])
            ax4.set_ylim([all_stiffness.min()*0.5, all_stiffness.max()*2])

            # 更新信息文本
            phase_name = "Free Space Exploration" if self.alpha[frame] < 0.3 else \
                        ("Manifold Convergence" if self.alpha[frame] < 0.7 else "Constrained Insertion")

            info_text.set_text(
                f'Time: {self.time[frame]:.2f}s  |  Phase: {phase_name}  |  '
                f'α={self.alpha[frame]:.3f}  |  '
                f'X-error: {abs(self.filtered_x[frame])*1000:.2f}mm  |  '
                f'Q_x/Q_z ratio: {self.Q_xx[frame]/self.Q_zz[frame]:.1f}x'
            )

            return (human_line, vist_line, human_marker, vist_marker,
                    alpha_line, alpha_fill, ellipse,
                    stiffness_x_line, stiffness_z_line, info_text)

        # 创建动画
        print("正在生成VIST流形约束可视化...")
        print(f"总帧数: {self.n_steps}")

        anim = FuncAnimation(fig, update, frames=range(0, self.n_steps, 2),
                           init_func=init, blit=False, interval=50, repeat=True)

        return fig, anim


def main():
    """主函数"""
    print("="*60)
    print("VIST流形约束可视化 - IROS补充材料")
    print("="*60)

    # 创建可视化器
    visualizer = VISTManifoldVisualizer()

    # 生成可视化
    fig, anim = visualizer.create_visualization()

    # 保存为GIF
    output_gif = '/home/ilex/Dev/VIST/vist_manifold_constraint.gif'
    print(f"\n正在保存GIF动画到: {output_gif}")
    from matplotlib.animation import PillowWriter
    writer = PillowWriter(fps=20)
    anim.save(output_gif, writer=writer, dpi=120)

    file_size = os.path.getsize(output_gif) / (1024 * 1024)
    print(f"✓ GIF动画已保存")
    print(f"  文件大小: {file_size:.2f} MB")

    # 可选：保存为MP4（需要ffmpeg）
    try:
        output_mp4 = '/home/ilex/Dev/VIST/vist_manifold_constraint.mp4'
        print(f"\n正在保存MP4视频到: {output_mp4}")
        writer = FFMpegWriter(fps=20, bitrate=2000)
        anim.save(output_mp4, writer=writer, dpi=120)

        file_size = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"✓ MP4视频已保存")
        print(f"  文件大小: {file_size:.2f} MB")
    except Exception as e:
        print(f"⚠️ MP4保存失败（可能需要安装ffmpeg）: {e}")

    print("\n" + "="*60)
    print("✅ 可视化完成！")
    print("="*60)
    print("\n可视化特点:")
    print("  1. 空间轨迹: 展示'管道'效应（轨迹被吸到流形上）")
    print("  2. 意图因子: α从0→1的平滑过渡")
    print("  3. 协方差椭圆: 从圆形（各向同性）→针状（各向异性）")
    print("  4. 刚度分析: X轴刚度↑（冻结），Z轴刚度→（自由）")
    print("\n这个可视化完美展示了VIST的核心数学原理！")


if __name__ == '__main__':
    main()
