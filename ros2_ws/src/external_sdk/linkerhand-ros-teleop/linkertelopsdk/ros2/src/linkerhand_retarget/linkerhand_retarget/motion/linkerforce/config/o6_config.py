# 手指配置常量
FINGER_CONFIGS = {
    # 拇指侧摆3个关节的加权系数，人手的0/1/2序列，对应URDF的第1关节(下标0)
    'thumb_abduction': {
        'name': '拇指侧摆',
        'joints': [0, 1, 2],
        'weights': [0.4, 0.6, 0],
        'robot_idx': 0,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    # 拇指弯曲3个关节的加权系数，人手的2/3/4序列，对应URDF的第2关节(下标1)
    'thumb_flexion': {
        'name': '拇指弯曲',
        'joints': [2, 3, 4],
        'weights': [0, 0.0, 1],
        'robot_idx': 1,
        'type': 'thumb',
        'reverse_motion': False,
        # 动态权重配置，阈值0.2，超过阈值使用high_weight_config，低于阈值使用low_weight_config
        'dynamic_weight': {  
            'trigger_finger': 'thumb_abduction',
            'threshold': 0.3,
            'low_weight_config': {
                # v2版配置
                # 'joints': [2, 4],
                # 'weights': [0.5, 0.5],
                # 'reverse_motion': False      # Lffg1-02(V2版)系列是True
                # v1版配置
                'joints': [2, 3, 4],
                'weights': [1, 0.0, 0],
                'reverse_motion': False        # Lffg1-01(V1版)系列是False
            },
            'high_weight_config': {
                'joints': [2, 3, 4],
                'weights': [0.3, 0.0, 0.7],
                'reverse_motion': False
            }
        }
    },
    # 食指弯曲3个关节的加权系数，人手的6/7/8序列，对应URDF的第4关节(下标3)
    'index': {
        'name': '食指',
        'joints': [6, 7, 8],
        'weights': [0.3, 0.0, 0.7],
        'robot_idx': 3,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None  
    },
    # 中指弯曲3个关节的加权系数，人手的10/11/12序列，对应URDF的第6关节(下标5)
    'middle': {
        'name': '中指',
        'joints': [10, 11, 12],
        'weights': [0.5, 0.1, 0.4],
        'robot_idx': 5,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None 
    },
    # 无名指弯曲3个关节的加权系数，人手的14/15/16序列，对应URDF的第8关节(下标7)
    'ring': {
        'name': '无名指',
        'joints': [14, 15, 16],
        'weights': [0.5, 0.1, 0.4],
        'robot_idx': 7,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None 
    },
    # 小指弯曲3个关节的加权系数，人手的18/19/20序列，对应URDF的第10关节(下标9)
    'pinky': {
        'name': '小指',
        'joints': [18, 19, 20],
        'weights': [0.5, 0.1, 0.4],
        'robot_idx': 9,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None 
    }
}

# 映射顺序
MAPPING_ORDER = [
    'thumb_abduction', 'thumb_flexion', 
    'index', 'middle', 'ring', 'pinky'
]

# 三态默认配置
THREE_STATE_CONFIG = {
    'states': ['original', 'opose', 'fist'],
    'state_names': {
        'original': '张手',
        'opose': 'O手势',
        'fist': '握拳'
    }
}

ROBOT_OPOSE_LEFT = [
    1.1, 0.35, 0.0, 0.80, 0.0, 0.80, 0.0, 0.80, 0.0, 0.80, 0.0
]

ROBOT_OPOSE_RIGHT = [
    1.1, 0.35, 0.0, 0.80, 0.0, 0.80, 0.0, 0.80, 0.0, 0.80, 0.0
]

PLOTGUI_ROBOT_ID = [
    0, 1, 2
]