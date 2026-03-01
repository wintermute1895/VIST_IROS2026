import numpy as np
from linkerhand.handcore import HandCore


class RightHand:
    def __init__(self, handcore: HandCore, length=10):
        self.g_jointpositions = [255] * length
        self.g_jointvelocity = [255] * length
        self.g_jointpositions_arc = [0.0] * length
        self.g_jointvelocity_arc = [0.0] * length
        self.last_jointpositions = [255] * length
        self.last_jointvelocity = [255] * length
        self.handstate = [0] * length
        self.handcore = handcore
        self.calibrationokpose = None
        self.calibrationoriginal = None

    def joint_update(self, joint_arc):
        qpos = np.zeros(25)
        qpos[16] = joint_arc[1] * 1.2
        qpos[17] = joint_arc[0] * -1 + joint_arc[1] * 1
        qpos[20] = joint_arc[4] * 1.3 + joint_arc[2] * 1.2
        # print("muzzhiok",qpos[17],joint_arc[0],joint_arc[1])
        # self.calibrationoriginal[2],self.calibrationoriginal[3],self.calibrationoriginal[4])
        # if joint_arc[6] < 0.2 and joint_arc[7] < 0.2 and joint_arc[8] < 0.2:
        #     print("手指伸直状态",joint_arc[6],joint_arc[7],joint_arc[8])
        #     qpos[1] = 0
        #     qpos[2] = 0
        #     qpos[3] = 0
        # elif joint_arc[6] > joint_arc[7] > joint_arc[8]:
        #     print("2.3关节伸直状态",joint_arc[6],joint_arc[7],joint_arc[8])
        # else:
        #     print("2.3关节弯曲状态",joint_arc[6],joint_arc[7],joint_arc[8])
        self.g_jointpositions = self.handcore.trans_to_motor_right(qpos)

    def joint_arc_update(self, joint_arc):
        qpos = np.zeros(25)

        qpos[16] = joint_arc[1] * -1
        qpos[17] = joint_arc[0] * -2 + joint_arc[1] * -1.2
        qpos[17] = qpos[17] * 1.1
        qpos[20] = joint_arc[4] * 0.2 + joint_arc[2] * 1.0
        # print("muzzhiok",qpos[16],joint_arc[0],joint_arc[1])
        qpos[1] = joint_arc[6] * 0.1 + joint_arc[8] * 0.3
        qpos[9] = joint_arc[10] * 0.1 + joint_arc[12] * 0.7
        qpos[13] = joint_arc[14] * 0.1 + joint_arc[16] * 0.7
        qpos[5] = joint_arc[18] * 0.1 + joint_arc[20] * 0.7
        
        self.g_jointpositions_arc = qpos

    def speed_update(self):
        for i in range(len(self.g_jointpositions)):
            lastpos = self.last_jointpositions[i]
            position_error = int(abs(self.g_jointpositions[i] - lastpos))
            position_derict = 1 if self.g_jointpositions[i] - lastpos > 0 else -1
            slow_limit = 2
            fast_limit = 10
            max_vel = int(self.last_jointvelocity[i] * 2)
            mid_vel = int(self.last_jointvelocity[i] * 0.7)
            min_vel = int(self.last_jointvelocity[i] * 0.5)
            target_vel = self.last_jointvelocity[i]
            if self.handstate[i] == 0:  # stop
                if 0 < position_error:
                    target_vel = position_error * 3 + 5
                    self.handstate[i] = 1
            elif self.handstate[i] == 1:  # slow
                if position_error >= fast_limit:
                    target_vel = position_error * 5 + 30
                    if target_vel > mid_vel:
                        target_vel = mid_vel
                    self.handstate[i] = 2
                elif position_error == 0:
                    self.handstate[i] = 0
                else:
                    target_vel = position_error * 3 + 10
            else:  # fast
                if position_error >= fast_limit:
                    target_vel = position_error * 3 + 50
                    if target_vel > max_vel:
                        target_vel = max_vel
                elif slow_limit < position_error < fast_limit:
                    target_vel = position_error * 3 + 20
                    if target_vel < mid_vel:
                        target_vel = mid_vel
                    self.handstate[i] = 3
                elif 0 < position_error <= slow_limit:
                    target_vel = position_error * 3 + 10
                    if target_vel < min_vel:
                        target_vel = min_vel
                    self.handstate[i] = 1
            if i == 0 or i == 1 or i == 9:
                target_vel = 25
            self.g_jointvelocity[i] = int(target_vel)

            if self.g_jointvelocity[i] > 255:
                self.g_jointvelocity[i] = 255
            self.last_jointvelocity[i] = self.g_jointvelocity[i]
            self.last_jointpositions[i] = self.g_jointpositions[i]


