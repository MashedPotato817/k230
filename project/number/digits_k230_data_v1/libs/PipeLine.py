import os
from media.sensor import *
from media.display import *
from media.media import *
from libs.Utils import ScopedTiming
import nncase_runtime as nn
import image
import utime


class PipeLine:
    def __init__(self, rgb888p_size=[224, 224], display_mode="hdmi",
                 display_size=None, osd_layer_num=1, debug_mode=0):
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = display_size
        self.display_mode = display_mode
        self.sensor = None
        self.osd_img = None
        self.cur_frame = None
        self.debug_mode = debug_mode
        self.osd_layer_num = osd_layer_num

    def create(self, sensor=None, hmirror=None, vflip=None, fps=60):
        with ScopedTiming("init PipeLine", self.debug_mode > 0):
            nn.shrink_memory_pool()
            board = os.uname()[-1]
            if board in ("k230d_canmv_bpi_zero", "k230_canmv_lckfb",
                         "k230d_canmv_atk_dnk230d"):
                self.sensor = Sensor(id=0, fps=30) if sensor is None else sensor
            else:
                self.sensor = Sensor(fps=fps) if sensor is None else sensor

            self.sensor.reset()
            if hmirror is not None:
                self.sensor.set_hmirror(hmirror)
            if vflip is not None:
                self.sensor.set_vflip(vflip)

            display_map = {
                "hdmi": Display.LT9611,
                "lt9611": Display.LT9611,
                "lcd": Display.ST7701,
                "st7701": Display.ST7701,
                "hx8399": Display.HX8399,
            }
            display_type = display_map.get(self.display_mode, Display.ST7701)
            if self.display_size is None:
                Display.init(display_type, osd_num=self.osd_layer_num, to_ide=True)
            else:
                Display.init(display_type, width=self.display_size[0],
                             height=self.display_size[1],
                             osd_num=self.osd_layer_num, to_ide=True)
            self.display_size = [Display.width(), Display.height()]

            # Channel 0: LCD and VS Code preview video.
            self.sensor.set_framesize(w=self.display_size[0], h=self.display_size[1])
            self.sensor.set_pixformat(PIXEL_FORMAT_YUV_SEMIPLANAR_420)

            # Channel 1: independent RGB565 still-image stream.
            self.sensor.set_framesize(w=self.display_size[0], h=self.display_size[1],
                                      chn=CAM_CHN_ID_1)
            self.sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_1)

            # Channel 2: RGB888P input for AI inference.
            self.sensor.set_framesize(w=self.rgb888p_size[0], h=self.rgb888p_size[1],
                                      chn=CAM_CHN_ID_2)
            self.sensor.set_pixformat(PIXEL_FORMAT_RGB_888_PLANAR,
                                      chn=CAM_CHN_ID_2)

            self.osd_img = image.Image(self.display_size[0], self.display_size[1],
                                       image.ARGB8888)
            bind_info = self.sensor.bind_info(x=0, y=0, chn=CAM_CHN_ID_0)
            Display.bind_layer(**bind_info, dstlayer=Display.LAYER_VIDEO1)
            MediaManager.init()
            self.sensor.run()

    def get_frame(self):
        with ScopedTiming("get a frame", self.debug_mode > 0):
            self.cur_frame = self.sensor.snapshot(chn=CAM_CHN_ID_2)
            return self.cur_frame.to_numpy_ref()

    def get_capture_frame(self):
        return self.sensor.snapshot(chn=CAM_CHN_ID_1)

    def show_image(self):
        with ScopedTiming("show result", self.debug_mode > 0):
            Display.show_image(self.osd_img, 0, 0, Display.LAYER_OSD3)

    def get_display_size(self):
        return self.display_size

    def destroy(self):
        with ScopedTiming("deinit PipeLine", self.debug_mode > 0):
            os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
            self.sensor.stop()
            Display.deinit()
            utime.sleep_ms(50)
            MediaManager.deinit()
