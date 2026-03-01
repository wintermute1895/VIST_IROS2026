from setuptools import setup
import os
from glob import glob

package_name = 'performance_monitor'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='your@email.com',
    description='ROS2遥操作性能监控工具',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'performance_monitor = performance_monitor.performance_monitor:main',
            'performance_monitor_advanced = performance_monitor.performance_monitor_advanced:main',
            'analyze_performance = performance_monitor.analyze_performance:main',
        ],
    },
)
