"""
VIST卡尔曼滤波器改进建议

问题：当前实现不支持"纯预测模式"，导致频率不匹配时会用旧数据重复更新

解决方案：在solve()方法中添加has_new_observation参数
"""

# ==========================================
# 修改1: 在 vist_kalman_filter.py 的 solve() 方法中添加参数
# ==========================================

def solve(self, target_pos=None, target_quat=None, q_init=None,
          elbow_pos=None, shoulder_pos=None, has_new_observation=True):
    """
    VIST 求解主接口（支持预测模式）

    Args:
        target_pos: 目标位置 (3D) - 腕部/手部位置（可选）
        target_quat: 目标四元数 (可选)
        q_init: 初始关节角度 (可选，用于初始化状态)
        elbow_pos: 肘部位置 (可选，用于几何解析解)
        shoulder_pos: 肩部位置 (可选，用于几何解析解)
        has_new_observation: 是否有新的观测数据（默认True保持向后兼容）

    Returns:
        q_solution: 关节角度解
        success: 是否成功
        error: 位置误差
    """
    try:
        # 如果提供了初始猜测，初始化状态
        if q_init is not None and self.iteration_count == 0:
            # ... 初始化代码（保持不变）
            pass

        # 1. 预测步骤（总是执行）
        self.predict()

        # 2. 更新步骤（只在有新观测时执行）
        if has_new_observation and target_pos is not None:
            # 有新观测：执行完整的更新步骤

            # 2.1 意图检测
            current_pos = self._get_current_end_effector_position()
            velocity = self.state[self.n_joints:self.n_joints+3]
            self.detect_intent(target_pos, current_pos, velocity)

            # 2.2 从配置读取启用状态
            use_geometric_solver = self.config.vist_geometric_solver_enabled
            use_biomimetic = self.config.vist_biomimetic_enabled

            # 2.3 计算人类指令
            human_delta_theta = None
            if use_geometric_solver and self.geometric_solver is not None and \
               elbow_pos is not None and shoulder_pos is not None:
                wrist_pos = target_pos
                human_delta_theta = self.compute_human_delta_theta_from_elbow(
                    shoulder_pos, elbow_pos, wrist_pos, target_quat
                )

            # 2.4 更新步骤
            q_solution, success = self.update(
                target_pos,
                target_quat,
                human_delta_theta=human_delta_theta,
                previous_target_pos=self.previous_target_pos,
                elbow_pos=elbow_pos,
                shoulder_pos=shoulder_pos,
                use_biomimetic=use_biomimetic
            )

            # 2.5 更新历史数据
            self.previous_target_pos = target_pos.copy()

        else:
            # 没有新观测：只使用预测值
            q_solution = self.state[:self.n_joints]
            success = True

        # 3. 计算误差（用于兼容性）
        if target_pos is not None:
            current_pos = self._get_current_end_effector_position()
            error = np.linalg.norm(target_pos - current_pos)
        else:
            error = 0.0

        return q_solution, success, error

    except Exception as e:
        print(f"❌ [VIST] solve() 错误: {e}")
        import traceback
        traceback.print_exc()
        return np.zeros(self.n_joints), False, float('inf')


# ==========================================
# 修改2: 在控制循环中使用has_new_observation参数
# ==========================================

# 在 run_real_robot_vist_refactored.py 的控制循环中：

