#!/usr/bin/env python3
"""
数据流实时验证工具
在不连真机的情况下验证数据流的完整性
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
from collections import deque
import time

class DataFlowValidator(Node):
    def __init__(self):
        super().__init__('data_flow_validator')

        # 存储最近的数据
        self.linkerta_left = deque(maxlen=10)
        self.linkerta_right = deque(maxlen=10)
        self.filtered_left = deque(maxlen=10)
        self.filtered_right = deque(maxlen=10)

        # 订阅所有关键话题
        self.create_subscription(JointState, '/left_arm_joint_control',
                                lambda msg: self.linkerta_left.append(np.array(msg.position[:7])), 10)
        self.create_subscription(JointState, '/right_arm_joint_control',
                                lambda msg: self.linkerta_right.append(np.array(msg.position[:7])), 10)
        self.create_subscription(JointState, '/filtered_left_joint_control',
                                lambda msg: self.filtered_left.append(np.array(msg.position[:7])), 10)
        self.create_subscription(JointState, '/filtered_right_joint_control',
                                lambda msg: self.filtered_right.append(np.array(msg.position[:7])), 10)

        # 定时验证
        self.timer = self.create_timer(2.0, self.validate_data_flow)

        # 加载配置
        self.left_directions = np.array([1, 1, -1, 1, -1, 1, 1])
        self.right_directions = np.array([-1, 1, -1, 1, -1, -1, 1])

        print('=' * 80)
        print('数据流实时验证工具')
        print('=' * 80)
        print('订阅话题:')
        print('  1. /left_arm_joint_control (LinkerTA左臂)')
        print('  2. /right_arm_joint_control (LinkerTA右臂)')
        print('  3. /filtered_left_joint_control (滤波后左臂)')
        print('  4. /filtered_right_joint_control (滤波后右臂)')
        print('')
        print('验证内容:')
        print('  - 数据流连通性')
        print('  - 方向修正是否生效')
        print('  - 数据一致性检查')
        print('=' * 80)
        print('')

    def validate_data_flow(self):
        """验证数据流"""
        print(f'\n{"=" * 80}')
        print(f'验证时间: {time.strftime("%H:%M:%S")}')
        print(f'{"=" * 80}')

        # 检查1: 数据流连通性
        print('\n【检查1】数据流连通性:')
        self.check_connectivity('LinkerTA左臂', self.linkerta_left)
        self.check_connectivity('LinkerTA右臂', self.linkerta_right)
        self.check_connectivity('滤波后左臂', self.filtered_left)
        self.check_connectivity('滤波后右臂', self.filtered_right)

        # 检查2: 方向修正验证（左臂）
        if len(self.linkerta_left) > 0 and len(self.filtered_left) > 0:
            print('\n【检查2】左臂方向修正验证:')
            self.verify_direction_correction(
                self.linkerta_left[-1],
                self.filtered_left[-1],
                self.left_directions,
                '左臂'
            )

        # 检查3: 方向修正验证（右臂）
        if len(self.linkerta_right) > 0 and len(self.filtered_right) > 0:
            print('\n【检查3】右臂方向修正验证:')
            self.verify_direction_correction(
                self.linkerta_right[-1],
                self.filtered_right[-1],
                self.right_directions,
                '右臂'
            )

        # 检查4: 数据变化检测
        print('\n【检查4】数据变化检测:')
        self.check_data_variation('左臂原始', self.linkerta_left)
        self.check_data_variation('右臂原始', self.linkerta_right)

    def check_connectivity(self, name, data_queue):
        """检查数据流连通性"""
        if len(data_queue) > 0:
            print(f'  ✓ {name:15s} - 接收到 {len(data_queue)} 个样本')
        else:
            print(f'  ✗ {name:15s} - 无数据')

    def verify_direction_correction(self, raw, filtered, directions, arm_name):
        """验证方向修正"""
        # 计算期望值（应用方向修正）
        expected = raw * directions

        # 对于GELLO滤波器，filtered应该等于expected
        # 允许小的数值误差
        diff = np.abs(filtered - expected)
        max_diff = np.max(diff)

        print(f'  原始数据:   {raw[:3]}...')
        print(f'  方向系数:   {directions[:3]}...')
        print(f'  期望输出:   {expected[:3]}...')
        print(f'  实际输出:   {filtered[:3]}...')
        print(f'  最大误差:   {max_diff:.6f}')

        if max_diff < 0.01:
            print(f'  ✓ {arm_name}方向修正正确')
        else:
            print(f'  ✗ {arm_name}方向修正可能有问题')
            # 找出哪些关节有问题
            for i in range(len(diff)):
                if diff[i] > 0.01:
                    print(f'    关节{i}: 期望={expected[i]:.3f}, 实际={filtered[i]:.3f}, 差值={diff[i]:.3f}')

    def check_data_variation(self, name, data_queue):
        """检查数据是否有变化"""
        if len(data_queue) < 2:
            print(f'  {name:15s} - 样本不足')
            return

        # 计算最近10个样本的标准差
        data_array = np.array(list(data_queue))
        std = np.std(data_array, axis=0)
        max_std = np.max(std)

        if max_std < 0.1:
            print(f'  ⚠ {name:15s} - 数据几乎不变 (std={max_std:.3f})')
            print(f'    提示: 请移动遥操臂以产生数据变化')
        else:
            print(f'  ✓ {name:15s} - 数据正常变化 (std={max_std:.3f})')

def main():
    rclpy.init()
    validator = DataFlowValidator()

    print('\n提示:')
    print('  1. 确保已启动 LinkerTA 节点')
    print('  2. 确保已启动左右臂滤波节点')
    print('  3. 移动遥操臂以产生数据变化')
    print('  4. 观察验证结果')
    print('\n按 Ctrl+C 停止\n')

    try:
        rclpy.spin(validator)
    except KeyboardInterrupt:
        print('\n\n验证完成')
    finally:
        validator.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()