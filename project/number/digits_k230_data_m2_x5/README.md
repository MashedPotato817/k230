# 数字检测：基础版本

该目录是 8 类数字目标检测的基础部署版本。类别及阈值、锚框等参数由 [`mp_deployment_source/deploy_config.json`](mp_deployment_source/deploy_config.json) 定义。

## 文件说明

- `det_image_1_3.py`：从开发板 `/sdcard/test.jpg` 读取单张图片并显示检测结果。
- `det_video_1_3.py`：摄像头实时检测；K0（GPIO34）按下时保存带检测框的照片到 `/data/pic/`。
- `det_image_1_2_2.py`、`det_video_1_2_2.py`：另一套兼容实现。
- `libs/`：项目随附的管线代码；其余 CanMV 部署依赖需按脚本导入补齐。
- `mp_deployment_source/`：部署配置和本地模型放置位置。

## 部署

将配置文件与自己的模型上传到 `/sdcard/mp_deployment_source/`。模型文件名必须与配置中的 `kmodel_path` 一致；仓库不包含模型。运行 `det_image_1_3.py` 前，另将待测图片上传为 `/sdcard/test.jpg`。
