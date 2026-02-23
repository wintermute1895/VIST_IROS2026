import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
import numpy as np
import threading

class PyQtGraphPlot:
    def __init__(self):
        self.app = QtWidgets.QApplication([])
        self.win = pg.GraphicsLayoutWidget(show=True, title="实时数据监控")
        self.plot = self.win.addPlot(title="传感器数据")
        self.curve = self.plot.plot(pen='y')
        
        self.data = np.zeros(1000)
        self.ptr = 0
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)  # 更新间隔50ms
        
    def update_data(self, new_value):
        self.data[self.ptr] = new_value
        self.ptr = (self.ptr + 1) % len(self.data)
        
    def update(self):
        self.curve.setData(np.roll(self.data, -self.ptr))
        
    def start(self):
        self.app.exec_()
