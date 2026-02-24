#!/bin/bash
# 自动应用SDK补丁脚本

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VIST_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
PATCHES_DIR="$VIST_ROOT/patches"

echo "应用SDK补丁..."

# 应用arm_teleop QoS修复
if [ -f "$PATCHES_DIR/arm_teleop_qos_fix.patch" ]; then
    echo "应用 arm_teleop_qos_fix.patch..."
    cd "$VIST_ROOT/external_sdk/arm_teleop"
    if git apply --check "$PATCHES_DIR/arm_teleop_qos_fix.patch" 2>/dev/null; then
        git apply "$PATCHES_DIR/arm_teleop_qos_fix.patch"
        echo "✓ arm_teleop_qos_fix.patch 应用成功"
    else
        echo "⚠ arm_teleop_qos_fix.patch 已应用或不适用"
    fi
fi

# 应用arm_teleop配置修改
if [ -f "$PATCHES_DIR/arm_teleop_config.patch" ]; then
    echo "应用 arm_teleop_config.patch..."
    cd "$VIST_ROOT/external_sdk/arm_teleop"
    if git apply --check "$PATCHES_DIR/arm_teleop_config.patch" 2>/dev/null; then
        git apply "$PATCHES_DIR/arm_teleop_config.patch"
        echo "✓ arm_teleop_config.patch 应用成功"
    else
        echo "⚠ arm_teleop_config.patch 已应用或不适用"
    fi
fi

echo "补丁应用完成"