import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/ilex/Dev/VIST/src/robot/sdk/linkerhand-ros-teleop-main/linkertelopsdk/ros2/install/linkerhand_retarget'
