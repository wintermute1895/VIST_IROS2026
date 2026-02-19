#!/usr/bin/env python3
"""
VIST实时参数调试界面
使用Gradio创建Web界面，实时调整和验证VIST机制
"""

import gradio as gr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.parameter_override import ParameterOverrideManager

# 全局状态
override_manager = ParameterOverrideManager()
state_history = {
    'time': [],
    'alpha': [],
    'alpha_override': [],
    'r_human': [],
    'r_virtual': [],
    'end_effector_pos': [],
    'end_effector_vel': [],
}

def update_alpha_override(value, enabled):
    """更新α覆盖"""
    if enabled:
        override_manager.update_alpha(value)
        return f"✅ α强制设置为 {value:.3f}"
    else:
        override_manager.update_alpha(None)
        return "⚪ α由意图检测自动计算"

def update_r_human_override(value, enabled):
    """更新R_human覆盖"""
    if enabled:
        override_manager.update_r_human(value)
        return f"✅ R_human强制设置为 {value:.2e}"
    else:
        override_manager.update_r_human(None)
        return "⚪ R_human由α自动调度"

def update_r_virtual_override(value, enabled):
    """更新R_virtual覆盖"""
    if enabled:
        override_manager.update_r_virtual(value)
        return f"✅ R_virtual强制设置为 {value:.2e}"
    else:
        override_manager.update_r_virtual(None)
        return "⚪ R_virtual由α自动调度"

def update_manifold_override(enabled):
    """更新流形约束覆盖"""
    if enabled:
        override_manager.update_manifold_enabled(True)
        return "✅ 流形约束强制启用"
    else:
        override_manager.update_manifold_enabled(None)
        return "⚪ 流形约束由α自动控制"

def update_human_lambda(value):
    """更新R_human指数系数"""
    override_manager.update_human_lambda(value)
    return f"λ = {value:.2f}"

def update_virtual_min(value):
    """更新R_virtual最小值"""
    override_manager.update_virtual_min(value)
    return f"R_min = {value:.2e}"

def update_z_lock_threshold(value):
    """更新Z轴锁定阈值"""
    override_manager.update_z_lock_threshold(value)
    return f"阈值 = {value:.2f}"

def reset_all_overrides():
    """重置所有覆盖"""
    override_manager.reset()
    return "✅ 所有覆盖已重置"

def plot_alpha_history():
    """绘制α历史"""
    fig = Figure(figsize=(10, 4))
    ax = fig.add_subplot(111)

    if len(state_history['time']) > 0:
        ax.plot(state_history['time'], state_history['alpha'],
                label='计算的α', linewidth=2)
        if any(state_history['alpha_override']):
            ax.plot(state_history['time'], state_history['alpha_override'],
                    label='覆盖的α', linestyle='--', linewidth=2)

    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('意图因子 α')
    ax.set_ylim([0, 1])
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title('意图因子α时间序列')

    return fig

def plot_covariance_history():
    """绘制协方差历史"""
    fig = Figure(figsize=(10, 4))
    ax = fig.add_subplot(111)

    if len(state_history['time']) > 0:
        ax.semilogy(state_history['time'], state_history['r_human'],
                   label='R_human', linewidth=2)
        ax.semilogy(state_history['time'], state_history['r_virtual'],
                   label='R_virtual', linewidth=2)

    ax.set_xlabel('时间 (s)')
    ax.set_ylabel('观测噪声协方差')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_title('观测噪声协方差时间序列')

    return fig

