#####################################################################################################
# @file         main.py
# @brief        超广角摄像头拍照
#
# 使用J2/CSI1超广角摄像头。K0拍照并保存到/data/pic。
#####################################################################################################

import time
import os
from machine import Pin, FPIOA
from media.sensor import *
from media.display import *
from media.media import *


sensor = None

try:
    fpioa = FPIOA()
    fpioa.set_function(34, FPIOA.GPIO34)
    key0 = Pin(34, Pin.IN, pull=Pin.PULL_UP, drive=7)

    try:
        os.mkdir("/data/pic")
    except Exception:
        pass

    # J2接口的超广角摄像头对应MIPI CSI1。
    sensor = Sensor(id=1, width=1280, height=960)
    sensor.reset()

    # 通道0实时显示，通道1输出高分辨率照片。
    sensor.set_framesize(Sensor.VGA)
    sensor.set_pixformat(Sensor.YUV420SP)
    sensor.set_framesize(Sensor.SXGAM, chn=CAM_CHN_ID_1)
    sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_1)

    bind_info = sensor.bind_info()
    Display.bind_layer(**bind_info, layer=Display.LAYER_VIDEO1)
    Display.init(Display.ST7701, width=640, height=480, to_ide=True)
    MediaManager.init()
    sensor.run()
    print("wide camera ready: CSI1")

    key0_last = 1
    while True:
        os.exitpoint()
        key0_now = key0.value()

        # K0下降沿拍照，长按只保存一张。
        if key0_last and not key0_now:
            filename = "/data/pic/wide_%d.jpg" % time.ticks_ms()
            photo = sensor.snapshot(chn=CAM_CHN_ID_1)
            photo.save(filename, quality=95)
            print("photo saved:", filename)

        key0_last = key0_now
        time.sleep_ms(10)

except KeyboardInterrupt as e:
    print("user stop:", e)
except BaseException as e:
    print("Exception:", e)
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
