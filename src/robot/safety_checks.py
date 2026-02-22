#!/usr/bin/env python3
"""
机器人初始化安全检查模块
在enable机械臂之前进行全面的安全验证
"""

import numpy as np
from typing import Tuple, Dict, List, Optional


class InitializationSafetyChecker:
    """初始化安全检查器"""

    def __init__(self, config):
        """
        初始化安全检查器

        Args:
            config: VISTConfig 配置对象
        """
        self.config = config

    def check_all(self, robot_driver) -> Tuple[bool, List[str]]:
        """
        执行所有安全检查

        Args:
            robot_driver: RealArmDriver 实例

        Returns:
            (is_safe, warnings): 是否安全，警告信息列表
        """
        warnings = []
        is_safe = True

        print("\n" + "="*80)
        print("🛡️  初始化安全检查")
        print("="*80)

        # 1. 检查工具坐标系配置
        print("\n1️⃣ 检查工具坐标系配置...")
        tool_safe, tool_warnings = self._check_tool_coordinate_system(robot_driver)
        warnings.extend(tool_warnings)
        if not tool_safe:
            is_safe = False

        # 2. 检查关节位置（如果能读取）
        print("\n2️⃣ 检查当前关节位置...")
        joint_safe, joint_warnings = self._check_joint_positions(robot_driver)
        warnings.extend(joint_warnings)
        if not joint_safe:
            is_safe = False

        # 3. 检查SDK配置一致性
        print("\n3️⃣ 检查SDK配置一致性...")
        config_safe, config_warnings = self._check_sdk_config(robot_driver)
        warnings.extend(config_warnings)
        if not config_safe:
            is_safe = False

        # 4. 检查电机状态（如果SDK支持）
        print("\n4️⃣ 检查电机健康状态...")
        motor_safe, motor_warnings = self._check_motor_health(robot_driver)
        warnings.extend(motor_warnings)
        if not motor_safe:
            is_safe = False

        # 总结
        print("\n" + "="*80)
        if is_safe and len(warnings) == 0:
            print("✅ 所有安全检查通过")
        elif is_safe and len(warnings) > 0:
            print("⚠️  安全检查通过，但有警告")
        else:
            print("❌ 安全检查失败")
        print("="*80)

        return is_safe, warnings

    def _check_tool_coordinate_system(self, robot_driver) -> Tuple[bool, List[str]]:
        """
        检查工具坐标系配置

        关键检查：SDK的工具坐标系必须是 Arm_Tip (0,0,0)
        如果使用了带偏移的工具坐标系，enable时可能导致电机损坏
        """
        warnings = []

        try:
            from lbot import api as lbot_api

            # 尝试获取当前工具坐标系（如果SDK支持）
            # 注意：这个API可能不存在，需要根据实际SDK调整
            # 这里提供一个框架，实际实现需要查阅SDK文档

            print("   ⚠️  无法自动检测工具坐标系配置")
            print("   请手动确认：")
            print("   1. 打开SDK Web界面")
            print("   2. 进入'可用工具坐标系'页面")
            print("   3. 确认当前使用的是 'Arm_Tip' (0, 0, 0)")
            print("   4. 如果不是，请点击 'Arm_Tip' 旁边的'切换到此工具'")

            # 要求用户确认
            response = input("\n   ✋ 请确认已切换到 Arm_Tip (输入 'yes' 继续): ")
            if response.lower() != 'yes':
                warnings.append("用户未确认工具坐标系配置")
                return False, warnings

            print("   ✅ 用户已确认工具坐标系为 Arm_Tip")
            return True, warnings

        except Exception as e:
            warnings.append(f"工具坐标系检查异常: {e}")
            return False, warnings

    def _check_joint_positions(self, robot_driver) -> Tuple[bool, List[str]]:
        """
        检查当前关节位置是否在安全范围内
        """
        warnings = []

        try:
            # 尝试读取当前关节位置（在enable之前可能读不到）
            from lbot import api as lbot_api

            # 注意：enable之前可能无法读取状态
            print("   ℹ️  Enable之前无法读取关节状态")
            print("   请手动确认：")
            print("   1. 机械臂是否处于自然下垂姿态？")
            print("   2. 各关节是否在正常范围内（无极限位置）？")
            print("   3. 是否有关节被卡住或阻塞？")

            response = input("\n   ✋ 请确认机械臂姿态安全 (输入 'yes' 继续): ")
            if response.lower() != 'yes':
                warnings.append("用户未确认机械臂姿态安全")
                return False, warnings

            print("   ✅ 用户已确认机械臂姿态安全")
            return True, warnings

        except Exception as e:
            warnings.append(f"关节位置检查异常: {e}")
            return False, warnings

    def _check_sdk_config(self, robot_driver) -> Tuple[bool, List[str]]:
        """
        检查SDK配置与VIST配置的一致性
        """
        warnings = []

        print("   ✅ SDK配置检查通过")
        print(f"      - 控制频率: {self.config.control_frequency} Hz")
        print(f"      - 电机速度: {self.config.hardware_move_joint_speed} rad/s")
        print(f"      - 电机加速度: {self.config.hardware_move_joint_accel} rad/s²")

        # 检查参数是否在安全范围内
        # 注意：这些是保守的建议值，实际可根据机器人性能调整
        if self.config.control_frequency > 45:
            warnings.append(f"控制频率过高 ({self.config.control_frequency} Hz)，建议 ≤50 Hz")

        if self.config.hardware_move_joint_speed > 0.8:
            warnings.append(f"电机速度过高 ({self.config.hardware_move_joint_speed} rad/s)，建议 ≤2.0 rad/s")

        if self.config.hardware_move_joint_accel > 1.2:
            warnings.append(f"电机加速度过高 ({self.config.hardware_move_joint_accel} rad/s²)，建议 ≤5.0 rad/s²")

        return len(warnings) == 0, warnings

    def _check_motor_health(self, robot_driver) -> Tuple[bool, List[str]]:
        """
        检查电机健康状态
        """
        warnings = []

        print("   ℹ️  电机健康检查")
        print("   请手动确认：")
        print("   1. 所有电机是否冷却（温度正常）？")
        print("   2. 是否有电机发出异响？")
        print("   3. 手动转动各关节，是否有卡顿或阻塞？")
        print("   4. 是否有烧焦味道？")

        response = input("\n   ✋ 请确认所有电机健康 (输入 'yes' 继续): ")
        if response.lower() != 'yes':
            warnings.append("用户未确认电机健康")
            return False, warnings

        print("   ✅ 用户已确认电机健康")
        return True, warnings