def plot_trajectory():
    """绘制末端轨迹"""
    fig = Figure(figsize=(10, 8))

    # XY平面
    ax1 = fig.add_subplot(221)
    if len(state_history['end_effector_pos']) > 0:
        pos = np.array(state_history['end_effector_pos'])
        ax1.plot(pos[:, 0], pos[:, 1], linewidth=2)
        ax1.scatter(pos[0, 0], pos[0, 1], c='green', s=100, label='起点')
        ax1.scatter(pos[-1, 0], pos[-1, 1], c='red', s=100, label='终点')
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_title('XY平面轨迹')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.axis('equal')

    # XZ平面
    ax2 = fig.add_subplot(222)
    if len(state_history['end_effector_pos']) > 0:
        pos = np.array(state_history['end_effector_pos'])
        ax2.plot(pos[:, 0], pos[:, 2], linewidth=2)
        ax2.scatter(pos[0, 0], pos[0, 2], c='green', s=100, label='起点')
        ax2.scatter(pos[-1, 0], pos[-1, 2], c='red', s=100, label='终点')
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Z (m)')
    ax2.set_title('XZ平面轨迹')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # YZ平面
    ax3 = fig.add_subplot(223)
    if len(state_history['end_effector_pos']) > 0:
        pos = np.array(state_history['end_effector_pos'])
        ax3.plot(pos[:, 1], pos[:, 2], linewidth=2)
        ax3.scatter(pos[0, 1], pos[0, 2], c='green', s=100, label='起点')
        ax3.scatter(pos[-1, 1], pos[-1, 2], c='red', s=100, label='终点')
    ax3.set_xlabel('Y (m)')
    ax3.set_ylabel('Z (m)')
    ax3.set_title('YZ平面轨迹')
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # 3D轨迹
    ax4 = fig.add_subplot(224, projection='3d')
    if len(state_history['end_effector_pos']) > 0:
        pos = np.array(state_history['end_effector_pos'])
        ax4.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=2)
        ax4.scatter(pos[0, 0], pos[0, 1], pos[0, 2], c='green', s=100, label='起点')
        ax4.scatter(pos[-1, 0], pos[-1, 1], pos[-1, 2], c='red', s=100, label='终点')
    ax4.set_xlabel('X (m)')
    ax4.set_ylabel('Y (m)')
    ax4.set_zlabel('Z (m)')
    ax4.set_title('3D轨迹')
    ax4.legend()

    fig.tight_layout()
    return fig