def run(self, duration=None, countdown_seconds=10):
    """运行真机控制循环"""
    # ... 初始化代码 ...

    # 添加：记录上一次视觉数据的时间戳
    last_vision_timestamp = None

    while time.time() - start_time < duration:
        loop_start = time.time()

        # 1. 接收人体关键点
        human_keypoints = self.robot.receive_keypoints()

        # 检查是否有新数据
        has_new_vision = False
        if human_keypoints is not None:
            current_timestamp = human_keypoints.get('timestamp', time.time())
            if last_vision_timestamp is None or current_timestamp > last_vision_timestamp:
                has_new_vision = True
                last_vision_timestamp = current_timestamp

        # 2. VIST 控制器处理（传递has_new_observation标志）
        if has_new_vision and human_keypoints is not None:
            # 有新视觉数据：完整处理
            q_safe, success, debug_info = self.controller.process(
                human_keypoints,
                has_new_observation=True
            )
        else:
            # 没有新视觉数据：只预测
            q_safe, success, debug_info = self.controller.process(
                None,  # 不传入关键点
                has_new_observation=False
            )

        # 3. 发送到真机
        if success:
            self.robot.send_command(q_safe)

        # 4. 控制频率
        elapsed = time.time() - loop_start
        if elapsed < self.config.control_dt:
            time.sleep(self.config.control_dt - elapsed)


# ==========================================
# 修改3: 在VISTController中支持预测模式
# ==========================================

# 在 src/control/vist_controller.py 中：

def process(self, human_keypoints, has_new_observation=True):
    """
    处理人体关键点，返回安全的关节角度

    Args:
        human_keypoints: 人体关键点字典（可以为None）
        has_new_observation: 是否有新的观测数据

    Returns:
        q_safe: 安全的关节角度
        success: 是否成功
        debug_info: 调试信息
    """
    try:
        if has_new_observation and human_keypoints is not None:
            # 有新观测：完整处理流程

            # 1. 运动映射
            result = self.mapper.human_to_robot(human_keypoints)
            if result is None:
                return None, False, {'error': 'Mapping failed'}

            target_pos, target_quat, debug_info = result
            target_elbow = debug_info['elbow_pos']

            # 2. 工作空间检查
            # ... 检查代码 ...

            # 3. VIST求解（有新观测）
            q_solution, success, error = self.vist_filter.solve(
                target_pos=target_pos,
                target_quat=target_quat,
                q_init=self.q_current,
                elbow_pos=target_elbow,
                shoulder_pos=self.config.robot_shoulder_position,
                has_new_observation=True  # ✅ 明确标记有新观测
            )

        else:
            # 没有新观测：只预测
            q_solution, success, error = self.vist_filter.solve(
                target_pos=None,
                has_new_observation=False  # ✅ 明确标记无新观测
            )
            debug_info = {'mode': 'prediction_only'}

        if not success:
            return None, False, debug_info

        # 4. 安全控制
        q_safe = self.safety_controller.apply_safety_limits(
            q_solution,
            self.q_current
        )

        # 5. 更新当前状态
        self.q_current = q_safe

        return q_safe, True, debug_info

    except Exception as e:
        return None, False, {'error': str(e)}


# ==========================================
# 修改4: 在视觉节点中添加时间戳
# ==========================================

# 在 src/nodes/vision_node_depth.py 的 send_keypoints() 方法中：

def send_keypoints(self, keypoints):
    """
    通过 UDP 发送关键点数据（带时间戳）
    """
    if keypoints is None:
        return

    try:
        # ✅ 添加时间戳（用于检测数据新鲜度）
        packet = {
            'keypoints': keypoints,
            'timestamp': time.time()  # 高精度时间戳
        }
        data = json.dumps(packet).encode('utf-8')
        self.sock.sendto(data, self.udp_addr)
    except Exception as e:
        print(f"⚠️ [VisionNodeDepth] UDP 发送失败: {e}")


# ==========================================
# 总结：修改清单
# ==========================================

"""
1. ✅ vist_kalman_filter.py
   - solve() 方法添加 has_new_observation 参数
   - 区分"有新观测"和"无新观测"两种模式

2. ✅ run_real_robot_vist_refactored.py
   - 控制循环中检测视觉数据新鲜度
   - 根据是否有新数据调用不同模式

3. ✅ vist_controller.py
   - process() 方法支持预测模式
   - 传递 has_new_observation 标志

4. ✅ vision_node_depth.py
   - 发送数据时添加时间戳
   - 用于判断数据新鲜度

5. ✅ test_frequency_mismatch_simulation.py
   - 完整的频率不匹配仿真测试
   - 验证VIST在不同频率下的表现
"""