class LeftHand:
    def __init__(self, handcore: HandCore, length=10):
        self.g_jointpositions = [255] * length
        self.g_jointvelocity = [255] * length
        self.g_jointpositions_arc = [0.0] * length
        self.g_jointvelocity_arc = [0.0] * length
        self.last_jointpositions = [255] * length
        self.last_jointvelocity = [255] * length
        self.handstate = [0] * length
        self.handcore = handcore
        self.calibrationokpose = None
        self.calibrationoriginal = None

    def joint_update(self, joint_arc):
        qpos = np.zeros(25)
        qpos = np.zeros(25)

        qpos[16] = joint_arc[1] * -1
        qpos[17] = joint_arc[0] * -2 + joint_arc[1] * -1.2
        qpos[17] = qpos[17] * 1.1
        qpos[20] = joint_arc[4] * 0.2 + joint_arc[2] * 1.0
        # print("muzzhiok",qpos[16],joint_arc[0],joint_arc[1])
        qpos[1] = joint_arc[6] * 0.1 + joint_arc[8] * 0.3
        qpos[9] = joint_arc[10] * 0.1 + joint_arc[12] * 0.7
        qpos[13] = joint_arc[14] * 0.1 + joint_arc[16] * 0.7
        qpos[5] = joint_arc[18] * 0.1 + joint_arc[20] * 0.7

        self.g_jointpositions = self.handcore.trans_to_motor_left(qpos)

    def joint_arc_update(self, joint_arc):
        qpos = np.zeros(25)

        qpos[16] = joint_arc[1] * -1
        qpos[17] = joint_arc[0] * -2 + joint_arc[1] * -1.2
        qpos[17] = qpos[17] * 1.1
        qpos[20] = joint_arc[4] * 0.2 + joint_arc[2] * 1.0
        # print("muzzhiok",qpos[16],joint_arc[0],joint_arc[1])
        qpos[1] = joint_arc[6] * 0.1 + joint_arc[8] * 0.3
        qpos[9] = joint_arc[10] * 0.1 + joint_arc[12] * 0.7
        qpos[13] = joint_arc[14] * 0.1 + joint_arc[16] * 0.7
        qpos[5] = joint_arc[18] * 0.1 + joint_arc[20] * 0.7
        
        self.g_jointpositions_arc = qpos

    def speed_update(self):
        for i in range(len(self.g_jointpositions)):
            lastpos = self.last_jointpositions[i]
            position_error = int(abs(self.g_jointpositions[i] - lastpos))
            position_derict = 1 if self.g_jointpositions[i] - lastpos > 0 else -1
            slow_limit = 2
            fast_limit = 10
            max_vel = int(self.last_jointvelocity[i] * 2)
            mid_vel = int(self.last_jointvelocity[i] * 0.7)
            min_vel = int(self.last_jointvelocity[i] * 0.5)
            target_vel = self.last_jointvelocity[i]
            if self.handstate[i] == 0:  # stop
                if 0 < position_error:
                    target_vel = position_error * 3 + 5
                    self.handstate[i] = 1
            elif self.handstate[i] == 1:  # slow
                if position_error >= fast_limit:
                    target_vel = position_error * 3 + 30
                    if target_vel > mid_vel:
                        target_vel = mid_vel
                    self.handstate[i] = 2
                elif position_error == 0:
                    self.handstate[i] = 0
                else:
                    target_vel = position_error * 3 + 10
            else:  # fast
                if position_error >= fast_limit:
                    target_vel = position_error * 3 + 50
                    if target_vel > max_vel:
                        target_vel = max_vel
                elif slow_limit < position_error < fast_limit:
                    target_vel = position_error * 3 + 20
                    if target_vel < mid_vel:
                        target_vel = mid_vel
                    self.handstate[i] = 3
                elif 0 < position_error <= slow_limit:
                    target_vel = position_error * 3 + 10
                    if target_vel < min_vel:
                        target_vel = min_vel
                    self.handstate[i] = 1
            # if position_derict == -1:
            #     target_vel = 2 * target_vel
            # if i == 0 or i == 1 or i == 9:
            #     target_vel = 100
            self.g_jointvelocity[i] = int(target_vel * 0.6)
            if self.g_jointvelocity[i] > 255:
                self.g_jointvelocity[i] = 255
            self.g_jointvelocity[i] = 255
            self.last_jointvelocity[i] = self.g_jointvelocity[i]
            self.last_jointpositions[i] = self.g_jointpositions[i] 