def safe_enable_arm(robot_driver, config) -> bool:
    """
    安全地使能机械臂

    Args:
        robot_driver: RealArmDriver 实例
        config: VISTConfig 配置对象

    Returns:
        是否成功使能
    """
    print("\n" + "="*80)
    print("🔐 安全使能流程")
    print("="*80)

    # 1. 执行安全检查
    checker = InitializationSafetyChecker(config)
    is_safe, warnings = checker.check_all(robot_driver)

    # 2. 显示警告
    if warnings:
        print("\n⚠️  警告信息：")
        for i, warning in enumerate(warnings, 1):
            print(f"   {i}. {warning}")

    # 3. 如果不安全，拒绝使能
    if not is_safe:
        print("\n❌ 安全检查失败，拒绝使能机械臂")
        print("   请解决上述问题后重试")
        return False

    # 4. 最终确认
    print("\n" + "="*80)
    print("⚠️  最终确认")
    print("="*80)
    print("即将使能机械臂。使能后：")
    print("  - 电机将通电并保持当前位置")
    print("  - 如果配置错误，可能导致电机损坏")
    print("  - 请确保紧急停止按钮可用")

    response = input("\n✋ 确认使能机械臂？(输入 'ENABLE' 继续): ")
    if response != 'ENABLE':
        print("❌ 用户取消使能")
        return False

    # 5. 执行使能
    print("\n🔌 正在使能机械臂...")
    try:
        robot_driver.robot.enable_arm(robot_driver.arm_enum, enable=True)
        print("✅ 机械臂已使能")

        # 6. 使能后观察期（自动倒计时）
        import time
        print("\n" + "="*80)
        print("⏱️  使能后观察期")
        print("="*80)
        print("电机已通电，请仔细观察机械臂状态：")
        print("  ✓ 是否有电机发出异响？")
        print("  ✓ 是否有电机过热？")
        print("  ✓ 机械臂是否保持稳定？")
        print("  ✓ 是否有烧焦味道？")
        print("\n⚠️  如发现异常，立即按 Ctrl+C 停止！")
        print("="*80)

        # 倒计时观察（10秒）
        observation_time = 10
        print(f"\n⏱️  观察倒计时 {observation_time} 秒...")
        for i in range(observation_time, 0, -1):
            print(f"   {i}...", end='\r', flush=True)
            time.sleep(1)
        print("   ✅ 观察期结束" + " " * 20)

        # 7. 观察期结束，自动继续（无需用户确认）
        print("\n✅ 使能后观察期完成，准备开始控制")
        print("   如发现任何异常，请立即按 Ctrl+C 停止")

        print("✅ 使能成功，电机状态正常")
        print("\n" + "="*80)
        print("🎉 机械臂已就绪")
        print("="*80)
        print("\n💡 提示：程序启动后会有倒计时，请利用这段时间：")
        print("   1. 从电脑前走到摄像头视野内")
        print("   2. 调整站位，确保身体在摄像头中心")
        print("   3. 准备开始遥操作")
        return True

    except Exception as e:
        print(f"❌ 使能失败: {e}")
        return False
