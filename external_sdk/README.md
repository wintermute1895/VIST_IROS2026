# External SDKs

This directory contains third-party SDKs and libraries used by the VIST project.

## Directory Structure

```
external_sdk/
├── arm_teleop/              # 外骨骼臂遥操作SDK（lbot）
├── linkerhand-ros-teleop/   # 手套遥操作SDK（ROS2）
├── linkerhand-python-sdk/   # 手部Python SDK
├── linkerarm/               # LinkerArm SDK
└── dex_retargeting/         # 手部重定向库
```

## SDKs Description

### 1. arm_teleop
- **Purpose**: 外骨骼臂遥操作SDK，基于lbot驱动
- **Type**: ROS2 package
- **Usage**: 外骨骼关节编码器数据采集和机械臂控制
- **Build**:
  ```bash
  cd external_sdk/arm_teleop
  colcon build --symlink-install
  ```

### 2. linkerhand-ros-teleop
- **Purpose**: LinkerHand数据手套遥操作SDK
- **Type**: ROS2 package
- **Usage**: 数据手套数据采集和发布
- **Build**:
  ```bash
  cd external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2
  colcon build --symlink-install
  ```

### 3. linkerhand-python-sdk
- **Purpose**: LinkerHand灵巧手Python SDK
- **Type**: Python library
- **Usage**: 灵巧手控制（非ROS2环境）
- **Install**:
  ```bash
  pip install -r external_sdk/linkerhand-python-sdk/requirements.txt
  ```

### 4. linkerarm
- **Purpose**: LinkerArm机械臂SDK
- **Type**: Python library
- **Usage**: 机械臂控制接口
- **Install**:
  ```bash
  pip install -r external_sdk/linkerarm/requirements.txt
  ```

### 5. dex_retargeting
- **Purpose**: 手部重定向库（dex-retargeting）
- **Type**: Python library
- **Source**: https://github.com/dexsuite/dex-retargeting
- **Usage**: 视觉手部姿态重定向到机器人手
- **Install**:
  ```bash
  cd external_sdk/dex_retargeting
  pip install -e .
  ```

## External SDKs (Not in Repository)

### linkerhand-ros2-sdk
- **Location**: `~/Downloads/linkerhand-ros2-sdk-main/`
- **Purpose**: LinkerHand灵巧手ROS2 SDK（原生版本）
- **Type**: ROS2 package
- **Usage**: L10灵巧手CAN控制
- **Why External**:
  - 系统级依赖，安装在用户目录
  - 需要系统权限配置（CAN接口）
  - 独立于项目版本管理

## Usage in Project

### Python Import

项目代码中引用这些SDK时，需要添加路径：

```python
import sys
import os

# 添加external_sdk到Python路径
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'external_sdk', 'dex_retargeting'))
sys.path.insert(0, os.path.join(project_root, 'external_sdk', 'linkerarm'))
```

或者在项目启动脚本中统一配置：

```python
# setup_paths.py
import sys
import os

def setup_external_sdk_paths():
    project_root = os.path.dirname(os.path.abspath(__file__))
    external_sdk = os.path.join(project_root, 'external_sdk')

    sdks = ['dex_retargeting', 'linkerarm', 'linkerhand-python-sdk']
    for sdk in sdks:
        sdk_path = os.path.join(external_sdk, sdk)
        if os.path.exists(sdk_path) and sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
```

### ROS2 Packages

ROS2 SDK需要先编译，然后source：

```bash
# 外骨骼臂SDK
cd external_sdk/arm_teleop
colcon build --symlink-install
source install/setup.bash

# 手套SDK
cd external_sdk/linkerhand-ros-teleop/linkertelopsdk/ros2
colcon build --symlink-install
source install/setup.bash
```

## Maintenance

### Updating SDKs

如果需要更新SDK：

1. **从源更新**（如果有git仓库）:
   ```bash
   cd external_sdk/<sdk_name>
   git pull
   ```

2. **手动替换**:
   - 下载新版本
   - 备份旧版本
   - 替换目录

3. **记录版本**:
   - 在此README中更新版本信息
   - 在项目文档中说明兼容性

### Version Control

这些SDK已包含在git仓库中，但build目录被忽略：

```gitignore
# SDK build directories
external_sdk/*/build/
external_sdk/*/install/
external_sdk/*/log/
external_sdk/*/__pycache__/
```

## License

各SDK的许可证请参考各自目录中的LICENSE文件。

## Contact

如果SDK有问题，请联系：
- arm_teleop: [厂商联系方式]
- linkerhand系列: 灵心巧手(北京)科技有限公司
- dex_retargeting: https://github.com/dexsuite/dex-retargeting

---

**Last Updated**: 2026-02-23
