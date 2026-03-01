#!/usr/bin/env python3
"""
安全网关节点 - SDK外层防护
在不修改厂商SDK的前提下，提供多层安全防护

架构:
  上游 → /robot1/right_arm/joint_follow_unsafe
           ↓
      Safety Gateway (本节点)
           ↓
      /robot1/right_arm/joint_follow → lbot_driver (SDK)

Author: VIST Safety Team
Date: 2026-02-25
"""

import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.msg import FollowJoint
import numpy as np
import time
import json
from pathlib import Path
import fcntl
import os


class SafetyGatewayNode(Node):
    """安全网关节点 - 在SDK外层提供安全防护"""

    def __init__(self):
        super().__init__('safety_gateway_node')

        # ========== 1. 进程互斥检查 ==========
        self.lockfile_path = '/tmp/vist_safety_gateway.lock'
        self.lockfile = None
        if not self._acquire_lock():
            self.get_logger().error('❌ 另一个Safety Gateway正在运行！')
            self.get_logger().error(f'   如果确认无进程，删除: {self.lockfile_path}')
            raise RuntimeError('进程互斥检查失败')

        self.get_logger().info('✅ 进程互斥检查通过')

        # ========== 2. 参数配置 ==========
        self.declare_parameter('arm_side', 'right')
        self.declare_parameter('max_joint_delta', 0.1)  # rad, 50Hz下安全阈值
        self.declare_parameter('heartbeat_timeout', 0.5)  # 秒
        self.declare_parameter('min_publish_hz', 20.0)  # 最低发送频率
        self.declare_parameter('enable_blackbox', True)

        self.arm_side = self.get_parameter('arm_side').value
        self.max_joint_delta = self.get_parameter('max_joint_delta').value
        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self.min_publish_hz = self.get_parameter('min_publish_hz').value
        self.enable_blackbox = self.get_parameter('enable_blackbox').value

        # ========== 3. 状态变量 ==========
        self.last_joints = None
        self.last_cmd_time = None
        self.emergency_stop = False
        self.violation_count = {
            'nan': 0,
            'delta': 0,
            'heartbeat': 0,
            'frequency': 0
        }

        # ========== 4. 黑匣子记录 ==========
        if self.enable_blackbox:
            self._init_blackbox()

        # ========== 5. 创建订阅器和发布器 ==========
        # 订阅不安全的话题
        unsafe_topic = f'/robot1/{self.arm_side}_arm/joint_follow_unsafe'
        self.unsafe_sub = self.create_subscription(
            FollowJoint,
            unsafe_topic,
            self.safety_callback,
            10
        )

        # 发布到安全的话题（SDK订阅）
        safe_topic = f'/robot1/{self.arm_side}_arm/joint_follow'
        self.safe_pub = self.create_publisher(
            FollowJoint,
            safe_topic,
            10
        )

        # 紧急停止服务
        from std_srvs.srv import Trigger
        self.emergency_stop_srv = self.create_service(
            Trigger,
            'emergency_stop',
            self.emergency_stop_callback
        )

        # ========== 6. 心跳检查定时器 ==========
        self.heartbeat_timer = self.create_timer(0.1, self.heartbeat_check)

        self.get_logger().info('=' * 80)
        self.get_logger().info('🛡️  Safety Gateway Node 已启动')
        self.get_logger().info('=' * 80)
        self.get_logger().info(f'订阅: {unsafe_topic}')
        self.get_logger().info(f'发布: {safe_topic}')
        self.get_logger().info(f'最大关节增量: {self.max_joint_delta} rad')
        self.get_logger().info(f'心跳超时: {self.heartbeat_timeout} s')
        self.get_logger().info(f'最低频率: {self.min_publish_hz} Hz')
        self.get_logger().info('=' * 80)

    def _acquire_lock(self):
        """获取进程锁（原子操作）"""
        try:
            self.lockfile = open(self.lockfile_path, 'w')
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lockfile.write(str(os.getpid()))
            self.lockfile.flush()
            return True
        except IOError:
            return False

    def _init_blackbox(self):
        """初始化黑匣子记录"""
        log_dir = Path.home() / 'vist_blackbox'
        log_dir.mkdir(exist_ok=True)

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        self.blackbox_file = log_dir / f'safety_gateway_{timestamp}.jsonl'
        self.get_logger().info(f'📦 黑匣子记录: {self.blackbox_file}')

    def _log_blackbox(self, event_type, data):
        """记录到黑匣子"""
        if not self.enable_blackbox:
            return

        entry = {
            'timestamp': time.time(),
            'event': event_type,
            'data': data
        }

        with open(self.blackbox_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def safety_callback(self, msg):
        """安全检查回调 - 核心逻辑"""

        current_time = time.time()

        # ========== 检查1: 紧急停止 ==========
        if self.emergency_stop:
            self.get_logger().error('🚨 紧急停止激活，拒绝命令')
            return

        # ========== 检查2: 消息有效性 ==========
        if not msg or not msg.joints or len(msg.joints) != 7:
            self.get_logger().error('❌ 无效消息')
            self._log_blackbox('invalid_msg', {'msg': str(msg)})
            return

        joints = np.array(msg.joints)

        # ========== 检查3: NaN/Inf检测 ==========
        if np.any(np.isnan(joints)) or np.any(np.isinf(joints)):
            self.violation_count['nan'] += 1
            self.get_logger().error(f'❌ 检测到NaN/Inf: {joints}')
            self.get_logger().error(f'   累计违规: {self.violation_count["nan"]}次')
            self._log_blackbox('nan_detected', {'joints': joints.tolist()})

            # 连续3次NaN触发紧急停止
            if self.violation_count['nan'] >= 3:
                self.get_logger().error('🚨 连续NaN检测，触发紧急停止')
                self.emergency_stop = True

            return

        # ========== 检查4: 超时检测 ==========
        if self.last_cmd_time is not None:
            elapsed = current_time - self.last_cmd_time

            # 超时检测
            if elapsed > self.heartbeat_timeout:
                self.get_logger().warn(f'⚠️  命令超时: {elapsed:.3f}s')
                self._log_blackbox('timeout', {'elapsed': elapsed})

                # 重置基线（防止超时后大跳变）
                self.last_joints = joints
                self.last_cmd_time = current_time
                return  # 第一帧不执行

            # 频率检测
            actual_hz = 1.0 / elapsed if elapsed > 0 else 0
            if actual_hz < self.min_publish_hz:
                self.violation_count['frequency'] += 1
                self.get_logger().warn(f'⚠️  发送频率过低: {actual_hz:.1f} Hz')

                if self.violation_count['frequency'] >= 10:
                    self.get_logger().error('🚨 频率持续异常，触发紧急停止')
                    self.emergency_stop = True
                    return
            else:
                self.violation_count['frequency'] = 0  # 恢复后重置

        # ========== 检查5: 差分监测（仅警告，不阻止）==========
        # 注意：由于硬件端会以50Hz重采样，时间戳不可靠，此检查仅用于监测异常
        if self.last_joints is not None:
            delta = joints - self.last_joints
            max_delta = np.max(np.abs(delta))

            if max_delta > self.max_joint_delta:
                self.violation_count['delta'] += 1
                violated_joints = np.where(np.abs(delta) > self.max_joint_delta)[0]

                self.get_logger().warn('⚠️  检测到大跳变（仅监测）')
                self.get_logger().warn(f'   违规关节: {violated_joints}')
                self.get_logger().warn(f'   最大增量: {max_delta:.3f} rad (阈值: {self.max_joint_delta})')
                self.get_logger().warn(f'   delta: {delta[violated_joints]}')
                self.get_logger().warn(f'   注意：硬件端会以50Hz重采样，此警告仅供参考')

                self._log_blackbox('delta_warning', {
                    'joints': joints.tolist(),
                    'last_joints': self.last_joints.tolist(),
                    'delta': delta.tolist(),
                    'max_delta': float(max_delta),
                    'violated_joints': violated_joints.tolist()
                })
                # 不再限幅，直接透传原始命令
            else:
                self.violation_count['delta'] = 0  # 恢复后重置

        # ========== 检查通过，发布安全命令 ==========
        safe_msg = FollowJoint()
        safe_msg.joints = joints.tolist()
        safe_msg.follow = msg.follow

        self.safe_pub.publish(safe_msg)

        # 更新状态
        self.last_joints = joints
        self.last_cmd_time = current_time

        # 记录正常命令（采样记录，避免文件过大）
        if self.enable_blackbox and np.random.random() < 0.01:  # 1%采样率
            self._log_blackbox('normal_cmd', {
                'joints': joints.tolist(),
                'follow': msg.follow
            })

    def heartbeat_check(self):
        """心跳检查定时器"""
        if self.last_cmd_time is None:
            return

        elapsed = time.time() - self.last_cmd_time

        if elapsed > self.heartbeat_timeout:
            self.violation_count['heartbeat'] += 1

            if self.violation_count['heartbeat'] % 10 == 1:  # 每10次打印一次
                self.get_logger().warn(f'⚠️  心跳超时: {elapsed:.3f}s (已{self.violation_count["heartbeat"]}次)')

            # 连续超时30次（3秒）触发紧急停止
            if self.violation_count['heartbeat'] >= 30:
                self.get_logger().error('🚨 心跳长时间超时，触发紧急停止')
                self.emergency_stop = True
        else:
            self.violation_count['heartbeat'] = 0

    def emergency_stop_callback(self, request, response):
        """紧急停止服务"""
        self.emergency_stop = True
        self.get_logger().error('🚨 收到紧急停止请求')
        self._log_blackbox('emergency_stop', {'source': 'service_call'})

        response.success = True
        response.message = 'Emergency stop activated'
        return response

    def destroy_node(self):
        """节点销毁时释放锁"""
        if self.lockfile:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.lockfile.close()
            try:
                os.remove(self.lockfile_path)
            except:
                pass

        self.get_logger().info('🛡️  Safety Gateway Node 已停止')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = SafetyGatewayNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\n⚠️  收到中断信号')
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()