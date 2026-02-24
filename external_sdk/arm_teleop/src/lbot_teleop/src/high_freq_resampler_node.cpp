// Copyright (c) 2025 LinkerRobot Tech
//
// 高频重采样节点 - 解决跨时钟域抖动问题
// 功能:
// 1. 接收低频视觉指令(20-30Hz)
// 2. 使用EMA滤波器平滑插值到高频(200Hz)
// 3. 检测速度突变,防止抖动
// 4. 发布到底层驱动

#include <rclcpp/rclcpp.hpp>
#include <lbot_arm_interfaces/msg/follow_joint.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <deque>
#include <mutex>
#include <cmath>

class HighFreqResamplerNode : public rclcpp::Node
{
public:
    HighFreqResamplerNode() : Node("high_freq_resampler_node")
    {
        // 声明参数
        declare_parameters();
        load_parameters();

        // 创建订阅器 - 接收低频视觉指令
        left_vision_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            vision_left_topic_, 10,
            std::bind(&HighFreqResamplerNode::left_vision_callback, this, std::placeholders::_1));
        right_vision_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            vision_right_topic_, 10,
            std::bind(&HighFreqResamplerNode::right_vision_callback, this, std::placeholders::_1));

        // 创建发布器 - 发布高频平滑指令
        left_follow_pub_ = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
            driver_left_topic_, 10);
        right_follow_pub_ = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
            driver_right_topic_, 10);

        // 创建高频定时器 (200Hz = 5ms)
        auto timer_period = std::chrono::microseconds(static_cast<int>(1e6 / output_freq_hz_));
        high_freq_timer_ = this->create_wall_timer(
            timer_period,
            std::bind(&HighFreqResamplerNode::high_freq_timer_callback, this));

        print_config();
        RCLCPP_INFO(this->get_logger(), "High-Frequency Resampler Node initialized");
    }

