# 通用物体检测试验

基于 CanMV 的 `AIBase`、`AI2D` 与 `PipeLine` 实现实时 YOLOv8 目标检测，使用 COCO 80 类标签。

## 入口与默认配置

- 入口：[`main.py`](main.py)
- 摄像头：J2 / CSI1 超广角摄像头（`Sensor(id=1)`）
- 显示：LCD，640 × 480
- 推理输入：320 × 320
- 默认模型路径：`/sdcard/examples/kmodel/yolov8n_320.kmodel`

## 运行前准备

开发板需要具备 CanMV 的 `libs/AIBase.py`、`libs/AI2D.py`、`libs/PipeLine.py` 等运行库，并在默认路径放置与脚本匹配的 YOLOv8 Kmodel。模型不包含在本仓库；若改用其他模型，请同步修改模型路径、类别标签和输入尺寸。

上传 `main.py` 后在开发板运行即可。画面会叠加检测框、类别名称和置信度。
