# 药品车数字识别

面向药品车场景的 8 类数字目标检测部署版本。类别、置信度阈值、NMS 阈值和锚框由 [`mp_deployment_source/deploy_config.json`](mp_deployment_source/deploy_config.json) 管理。

## 可用脚本

- `det_image_1_3.py`：对 `/sdcard/test.jpg` 执行单图检测并在 IDE 中显示结果。
- `det_video_1_3.py`：摄像头实时检测；按下 K0（GPIO34）将带标注的画面保存到 `/data/pic/`。
- `det_image_1_2_2.py`、`det_video_1_2_2.py`：另一套兼容实现。

## 部署

1. 将 `deploy_config.json` 和与其 `kmodel_path` 对应的本地 `.kmodel` 放到开发板 `/sdcard/mp_deployment_source/`。
2. 准备脚本所需的 CanMV `libs` 依赖。
3. 单图测试时上传测试图片为 `/sdcard/test.jpg`，然后运行 `det_image_1_3.py`；实时测试运行 `det_video_1_3.py`。

模型权重不随仓库提供，避免将私有或未经授权的模型提交到 Git。
