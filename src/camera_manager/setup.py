from setuptools import setup
import os
from glob import glob

package_name = 'camera_manager'

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
    description='多相机管理和数据同步系统',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'realsense_camera_node = camera_manager.realsense_camera_node:main',
            'multi_camera_manager = camera_manager.multi_camera_manager:main',
            'list_cameras = camera_manager.list_cameras:list_realsense_cameras',
        ],
    },
)
