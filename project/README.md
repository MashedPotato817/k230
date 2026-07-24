# 项目导航

本目录存放面向 Kendryte K230D BOX / CanMV 的独立实验项目。代码需在安装了兼容 CanMV 固件的开发板上运行；可使用 VS Code 的 CanMV 扩展上传并执行。

| 项目 | 说明 | 入口 / 文档 |
| --- | --- | --- |
| `capture` | J2 / CSI1 超广角摄像头按键拍照 | [`capture/README.md`](capture/README.md) |
| `try` | COCO 80 类 YOLOv8 实时物体检测试验 | [`try/README.md`](try/README.md) |
| `number` | 数字目标检测模型及图像、视频推理脚本 | [`number/README.md`](number/README.md) |

## 通用运行方式

1. 用 CanMV 扩展连接开发板。
2. 按各子项目 README 的路径要求上传脚本、依赖和模型。
3. 在开发板上运行对应的 Python 入口脚本，并查看 CanMV 终端输出。

> 模型权重不随仓库分发，`.kmodel` 已被 Git 忽略。请仅使用自己训练或已获许可的模型文件。
