#!/bin/bash
# 数据采集脚本 - 右臂消融实验
# Data Collection Script - Right Arm Ablation Study

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
if [ $# -lt 2 ]; then
    echo "用法: $0 <exp_name> <duration_seconds>"
    echo ""
    echo "参数:"
    echo "  exp_name          实验名称"
    echo "  duration_seconds  采集时长（秒）"
    echo ""
    echo "说明:"
    echo "  默认采集所有数据（相机、手臂、手部控制）"
    echo "  采集后可以根据需要筛选和训练模型"
    echo ""
    echo "示例:"
    echo "  $0 exp0_no_filter 30"
    echo "  $0 exp1_ema_alpha03 30"
    exit 1
fi

EXP_NAME=$1
DURATION=$2

# 默认采集所有数据
WITH_CAMERA=true
WITH_HAND=true

# 创建实验目录
EXP_DIR="/home/ilex/Dev/VIST/data/exp_right_arm_only_$(date +%Y%m%d)"
mkdir -p "$EXP_DIR"

print_info "实验名称: ${EXP_NAME}"
print_info "采集时长: ${DURATION}秒"
print_info "保存目录: ${EXP_DIR}"
if [ "$WITH_CAMERA" = true ]; then
    print_info "相机录制: 启用"
else
    print_info "相机录制: 禁用"
fi
if [ "$WITH_HAND" = true ]; then
    print_info "手部控制录制: 启用"
else
    print_info "手部控制录制: 禁用"
fi

# 检查话题是否存在
print_info "检查话题连接..."

TOPICS=(
    "/right_arm_joint_control"
    "/filtered_right_joint_control"
    "/right_arm/joint_follow"
    "/right_arm/joint_states"
)

for topic in "${TOPICS[@]}"; do
    if ros2 topic list | grep -q "^${topic}$"; then
        print_info "✓ ${topic}"
    else
        print_warn "✗ ${topic} (未找到，将在采集时等待)"
    fi
done

# 检查发布者数量
print_info "检查发布者数量..."
PUB_COUNT=$(ros2 topic info /filtered_right_joint_control 2>/dev/null | grep "Publisher count:" | awk '{print $3}')

if [ -n "$PUB_COUNT" ]; then
    if [ "$PUB_COUNT" -eq 1 ]; then
        print_info "✓ 发布者数量正常: ${PUB_COUNT}"
    elif [ "$PUB_COUNT" -eq 0 ]; then
        print_error "✗ 滤波节点未启动！"
        print_error "请先启动滤波节点: ./scripts/start_right_arm_filter.sh none"
        exit 1
    else
        print_error "✗ 发布者数量异常: ${PUB_COUNT} (应该为1)"
        print_error "可能存在话题碰撞！请检查是否有多个滤波节点在运行"
        exit 1
    fi
fi

# 倒计时
print_warn "=========================================="
print_warn "准备开始数据采集"
print_warn "=========================================="
print_warn "请准备执行以下动作序列:"
print_warn "  1. 前后移动 (5秒)"
print_warn "  2. 左右移动 (5秒)"
print_warn "  3. 上下移动 (5秒)"
print_warn "  4. 旋转运动 (5秒)"
print_warn "  5. 组合运动 (剩余时间)"
print_warn "=========================================="
echo ""

for i in {3..1}; do
    echo -e "${BLUE}${i}...${NC}"
    sleep 1
done

print_info "开始采集！"

# 开始录制
cd "$EXP_DIR"

# 基础话题
RECORD_TOPICS=(
  /right_arm_joint_control
  /filtered_right_joint_control
  /right_arm/joint_follow
  /right_arm/joint_states
  /filter_performance
)

# 如果启用相机，添加相机话题
if [ "$WITH_CAMERA" = true ]; then
    CAMERA_TOPICS=(
      /camera/color/image_raw
      /camera/depth/image_raw
      /camera/color/camera_info
    )

    print_info "检查相机话题..."
    for topic in "${CAMERA_TOPICS[@]}"; do
        if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
            print_info "✓ 相机话题: ${topic}"
            RECORD_TOPICS+=("$topic")
        else
            print_warn "✗ 相机话题未找到: ${topic}"
        fi
    done
fi

# 如果启用手部控制，添加手部话题
if [ "$WITH_HAND" = true ]; then
    HAND_TOPICS=(
      /cb_right_hand_control_cmd
      /cb_right_hand_state
    )

    print_info "检查手部控制话题..."
    for topic in "${HAND_TOPICS[@]}"; do
        if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
            print_info "✓ 手部话题: ${topic}"
            RECORD_TOPICS+=("$topic")
        else
            print_warn "✗ 手部话题未找到: ${topic}"
        fi
    done
fi

# 启动录制
ros2 bag record "${RECORD_TOPICS[@]}" -o "${EXP_NAME}" &

RECORD_PID=$!

# 等待指定时长
sleep ${DURATION}

# 发送 SIGINT 信号停止录制
kill -SIGINT $RECORD_PID

# 等待进程结束
wait $RECORD_PID 2>/dev/null || true

print_info "数据采集完成！"
print_info "数据保存在: ${EXP_DIR}/${EXP_NAME}"

# 显示文件信息
print_info "文件信息:"
du -sh "${EXP_DIR}/${EXP_NAME}"

# 快速统计
print_info "快速统计:"
ros2 bag info "${EXP_DIR}/${EXP_NAME}" 2>/dev/null || true

print_info "=========================================="
print_info "✓ 实验 ${EXP_NAME} 完成"
print_info "=========================================="