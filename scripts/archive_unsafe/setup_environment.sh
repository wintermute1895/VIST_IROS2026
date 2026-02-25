#!/bin/bash
# VIST 环境自动配置脚本
# 用途：一键配置VIST项目所需的所有依赖

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印函数
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    print_error "请不要使用root用户运行此脚本"
    exit 1
fi

print_info "开始配置VIST环境..."

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VIST_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

print_info "VIST项目路径: $VIST_ROOT"

# 1. 检查Ubuntu版本
print_info "检查系统版本..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$VERSION_ID" != "22.04" ]; then
        print_warn "推荐使用Ubuntu 22.04，当前版本: $VERSION_ID"
        read -p "是否继续? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    print_warn "无法检测系统版本"
fi

# 2. 检查ROS2 Humble
print_info "检查ROS2 Humble..."
if [ -f /opt/ros/humble/setup.bash ]; then
    print_info "✓ ROS2 Humble已安装"
else
    print_warn "ROS2 Humble未安装"
    read -p "是否自动安装ROS2 Humble? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "安装ROS2 Humble..."

        # 添加ROS2源
        sudo apt update
        sudo apt install -y software-properties-common curl
        sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
          -o /usr/share/keyrings/ros-archive-keyring.gpg

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
          http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
          | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

        # 安装ROS2
        sudo apt update
        sudo apt install -y ros-humble-desktop ros-dev-tools ros-humble-rosbag2-py

        print_info "✓ ROS2 Humble安装完成"
    else
        print_error "ROS2 Humble是必需的，请手动安装后重新运行此脚本"
        exit 1
    fi
fi

# 3. 检查Python版本
print_info "检查Python版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python版本过低: $PYTHON_VERSION (需要 >= $REQUIRED_VERSION)"
    print_info "建议使用conda创建Python 3.10环境"
    exit 1
else
    print_info "✓ Python版本: $PYTHON_VERSION"
fi

# 4. 安装Python依赖
print_info "安装Python依赖..."
if [ -f "$VIST_ROOT/requirements.txt" ]; then
    pip install -r "$VIST_ROOT/requirements.txt"
    print_info "✓ Python依赖安装完成"
else
    print_warn "未找到requirements.txt"
fi

# 5. 编译lbot_arm_interfaces
print_info "编译lbot_arm_interfaces..."
if [ -d "$VIST_ROOT/external_sdk/arm_teleop" ]; then
    cd "$VIST_ROOT/external_sdk/arm_teleop"

    # Source ROS2
    source /opt/ros/humble/setup.bash

    # 编译
    colcon build --packages-select lbot_arm_interfaces

    if [ $? -eq 0 ]; then
        print_info "✓ lbot_arm_interfaces编译成功"
    else
        print_error "lbot_arm_interfaces编译失败"
        exit 1
    fi
else
    print_warn "未找到arm_teleop SDK"
fi

# 6. 创建环境配置文件
print_info "创建环境配置文件..."
ENV_FILE="$HOME/.vist_env.sh"

cat > "$ENV_FILE" << EOF
#!/bin/bash
# VIST 环境配置
# 自动生成于: $(date)

# ROS2 Humble
source /opt/ros/humble/setup.bash

# VIST项目路径
export VIST_ROOT="$VIST_ROOT"

# 自定义消息类型
if [ -f "\$VIST_ROOT/external_sdk/arm_teleop/install/setup.bash" ]; then
    source "\$VIST_ROOT/external_sdk/arm_teleop/install/setup.bash"
fi

# 灵巧手SDK（可选）
if [ -f "\$VIST_ROOT/external_sdk/linkerhand-ros2-sdk/install/setup.bash" ]; then
    source "\$VIST_ROOT/external_sdk/linkerhand-ros2-sdk/install/setup.bash"
fi

# Python路径
export PYTHONPATH="\$VIST_ROOT/src:\$PYTHONPATH"

echo "✓ VIST环境已加载 (项目路径: \$VIST_ROOT)"
EOF

chmod +x "$ENV_FILE"
print_info "✓ 环境配置文件已创建: $ENV_FILE"

# 7. 添加到bashrc
if ! grep -q "source ~/.vist_env.sh" "$HOME/.bashrc"; then
    print_info "添加环境配置到 ~/.bashrc..."
    echo "" >> "$HOME/.bashrc"
    echo "# VIST环境" >> "$HOME/.bashrc"
    echo "source ~/.vist_env.sh" >> "$HOME/.bashrc"
    print_info "✓ 已添加到 ~/.bashrc"
else
    print_info "✓ ~/.bashrc已包含VIST环境配置"
fi

# 8. 验证安装
print_info "验证安装..."
source "$ENV_FILE"

# 检查ROS2
if command -v ros2 &> /dev/null; then
    print_info "✓ ROS2命令可用"
else
    print_error "✗ ROS2命令不可用"
fi

# 检查Python依赖
python3 -c "import numpy, scipy, matplotlib, yaml" 2>/dev/null
if [ $? -eq 0 ]; then
    print_info "✓ Python依赖可用"
else
    print_warn "✗ 部分Python依赖不可用"
fi

# 检查消息类型
python3 -c "from lbot_arm_interfaces.msg import FollowJoint" 2>/dev/null
if [ $? -eq 0 ]; then
    print_info "✓ lbot_arm_interfaces可用"
else
    print_warn "✗ lbot_arm_interfaces不可用（需要source环境）"
fi

# 完成
echo ""
print_info "========================================="
print_info "VIST环境配置完成！"
print_info "========================================="
echo ""
print_info "下一步："
print_info "1. 重新打开终端或运行: source ~/.bashrc"
print_info "2. 验证安装: cd $VIST_ROOT && ./scripts/verify_installation.sh"
print_info "3. 查看文档: cat $VIST_ROOT/SETUP.md"
echo ""