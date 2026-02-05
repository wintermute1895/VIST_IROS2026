#!/usr/bin/env python3
"""
============================================================================
LinkerHand L10 Hardware Driver - 优化版（解决CAN缓冲区溢出）
============================================================================
Purpose: 稳定的LinkerHand SDK接口，解决Error 105缓冲区溢出问题
Hardware: LinkerHand L10 via CAN Bus (10 DOF)

关键优化：
1. 帧间微延迟 - 防止瞬时并发
2. 变化量过滤 - 减少不必要的发送
3. 非阻塞发送 - 优雅处理缓冲区满
4. 严格频率控制 - 精确维持控制频率

============================================================================
"""

import sys
import os
import time
import numpy as np
from typing import List, Optional
import logging

# Add SDK to Python path
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_PATH = os.path.join(SCRIPT_DIR, "sdk", "linkerhand-python-sdk-main")
SDK_LINKERHAND_PATH = os.path.join(SDK_PATH, "LinkerHand")

if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)
if SDK_LINKERHAND_PATH not in sys.path:
    sys.path.insert(0, SDK_LINKERHAND_PATH)


class LinkerHandDriver:
    """
    优化的LinkerHand L10硬件驱动

    解决CAN总线缓冲区溢出问题（Error 105）

    Joint Order (10 elements) - 官方SDK顺序（来自SDK的get_finger_order()）:
      [0] thumb_cmc_pitch    - 拇指根部弯曲 (Thumb pitch)
      [1] thumb_cmc_yaw      - 拇指旋转 (Thumb yaw) ← 修正！
      [2] index_mcp_pitch    - 食指根部弯曲 (Index finger bend)
      [3] middle_mcp_pitch   - 中指根部弯曲 (Middle finger bend)
      [4] ring_mcp_pitch     - 无名指根部弯曲 (Ring finger bend)
      [5] pinky_mcp_pitch    - 小指根部弯曲 (Pinky finger bend)
      [6] index_mcp_roll     - 食指侧摆 (Index finger roll)
      [7] ring_mcp_roll      - 无名指侧摆 (Ring finger roll)
      [8] pinky_mcp_roll     - 小指侧摆 (Pinky finger roll)
      [9] thumb_cmc_roll     - 拇指侧摆 (Thumb roll) ← 修正！
    """

    # Constants
    EXPECTED_COMMAND_LENGTH = 10
    DEFAULT_CAN_ID = 0x27
    DEFAULT_CAN_CHANNEL = "can0"

    # 优化参数
    INTER_FRAME_DELAY = 0.0005  # 500微秒帧间延迟（0.5ms）
    CHANGE_THRESHOLD = 0.1      # 变化阈值：0.1度
    MAX_RETRY_ON_FULL = 2       # 缓冲区满时最大重试次数
    RETRY_DELAY = 0.001         # 重试延迟：1ms

    def __init__(self,
                 can_id: int = DEFAULT_CAN_ID,
                 can_channel: str = DEFAULT_CAN_CHANNEL,
                 mock_mode: bool = False,
                 enable_filtering: bool = True):
        """
        Initialize the LinkerHand driver with optimizations

        Args:
            can_id: CAN device ID (default: 0x27)
            can_channel: CAN interface name (default: "can0")
            mock_mode: If True, run in mock mode without hardware
            enable_filtering: If True, enable change-based filtering
        """
        self.can_id = can_id
        self.can_channel = can_channel
        self.mock_mode = mock_mode
        self.enable_filtering = enable_filtering
        self.is_initialized = False

        # 状态跟踪
        self.last_command = None
        self.command_count = 0
        self.dropped_frames = 0
        self.filtered_frames = 0

        # 统计信息
        self.total_send_attempts = 0
        self.successful_sends = 0
        self.buffer_full_errors = 0

        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Initialize SDK
        if not mock_mode:
            self._init_sdk()
        else:
            self.logger.info("="*70)
            self.logger.info("Running in MOCK MODE (no hardware)")
            self.logger.info("="*70)
            self.is_initialized = True

    def _init_sdk(self):
        """Initialize the LinkerHand SDK"""
        self.logger.info("="*70)
        self.logger.info("Initializing LinkerHand L10 SDK (Optimized)")
        self.logger.info("="*70)
        self.logger.info(f"  CAN ID: 0x{self.can_id:02X}")
        self.logger.info(f"  CAN Channel: {self.can_channel}")
        self.logger.info(f"  Inter-frame delay: {self.INTER_FRAME_DELAY*1000:.2f}ms")
        self.logger.info(f"  Change threshold: {self.CHANGE_THRESHOLD}°")
        self.logger.info(f"  Filtering: {'Enabled' if self.enable_filtering else 'Disabled'}")

        try:
            # Import SDK module
            from LinkerHand.core.can.linker_hand_l10_can import LinkerHandL10Can

            # Initialize SDK
            self.hand = LinkerHandL10Can(
                can_id=self.can_id,
                can_channel=self.can_channel
            )

            # Wait for initialization
            time.sleep(0.5)

            self.is_initialized = True
            self.logger.info("="*70)
            self.logger.info("✅ SDK initialized successfully")
            self.logger.info("="*70)

        except ImportError as e:
            self.logger.error("="*70)
            self.logger.error("❌ Failed to import LinkerHand SDK")
            self.logger.error("="*70)
            self.logger.error(f"Error: {e}")
            self.logger.error(f"SDK Path: {SDK_PATH}")
            raise

        except Exception as e:
            self.logger.error("="*70)
            self.logger.error("❌ Failed to initialize SDK")
            self.logger.error("="*70)
            self.logger.error(f"Error: {e}")
            raise

    def _should_send(self, joint_positions: List[float]) -> bool:
        """
        判断是否需要发送（基于变化量过滤）

        Args:
            joint_positions: 新的关节位置

        Returns:
            True if should send, False if can skip
        """
        if not self.enable_filtering:
            return True

        if self.last_command is None:
            return True

        # 计算最大变化量
        max_change = max(abs(new - old)
                        for new, old in zip(joint_positions, self.last_command))

        # 如果变化量小于阈值，跳过发送
        if max_change < self.CHANGE_THRESHOLD:
            self.filtered_frames += 1
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Filtered frame (max change: {max_change:.3f}°)")
            return False

        return True

    def move(self, joint_positions: List[float]) -> bool:
        """
        Send joint position commands to the hand (optimized)

        CRITICAL: SDK requires exactly 10 values in degrees!

        Args:
            joint_positions: List of 10 joint positions in degrees
                            官方SDK顺序（来自SDK的get_finger_order()）:
                            [Thumb_Pitch, Thumb_Yaw, Index_Pitch, Middle_Pitch,
                            Ring_Pitch, Pinky_Pitch, Index_Roll, Ring_Roll,
                            Pinky_Roll, Thumb_Roll]

        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.is_initialized:
            self.logger.error("❌ Driver not initialized!")
            return False

        # Validate input length
        if len(joint_positions) != self.EXPECTED_COMMAND_LENGTH:
            self.logger.error(
                f"❌ Invalid command length: {len(joint_positions)} "
                f"(expected {self.EXPECTED_COMMAND_LENGTH})"
            )
            return False

        # Validate data types and convert to float
        try:
            positions_float = [float(x) for x in joint_positions]
        except (ValueError, TypeError) as e:
            self.logger.error(f"❌ Invalid data type in command: {e}")
            return False

        # Check for NaN or Inf
        if not all(np.isfinite(x) for x in positions_float):
            self.logger.error("❌ Command contains NaN or Inf values")
            return False

        # 变化量过滤
        if not self._should_send(positions_float):
            return True  # 返回True因为这不是错误，只是跳过了

        # 发送命令（带重试机制）
        success = self._send_with_retry(positions_float)

        if success:
            self.last_command = positions_float
            self.command_count += 1
            self.successful_sends += 1
        else:
            self.dropped_frames += 1

        return success

    def _send_with_retry(self, positions: List[float]) -> bool:
        """
        发送命令，带重试机制处理缓冲区满的情况

        Args:
            positions: Joint positions to send

        Returns:
            True if successful, False otherwise
        """
        self.total_send_attempts += 1

        for attempt in range(self.MAX_RETRY_ON_FULL + 1):
            try:
                if self.mock_mode:
                    # Mock mode: just log
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"[MOCK] Would send: {positions}")
                    # 模拟帧间延迟
                    time.sleep(self.INTER_FRAME_DELAY)
                    return True
                else:
                    # Real mode: send to hardware
                    # 添加帧间延迟，防止瞬时并发
                    if attempt > 0:
                        time.sleep(self.RETRY_DELAY)

                    self.hand.set_joint_positions(positions)

                    # 成功发送后添加微延迟，让CAN总线有时间清空缓冲区
                    time.sleep(self.INTER_FRAME_DELAY)

                    return True

            except Exception as e:
                error_msg = str(e).lower()

                # 检查是否是缓冲区满错误
                if 'buffer' in error_msg or 'enobufs' in error_msg or '105' in error_msg:
                    self.buffer_full_errors += 1

                    if attempt < self.MAX_RETRY_ON_FULL:
                        # 还有重试机会
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(
                                f"Buffer full (attempt {attempt+1}/{self.MAX_RETRY_ON_FULL+1}), "
                                f"retrying after {self.RETRY_DELAY*1000:.1f}ms..."
                            )
                        continue
                    else:
                        # 重试次数用完，放弃这一帧
                        if self.command_count % 30 == 0:  # 每秒只打印一次
                            self.logger.warning(
                                f"⚠️  CAN buffer full after {self.MAX_RETRY_ON_FULL+1} attempts, "
                                f"dropping frame (total dropped: {self.dropped_frames+1})"
                            )
                        return False
                else:
                    # 其他错误
                    self.logger.error(f"❌ Failed to send command: {e}")
                    return False

        return False

    def reset(self) -> bool:
        """
        Reset hand to zero position (all joints straight)

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Resetting hand to zero position...")
        zero_position = [0.0] * self.EXPECTED_COMMAND_LENGTH

        # 重置时禁用过滤，确保发送
        old_filtering = self.enable_filtering
        self.enable_filtering = False

        success = self.move(zero_position)

        self.enable_filtering = old_filtering

        if success:
            self.logger.info("✅ Hand reset complete")
        else:
            self.logger.error("❌ Hand reset failed")

        return success

    def close(self):
        """
        Safely close the driver and release resources
        """
        if not self.is_initialized:
            return

        self.logger.info("="*70)
        self.logger.info("Closing LinkerHand driver")
        self.logger.info("="*70)

        # 显示统计信息
        if self.total_send_attempts > 0:
            success_rate = 100.0 * self.successful_sends / self.total_send_attempts
            self.logger.info(f"  Total send attempts: {self.total_send_attempts}")
            self.logger.info(f"  Successful sends: {self.successful_sends}")
            self.logger.info(f"  Success rate: {success_rate:.1f}%")
            self.logger.info(f"  Dropped frames: {self.dropped_frames}")
            self.logger.info(f"  Filtered frames: {self.filtered_frames}")
            self.logger.info(f"  Buffer full errors: {self.buffer_full_errors}")

        # Reset to safe position
        self.reset()
        time.sleep(0.5)

        # Close SDK (if SDK provides a close method)
        if not self.mock_mode and hasattr(self.hand, 'close'):
            try:
                self.hand.close()
                self.logger.info("✅ SDK closed")
            except Exception as e:
                self.logger.warning(f"Warning during SDK close: {e}")

        self.is_initialized = False
        self.logger.info("="*70)
        self.logger.info(f"✅ Driver closed (sent {self.command_count} commands)")
        self.logger.info("="*70)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False

    def get_status(self) -> dict:
        """
        Get driver status information

        Returns:
            Dictionary with status information
        """
        success_rate = (100.0 * self.successful_sends / self.total_send_attempts
                       if self.total_send_attempts > 0 else 0.0)

        return {
            'initialized': self.is_initialized,
            'mock_mode': self.mock_mode,
            'can_id': self.can_id,
            'can_channel': self.can_channel,
            'command_count': self.command_count,
            'last_command': self.last_command,
            'total_attempts': self.total_send_attempts,
            'successful_sends': self.successful_sends,
            'success_rate': success_rate,
            'dropped_frames': self.dropped_frames,
            'filtered_frames': self.filtered_frames,
            'buffer_full_errors': self.buffer_full_errors,
        }


