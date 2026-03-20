#!/usr/bin/env python3
"""
VIST Alpha 数据记录器 - 异步版本
通过订阅 /vist_intent_factors 话题记录 α 值，不影响控制循环性能
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
import numpy as np
import time
from datetime import datetime
import os

class AlphaLogger(Node):
    def __init__(self, log_file=None):
        super().__init__('alpha_logger')

        # 创建日志文件
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = os.path.expanduser("~/Dev/VIST/data/alpha_logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"alpha_log_{timestamp}.csv")

        self.log_file = log_file
        self.start_time = time.time()

        # 创建订阅器
        self.subscription = self.create_subscription(
            Float64MultiArray,
            '/vist_intent_factors',
            self.alpha_callback,
            10
        )

        # 写入CSV头
        with open(self.log_file, 'w') as f:
            f.write("timestamp,elapsed_time,alpha,alpha_geo,alpha_vel,alpha_alignment,Q_norm,R_norm,K_norm\n")

        self.get_logger().info(f'Alpha Logger 已启动')
        self.get_logger().info(f'日志文件: {self.log_file}')
        self.get_logger().info('按 Ctrl+C 停止记录')

        # 统计信息
        self.count = 0
        self.last_print_time = time.time()

    def alpha_callback(self, msg):
        """接收 α 数据并写入文件"""
        current_time = time.time()
        elapsed = current_time - self.start_time

        # 提取数据
        alpha = msg.data[0] if len(msg.data) > 0 else 0.0
        alpha_geo = msg.data[1] if len(msg.data) > 1 else 0.0
        alpha_vel = msg.data[2] if len(msg.data) > 2 else 0.0
        alpha_alignment = msg.data[3] if len(msg.data) > 3 else 0.0
        Q_norm = msg.data[4] if len(msg.data) > 4 else 0.0
        R_norm = msg.data[5] if len(msg.data) > 5 else 0.0
        K_norm = msg.data[6] if len(msg.data) > 6 else 0.0

        # 异步写入（批量缓冲）
        with open(self.log_file, 'a') as f:
            f.write(f"{current_time:.6f},{elapsed:.6f},{alpha:.6f},{alpha_geo:.6f},{alpha_vel:.6f},{alpha_alignment:.6f},{Q_norm:.6f},{R_norm:.6f},{K_norm:.6f}\n")

        self.count += 1

        # 每秒打印一次统计
        if current_time - self.last_print_time >= 1.0:
            self.get_logger().info(f'已记录 {self.count} 条数据 | α={alpha:.3f} | Q={Q_norm:.2e} R={R_norm:.2e} K={K_norm:.2e}')
            self.last_print_time = current_time

def main(args=None):
    rclpy.init(args=args)
    logger = AlphaLogger()

    try:
        rclpy.spin(logger)
    except KeyboardInterrupt:
        print(f'\n记录完成！共 {logger.count} 条数据')
        print(f'日志文件: {logger.log_file}')
    finally:
        logger.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
