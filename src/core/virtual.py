import numpy as np
import pinocchio as pin
import os

class VirtualFixture:
    """
    对应文档 3.1 节：z_virtual 生成器
    利用 IK 将孔位的笛卡尔坐标映射为关节空间目标，实现'隐式力引导'。
    """
    def __init__(self, urdf_path, ee_frame_name="link6"):
        # 加载机器人模型 (轻量级，只用于计算几何，不涉及动力学)
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()
        self.ee_frame_id = self.model.getFrameId(ee_frame_name)
        
        # IK 参数
        self.damp = 1e-12
        self.it_max = 1000
        self.eps = 1e-4

    def get_virtual_observation(self, hole_pos, hole_quat, q_seed):
        """
        计算 z_virtual [cite: 39]
        :param hole_pos: 目标孔位位置 [x, y, z]
        :param hole_quat: 目标孔位姿态四元数 [x, y, z, w]
        :param q_seed: 当前机器人关节角 (作为种子点，防止多解跳变)
        :return: z_virtual (7维关节角)
        """
        # 转换目标为 SE3 格式
        target_rot = pin.Quaternion(np.array(hole_quat)).matrix()
        target_pose = pin.SE3(target_rot, np.array(hole_pos))
        
        q = q_seed.copy()
        
        # 执行数值 IK (Newton-Raphson)
        for i in range(self.it_max):
            pin.forwardKinematics(self.model, self.data, q)
            pin.updateFramePlacements(self.model, self.data)
            
            # 计算当前末端与目标的误差
            curr_pose = self.data.oMf[self.ee_frame_id]
            diff = pin.log6(curr_pose.inverse() * target_pose).vector
            
            if np.linalg.norm(diff) < self.eps:
                # 收敛
                return q
            
            # 计算雅可比矩阵
            J = pin.computeFrameJacobian(self.model, self.data, q, self.ee_frame_id)
            
            # 求解关节增量 (J * dq = diff)
            v = -diff
            # 使用阻尼伪逆求解
            dq = -J.T.dot(np.linalg.solve(J.dot(J.T) + self.damp * np.eye(6), v))
            
            q = pin.integrate(self.model, q, dq)
            
        # 如果未收敛，返回最后计算的值（在虚拟引导中，这通常也足够好）
        return q