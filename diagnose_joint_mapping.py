#!/usr/bin/env python3
"""
关节映射诊断工具
帮助确定正确的关节索引映射
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
import sys

class JointMappingDiagnostic(Node):
    def __init__(self):
        super().__init__('joint_mapping_diagnostic')

        self.subscription = self.create_subscription(
            JointState,
            '/left_arm_joint_control',
            self.callback,
            10
        )

        self.last_values = None
        self.count = 0

        print('=' * 70)
        print('关节映射诊断工具')
        print('=' * 70)
        print('')
        print('使用说明:')
        print('1. 保持遥操臂静止，等待基准数据')
        print('2. 然后逐个移动每个关节')
        print('3. 观察哪个索引的值变化最大')
        print('')
        print('等待数据...')
        print('=' * 70)

    def callback(self, msg):
        self.count += 1
        current_values = np.array(msg.position)

        if self.count == 1:
            print(f'\n✓ 收到第一条数据')
            print(f'  关节数量: {len(current_values)}')
            print(f'  数据范围: [{np.min(current_values):.3f}, {np.max(current_values):.3f}]')
            print('')
            print('基准值:')
            for i, val in enumerate(current_values):
                print(f'  [{i}]: {val:8.3f}')
            print('')
            print('现在请移动遥操臂的第1个关节（肩部俯仰）...')
            self.last_values = current_values.copy()

        elif self.count > 10 and self.count % 20 == 0:
            # 计算变化量
            delta = current_values - self.last_values
            max_change_idx = np.argmax(np.abs(delta))
            max_change_val = delta[max_change_idx]

            print(f'\n样本 {self.count}:')
            print(f'  最大变化: 索引[{max_change_idx}] = {max_change_val:+.3f}')
            print('')
            print('  所有关节变化:')
            for i, (curr, last, d) in enumerate(zip(current_values, self.last_values, delta)):
                if abs(d) > 0.1:  # 只显示变化超过0.1的
                    print(f'    [{i}]: {last:7.3f} → {curr:7.3f} (Δ{d:+.3f})')

            self.last_values = current_values.copy()

def main():
    rclpy.init()
    diagnostic = JointMappingDiagnostic()

    print('')
    print('提示: 按Ctrl+C停止')
    print('')

    try:
        rclpy.spin(diagnostic)
    except KeyboardInterrupt:
        print('\n\n诊断完成')
        print('=' * 70)
        print('根据上面的输出，确定正确的关节映射')
        print('=' * 70)
    finally:
        diagnostic.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
