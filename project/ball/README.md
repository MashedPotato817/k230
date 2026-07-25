# 10mm 钢珠识别

## 任务名称：图像检测

## 任务说明

在图片中检测出目标物体，并给出物体的位置信息、类别信息和分数。

## 数据上传方式

一种是上传图片，您需要了解任务的数据标注过程，并在平台内部完成标注过程，需要注意的是：OCR识别任务不支持在线标注。

一种是上传压缩包，压缩包内包含已经标注好的数据，包含原图和标注文件，数据组织格式查看压缩包格式说明，进行压缩时需要注意：将文件夹内的所有子文件夹和文件选中，右键选择压缩，而不是选中外部的文件夹压缩。

## 压缩包格式说明

除了上传图片标注方法外，还可以使用压缩包的形式上传数据，压缩包内包含已经标注好的数据，包含原图和标注文件。不同的任务有不同的组织形式，这里对几种任务的数据组织格式进行说明。

### 图像检测任务

图像检测任务使用 Pascal VOC 格式，文件夹需包含images和xml两个文件夹，且一张图片对应一个同名xml文件。可以增加labels.txt文件，每行表示一个类别名称。

```
📦 my_dataset
├── 📁 images
│   ├── 0.jpg
│   ├── 1.jpg
│   └──...
├── 📁 xml
│   ├── 0.xml
│   ├── 1.xml
│   └──...
└── labels.txt（可选）
```

🚩Note: 压缩zip包时，请进入到my_dataset目录，选中所有子目录和文件images、xml、labels.txt等，右键选择压缩，而不是选中外部的文件夹压缩。

## 数据集

本地数据集位于 `project/ball/dataset`，两个数据集保持独立，类别名称统一为 `gangqiu`。

| 数据集 | 图片 / XML | 标注框数 | 命名规则 |
| --- | ---: | ---: | --- |
| `dataset_xzh` | 95 / 95 | 3,229 | `x000001` 至 `x000095` |
| `dataset_ywq` | 99 / 99 | 592 | `y000001` 至 `y000099` |

- 两个数据集均含 `images/`、`xml/` 与 `labels.txt`，图片和 XML 同名配对。
- `dataset_xzh` 还保留了原始 YOLO 格式的 `labels/`，并已与图片同步命名，便于后续增强或回退。
- 打包上传时进入对应数据集目录，选择 `images/`、`xml/`、`labels.txt` 压缩；ZIP 根目录不要再包含一层数据集文件夹。

数据集抽样诊断及提升识别准确率的建议见 [`docs/ball_detection_dataset_recommendations.md`](docs/ball_detection_dataset_recommendations.md)。

## 训练模型与 K230 部署

训练输出位于 `project/ball/models/gangzhu_k230_train_y1`：

- 模型：`mp_deployment_source/best_AnchorBaseDet_can2_5_s_20260725014102.kmodel`
- 配置：`mp_deployment_source/deploy_config.json`
- 类别：`gangqiu`
- 输入尺寸：320 × 320
- 视频推理脚本：`det_video.py`

将 `mp_deployment_source/` 上传至开发板 `/sdcard/mp_deployment_source/`，再将 `det_video.py` 上传至 `/sdcard/det_video.py`。开发板现有的 `/sdcard/libs/` 保持不动。

当前视频脚本设置为 `display_mode = "lcd"`，适用于 K230D BOX 的 LCD（ST7701）显示。CSI2/J1 上的 GC2093 摄像头被系统识别后，再运行 `det_video.py`；若使用 HDMI/LT9611 显示器，则需将显示模式改回 `lt9611`。

