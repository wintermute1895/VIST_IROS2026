import time
import numpy as np
import socket
import json

# 引用 core (大脑)
from src.core.estimator import IntentAdaptiveEstimator
from src.core.intent import IntentInference
from src.core.motion_mapper import ArmMotionMapper
from src.core.pink_ik_solver import PinkIKSolver  # 使用 Pink IK 求解器
from src.core.one_euro_filter import VectorOneEuroFilter, QuaternionOneEuroFilter  # One Euro 滤波器

# 引用 driver (手脚)
from src.robot.arm_driver import MockArmDriver

# 引用可视化
from src.robot.viz_server import RobotVisualizer


class ArmNode:
    def __init__(self, visualize=True, dof=7, udp_port=6001):
        """
        初始化手臂控制节点
        :param visualize: 是否启用 MeshCat 可视化
        :param dof: 自由度数量
        :param udp_port: UDP 接收端口（用于接收人体关键点数据）
        """
        print("🤖 [ArmNode] 初始化手臂控制节点...")

        # 1. 初始化驱动器（使用 Mock 模式进行仿真）
        self.driver = MockArmDriver(dof=dof)
        self.driver.connect()

        # 2. 初始化核心算法组件
        self.estimator = IntentAdaptiveEstimator(dt=0.01)
        self.intent = IntentInference()

        # 3. 初始化运动映射器
        print("🧠 [ArmNode] 初始化运动映射器...")
        self.mapper = ArmMotionMapper(
            robot_shoulder_pos=[0.0, -0.096, 1.217],  # 右臂肩部在基座坐标系中的位置（从URDF提取）
            arm_lengths={'upper': 0.2908, 'fore': 0.2366}  # 臂长（米，从URDF提取）
        )
        # 设置滤波器参数（可选）
        self.mapper.set_filter_alpha(0.5)  # 中等平滑

        # 4. 初始化逆运动学求解器（使用 Pink 分层优化）
        print("🧠 [ArmNode] 初始化逆运动学求解器（Pink）...")
        self.ik_solver = PinkIKSolver()

        # 初始化关节命令（从 IK 求解器获取中立位置）
        self.q_cmd = self.ik_solver.q.copy()
        self.q_cmd_prev = self.q_cmd.copy()  # 用于速度限制
        print(f"✅ [ArmNode] IK 求解器初始化完成，关节数: {len(self.q_cmd)}")

        # 4.5 初始化 One Euro 滤波器（用于平滑目标位姿）
        print("🧠 [ArmNode] 初始化 One Euro 滤波器...")
        # 位置滤波器：较强的平滑（min_cutoff=0.5Hz）
        self.pos_filter = VectorOneEuroFilter(
            min_cutoff=0.5,  # 低速时强平滑
            beta=0.01,       # 对速度变化的响应
            d_cutoff=1.0     # 速度估计的平滑
        )
        # 姿态滤波器：中等平滑
        self.quat_filter = QuaternionOneEuroFilter(
            min_cutoff=0.8,  # 姿态可以稍微响应快一点
            beta=0.01,
            d_cutoff=1.0
        )
        print("✅ [ArmNode] One Euro 滤波器初始化完成")

        # 速度限制参数（安全保护）
        self.max_joint_velocity = 0.1  # rad/s（降低到0.1以确保安全）
        self.max_joint_acceleration = 1.0  # rad/s²
        print(f"⚠️  [ArmNode] 安全限制: 最大关节速度 = {self.max_joint_velocity} rad/s")

        # 5. 初始化 UDP 接收器（用于接收人体关键点数据）
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", self.udp_port))
        self.sock.setblocking(False)  # 非阻塞模式
        print(f"📡 [ArmNode] UDP 接收器已启动，端口: {self.udp_port}")

        # 存储最新的人体关键点数据
        self.latest_human_kps = None
        self.last_data_timestamp = None  # 最后接收数据的时间戳
        self.data_timeout = 0.5  # 数据过期阈值（秒）

        # IK 失败计数器（安全保护）
        self.ik_failure_count = 0
        self.max_ik_failures = 5  # 连续失败阈值

        # 6. 初始化可视化器（可选）
        self.visualize = visualize
        self.viz = None
        if self.visualize:
            try:
                print("🖥️ [ArmNode] 启动 MeshCat 可视化...")
                self.viz = RobotVisualizer()
                self._setup_target_frame_visualization()
                print("✅ [ArmNode] 可视化器初始化成功")
            except Exception as e:
                print(f"⚠️ [ArmNode] 可视化器初始化失败: {e}")
                print("   继续运行但不显示可视化")
                self.visualize = False

        print("✅ [ArmNode] 初始化完成")

    def _setup_target_frame_visualization(self):
        """设置目标坐标系的可视化（在 MeshCat 中显示坐标轴）"""
        if self.viz is None:
            return

        try:
            import meshcat.geometry as g

            # 创建坐标轴（X=红色, Y=绿色, Z=蓝色）
            # 增大尺寸以便更容易看到
            axis_length = 0.15  # 坐标轴长度（米）- 增大到15cm
            axis_radius = 0.008  # 坐标轴半径 - 增大到8mm

            # X 轴（红色）
            self.viz.viz.viewer["target_frame/x_axis"].set_object(
                g.Cylinder(axis_length, axis_radius),
                g.MeshLambertMaterial(color=0xff0000)
            )
            # Y 轴（绿色）
            self.viz.viz.viewer["target_frame/y_axis"].set_object(
                g.Cylinder(axis_length, axis_radius),
                g.MeshLambertMaterial(color=0x00ff00)
            )
            # Z 轴（蓝色）
            self.viz.viz.viewer["target_frame/z_axis"].set_object(
                g.Cylinder(axis_length, axis_radius),
                g.MeshLambertMaterial(color=0x0000ff)
            )

            # 初始位置设置为原点附近（便于调试）
            # 注意：这会在收到第一帧数据后被更新
            initial_pos = np.array([0.3, 0.0, 0.3])  # 在机器人前方
            print(f"🎯 [ArmNode] 目标坐标系初始位置: {initial_pos}")

            # 创建一个简单的初始变换（单位矩阵）
            T_init = np.eye(4)
            T_init[:3, 3] = initial_pos

            # 为每个轴设置初始位置
            for axis_name in ['x_axis', 'y_axis', 'z_axis']:
                self.viz.viz.viewer[f"target_frame/{axis_name}"].set_transform(T_init)

            print("✅ [ArmNode] 目标坐标系可视化已设置（增大尺寸）")
        except Exception as e:
            print(f"⚠️ [ArmNode] 设置目标坐标系可视化失败: {e}")
            import traceback
            traceback.print_exc()

    def _display_target_frame(self, position, quaternion):
        """
        在 MeshCat 中显示目标坐标系
        :param position: 3D 位置 [x, y, z]
        :param quaternion: 四元数 [x, y, z, w]
        """
        if self.viz is None:
            return

        try:
            from scipy.spatial.transform import Rotation

            # 将四元数转换为旋转矩阵
            rot = Rotation.from_quat(quaternion)
            R = rot.as_matrix()

            # 提取各个轴的方向向量
            x_axis = R[:, 0]  # X轴方向
            y_axis = R[:, 1]  # Y轴方向
            z_axis = R[:, 2]  # Z轴方向

            axis_length = 0.15  # 坐标轴长度（与初始化时一致）

            # 为每个轴创建变换矩阵
            # MeshCat 的 Cylinder 默认沿 Z 轴，所以我们需要旋转它

            # X 轴（红色）：需要将 Z 轴旋转到 X 轴方向
            T_x = self._axis_transform(position, x_axis, axis_length)
            self.viz.viz.viewer["target_frame/x_axis"].set_transform(T_x)

            # Y 轴（绿色）：需要将 Z 轴旋转到 Y 轴方向
            T_y = self._axis_transform(position, y_axis, axis_length)
            self.viz.viz.viewer["target_frame/y_axis"].set_transform(T_y)

            # Z 轴（蓝色）：需要将 Z 轴旋转到 Z 轴方向（可能需要旋转）
            T_z = self._axis_transform(position, z_axis, axis_length)
            self.viz.viz.viewer["target_frame/z_axis"].set_transform(T_z)

            # 调试：每60帧打印一次位置信息
            if not hasattr(self, '_viz_counter'):
                self._viz_counter = 0
            self._viz_counter += 1

            if self._viz_counter % 60 == 0:
                print(f"🎯 [Viz] 目标坐标系位置: {position}")
                print(f"   X轴方向: {x_axis}")
                print(f"   Y轴方向: {y_axis}")
                print(f"   Z轴方向: {z_axis}")

        except Exception as e:
            print(f"⚠️ [ArmNode] 显示目标坐标系失败: {e}")
            import traceback
            traceback.print_exc()

    def _axis_transform(self, position, direction, length):
        """
        创建一个坐标轴的变换矩阵
        :param position: 坐标系原点
        :param direction: 轴的方向向量（单位向量）
        :param length: 轴的长度
        :return: 4x4 变换矩阵
        """
        # 圆柱体的中心位置（沿着方向偏移半个长度）
        center = position + direction * (length / 2)

        # 构建旋转矩阵：将 Z 轴（圆柱体默认方向）旋转到目标方向
        # 使用 Rodrigues 旋转公式或者直接构建旋转矩阵

        # 默认方向是 Z 轴 [0, 0, 1]
        z_default = np.array([0, 0, 1])

        # 如果方向已经是 Z 轴，不需要旋转
        if np.allclose(direction, z_default):
            R = np.eye(3)
        elif np.allclose(direction, -z_default):
            # 如果方向是 -Z 轴，旋转 180 度
            R = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, -1]])
        else:
            # 计算旋转轴（叉乘）
            axis = np.cross(z_default, direction)
            axis = axis / np.linalg.norm(axis)

            # 计算旋转角度
            angle = np.arccos(np.clip(np.dot(z_default, direction), -1.0, 1.0))

            # 使用 Rodrigues 公式构建旋转矩阵
            from scipy.spatial.transform import Rotation
            R = Rotation.from_rotvec(axis * angle).as_matrix()

        # 构建 4x4 变换矩阵
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = center

        return T

    def spin_once(self):
        """单次控制循环"""
        # A. 听 (IO) - 接收人体关键点数据（UDP）
        self._receive_human_keypoints()

        # 检查数据是否过期
        if self.last_data_timestamp is not None:
            data_age = time.time() - self.last_data_timestamp
            if data_age > self.data_timeout:
                print(f"⚠️ [ArmNode] 数据过期 ({data_age*1000:.0f}ms)，停止运动")
                self.latest_human_kps = None  # 清除过期数据

        # B. 想 (Core Logic) - 运动映射
        if self.latest_human_kps is not None:
            try:
                # 使用 mapper 计算目标位姿
                result = self.mapper.human_to_robot(self.latest_human_kps)
                if result is None:
                    # 映射返回 None（奇异点），保持当前位置
                    _, q_curr, _ = self.driver.get_state()
                    q_cmd = q_curr
                    return

                target_pos, target_quat, debug_info = result

                # 调试：打印旋转矩阵信息（每30帧打印一次）
                if hasattr(self, '_debug_counter'):
                    self._debug_counter += 1
                else:
                    self._debug_counter = 0

                if self._debug_counter % 30 == 0:
                    R = debug_info['rotation_matrix']
                    print(f"\n🔍 [Debug] 旋转矩阵检查:")
                    print(f"   X轴: {debug_info['x_axis']}")
                    print(f"   Y轴: {debug_info['y_axis']}")
                    print(f"   Z轴: {debug_info['z_axis']}")
                    print(f"   正交性误差: {debug_info['orthogonality_error']:.2e}")
                    # 检查轴之间的点积（应该接近0）
                    dot_xy = np.dot(debug_info['x_axis'], debug_info['y_axis'])
                    dot_xz = np.dot(debug_info['x_axis'], debug_info['z_axis'])
                    dot_yz = np.dot(debug_info['y_axis'], debug_info['z_axis'])
                    print(f"   X·Y = {dot_xy:.6f} (应该≈0)")
                    print(f"   X·Z = {dot_xz:.6f} (应该≈0)")
                    print(f"   Y·Z = {dot_yz:.6f} (应该≈0)")

                # 可视化目标坐标系
                if self.visualize and self.viz is not None:
                    self._display_target_frame(target_pos, target_quat)

                # ==========================================
                # One Euro 滤波（平滑目标位姿）
                # ==========================================
                # 应用 One Euro Filter 到目标位姿
                target_pos_filtered = self.pos_filter(target_pos, time.time())
                target_quat_filtered = self.quat_filter(target_quat, time.time())

                # 同样滤波肘部位置
                elbow_pos = debug_info.get('elbow_pos', None)
                if elbow_pos is not None:
                    if not hasattr(self, 'elbow_filter'):
                        self.elbow_filter = VectorOneEuroFilter(
                            min_cutoff=0.5, beta=0.01, d_cutoff=1.0
                        )
                    elbow_pos_filtered = self.elbow_filter(elbow_pos, time.time())
                else:
                    elbow_pos_filtered = None

                # ==========================================
                # 逆运动学求解（IK）- 分层优化（手腕 + 肘部）
                # ==========================================
                # 使用 Warm Start：上一帧的 q_cmd 作为初始猜测
                # Pink 分层优化：
                #   Task 1（高优先级）：手腕位姿（6-DoF）
                #   Task 2（低优先级）：肘部位置（3-DoF）
                ik_start_time = time.time()

                q_solution, success, ik_error = self.ik_solver.solve(
                    target_pos_filtered,      # 使用滤波后的位置
                    target_quat=target_quat_filtered,  # 使用滤波后的姿态
                    elbow_pos=elbow_pos_filtered,      # 使用滤波后的肘部位置
                    q_init=self.q_cmd,
                    max_iter=50,  # 统一使用50轮迭代，保证收敛精度
                    dt=0.1        # Pink 的时间步长
                )

                ik_elapsed = (time.time() - ik_start_time) * 1000  # 转换为毫秒

                # ==========================================
                # 速度限制（安全保护）
                # ==========================================
                if success:
                    # 计算关节速度（rad/s）
                    dt_control = 1.0 / 50.0  # 50 Hz 控制频率
                    q_velocity = (q_solution - self.q_cmd_prev) / dt_control

                    # 限制速度
                    q_velocity_limited = np.clip(
                        q_velocity,
                        -self.max_joint_velocity,
                        self.max_joint_velocity
                    )

                    # 应用速度限制后的命令
                    q_cmd_safe = self.q_cmd_prev + q_velocity_limited * dt_control

                    # 检查是否有速度限制生效
                    if not np.allclose(q_velocity, q_velocity_limited, atol=1e-6):
                        if self._debug_counter % 30 == 0:
                            max_vel = np.max(np.abs(q_velocity))
                            print(f"⚠️  [Safety] 速度限制生效: {max_vel:.3f} → {self.max_joint_velocity:.3f} rad/s")

                    # 更新命令
                    self.q_cmd = q_cmd_safe
                    self.q_cmd_prev = q_cmd_safe.copy()
                    self.ik_failure_count = 0  # 重置失败计数器

                    # 每 60 帧打印一次调试信息
                    if self._debug_counter % 60 == 0:
                        print(f"\n✅ [IK] 分层优化求解成功（Pink）")
                        print(f"   手腕位置: {target_pos_filtered}")
                        if elbow_pos_filtered is not None:
                            print(f"   肘部位置: {elbow_pos_filtered}")
                        print(f"   IK 误差: {ik_error*1000:.2f}mm")
                        print(f"   计算耗时: {ik_elapsed:.2f}ms")
                        print(f"   最大关节速度: {np.max(np.abs(q_velocity_limited)):.3f} rad/s")

                # 处理 IK 求解结果
                if not success:
                    # 未收敛，增加失败计数
                    self.ik_failure_count += 1
                    print(f"⚠️ [IK] 分层优化失败 (误差={ik_error*1000:.2f}mm, 耗时={ik_elapsed:.2f}ms)")
                    print(f"   失败计数: {self.ik_failure_count}/{self.max_ik_failures}")

                    # 检查是否超过失败阈值
                    if self.ik_failure_count >= self.max_ik_failures:
                        print(f"❌ [IK] 连续失败 {self.max_ik_failures} 次，进入安全模式")
                        print(f"   保持当前姿态，清除目标数据")
                        self.latest_human_kps = None  # 清除数据，停止运动
                        self.ik_failure_count = 0  # 重置计数器
                    else:
                        # 保持上一帧姿态（安全策略）
                        print(f"   保持上一帧姿态不动")
                        # self.q_cmd 保持不变

            except ValueError as e:
                print(f"⚠️ [ArmNode] 映射失败: {e}")
                # 如果映射失败，保持当前姿态
                # self.q_cmd 保持不变
        else:
            # 如果没有收到人体关键点数据，保持当前姿态
            # self.q_cmd 保持不变
            pass

        # C. 做 (IO) - 发送控制指令
        self.driver.send_command(self.q_cmd)

        # D. 可视化 - 更新机器人显示
        if self.visualize and self.viz is not None:
            # 使用计算出的关节角度进行可视化
            # 这样显示的是 IK 求解后的真实机械臂姿态
            q_display = self.q_cmd

            # 扩展到完整的机器人关节数（如果需要）
            if len(q_display) < self.viz.model.nq:
                q_full = np.zeros(self.viz.model.nq)
                q_full[:len(q_display)] = q_display
                self.viz.display(q_full)
            else:
                self.viz.display(q_display)

    def _receive_human_keypoints(self):
        """从 UDP 接收人体关键点数据（带时间戳检查）"""
        try:
            data, addr = self.sock.recvfrom(4096)
            packet = json.loads(data.decode('utf-8'))

            # 新格式：包含 keypoints 和 timestamp
            if 'keypoints' in packet and 'timestamp' in packet:
                keypoints = packet['keypoints']
                timestamp = packet['timestamp']

                # 期望的数据格式
                required_keys = ['shoulder', 'elbow', 'wrist', 'index_mcp', 'pinky_mcp']
                if all(key in keypoints for key in required_keys):
                    self.latest_human_kps = {
                        'shoulder': np.array(keypoints['shoulder']),
                        'elbow': np.array(keypoints['elbow']),
                        'wrist': np.array(keypoints['wrist']),
                        'index_mcp': np.array(keypoints['index_mcp']),
                        'pinky_mcp': np.array(keypoints['pinky_mcp'])
                    }
                    self.last_data_timestamp = timestamp
                else:
                    print(f"⚠️ [ArmNode] 收到的数据格式不正确: {keypoints.keys()}")
                    print(f"   期望的键: {required_keys}")
            else:
                # 兼容旧格式（无时间戳）
                required_keys = ['shoulder', 'elbow', 'wrist', 'index_mcp', 'pinky_mcp']
                if all(key in packet for key in required_keys):
                    self.latest_human_kps = {
                        'shoulder': np.array(packet['shoulder']),
                        'elbow': np.array(packet['elbow']),
                        'wrist': np.array(packet['wrist']),
                        'index_mcp': np.array(packet['index_mcp']),
                        'pinky_mcp': np.array(packet['pinky_mcp'])
                    }
                    self.last_data_timestamp = time.time()  # 使用接收时间
                else:
                    print(f"⚠️ [ArmNode] 收到的数据格式不正确: {packet.keys()}")
                    print(f"   期望的键: {required_keys}")

        except BlockingIOError:
            # 没有数据可读（非阻塞模式）
            pass
        except json.JSONDecodeError as e:
            print(f"⚠️ [ArmNode] JSON 解析失败: {e}")
        except Exception as e:
            print(f"⚠️ [ArmNode] UDP 接收失败: {e}")

    def run(self, frequency=100):
        """
        运行控制循环
        :param frequency: 控制频率 (Hz)
        """
        dt = 1.0 / frequency
        print(f"🚀 [ArmNode] 开始运行，频率: {frequency} Hz")

        try:
            while True:
                start_time = time.time()

                self.spin_once()

                # 频率控制
                elapsed = time.time() - start_time
                sleep_time = max(0, dt - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n⏹️ [ArmNode] 收到停止信号，正在退出...")


if __name__ == "__main__":
    # 创建并运行手臂控制节点
    node = ArmNode(visualize=True, dof=7)
    node.run(frequency=50)  # 50 Hz 控制频率
