#!/usr/bin/env python3
"""
VIST 实时监控节点 v3.0

订阅 VIST 滤波器的诊断信息，实时显示：
- 笛卡尔速度和位置距离
- 意图因子 α（融合速度和距离）
- R_human 和 R_virtual 的动态变化
- Q 的动态变化
- 关节变化量和卡尔曼增益K
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
import numpy as np
import time


class VISTMonitor(Node):
    def __init__(self):
        super().__init__('vist_monitor')

        self.get_logger().info('=' * 70)
        self.get_logger().info('VIST 实时监控 v3.0')
        self.get_logger().info('=' * 70)

        # 订阅诊断话题
        self.create_subscription(
            Float64MultiArray,
            '/vist_diagnostics',
            self.diagnostics_callback,
            10
        )

        # 订阅意图因子话题
        self.create_subscription(
            Float64MultiArray,
            '/vist_intent_factors',
            self.intent_factors_callback,
            10
        )

        # 统计信息
        self.frame_count = 0
        self.last_print_time = time.time()
        self.print_interval = 1.0  # 每秒打印一次

        # 历史数据
        self.velocity_history = []
        self.alpha_history = []
        self.distance_history = []
        self.max_history_size = 100

        # 意图因子数据
        self.alpha_velocity = 0.0
        self.alpha_distance = 0.0
        self.q_norm = 0.0
        self.r_norm = 0.0
        self.k_norm = 0.0

        self.get_logger().info('等待 VIST 诊断数据...')
        self.get_logger().info('提示：确保 vist_filter_node 发布 /vist_diagnostics 和 /vist_intent_factors 话题')

    def intent_factors_callback(self, msg):
        """
        意图因子数据格式：
        [0]: alpha (总意图因子)
        [1]: alpha_distance (距离因素)
        [2]: alpha_velocity (速度因素)
        [3]: alpha_alignment (对齐因素)
        [4]: Q_norm
        [5]: R_norm
        [6]: K_norm
        """
        if len(msg.data) >= 7:
            self.alpha_velocity = msg.data[2]
            self.alpha_distance = msg.data[1]
            self.q_norm = msg.data[4]
            self.r_norm = msg.data[5]
            self.k_norm = msg.data[6]

    def diagnostics_callback(self, msg):
        """
        诊断数据格式 v3.0：
        [0]: 笛卡尔速度范数 (m/s)
        [1]: 意图因子 α
        [2]: R_human 放大倍数
        [3]: Q 速度方差
        [4-6]: 笛卡尔速度 xyz
        [7]: 末端到目标XY距离 (m)
        [8]: 关节变化量范数
        [9]: 卡尔曼增益K范数
        [10]: R_virtual 缩小倍数
        """
        self.frame_count += 1

        # 兼容v2.0和v3.0格式
        if len(msg.data) >= 11:
            # v3.0完整格式
            velocity_norm = msg.data[0]
            alpha = msg.data[1]
            r_human_scale = msg.data[2]
            q_variance = msg.data[3]
            cart_vel = np.array(msg.data[4:7])
            distance_to_target = msg.data[7]
            joint_delta_norm = msg.data[8]
            k_gain_norm = msg.data[9]
            r_virtual_scale = msg.data[10]
        elif len(msg.data) >= 7:
            # v2.0兼容格式
            velocity_norm = msg.data[0]
            alpha = msg.data[1]
            r_human_scale = msg.data[2]
            q_variance = msg.data[3]
            cart_vel = np.array(msg.data[4:7])
            distance_to_target = 0.0
            joint_delta_norm = 0.0
            k_gain_norm = 0.0
            r_virtual_scale = 1.0
        else:
            return

        # 更新历史
        self.velocity_history.append(velocity_norm)
        self.alpha_history.append(alpha)
        self.distance_history.append(distance_to_target)
        if len(self.velocity_history) > self.max_history_size:
            self.velocity_history.pop(0)
            self.alpha_history.pop(0)
            self.distance_history.pop(0)

        # 定期打印
        current_time = time.time()
        if current_time - self.last_print_time >= self.print_interval:
            self.print_status(velocity_norm, alpha, r_human_scale, r_virtual_scale,
                            q_variance, cart_vel, distance_to_target,
                            joint_delta_norm, k_gain_norm)
            self.last_print_time = current_time

    def print_status(self, velocity_norm, alpha, r_human_scale, r_virtual_scale,
                    q_variance, cart_vel, distance_to_target,
                    joint_delta_norm, k_gain_norm):
        """打印当前状态"""
        # 计算统计信息
        avg_velocity = np.mean(self.velocity_history) if self.velocity_history else 0
        avg_alpha = np.mean(self.alpha_history) if self.alpha_history else 0
        avg_distance = np.mean(self.distance_history) if self.distance_history else 0

        # 判断模式
        mode = "精密对准" if alpha > 0.5 else "自由移动"
        mode_emoji = "🎯" if alpha > 0.5 else "🚀"

        # 颜色编码（使用 ANSI 转义码）
        if alpha > 0.7:
            color = "\033[91m"  # 红色（精密）
        elif alpha > 0.3:
            color = "\033[93m"  # 黄色（中间）
        else:
            color = "\033[92m"  # 绿色（自由）
        reset = "\033[0m"

        self.get_logger().info('')
        self.get_logger().info(f'{color}{"=" * 70}{reset}')
        self.get_logger().info(f'{color}帧 {self.frame_count} | {mode_emoji} {mode}{reset}')
        self.get_logger().info(f'{color}{"=" * 70}{reset}')

        # 速度信息
        self.get_logger().info(f'  笛卡尔速度: {velocity_norm:.4f} m/s (平均: {avg_velocity:.4f})')
        self.get_logger().info(f'  速度分量: X={cart_vel[0]:.3f}, Y={cart_vel[1]:.3f}, Z={cart_vel[2]:.3f}')

        # 位置信息
        self.get_logger().info(f'  末端到目标XY距离: {distance_to_target:.4f} m (平均: {avg_distance:.4f})')
        self.get_logger().info(f'  目标位置: (0.41, -0.11)')

        # 意图因子
        self.get_logger().info(f'  {color}意图因子 α: {alpha:.3f}{reset} (平均: {avg_alpha:.3f}, 范围: [0.05, 0.95])')
        self.get_logger().info(f'    ├─ α_velocity (速度因素): {self.alpha_velocity:.3f}')
        self.get_logger().info(f'    └─ α_distance (距离因素): {self.alpha_distance:.3f}')

        # 观测噪声
        self.get_logger().info(f'  R_human 放大: {r_human_scale:.2f}x (α越大越不信任人类)')
        self.get_logger().info(f'  R_virtual 缩小: {r_virtual_scale:.2f}x (α越大越信任虚拟)')

        # 过程噪声
        self.get_logger().info(f'  Q 速度方差: {q_variance:.6f}')

        # 协方差范数
        self.get_logger().info(f'  协方差范数: Q={self.q_norm:.4f}, R={self.r_norm:.4f}, K={self.k_norm:.4f}')

        # 滤波器状态
        self.get_logger().info(f'  关节变化量: {joint_delta_norm:.6f}')
        self.get_logger().info(f'  卡尔曼增益K: {k_gain_norm:.6f}')

        # 效果指示
        if alpha > 0.7:
            self.get_logger().info(f'  💡 效果: XY 方向强约束（粘稠），Z 方向柔顺')
        elif alpha > 0.3:
            self.get_logger().info(f'  💡 效果: 中等约束')
        else:
            self.get_logger().info(f'  💡 效果: 自由移动，最小约束')


def main(args=None):
    rclpy.init(args=args)
    monitor = VISTMonitor()

    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
