import numpy as np
from scipy.signal import butter, lfilter

class SecondOrderFilter:
    def __init__(self, fps=60, cutoff=2.0): 
        self.b, self.a = butter(2, cutoff / (fps / 2), btype='low')
        self.zi = None
        self.initialized = False

    def apply(self, value):
        if self.zi is None:
            self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, value.shape[0]))
        if not self.initialized:
            self.zi = lfilter(self.b, self.a, value[None, :], axis=0, zi=self.zi * 0 + value)[1]
            self.initialized = True
            return value
        filtered, self.zi = lfilter(self.b, self.a, value[None, :], axis=0, zi=self.zi)
        return filtered[0]