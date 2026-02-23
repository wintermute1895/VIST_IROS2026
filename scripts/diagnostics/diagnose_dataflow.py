#!/usr/bin/env python3
"""
真机 vs 仿真数据流对比诊断

对比真机和仿真的完整控制流程，找出差异
"""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config

def main():
    print("=" * 80)
    print("🔍 真机 vs 仿真数据流对比诊断")
    print("=" * 80)

    config = get_config()

    print("\n" + "=" * 80)
    print("📊 数据流对比")
    print("=" * 80)

    print("\n【仿真流程】(simulate_full_flow.py):")
    print("  1. UDP接收视觉数据 → packet")
    print("  2. 提取关键点: human_kps = packet['keypoints']")
    print("  3. 运动映射: mapper.human_to_robot(human_kps) → (target_pos, target_quat)")
    print("  4. VIST求解: solver.solve(target_pos, target_quat, q_init, elbow_pos, shoulder_pos)")
    print("  5. 扩展到完整模型: q_full[controlled_indices] = q_solution")
    print("  6. 更新可视化: visualizer.update(q_full)")
    print("  ❌ 没有安全控制器")
    print("  ❌ 没有速度/加速度限制")
    print("  ❌ 没有关节锁定")

    print("\n【真机流程】(run_real_robot_vist_refactored.py):")
    print("  1. UDP接收视觉数据 → packet")
    print("  2. 提取关键点: human_keypoints = packet['keypoints']")
    print("  3. VIST控制器处理: controller.process(human_keypoints)")
    print("     3.1 运动映射: mapper.human_to_robot(human_keypoints)")
    print("     3.2 VIST求解: vist_filter.solve(...)")
    print("     3.3 安全控制: safety_controller.process_command(q_solution)")
    print("  4. 关节锁定: q_command[i] = q_init[i] if not joint_enabled[i]")
    print("  5. 发送到真机: robot.send_command(q_command)")
    print("  ✅ 有安全控制器（速度/加速度限制）")
    print("  ✅ 有关节锁定功能")

    print("\n" + "=" * 80)
    print("🔑 关键差异")
    print("=" * 80)

    print("\n1. 【安全控制器】")
    print(f"   仿真: 无")
    print(f"   真机: 有（速度限制={config.max_joint_velocity} rad/s, 加速度限制={config.max_joint_acceleration} rad/s²）")
    print(f"   影响: 真机运动会被限制，可能导致延迟和不跟手")

    print("\n2. 【硬件延迟】")
    print(f"   仿真: 无延迟，直接更新可视化")
    print(f"   真机: 有延迟（TCP通信 + 电机响应 + 轨迹规划）")
    print(f"   影响: 真机响应慢于仿真")

    print("\n3. 【重力补偿】")
    print(f"   仿真: 无重力影响")
    print(f"   真机: 受重力影响，末端负载会导致下垂")
    print(f"   影响: 真机姿态可能偏离目标")

    print("\n4. 【控制频率】")
    print(f"   仿真: 尽可能快（受限于UDP接收）")
    print(f"   真机: {1.0/config.control_dt:.1f} Hz")
    print(f"   影响: 真机更新频率可能不够")

    print("\n5. 【关节锁定】")
    print(f"   配置: {config.robot_joint_enabled}")
    locked = [i for i, enabled in enumerate(config.robot_joint_enabled) if not enabled]
    if locked:
        print(f"   锁定关节: {locked}")
    else:
        print(f"   所有关节使能")

    print("\n" + "=" * 80)
    print("⚠️  可能的问题原因")
    print("=" * 80)

    issues = []

    # 1. 速度限制太低
    if config.max_joint_velocity < 0.5:
        issues.append({
            'title': '速度限制过低',
            'current': f'{config.max_joint_velocity} rad/s',
            'suggestion': '提高到 0.5-0.8 rad/s',
            'impact': '运动缓慢，不跟手'
        })

    # 2. 控制频率太低
    if 1.0/config.control_dt < 15:
        issues.append({
            'title': '控制频率过低',
            'current': f'{1.0/config.control_dt:.1f} Hz',
            'suggestion': '提高到 15-20 Hz',
            'impact': '关节颤动，响应不平滑'
        })

    # 3. 没有重力补偿
    issues.append({
        'title': '缺少重力补偿',
        'current': '无',
        'suggestion': '添加重力补偿或使用力矩控制',
        'impact': '末端下垂，姿态不准确'
    })

    # 4. 安全控制器延迟
    issues.append({
        'title': '安全控制器引入延迟',
        'current': '速度/加速度限制',
        'suggestion': '调整限制参数或优化算法',
        'impact': '响应延迟，不跟手'
    })

    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue['title']}")
        print(f"   当前: {issue['current']}")
        print(f"   建议: {issue['suggestion']}")
        print(f"   影响: {issue['impact']}")

    print("\n" + "=" * 80)
    print("🔧 建议的调试步骤")
    print("=" * 80)
    print("\n1. 验证关节锁定功能是否生效")
    print("   - 设置只使能 Joint 0")
    print("   - 运行真机控制，观察其他关节是否保持不动")
    print("\n2. 逐步提高速度限制")
    print("   - 从 0.3 → 0.5 → 0.8 rad/s")
    print("   - 观察运动是否更跟手")
    print("\n3. 提高控制频率")
    print("   - 从 10 Hz → 15 Hz → 20 Hz")
    print("   - 观察颤动是否减少")
    print("\n4. 对比关节角度输出")
    print("   - 在仿真和真机中打印相同输入下的关节角度")
    print("   - 验证计算逻辑是否一致")
    print("\n5. 添加重力补偿")
    print("   - 在目标角度上添加重力补偿偏移")
    print("   - 或使用力矩控制模式")

    print("\n" + "=" * 80)
    print("⚠️  注意事项")
    print("=" * 80)
    print("\n- 电机发热说明负载过大或控制频率过高")
    print("- 建议让电机休息后再继续测试")
    print("- 逐步调整参数，不要一次改太多")
    print("- 每次调整后观察效果，记录数据")

if __name__ == "__main__":
    main()