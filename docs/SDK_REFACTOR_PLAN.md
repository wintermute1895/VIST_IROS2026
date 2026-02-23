# SDK目录重构方案

## 当前问题

SDK被放在 `src/robot/sdk/` 下，这不符合项目结构最佳实践：
- `src/` 目录应该只包含项目自己的源代码
- 第三方SDK应该与项目代码分离
- 难以区分哪些是项目代码，哪些是第三方依赖

## 推荐方案

### 方案A: 移动到 external/ 目录（推荐）

```
VIST/
├── src/                    # 项目源代码
│   ├── core/
│   ├── control/
│   ├── robot/
│   │   ├── arm/           # 臂控制接口（项目代码）
│   │   ├── hand/          # 手控制接口（项目代码）
│   │   ├── arm_driver.py
│   │   └── hand_driver.py
│   └── ...
│
├── external/               # 第三方SDK和库
│   ├── arm_teleop/        # 外骨骼臂SDK
│   ├── linkerhand-ros-teleop/  # 手套SDK
│   ├── linkerhand-python-sdk/  # 手部Python SDK
│   ├── linkerarm/         # LinkerArm SDK
│   └── dex_retargeting/   # 手部重定向库
│
└── ...
```

**优点**:
- 清晰区分项目代码和第三方代码
- 符合常见的项目结构规范
- 便于管理和更新SDK

### 方案B: 使用 git submodule

如果这些SDK有git仓库，可以使用submodule管理：

```bash
# 移除当前的SDK目录
git rm -r src/robot/sdk

# 添加为submodule
git submodule add <repo_url> external/arm_teleop
git submodule add <repo_url> external/linkerhand-ros-teleop
# ...
```

**优点**:
- 可以跟踪SDK的版本
- 便于更新SDK
- 不会污染项目仓库

**缺点**:
- 需要SDK有公开的git仓库
- submodule管理稍微复杂

### 方案C: 保持现状，但添加说明

如果暂时不想移动，至少应该：
1. 在 `src/robot/sdk/README.md` 中说明这些是第三方SDK
2. 添加 `.gitignore` 规则（如果SDK很大）
3. 在文档中明确说明SDK的来源和版本

## 实施步骤（方案A）

### 1. 创建 external 目录并移动SDK

```bash
# 创建external目录
mkdir -p external

# 移动SDK
mv src/robot/sdk/arm_teleop external/
mv src/robot/sdk/linkerhand-ros-teleop-main external/linkerhand-ros-teleop
mv src/robot/sdk/linkerhand-python-sdk-main external/linkerhand-python-sdk
mv src/robot/sdk/linkerarm external/
mv src/robot/sdk/dex_retargeting external/

# 删除空的sdk目录
rmdir src/robot/sdk
```

### 2. 更新代码中的导入路径

需要更新所有引用SDK的代码，例如：

**之前**:
```python
from src.robot.sdk.dex_retargeting import ...
```

**之后**:
```python
import sys
sys.path.append('external/dex_retargeting')
from dex_retargeting import ...
```

或者在项目根目录的 `__init__.py` 或启动脚本中统一添加路径：

```python
import sys
import os

# 添加external目录到Python路径
external_dir = os.path.join(os.path.dirname(__file__), 'external')
for sdk in ['dex_retargeting', 'linkerhand-python-sdk']:
    sys.path.insert(0, os.path.join(external_dir, sdk))
```

### 3. 更新配置文件

如果配置文件中有SDK路径，也需要更新：

```yaml
# config/experiment_config.yaml
hand:
  ros2_sdk_path: "~/Downloads/linkerhand-ros2-sdk-main"  # 外部SDK，不在项目中

# 项目内的SDK路径
sdk:
  dex_retargeting: "external/dex_retargeting"
  linkerarm: "external/linkerarm"
```

### 4. 创建 external/README.md

```markdown
# External Dependencies

This directory contains third-party SDKs and libraries.

## SDKs

### arm_teleop
- **Purpose**: 外骨骼臂遥操作SDK（lbot）
- **Source**: [来源链接]
- **Version**: [版本号]
- **License**: [许可证]

### linkerhand-ros-teleop
- **Purpose**: 手套遥操作SDK
- **Source**: [来源链接]
- **Version**: [版本号]

### linkerhand-python-sdk
- **Purpose**: 手部Python SDK
- **Source**: [来源链接]
- **Version**: [版本号]

### linkerarm
- **Purpose**: LinkerArm SDK
- **Source**: [来源链接]
- **Version**: [版本号]

### dex_retargeting
- **Purpose**: 手部重定向库
- **Source**: https://github.com/dexsuite/dex-retargeting
- **Version**: [版本号]

## Installation

These SDKs are included in the repository for convenience.
To update them, please refer to their respective documentation.
```

### 5. 更新 .gitignore（可选）

如果SDK很大或者经常变化，可以考虑不提交到git：

```gitignore
# External SDKs (download separately)
external/arm_teleop/build/
external/*/build/
external/*/__pycache__/
```

## 其他SDK的处理

### linkerhand-ros2-sdk（在 ~/Downloads/）

这个SDK在项目外部，这是正确的做法。可以考虑：

1. **保持现状**（推荐）: 作为系统级依赖，安装在用户目录
2. **添加到external/**: 如果需要版本控制
3. **使用软链接**: `ln -s ~/Downloads/linkerhand-ros2-sdk-main external/linkerhand-ros2-sdk`

## 推荐行动

### 立即执行（最小改动）
1. 创建 `external/` 目录
2. 移动SDK到 `external/`
3. 更新导入路径
4. 添加 `external/README.md`

### 后续优化
1. 考虑使用git submodule
2. 或者通过包管理器安装（如果SDK支持）
3. 统一SDK版本管理

---

**准备好重构SDK目录了吗？**
