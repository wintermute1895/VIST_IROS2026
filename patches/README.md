# SDK 修改补丁

本目录包含对外部SDK的修改补丁。

## 为什么使用补丁？

外部SDK（如 `arm_teleop`, `linkerhand-ros2-sdk`）是独立的git仓库，不应该直接包含在主仓库中。但我们对这些SDK做了一些必要的修改，因此使用补丁文件来记录这些修改。

## 补丁列表

### 1. arm_teleop_qos_fix.patch

**修改内容**：修复ROS2 QoS配置问题

**文件**：`external_sdk/arm_teleop/src/lbot_driver/src/lbot_driver.cpp`

**说明**：将 `rclcpp::QoS` 改为 `rmw_qos_profile_t` 以兼容ROS2 Humble

**应用方法**：
```bash
cd external_sdk/arm_teleop
git apply ../../patches/arm_teleop_qos_fix.patch
```

### 2. arm_teleop_config.patch

**修改内容**：遥操配置文件修改

**文件**：`external_sdk/arm_teleop/src/lbot_teleop/`

**说明**：调整遥操参数以适配VIST系统

**应用方法**：
```bash
cd external_sdk/arm_teleop
git apply ../../patches/arm_teleop_config.patch
```

## 自动应用所有补丁

```bash
# 在VIST根目录运行
./scripts/apply_sdk_patches.sh
```

## 创建新补丁

如果你修改了SDK代码，创建新补丁：

```bash
# 在SDK目录中
cd external_sdk/arm_teleop
git diff > ../../patches/my_changes.patch

# 或者针对特定文件
git diff src/lbot_driver/src/lbot_driver.cpp > ../../patches/driver_fix.patch
```

## 注意事项

1. **不要直接提交SDK源码**：SDK是独立的git仓库，应该作为submodule或通过补丁管理
2. **补丁可能失效**：如果SDK更新，补丁可能需要重新生成
3. **记录修改原因**：在补丁说明中清楚记录为什么需要这个修改
4. **考虑上游贡献**：如果修改是通用的bug修复，考虑向上游SDK提交PR

## SDK管理建议

### 方案A：使用git submodule（推荐）

```bash
# 添加SDK为submodule
git submodule add <sdk-repo-url> external_sdk/arm_teleop

# 克隆时初始化submodule
git clone --recursive <your-repo-url>

# 或者在已克隆的仓库中
git submodule update --init --recursive
```

### 方案B：Fork SDK

1. Fork SDK到你的GitHub账号
2. 在fork中提交修改
3. 在VIST项目中引用你的fork

### 方案C：使用补丁（当前方案）

适用于：
- SDK没有公开仓库
- 修改较少且临时
- 不想管理submodule

---

**最后更新**: 2026-02-24