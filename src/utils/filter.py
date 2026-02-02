import numpy as np
from scipy.signal import butter, lfilter

class SecondOrderFilter:
    """
    通用二阶巴特沃斯低通滤波器 (Second-Order Butterworth Low-Pass Filter)
    
    特点：
    - 状态有记忆 (Stateful)：会记住上一帧的数据，保证平滑连续。
    - 自动初始化：第一帧数据进来时，会自动对齐，防止从 0 跳变。
    - 通用性：支持单个数值 (float) 或 向量 (numpy array [x, y, z])。
    """
    def __init__(self, fps=60, cutoff=2.0):
        """
        :param fps: 数据采样率/帧率 (Hz)。通常对应 1/dt。
        :param cutoff: 截止频率 (Hz)。
                       - 越小 (e.g. 0.5): 越平滑，延迟越大，抗抖动强。
                       - 越大 (e.g. 5.0): 越灵敏，延迟越小，但会有抖动。
        """
        # 计算归一化频率 (Nyquist frequency = fps / 2)
        nyq = fps / 2
        normal_cutoff = cutoff / nyq
        
        # 防止截止频率超出奈奎斯特频率导致报错
        if normal_cutoff >= 1.0:
            normal_cutoff = 0.99

        # 设计滤波器参数 b (分子), a (分母)
        self.b, self.a = butter(2, normal_cutoff, btype='low')
        
        # 滤波器内部状态 zi (Initial Conditions)
        self.zi = None
        self.initialized = False

    def apply(self, value):
        """
        应用滤波
        :param value: 当前帧的原始观测值 (Scalar or Numpy Array)
        :return: 滤波后的平滑值
        """
        # 1. 确保输入是 numpy array，方便切片操作
        value = np.array(value)
        
        # 2. 初始化状态矩阵 zi
        # lfilter 的 zi 需要的 shape 是: (Order, *Value_Shape)
        if self.zi is None:
            # 自动适配输入的维度
            if value.ndim == 0:
                shape = (1,)
            else:
                shape = value.shape
            
            # max(len(a), len(b)) - 1 对于二阶滤波器通常是 2
            n_states = max(len(self.a), len(self.b)) - 1
            self.zi = np.zeros((n_states,) + shape)

        # 3. 处理第一帧 (Warm start)
        # 如果不这样做，滤波器默认从0开始，会导致第一帧数据瞬间“飞”出去然后慢慢回来
        if not self.initialized:
            # 让滤波器的初始状态 zi 填满当前值，假装过去一直停在这里
            self.zi = lfilter(self.b, self.a, value[None, ...], axis=0, zi=self.zi * 0 + value)[1]
            self.initialized = True
            return value

        # 4. 正常滤波
        # value[None, ...] 是为了增加一个时间维度 (Time Axis)，因为 lfilter 期望输入是序列
        filtered, self.zi = lfilter(self.b, self.a, value[None, ...], axis=0, zi=self.zi)
        
        # 返回结果 (去掉时间维度)
        return filtered[0]