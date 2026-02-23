# 手指配置常量
FINGER_CONFIGS = {
    'thumb_rotate': {
        'name': '拇指旋转',
        'joints': [1, 2],
        'weights': [0.3, 0.7],
        'robot_idx': 0,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'thumb_abduction': {
        'name': '拇指侧摆',
        'joints': [0, 1, 2],
        'weights': [0.6, 0.1, 0.3],
        'robot_idx': 1,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'thumb_flexion': {
        'name': '拇指弯曲',
        'joints': [2, 3, 4],
        'weights': [0.3, 0.1, 0.6],
        'robot_idx': 2,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'index': {
        'name': '食指',
        'joints': [6, 7, 8],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 5,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'middle': {
        'name': '中指',
        'joints': [10, 11, 12],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 8,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'ring': {
        'name': '无名指',
        'joints': [14, 15, 16],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 11,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    'pinky': {
        'name': '小指',
        'joints': [18, 19, 20],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 14,
        'type': 'finger',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    }
}

# 映射顺序
MAPPING_ORDER = [
    'thumb_rotate', 'thumb_abduction', 'thumb_flexion', 
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

ROBOT_OPOSE_LEFT =  [
    0.2, 1.088, 0.369, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0
]

ROBOT_OPOSE_RIGHT = [
    0.2, 1.088, 0.369, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0, 0.6, 0.0, 0.0
]