private:
    // ========== 参数声明 ==========
    void declare_parameters()
    {
        this->declare_parameter<std::string>("vision_left_topic", "/left_arm_joint_control");
        this->declare_parameter<std::string>("vision_right_topic", "/right_arm_joint_control");
        this->declare_parameter<std::string>("driver_left_topic", "/robot1/left_arm/joint_follow");
        this->declare_parameter<std::string>("driver_right_topic", "/robot1/right_arm/joint_follow");

        this->declare_parameter<double>("output_freq_hz", 200.0);  // 输出频率
        this->declare_parameter<double>("ema_alpha", 0.3);         // EMA平滑系数 (0.1-0.5)
        this->declare_parameter<double>("max_joint_velocity", 2.0); // 最大关节速度 rad/s
        this->declare_parameter<double>("velocity_spike_threshold", 5.0); // 速度突变阈值
        this->declare_parameter<double>("timeout_sec", 0.5);       // 视觉信号超时时间
        this->declare_parameter<bool>("enable_velocity_limit", true);
        this->declare_parameter<bool>("follow_mode", false);       // 发送给底层的follow参数
        this->declare_parameter<bool>("convert_to_radians", true); // 是否转换角度到弧度
    }

    void load_parameters()
    {
        vision_left_topic_ = this->get_parameter("vision_left_topic").as_string();
        vision_right_topic_ = this->get_parameter("vision_right_topic").as_string();
        driver_left_topic_ = this->get_parameter("driver_left_topic").as_string();
        driver_right_topic_ = this->get_parameter("driver_right_topic").as_string();

        output_freq_hz_ = this->get_parameter("output_freq_hz").as_double();
        ema_alpha_ = this->get_parameter("ema_alpha").as_double();
        max_joint_velocity_ = this->get_parameter("max_joint_velocity").as_double();
        velocity_spike_threshold_ = this->get_parameter("velocity_spike_threshold").as_double();
        timeout_sec_ = this->get_parameter("timeout_sec").as_double();
        enable_velocity_limit_ = this->get_parameter("enable_velocity_limit").as_bool();
        follow_mode_ = this->get_parameter("follow_mode").as_bool();
        convert_to_radians_ = this->get_parameter("convert_to_radians").as_bool();

        dt_ = 1.0 / output_freq_hz_;  // 高频周期
    }

    void print_config()
    {
        RCLCPP_INFO(this->get_logger(), "========== High-Freq Resampler Config ==========");
        RCLCPP_INFO(this->get_logger(), "Vision topics: %s, %s",
                    vision_left_topic_.c_str(), vision_right_topic_.c_str());
        RCLCPP_INFO(this->get_logger(), "Driver topics: %s, %s",
                    driver_left_topic_.c_str(), driver_right_topic_.c_str());
        RCLCPP_INFO(this->get_logger(), "Output frequency: %.1f Hz (dt=%.3f ms)",
                    output_freq_hz_, dt_ * 1000.0);
        RCLCPP_INFO(this->get_logger(), "EMA alpha: %.2f", ema_alpha_);
        RCLCPP_INFO(this->get_logger(), "Max joint velocity: %.2f rad/s", max_joint_velocity_);
        RCLCPP_INFO(this->get_logger(), "Velocity spike threshold: %.2f rad/s", velocity_spike_threshold_);
        RCLCPP_INFO(this->get_logger(), "Timeout: %.2f sec", timeout_sec_);
        RCLCPP_INFO(this->get_logger(), "Velocity limit: %s", enable_velocity_limit_ ? "enabled" : "disabled");
        RCLCPP_INFO(this->get_logger(), "Follow mode: %s", follow_mode_ ? "true (high)" : "false (low)");
        RCLCPP_INFO(this->get_logger(), "================================================");
    }

    // ========== 关节状态结构 ==========
    struct JointState {
        std::vector<double> position;
        std::vector<double> velocity;
        rclcpp::Time timestamp;
        bool valid = false;
    };

    // ========== 低频视觉回调 ==========
    void left_vision_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (msg->position.empty()) return;

        std::lock_guard<std::mutex> lock(left_mutex_);

        // 转换单位
        std::vector<double> joints(msg->position.size());
        for (size_t i = 0; i < msg->position.size(); ++i) {
            joints[i] = convert_to_radians_ ? (msg->position[i] * M_PI / 180.0) : msg->position[i];
        }

        // 初始化滤波器状态
        if (!left_current_.valid) {
            left_current_.position = joints;
            left_current_.velocity.resize(joints.size(), 0.0);
            left_current_.timestamp = this->now();
            left_current_.valid = true;
            left_target_ = left_current_;
            RCLCPP_INFO(this->get_logger(), "Left arm initialized with %zu joints", joints.size());
            return;
        }

        // 更新目标位置
        left_target_.position = joints;
        left_target_.timestamp = this->now();
        left_target_.valid = true;

        // 检测速度突变
        double dt_vision = (left_target_.timestamp - left_current_.timestamp).seconds();
        if (dt_vision > 0.001) {  // 避免除零
            for (size_t i = 0; i < joints.size(); ++i) {
                double velocity = (left_target_.position[i] - left_current_.position[i]) / dt_vision;
                if (std::abs(velocity) > velocity_spike_threshold_) {
                    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                        "Left joint %zu velocity spike detected: %.2f rad/s (dt=%.3f s)",
                        i, velocity, dt_vision);
                }
            }
        }
    }

    void right_vision_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (msg->position.empty()) return;

        std::lock_guard<std::mutex> lock(right_mutex_);

        std::vector<double> joints(msg->position.size());
        for (size_t i = 0; i < msg->position.size(); ++i) {
            joints[i] = convert_to_radians_ ? (msg->position[i] * M_PI / 180.0) : msg->position[i];
        }

        if (!right_current_.valid) {
            right_current_.position = joints;
            right_current_.velocity.resize(joints.size(), 0.0);
            right_current_.timestamp = this->now();
            right_current_.valid = true;
            right_target_ = right_current_;
            RCLCPP_INFO(this->get_logger(), "Right arm initialized with %zu joints", joints.size());
            return;
        }

        right_target_.position = joints;
        right_target_.timestamp = this->now();
        right_target_.valid = true;

        double dt_vision = (right_target_.timestamp - right_current_.timestamp).seconds();
        if (dt_vision > 0.001) {
            for (size_t i = 0; i < joints.size(); ++i) {
                double velocity = (right_target_.position[i] - right_current_.position[i]) / dt_vision;
                if (std::abs(velocity) > velocity_spike_threshold_) {
                    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                        "Right joint %zu velocity spike detected: %.2f rad/s (dt=%.3f s)",
                        i, velocity, dt_vision);
                }
            }
        }
    }

    // ========== 高频定时器回调 (200Hz) ==========
    void high_freq_timer_callback()
    {
        // 处理左臂
        {
            std::lock_guard<std::mutex> lock(left_mutex_);
            if (left_current_.valid) {
                // 检查超时
                double time_since_update = (this->now() - left_target_.timestamp).seconds();
                if (time_since_update > timeout_sec_) {
                    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                        "Left vision signal timeout (%.2f s), holding position", time_since_update);
                    // 保持当前位置,速度归零
                    std::fill(left_current_.velocity.begin(), left_current_.velocity.end(), 0.0);
                } else {
                    // EMA滤波器平滑插值
                    smooth_interpolate(left_current_, left_target_, ema_alpha_, dt_);
                }

                // 发布平滑后的指令
                publish_follow_joint(left_follow_pub_, left_current_);
            }
        }

        // 处理右臂
        {
            std::lock_guard<std::mutex> lock(right_mutex_);
            if (right_current_.valid) {
                double time_since_update = (this->now() - right_target_.timestamp).seconds();
                if (time_since_update > timeout_sec_) {
                    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                        "Right vision signal timeout (%.2f s), holding position", time_since_update);
                    std::fill(right_current_.velocity.begin(), right_current_.velocity.end(), 0.0);
                } else {
                    smooth_interpolate(right_current_, right_target_, ema_alpha_, dt_);
                }

                publish_follow_joint(right_follow_pub_, right_current_);
            }
        }
    }

    // ========== EMA平滑插值算法 ==========
    void smooth_interpolate(JointState& current, const JointState& target, double alpha, double dt)
    {
        if (current.position.size() != target.position.size()) return;

        for (size_t i = 0; i < current.position.size(); ++i) {
            // EMA滤波: x_new = alpha * x_target + (1 - alpha) * x_current
            double position_new = alpha * target.position[i] + (1.0 - alpha) * current.position[i];

            // 计算速度
            double velocity_new = (position_new - current.position[i]) / dt;

            // 速度限制
            if (enable_velocity_limit_ && std::abs(velocity_new) > max_joint_velocity_) {
                double sign = (velocity_new > 0) ? 1.0 : -1.0;
                velocity_new = sign * max_joint_velocity_;
                position_new = current.position[i] + velocity_new * dt;

                RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                    "Joint %zu velocity limited: %.2f -> %.2f rad/s", i,
                    (position_new - current.position[i]) / dt, velocity_new);
            }

            current.position[i] = position_new;
            current.velocity[i] = velocity_new;
        }

        current.timestamp = this->now();
    }

    // ========== 发布函数 ==========
    void publish_follow_joint(
        rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr pub,
        const JointState& state)
    {
        auto msg = lbot_arm_interfaces::msg::FollowJoint();
        msg.joints.resize(state.position.size());
        for (size_t i = 0; i < state.position.size(); ++i) {
            msg.joints[i] = static_cast<float>(state.position[i]);
        }
        msg.follow = follow_mode_;
        pub->publish(msg);
    }

    // ========== 成员变量 ==========
    // 参数
    std::string vision_left_topic_;
    std::string vision_right_topic_;
    std::string driver_left_topic_;
    std::string driver_right_topic_;
    double output_freq_hz_;
    double ema_alpha_;
    double max_joint_velocity_;
    double velocity_spike_threshold_;
    double timeout_sec_;
    double dt_;
    bool enable_velocity_limit_;
    bool follow_mode_;
    bool convert_to_radians_;

    // 订阅器和发布器
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr left_vision_sub_;
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr right_vision_sub_;
    rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr left_follow_pub_;
    rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr right_follow_pub_;
    rclcpp::TimerBase::SharedPtr high_freq_timer_;

    // 状态变量
    JointState left_current_;
    JointState left_target_;
    JointState right_current_;
    JointState right_target_;

    std::mutex left_mutex_;
    std::mutex right_mutex_;
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<HighFreqResamplerNode>();
    RCLCPP_INFO(node->get_logger(), "High-Frequency Resampler spinning at 200Hz...");
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