# ============================================================================
# Testing Functions
# ============================================================================

def test_driver(mock_mode: bool = False):
    """
    Test the driver with simple movements

    Args:
        mock_mode: If True, run without hardware
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    print("\n" + "="*70)
    print("LinkerHand L10 Driver Test (Optimized)")
    if mock_mode:
        print("(MOCK MODE - No Hardware)")
    print("="*70)

    try:
        with LinkerHandDriver(
            can_id=0x27,
            can_channel="can0",
            mock_mode=mock_mode,
            enable_filtering=True
        ) as driver:

            print("\n✅ Driver initialized")
            print(f"Status: {driver.get_status()}")

            # Test 1: Reset
            print("\n[Test 1] Reset to zero...")
            driver.reset()
            time.sleep(2)

            # Test 2: Move thumb (indices 0-1)
            print("\n[Test 2] Moving thumb...")
            cmd = [45.0, 45.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            driver.move(cmd)
            time.sleep(2)

            # Test 3: Move all fingers (indices 2-5)
            print("\n[Test 3] Moving all fingers...")
            cmd = [0.0, 0.0, 60.0, 60.0, 60.0, 60.0, 0.0, 0.0, 0.0, 0.0]
            driver.move(cmd)
            time.sleep(2)

            # Test 4: Rapid movements (test filtering)
            print("\n[Test 4] Rapid movements (testing filtering)...")
            for i in range(10):
                cmd = [0.0, 0.0, 60.0 + i*0.05, 60.0, 60.0, 60.0, 0.0, 0.0, 0.0, 0.0]
                driver.move(cmd)
                time.sleep(0.033)  # 30Hz

            # Test 5: Final reset
            print("\n[Test 5] Final reset...")
            driver.reset()
            time.sleep(1)

            print("\n" + "="*70)
            print("✅ All tests completed")
            print(f"Final status: {driver.get_status()}")
            print("="*70)

    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ Test failed: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run in mock mode by default for testing
    import argparse
    parser = argparse.ArgumentParser(description='Test LinkerHand driver')
    parser.add_argument('--real', action='store_true',
                       help='Use real hardware (default: mock mode)')
    args = parser.parse_args()

    test_driver(mock_mode=not args.real)
