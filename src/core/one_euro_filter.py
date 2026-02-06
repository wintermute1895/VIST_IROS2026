"""
One Euro Filter Implementation for Smooth Motion Tracking

The One Euro Filter is a simple and effective filter for noisy signals,
particularly useful for human motion tracking. It adapts its cutoff frequency
based on the signal's velocity, providing both smoothness and responsiveness.

Reference:
Casiez, G., Roussel, N., & Vogel, D. (2012).
1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems.
"""

import numpy as np
import time


class OneEuroFilter:
    """
    One Euro Filter for smoothing noisy signals

    Parameters:
        min_cutoff: Minimum cutoff frequency (Hz) - controls smoothing at low speeds
        beta: Speed coefficient - controls how much the cutoff increases with speed
        d_cutoff: Cutoff frequency for derivative (Hz) - smooths the velocity estimate
    """

    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        """
        Initialize One Euro Filter

        Args:
            min_cutoff: Minimum cutoff frequency (default: 1.0 Hz)
                       Lower = more smoothing, higher = more responsive
            beta: Speed coefficient (default: 0.007)
                 Higher = more responsive to fast movements
            d_cutoff: Derivative cutoff frequency (default: 1.0 Hz)
        """
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        # State variables
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def __call__(self, x, t=None):
        """
        Filter a new value

        Args:
            x: New value (can be scalar or numpy array)
            t: Timestamp (seconds). If None, uses current time

        Returns:
            Filtered value
        """
        if t is None:
            t = time.time()

        x = np.asarray(x, dtype=np.float64)

        # First call: initialize
        if self.x_prev is None:
            self.x_prev = x.copy()
            self.dx_prev = np.zeros_like(x)
            self.t_prev = t
            return x.copy()

        # Compute time delta
        dt = t - self.t_prev
        if dt <= 0:
            dt = 1e-6  # Avoid division by zero

        # Estimate derivative (velocity)
        dx = (x - self.x_prev) / dt

        # Smooth the derivative
        alpha_d = self._smoothing_factor(dt, self.d_cutoff)
        dx_filtered = self._exponential_smoothing(alpha_d, dx, self.dx_prev)

        # Compute adaptive cutoff frequency
        cutoff = self.min_cutoff + self.beta * np.abs(dx_filtered)

        # Smooth the signal
        alpha = self._smoothing_factor(dt, cutoff)
        x_filtered = self._exponential_smoothing(alpha, x, self.x_prev)

        # Update state
        self.x_prev = x_filtered.copy()
        self.dx_prev = dx_filtered.copy()
        self.t_prev = t

        return x_filtered

    def _smoothing_factor(self, dt, cutoff):
        """
        Compute smoothing factor alpha from cutoff frequency

        Args:
            dt: Time delta (seconds)
            cutoff: Cutoff frequency (Hz) or array of cutoffs

        Returns:
            Alpha value(s) in [0, 1]
        """
        tau = 1.0 / (2.0 * np.pi * cutoff)
        alpha = 1.0 / (1.0 + tau / dt)
        return alpha

    def _exponential_smoothing(self, alpha, x, x_prev):
        """
        Apply exponential smoothing

        Args:
            alpha: Smoothing factor in [0, 1]
            x: Current value
            x_prev: Previous filtered value

        Returns:
            Smoothed value
        """
        return alpha * x + (1.0 - alpha) * x_prev

    def reset(self):
        """Reset filter state"""
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None


class VectorOneEuroFilter:
    """
    One Euro Filter for 3D vectors (positions, velocities, etc.)

    Applies independent One Euro Filters to each component.
    """

    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        """
        Initialize vector filter

        Args:
            min_cutoff: Minimum cutoff frequency (Hz)
            beta: Speed coefficient
            d_cutoff: Derivative cutoff frequency (Hz)
        """
        self.filters = [
            OneEuroFilter(min_cutoff, beta, d_cutoff),
            OneEuroFilter(min_cutoff, beta, d_cutoff),
            OneEuroFilter(min_cutoff, beta, d_cutoff)
        ]

    def __call__(self, vec, t=None):
        """
        Filter a 3D vector

        Args:
            vec: 3D vector [x, y, z]
            t: Timestamp (seconds)

        Returns:
            Filtered 3D vector
        """
        vec = np.asarray(vec, dtype=np.float64)
        if len(vec) != 3:
            raise ValueError(f"Expected 3D vector, got shape {vec.shape}")

        filtered = np.array([
            self.filters[0](vec[0], t),
            self.filters[1](vec[1], t),
            self.filters[2](vec[2], t)
        ])

        return filtered

    def reset(self):
        """Reset all filters"""
        for f in self.filters:
            f.reset()


class QuaternionOneEuroFilter:
    """
    One Euro Filter for quaternions

    Filters quaternions in a way that preserves unit norm and handles
    the double-cover property of quaternions.
    """

    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        """
        Initialize quaternion filter

        Args:
            min_cutoff: Minimum cutoff frequency (Hz)
            beta: Speed coefficient
            d_cutoff: Derivative cutoff frequency (Hz)
        """
        self.filters = [
            OneEuroFilter(min_cutoff, beta, d_cutoff),
            OneEuroFilter(min_cutoff, beta, d_cutoff),
            OneEuroFilter(min_cutoff, beta, d_cutoff),
            OneEuroFilter(min_cutoff, beta, d_cutoff)
        ]

    def __call__(self, quat, t=None):
        """
        Filter a quaternion

        Args:
            quat: Quaternion [x, y, z, w]
            t: Timestamp (seconds)

        Returns:
            Filtered quaternion (normalized)
        """
        quat = np.asarray(quat, dtype=np.float64)
        if len(quat) != 4:
            raise ValueError(f"Expected quaternion [x,y,z,w], got shape {quat.shape}")

        # Handle quaternion double-cover: ensure shortest path
        if hasattr(self, 'quat_prev'):
            if np.dot(quat, self.quat_prev) < 0:
                quat = -quat

        # Filter each component
        filtered = np.array([
            self.filters[0](quat[0], t),
            self.filters[1](quat[1], t),
            self.filters[2](quat[2], t),
            self.filters[3](quat[3], t)
        ])

        # Normalize to ensure unit quaternion
        filtered = filtered / np.linalg.norm(filtered)

        self.quat_prev = filtered.copy()

        return filtered

    def reset(self):
        """Reset all filters"""
        for f in self.filters:
            f.reset()
        if hasattr(self, 'quat_prev'):
            delattr(self, 'quat_prev')
