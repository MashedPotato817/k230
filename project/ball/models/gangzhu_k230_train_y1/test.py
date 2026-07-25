# CSI2 摄像头测试脚本

from media.sensor import Sensor
sensor = Sensor(width=1280, height=960)
sensor.reset()
print("CSI2 camera OK")