def create_debug_interface():
    """创建调试界面"""

    with gr.Blocks(title="VIST实时参数调试", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# VIST实时参数调试界面")
        gr.Markdown("用于验证VIST机制效果的实时参数调整工具")

        with gr.Tabs():
            # Tab 1: 机制层参数覆盖
            with gr.Tab("🎯 机制层参数"):
                gr.Markdown("## 强制覆盖被机制影响的参数")
                gr.Markdown("⚠️ 这些参数会绕过VIST机制，直接设置最终值")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 意图因子 α")
                        alpha_enabled = gr.Checkbox(label="启用α覆盖", value=False)
                        alpha_slider = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.5, step=0.01,
                            label="强制α值", interactive=True
                        )
                        alpha_status = gr.Textbox(label="状态", value="⚪ α由意图检测自动计算")

                        gr.Markdown("**验证实验**: 设置α=1.0，在摄像头前让手在XY方向抖动，观察末端是否锁定在Z轴")

                    with gr.Column():
                        gr.Markdown("### 观测噪声 R_human")
                        r_human_enabled = gr.Checkbox(label="启用R_human覆盖", value=False)
                        r_human_slider = gr.Slider(
                            minimum=-4, maximum=-1, value=-2, step=0.1,
                            label="log10(R_human)", interactive=True
                        )
                        r_human_status = gr.Textbox(label="状态", value="⚪ R_human由α自动调度")

                        gr.Markdown("**验证实验**: 设置R_human=1e-1（高噪声），观察人类抖动是否被抑制")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 观测噪声 R_virtual")
                        r_virtual_enabled = gr.Checkbox(label="启用R_virtual覆盖", value=False)
                        r_virtual_slider = gr.Slider(
                            minimum=-4, maximum=-1, value=-3, step=0.1,
                            label="log10(R_virtual)", interactive=True
                        )
                        r_virtual_status = gr.Textbox(label="状态", value="⚪ R_virtual由α自动调度")

                        gr.Markdown("**验证实验**: 设置R_virtual=1e-4（低噪声），观察虚拟引导的磁吸引效果")

                    with gr.Column():
                        gr.Markdown("### 流形约束")
                        manifold_enabled = gr.Checkbox(label="强制启用流形约束", value=False)
                        manifold_status = gr.Textbox(label="状态", value="⚪ 流形约束由α自动控制")

                        gr.Markdown("**验证实验**: 强制启用流形约束，观察末端是否只在Z轴运动")

                # 更新回调
                alpha_slider.change(
                    fn=lambda v, e: update_alpha_override(v, e),
                    inputs=[alpha_slider, alpha_enabled],
                    outputs=alpha_status
                )
                alpha_enabled.change(
                    fn=lambda v, e: update_alpha_override(v, e),
                    inputs=[alpha_slider, alpha_enabled],
                    outputs=alpha_status
                )

                r_human_slider.change(
                    fn=lambda v, e: update_r_human_override(10**v, e),
                    inputs=[r_human_slider, r_human_enabled],
                    outputs=r_human_status
                )
                r_human_enabled.change(
                    fn=lambda v, e: update_r_human_override(10**v, e),
                    inputs=[r_human_slider, r_human_enabled],
                    outputs=r_human_status
                )

                r_virtual_slider.change(
                    fn=lambda v, e: update_r_virtual_override(10**v, e),
                    inputs=[r_virtual_slider, r_virtual_enabled],
                    outputs=r_virtual_status
                )
                r_virtual_enabled.change(
                    fn=lambda v, e: update_r_virtual_override(10**v, e),
                    inputs=[r_virtual_slider, r_virtual_enabled],
                    outputs=r_virtual_status
                )

                manifold_enabled.change(
                    fn=update_manifold_override,
                    inputs=manifold_enabled,
                    outputs=manifold_status
                )

            # Tab 2: 配置层参数
            with gr.Tab("⚙️ 配置层参数"):
                gr.Markdown("## 调整VIST机制的配置参数")
                gr.Markdown("这些参数会影响机制的行为，但不会绕过机制")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### R_human协方差调度")
                        human_lambda_slider = gr.Slider(
                            minimum=0.0, maximum=10.0, value=3.0, step=0.1,
                            label="指数系数 λ (R_human = R_base × exp(λα))"
                        )
                        human_lambda_status = gr.Textbox(label="当前值", value="λ = 3.00")

                        gr.Markdown("**效果**: λ越大，α→1时R_human增长越快，颤抖抑制越强")

                    with gr.Column():
                        gr.Markdown("### R_virtual协方差调度")
                        virtual_min_slider = gr.Slider(
                            minimum=-4, maximum=-2, value=-3, step=0.1,
                            label="log10(R_min) (R_virtual = R_min/(α+ε))"
                        )
                        virtual_min_status = gr.Textbox(label="当前值", value="R_min = 1.00e-03")

                        gr.Markdown("**效果**: R_min越小，α→1时虚拟引导权重越大，磁吸引越强")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Z轴锁定阈值")
                        z_threshold_slider = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.8, step=0.05,
                            label="α阈值（超过此值激活流形约束）"
                        )
                        z_threshold_status = gr.Textbox(label="当前值", value="阈值 = 0.80")

                        gr.Markdown("**效果**: 阈值越低，流形约束越早激活")

                # 更新回调
                human_lambda_slider.change(
                    fn=update_human_lambda,
                    inputs=human_lambda_slider,
                    outputs=human_lambda_status
                )

                virtual_min_slider.change(
                    fn=lambda v: update_virtual_min(10**v),
                    inputs=virtual_min_slider,
                    outputs=virtual_min_status
                )

                z_threshold_slider.change(
                    fn=update_z_lock_threshold,
                    inputs=z_threshold_slider,
                    outputs=z_threshold_status
                )

            # Tab 3: 实时监控
            with gr.Tab("📊 实时监控"):
                gr.Markdown("## 系统状态实时监控")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 当前状态")
                        current_alpha = gr.Number(label="当前α值", value=0.0)
                        current_r_human = gr.Number(label="当前R_human", value=0.0)
                        current_r_virtual = gr.Number(label="当前R_virtual", value=0.0)
                        current_pos = gr.Textbox(label="末端位置 (m)", value="[0.0, 0.0, 0.0]")

                    with gr.Column():
                        gr.Markdown("### 统计信息")
                        xy_drift = gr.Number(label="XY漂移 (m)", value=0.0)
                        z_motion = gr.Number(label="Z运动 (m)", value=0.0)
                        trajectory_length = gr.Number(label="轨迹长度 (m)", value=0.0)

                with gr.Row():
                    alpha_plot = gr.Plot(label="意图因子α历史")
                    cov_plot = gr.Plot(label="协方差历史")

                with gr.Row():
                    traj_plot = gr.Plot(label="末端轨迹")

                # 刷新按钮
                refresh_btn = gr.Button("🔄 刷新图表", variant="primary")
                refresh_btn.click(
                    fn=lambda: (plot_alpha_history(), plot_covariance_history(), plot_trajectory()),
                    outputs=[alpha_plot, cov_plot, traj_plot]
                )

            # Tab 4: 实验指南
            with gr.Tab("🧪 实验指南"):
                gr.Markdown("""
                ## VIST机制验证实验指南

                ### 实验1: 意图因子α的有效性
                **目的**: 验证α能准确反映用户意图

                **步骤**:
                1. 不启用任何覆盖，让α自动计算
                2. 在摄像头前执行插入动作
                3. 观察α值变化：
                   - 远离目标时 α≈0
                   - 接近目标时 α→1
                   - 方向对齐时 α增大

                **预期结果**: α与距离、速度、方向对齐相关

                ---

                ### 实验2: 颤抖抑制验证
                **目的**: 验证R_human(α)能抑制人类颤抖

                **步骤**:
                1. 启用α覆盖，设置α=1.0
                2. 在摄像头前让手在XY方向疯狂抖动
                3. 观察末端轨迹是否平滑

                **预期结果**:
                - α=0时：末端跟随手部抖动
                - α=1时：末端轨迹平滑，抖动被抑制

                ---

                ### 实验3: 虚拟引导磁吸引
                **目的**: 验证R_virtual(α)的磁吸引效果

                **步骤**:
                1. 设置目标位置
                2. 启用α覆盖，设置α=1.0
                3. 手部接近但不精确对准目标
                4. 观察末端是否被"吸引"到目标

                **预期结果**:
                - α=0时：末端跟随手部，不精确
                - α=1时：末端被吸引到目标，精确对准

                ---

                ### 实验4: 流形约束验证
                **目的**: 验证Q(α,J)的Z轴锁定效果

                **步骤**:
                1. 启用α覆盖，设置α=1.0
                2. 强制启用流形约束
                3. 在摄像头前让手在XY方向移动
                4. 观察末端是否只在Z轴运动

                **预期结果**:
                - 无约束：末端在XYZ方向都运动
                - 有约束：末端只在Z轴运动，XY方向锁定

                **关键验证**: 腕部关节不被锁死，能配合运动保持姿态

                ---

                ### 实验5: 参数敏感性分析
                **目的**: 理解各参数对系统的影响

                **步骤**:
                1. 调整λ (R_human指数系数)
                   - λ=1: 弱抑制
                   - λ=3: 中等抑制（默认）
                   - λ=10: 强抑制
                2. 观察颤抖抑制效果的变化

                3. 调整R_min (R_virtual最小值)
                   - R_min=1e-2: 弱吸引
                   - R_min=1e-3: 中等吸引（默认）
                   - R_min=1e-4: 强吸引
                4. 观察磁吸引效果的变化

                **预期结果**: 参数越极端，效果越明显

                ---

                ### 数据记录建议
                - 录制视频记录手部运动
                - 保存末端轨迹数据
                - 记录α、R_human、R_virtual时间序列
                - 计算XY漂移、Z运动、轨迹平滑度等指标
                """)

        # 底部控制
        with gr.Row():
            reset_btn = gr.Button("🔄 重置所有覆盖", variant="secondary")
            reset_status = gr.Textbox(label="重置状态", value="")

            reset_btn.click(
                fn=reset_all_overrides,
                outputs=reset_status
            )

    return demo

if __name__ == "__main__":
    demo = create_debug_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
