#!/usr/bin/env python3
"""
VIST 实时监控节点

订阅 VIST 滤波器的诊断信息，实时显示：
- 笛卡尔速度
- 意图因子 α
- R 和 Q 的动态变化
- 滤波效果
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray  # 改为 Float64
import numpy as np
import time


class VISTMonitor(Node):
    def __init__(self):
        super().__init__('vist_monitor')

        self.get_logger().info('=' * 70)
        self.get_logger().info('VIST 实时监控')
        self.get_logger().info('=' * 70)

        # 订阅诊断话题（需要在 vist_filter_node 中发布）
        self.create_subscription(
            Float64MultiArray,  # 改为 Float64
            '/vist_diagnostics',
            self.diagnostics_callback,
            10
        )

        # 统计信息
        self.frame_count = 0
        self.last_print_time = time.time()
        self.print_interval = 1.0  # 每秒打印一次

        # 历史数据
        self.velocity_history = []
        self.alpha_history = []
        self.max_history_size = 100

        self.get_logger().info('等待 VIST 诊断数据...')
        self.get_logger().info('提示：确保 vist_filter_node 发布 /vist_diagnostics 话题')

    def diagnostics_callback(self, msg):
        """
        诊断数据格式：
        [0]: 笛卡尔速度范数 (m/s)
        [1]: 意图因子 α
        [2]: R 放大倍数
        [3]: Q 速度方差
        [4-6]: 笛卡尔速度 xyz
        """
        self.frame_count += 1

        if len(msg.data) < 7:
            return

        velocity_norm = msg.data[0]
        alpha = msg.data[1]
        r_scale = msg.data[2]
        q_variance = msg.data[3]
        cart_vel = np.array(msg.data[4:7])

        # 更新历史
        self.velocity_history.append(velocity_norm)
        self.alpha_history.append(alpha)
        if len(self.velocity_history) > self.max_history_size:
            self.velocity_history.pop(0)
            self.alpha_history.pop(0)

        # 定期打印
        current_time = time.time()
        if current_time - self.last_print_time >= self.print_interval:
            self.print_status(velocity_norm, alpha, r_scale, q_variance, cart_vel)
            self.last_print_time = current_time

    def print_status(self, velocity_norm, alpha, r_scale, q_variance, cart_vel):
        """打印当前状态"""
        # 计算统计信息
        avg_velocity = np.mean(self.velocity_history) if self.velocity_history else 0
        avg_alpha = np.mean(self.alpha_history) if self.alpha_history else 0

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
        self.get_logger().info(f'  笛卡尔速度: {velocity_norm:.4f} m/s (平均: {avg_velocity:.4f})')
        self.get_logger().info(f'  速度分量: X={cart_vel[0]:.3f}, Y={cart_vel[1]:.3f}, Z={cart_vel[2]:.3f}')
        self.get_logger().info(f'  {color}意图因子 α: {alpha:.3f}{reset} (平均: {avg_alpha:.3f})')
        self.get_logger().info(f'  R 放大倍数: {r_scale:.2f}x')
        self.get_logger().info(f'  Q 速度方差: {q_variance:.6f}')

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
