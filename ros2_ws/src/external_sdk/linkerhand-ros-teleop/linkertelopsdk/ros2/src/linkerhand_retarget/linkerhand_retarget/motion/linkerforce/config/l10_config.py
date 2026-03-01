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
    # 'index_abduction': {
    #     'name': '食指侧摆',
    #     'joints': [5],
    #     'weights': [1],
    #     'robot_idx': 4,
    #     'type': 'finger'
    # },
    'index': {
        'name': '食指弯曲',
        'joints': [6, 7, 8],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 6,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    # 'middle_abduction': {
    #     'name': '食指侧摆',
    #     'joints': [5],
    #     'weights': [1],
    #     'robot_idx': 4,
    #     'type': 'finger'
    # },
    'middle': {
        'name': '中指弯曲',
        'joints': [10, 11, 12],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 9,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    # 'ring_abduction': {
    #     'name': '食指侧摆',
    #     'joints': [5],
    #     'weights': [1],
    #     'robot_idx': 4,
    #     'type': 'finger'
    # },
    'ring': {
        'name': '无名指弯曲',
        'joints': [14, 15, 16],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 13,
        'type': 'thumb',
        'reverse_motion': False,
        'dynamic_weight': None  # 拇指侧摆没有动态权重
    },
    # 'pinky_abduction': {
    #     'name': '食指侧摆',
    #     'joints': [5],
    #     'weights': [1],
    #     'robot_idx': 4,
    #     'type': 'finger'
    # },
    'pinky': {
        'name': '小指弯曲',
        'joints': [18, 19, 20],
        'weights': [0.5, 0.3, 0.2],
        'robot_idx': 17,
        'type': 'thumb',
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

ROBOT_OPOSE_LEFT = [
    0.091, 1.367, 0.39, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0, 0.710, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0
]

ROBOT_OPOSE_RIGHT = [
    0.091, 1.367, 0.39, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0, 0.710, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0, 0.0, 0.710, 0.0, 0.0
]