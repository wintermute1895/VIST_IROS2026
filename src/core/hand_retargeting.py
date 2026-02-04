import numpy as np
import os
import sys

# ---------------------------------------------------------
# 适配 v0.5.0+ 版本的导入逻辑
# ---------------------------------------------------------
try:
    # 新版文件名是 seq_retarget (没有 ing)
    from dex_retargeting.seq_retarget import SeqRetargeting
    from dex_retargeting.retargeting_config import RetargetingConfig
    print("✅ 成功加载 dex-retargeting v0.5.0+ 模块")
except ImportError:
    try:
        # 兼容旧版
        from dex_retargeting.seq_retargeting import SeqRetargeting
        from dex_retargeting.retargeting_config import RetargetingConfig
        print("✅ 成功加载 dex-retargeting 旧版模块")
    except ImportError as e:
        print(f"❌ 无法加载模块。报错信息: {e}")
        sys.exit(1)

class HandRetargeting:
    def __init__(self, config_path=None):
        # 1. 设定 URDF 路径 (确保该文件存在)
        self.urdf_path = "config/robot.urdf"
        
        # 2. 向量模式核心参数 (Vector Mode)
        # 严格对应 Linker Hand L10 的 6 个主动关节
        targets = [
            "thumb_cmc_pitch", "thumb_cmc_yaw",
            "index_mcp_pitch", "middle_mcp_pitch",
            "ring_mcp_pitch", "pinky_mcp_pitch"
        ]
        origins = ["hand_base_link"] * 5
        tasks = ["thumb_distal", "index_distal", "middle_distal", "ring_distal", "pinky_distal"]
        indices = np.array([4, 8, 12, 16, 20])

        # 3. 使用标准 Config 类构建
        try:
            config = RetargetingConfig(
                type="vector",
                urdf_path=self.urdf_path,
                wrist_link_name="hand_base_link",
                target_joint_names=targets,
                target_origin_link_names=origins,
                target_task_link_names=tasks,
                target_link_human_indices=indices
            )
            # v0.5.0 推荐的构建方式
            self.optimizer = config.build().optimizer
            
            # 动态适配固定关节 (解决 14 vs 4 报错)
            num_fixed = len(self.optimizer.fixed_joint_names)
            self.fixed_qpos = np.zeros(num_fixed)
            
            # 4. 初始化序列重定向包装器 (用于平滑滤波)
            self.retargeting = SeqRetargeting(
                optimizer=self.optimizer,
                filter_type="OneEuro",
                lp_filter_beta=0.05
            )
            
            print(f"🚀 优化器初始化成功！")
            print(f"📌 活动关节: {len(targets)}, 固定关节: {num_fixed}")
            
        except Exception as e:
            print(f"❌ 初始化优化器失败: {e}")
            raise

    def retarget(self, landmarks_3d):
        """
        输入: MediaPipe 3D 关键点 (21, 3)
        输出: 全量关节位置 qpos
        """
        # 传入动态生成的 fixed_qpos，确保维度永远匹配
        return self.retargeting.retarget(landmarks_3d, fixed_qpos=self.fixed_qpos)

if __name__ == "__main__":
    # 本地快速测试
    hr = HandRetargeting()
    test_data = np.zeros((21, 3))
    print("测试成功:", hr.retarget(test_data).shape)