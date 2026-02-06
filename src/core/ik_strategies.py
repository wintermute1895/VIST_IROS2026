"""
IK Strategy Pattern Implementation

This module implements the Strategy Pattern for IK solvers, allowing
dynamic switching between different IK algorithms:
- Differential IK (Jacobian-based, Damped Least Squares)
- Pink IK (Optimization-based, Multi-task)

Design Pattern: Strategy Pattern
- IKStrategy: Abstract base class
- DifferentialIKStrategy: Concrete strategy using Pinocchio CLIK
- PinkIKStrategy: Concrete strategy using Pink library
"""

import numpy as np
import pinocchio as pin
from scipy.spatial.transform import Rotation
from abc import ABC, abstractmethod
import os
import tempfile


class IKStrategy(ABC):
    """
    Abstract base class for IK strategies

    All IK strategies must implement the solve() method with a unified interface.
    """

    @abstractmethod
    def solve(self, target_pos, target_quat=None, elbow_target=None, q_current=None):
        """
        Solve inverse kinematics

        Args:
            target_pos: Target end-effector position [x, y, z] (numpy array)
            target_quat: Target orientation quaternion [x, y, z, w] (optional)
            elbow_target: Target elbow position [x, y, z] (optional, for redundancy resolution)
            q_current: Current joint configuration (numpy array)

        Returns:
            tuple: (q_solution, success, error)
                - q_solution: Joint angles (numpy array)
                - success: Whether IK converged (bool)
                - error: Final position error in meters (float)
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources (e.g., temporary files)"""
        pass


class DifferentialIKStrategy(IKStrategy):
    """
    Differential IK Strategy using Pinocchio CLIK

    Algorithm: Closed-Loop Inverse Kinematics with Damped Least Squares
    - Iterative optimization
    - Jacobian-based velocity control
    - Supports 3-DoF (position) and 6-DoF (position + orientation)
    """

    # 默认的右臂 7-DoF 关节名称列表
    DEFAULT_RIGHT_ARM_JOINTS = [
        "Right_Shoulder_Pitch_Joint",
        "Right_Shoulder_Roll_Joint",
        "Right_Shoulder_Yaw_Joint",
        "Right_Elbow_Pitch_Joint",
