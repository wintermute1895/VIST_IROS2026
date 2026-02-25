#!/bin/bash
# 右臂单独测试 - 快速启动脚本
# Right Arm Only Test - Quick Start Script

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <filter_type> [filter_params]"
    echo ""
    echo "可用的滤波器类型:"
    echo "  none              - 无滤波（基线）"
    echo "  ema <alpha>       - EMA滤波，例如: ema 0.3"
    echo "  one_euro <min_cutoff> <beta> - One-Euro滤波，例如: one_euro 1.0 0.007"
    echo ""
    echo "示例:"
    echo "  $0 none"
    echo "  $0 ema 0.3"
    echo "  $0 one_euro 1.0 0.007"
    exit 1
fi

FILTER_TYPE=$1

# 构建滤波器参数
FILTER_PARAMS="-p filter_type:=${FILTER_TYPE}"

case $FILTER_TYPE in
    none)
        print_info "使用无滤波模式（直通）"
        ;;
    ema)
        if [ $# -lt 2 ]; then
            print_error "EMA滤波需要alpha参数"
            exit 1
        fi
        ALPHA=$2
        FILTER_PARAMS="${FILTER_PARAMS} -p ema_alpha:=${ALPHA}"
        print_info "使用EMA滤波，alpha=${ALPHA}"
        ;;
    one_euro)
        if [ $# -lt 3 ]; then
            print_error "One-Euro滤波需要min_cutoff和beta参数"
            exit 1
        fi
        MIN_CUTOFF=$2
        BETA=$3
        FILTER_PARAMS="${FILTER_PARAMS} -p one_euro_min_cutoff:=${MIN_CUTOFF} -p one_euro_beta:=${BETA}"
        print_info "使用One-Euro滤波，min_cutoff=${MIN_CUTOFF}, beta=${BETA}"
        ;;
    *)
        print_error "未知的滤波器类型: ${FILTER_TYPE}"
        exit 1
        ;;
esac

# 安全提示
print_warn "=========================================="
print_warn "⚠️  安全提示"
print_warn "=========================================="
print_warn "1. 确保急停按钮在手边"
print_warn "2. 确认工作空间内无障碍物"
print_warn "3. 首次测试保持低速运动"
print_warn "4. 如有异常立即按下急停"
print_warn "=========================================="
echo ""
read -p "按Enter键继续，或Ctrl+C取消..."

# 检查ROS2环境
if [ -z "$ROS_DISTRO" ]; then
    print_error "ROS2环境未设置，请先source ROS2"
    exit 1
fi

print_info "ROS2环境: $ROS_DISTRO"

# 进入项目目录
cd /home/ilex/Dev/VIST

# 启动滤波节点
print_info "启动统一滤波节点..."
print_info "参数: ${FILTER_PARAMS}"

python3 src/nodes/unified_filter_node.py --ros-args \
  ${FILTER_PARAMS} \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true \
  -p performance_topic:=/filter_performance

print_info "滤波节点已停止"