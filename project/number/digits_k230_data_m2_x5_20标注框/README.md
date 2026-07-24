# 数字检测：20 标注框版本

这是以“20 标注框”命名的数据版本，结构和使用方式与基础版本一致，但拥有独立的训练/部署参数。请始终以本目录的 [`mp_deployment_source/deploy_config.json`](mp_deployment_source/deploy_config.json) 为准，不要混用其他目录的模型和配置。

## 可用脚本

- `det_image_1_3.py`：检测 `/sdcard/test.jpg`。
- `det_video_1_3.py`：实时摄像头检测，K0 按下时保存检测画面到 `/data/pic/`。
- `det_image_1_2_2.py`、`det_video_1_2_2.py`：另一套兼容实现。

## 部署

上传本目录的 `mp_deployment_source/deploy_config.json` 与同名 `.kmodel` 到开发板 `/sdcard/mp_deployment_source/`，再按脚本导入要求准备 `libs` 依赖。`.kmodel` 为本地私有模型，不在仓库中提供。
