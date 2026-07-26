#####################################################################################################
# @file         main.py
# @brief        超广角摄像头拍照
#
# 使用J2/CSI2超广角摄像头。K0拍照并保存到/data/balls。
#####################################################################################################

import time
import os
import image
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
        os.mkdir("/data/balls")
    except Exception:
        pass

    # J2接口的超广角摄像头对应MIPI CSI2。
    sensor = Sensor(id=2, width=1280, height=960)
    sensor.reset()

    # 通道0实时显示，通道1输出高分辨率照片。
    sensor.set_framesize(Sensor.VGA)
    sensor.set_pixformat(Sensor.YUV420SP)
    sensor.set_framesize(Sensor.SXGAM, chn=CAM_CHN_ID_1)
    sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_1)

    bind_info = sensor.bind_info()
    Display.bind_layer(**bind_info, layer=Display.LAYER_VIDEO1)
    Display.init(Display.ST7701, width=640, height=480, to_ide=True)
    osd_img = image.Image(640, 480, image.ARGB8888)
    MediaManager.init()
    sensor.run()
    print("wide camera ready: CSI2")

    key0_last = 1
    last_photo_number = 0
    while True:
        os.exitpoint()
        key0_now = key0.value()

        # 在预览画面左上角显示上一张已保存照片的编号。
        osd_img.clear()
        osd_img.draw_string_advanced(
            10, 10, 24, "pic_z%06d" % last_photo_number, color=(255, 255, 255, 255)
        )
        Display.show_image(osd_img, 0, 0, Display.LAYER_OSD3)

        # K0下降沿拍照，长按只保存一张。
        if key0_last and not key0_now:
            photo_number = last_photo_number + 1
            filename = "/data/balls/z%06d.jpg" % photo_number
            photo = sensor.snapshot(chn=CAM_CHN_ID_1)
            photo.save(filename, quality=95)
            last_photo_number = photo_number
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
