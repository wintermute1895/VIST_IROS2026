#!/bin/bash
# 检查数据单位是否一致

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== 数据单位检查工具 ===${NC}"
echo ""

# 加载ROS2环境
source /opt/ros/humble/setup.bash 2>/dev/null || true
if [ -f "external_sdk/arm_teleop/install/setup.bash" ]; then
    source external_sdk/arm_teleop/install/setup.bash 2>/dev/null || true
fi

echo "检查话题是否存在..."
TOPICS=$(ros2 topic list 2>/dev/null)

# 检查遥操臂话题
if echo "$TOPICS" | grep -q "/left_joint_follow"; then
    echo -e "${GREEN}✓ 找到遥操臂话题: /left_joint_follow${NC}"
    HAS_EXO=true
else
    echo -e "${YELLOW}⚠ 未找到遥操臂话题${NC}"
    HAS_EXO=false
fi

# 检查视觉控制话题
if echo "$TOPICS" | grep -q "/vision_control/joint_follow"; then
    echo -e "${GREEN}✓ 找到视觉控制话题: /vision_control/joint_follow${NC}"
    HAS_VISION=true
else
    echo -e "${YELLOW}⚠ 未找到视觉控制话题${NC}"
    HAS_VISION=false
fi

echo ""

# 函数：提取关节数据并分析
analyze_topic() {
    local topic=$1
    local name=$2

    echo -e "${YELLOW}分析 $name...${NC}"

    # 获取一条消息
    local data=$(timeout 5 ros2 topic echo "$topic" --once 2>/dev/null | grep "joints:")

    if [ -z "$data" ]; then
        echo -e "${RED}✗ 超时：5秒内未接收到数据${NC}"
        return 1
    fi

    # 提取数值
    local values=$(echo "$data" | sed 's/joints: \[//; s/\]//' | tr ',' '\n')

    # 计算统计信息
    local max_val=-999
    local min_val=999
    local sum=0
    local count=0

    while IFS= read -r val; do
        val=$(echo "$val" | xargs)  # 去除空格
        if [ ! -z "$val" ]; then
            # 使用bc进行浮点数比较
            if (( $(echo "$val > $max_val" | bc -l) )); then
                max_val=$val
            fi
            if (( $(echo "$val < $min_val" | bc -l) )); then
                min_val=$val
            fi
            sum=$(echo "$sum + $val" | bc -l)
            count=$((count + 1))
        fi
    done <<< "$values"

    if [ $count -eq 0 ]; then
        echo -e "${RED}✗ 无法解析数据${NC}"
        return 1
    fi

    local avg=$(echo "scale=4; $sum / $count" | bc -l)
    local abs_max=$(echo "scale=4; if ($max_val > -$min_val) $max_val else -$min_val" | bc -l)

    echo "  关节数量: $count"
    echo "  最小值: $min_val"
    echo "  最大值: $max_val"
    echo "  平均值: $avg"
    echo "  绝对最大值: $abs_max"

    # 判断单位
    if (( $(echo "$abs_max < 6.28" | bc -l) )); then
        echo -e "  ${GREEN}✓ 单位: 弧度 (radians)${NC}"
        echo "弧度" > /tmp/unit_$name
    else
        echo -e "  ${YELLOW}⚠ 单位: 角度 (degrees)${NC}"
        echo "角度" > /tmp/unit_$name
    fi

    echo ""
}

# 分析遥操臂
if [ "$HAS_EXO" = true ]; then
    analyze_topic "/left_joint_follow" "exo"
fi

# 分析视觉控制
if [ "$HAS_VISION" = true ]; then
    analyze_topic "/vision_control/joint_follow" "vision"
fi

# 对比结果
echo -e "${GREEN}=== 结论 ===${NC}"

if [ "$HAS_EXO" = true ] && [ "$HAS_VISION" = true ]; then
    exo_unit=$(cat /tmp/unit_exo 2>/dev/null || echo "未知")
    vision_unit=$(cat /tmp/unit_vision 2>/dev/null || echo "未知")

    if [ "$exo_unit" = "$vision_unit" ]; then
        echo -e "${GREEN}✓ 单位一致: 都是 $exo_unit${NC}"
        echo ""
        echo "可以直接对比数据！"
    else
        echo -e "${RED}✗ 单位不一致:${NC}"
        echo "  遥操臂: $exo_unit"
        echo "  视觉控制: $vision_unit"
        echo ""
        echo "需要转换单位！"
        if [ "$vision_unit" = "角度" ]; then
            echo "在发布前添加: joints = [np.deg2rad(j) for j in joints]"
        fi
    fi

    # 清理临时文件
    rm -f /tmp/unit_exo /tmp/unit_vision
elif [ "$HAS_EXO" = false ] && [ "$HAS_VISION" = false ]; then
    echo -e "${RED}✗ 没有找到任何话题${NC}"
    echo ""
    echo "请先启动节点："
    echo "  遥操臂: ./scripts/start_arm_teleop.sh"
    echo "  视觉控制: python3 scripts/experiments/simulate_full_flow.py"
else
    echo -e "${YELLOW}⚠ 只找到部分话题，无法对比${NC}"
fi

echo ""
echo "提示："
echo "- 弧度范围: -3.14 ~ 3.14"
echo "- 角度范围: -180 ~ 180"
echo "- 转换公式: 弧度 = 角度 × π / 180"