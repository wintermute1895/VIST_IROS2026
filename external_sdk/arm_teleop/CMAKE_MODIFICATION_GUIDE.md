# CMakeLists.txt 修改指南

## 需要在 src/lbot_teleop/CMakeLists.txt 中添加以下内容:

### 1. 在文件末尾的 install() 之前添加:

```cmake
# ========== 高频重采样节点 ==========
add_executable(high_freq_resampler_node src/high_freq_resampler_node.cpp)
ament_target_dependencies(high_freq_resampler_node
  rclcpp
  sensor_msgs
  lbot_arm_interfaces
)

# 安装可执行文件
install(TARGETS
  high_freq_resampler_node
  DESTINATION lib/${PROJECT_NAME}
)
```

### 2. 如果已有 install(TARGETS ...) 部分,则添加到现有列表中:

```cmake
install(TARGETS
  teleop_bridge_node  # 原有的
  high_freq_resampler_node  # 新增
  DESTINATION lib/${PROJECT_NAME}
)
```

### 3. 安装配置文件和launch文件(如果还没有):

```cmake
# 安装配置文件
install(DIRECTORY
  config
  DESTINATION share/${PROJECT_NAME}
)

# 安装launch文件
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)
```

### 4. 完整示例

如果你的 CMakeLists.txt 比较简单,可以参考以下完整结构:

```cmake
cmake_minimum_required(VERSION 3.8)
project(lbot_teleop)

# 编译选项
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找依赖
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(lbot_arm_interfaces REQUIRED)

# 包含目录
include_directories(include)

# ========== 原有的遥操作桥接节点 ==========
add_executable(teleop_bridge_node src/teleop_bridge_node.cpp)
ament_target_dependencies(teleop_bridge_node
  rclcpp
  sensor_msgs
  lbot_arm_interfaces
)

# ========== 高频重采样节点 ==========
add_executable(high_freq_resampler_node src/high_freq_resampler_node.cpp)
ament_target_dependencies(high_freq_resampler_node
  rclcpp
  sensor_msgs
  lbot_arm_interfaces
)

# ========== 安装 ==========
install(TARGETS
  teleop_bridge_node
  high_freq_resampler_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  config
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
```

## 编译步骤

```bash
cd /home/luka/Desktop/arm_teleop
colcon build --packages-select lbot_teleop
source install/setup.bash
```

## 验证安装

```bash
# 检查可执行文件是否安装
ros2 pkg executables lbot_teleop

# 应该看到:
# lbot_teleop high_freq_resampler_node
# lbot_teleop teleop_bridge_node

# 检查launch文件是否安装
ros2 launch lbot_teleop high_freq_resampler.launch.py --show-args
```
