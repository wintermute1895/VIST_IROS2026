#!/usr/bin/env python3
"""
角度单位诊断工具
检查VIST数据流中的角度单位是否一致
"""

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
import time

class AngleUnitDiagnostic(Node):
    def __init__(self):
        super().__init__('angle_unit_diagnostic')

        print("=" * 70)
        print("VIST 角度单位诊断工具")
        print("=" * 70)
        print("\n检查以下话题的角度单位:")
        print("  1. /robot1/left_arm/exo_hand_joint_control (外骨骼输入)")
        print("  2. /robot1/left_arm/vision_joint_control (视觉输入)")
        print("  3. /robot1/left_arm/joint_states (机械臂反馈)")
        print("  4. /filtered_left_joint_control (滤波输出)")
        print("\n等待数据...\n")

        # 数据存储
        self.data = {
            'exo': {'values': None, 'time': None, 'topic': '/robot1/left_arm/exo_hand_joint_control'},
            'vision': {'values': None, 'time': None, 'topic': '/robot1/left_arm/vision_joint_control'},
            'robot': {'values': None, 'time': None, 'topic': '/robot1/left_arm/joint_states'},
            'filtered': {'values': None, 'time': None, 'topic': '/filtered_left_joint_control'},
        }

        # 订阅所有话题
        self.create_subscription(JointState, '/robot1/left_arm/exo_hand_joint_control',
                                lambda msg: self.callback('exo', msg), 10)
        self.create_subscription(JointState, '/robot1/left_arm/vision_joint_control',
                                lambda msg: self.callback('vision', msg), 10)
        self.create_subscription(JointState, '/robot1/left_arm/joint_states',
                                lambda msg: self.callback('robot', msg), 10)
        self.create_subscription(JointState, '/filtered_left_joint_control',
                                lambda msg: self.callback('filtered', msg), 10)

        # 定时打印诊断信息
        self.create_timer(2.0, self.print_diagnostic)

    def callback(self, source, msg):
        """接收数据"""
        if len(msg.position) >= 7:
            self.data[source]['values'] = np.array(msg.position[:7])
            self.data[source]['time'] = time.time()

    def analyze_unit(self, values):
        """分析角度单位"""
        if values is None:
            return "无数据", None

        max_val = np.max(np.abs(values))
        mean_val = np.mean(np.abs(values))

        # 判断单位
        if max_val > 10:
            unit = "角度 (degree)"
            confidence = "高"
        elif max_val > 6.28:  # > 2π
            unit = "可能是角度"
            confidence = "中"
        elif max_val < 6.28:
            unit = "弧度 (radian)"
            confidence = "高"
        else:
            unit = "未知"
            confidence = "低"

        return unit, {
            'max': max_val,
            'mean': mean_val,
            'confidence': confidence
        }

    def print_diagnostic(self):
        """打印诊断信息"""
        print("\n" + "=" * 70)
        print(f"诊断时间: {time.strftime('%H:%M:%S')}")
        print("=" * 70)

        has_data = False
        issues = []

        for source, info in self.data.items():
            values = info['values']
            topic = info['topic']

            if values is None:
                print(f"\n[{source.upper()}] {topic}")
                print(f"  状态: ⚠️  无数据")
                continue

            has_data = True
            unit, stats = self.analyze_unit(values)

            # 检查数据新鲜度
            age = time.time() - info['time']
            fresh = "✓" if age < 1.0 else "⚠️ "

            print(f"\n[{source.upper()}] {topic}")
            print(f"  状态: {fresh} 数据年龄: {age:.2f}s")
            print(f"  单位: {unit} (置信度: {stats['confidence']})")
            print(f"  数值范围: max={stats['max']:.3f}, mean={stats['mean']:.3f}")
            print(f"  关节角度: [{', '.join([f'{v:.3f}' for v in values])}]")

            # 检测问题
            if "角度" in unit and source == 'filtered':
                issues.append(f"⚠️  {source}: 滤波输出应该是弧度，但检测到可能是角度！")

        # 单位一致性检查
        if has_data:
            print("\n" + "-" * 70)
            print("单位一致性检查:")

            units = {}
            for source, info in self.data.items():
                if info['values'] is not None:
                    unit, _ = self.analyze_unit(info['values'])
                    units[source] = unit

            # 检查是否所有源都使用相同单位
            unique_units = set(units.values())
            if len(unique_units) > 1:
                print(f"  ⚠️  检测到不同的角度单位:")
                for source, unit in units.items():
                    print(f"     {source}: {unit}")
                issues.append("不同数据源使用了不同的角度单位！")
            else:
                print(f"  ✓ 所有数据源使用相同单位: {list(unique_units)[0]}")

        # 显示问题
        if issues:
            print("\n" + "=" * 70)
            print("⚠️  发现问题:")
            for issue in issues:
                print(f"  {issue}")
            print("\n建议:")
            print("  1. 检查 vist_filter_node.py 中的单位转换逻辑")
            print("  2. 确认输入数据的单位（外骨骼、视觉）")
            print("  3. 确认 pinocchio 使用弧度")
            print("  4. 检查可视化脚本是否需要单位转换")
        else:
            if has_data:
                print("\n✓ 未发现明显的单位不一致问题")

        print("=" * 70)

def main():
    rclpy.init()
    node = AngleUnitDiagnostic()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n\n诊断结束")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()