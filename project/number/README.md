# 数字识别项目

这里包含 3 组 K230 数字目标检测部署文件。每组均提供单图与实时视频推理脚本，并通过 `mp_deployment_source/deploy_config.json` 保存类别、锚框、阈值和模型文件名。

| 目录 | 用途 | 类别顺序 |
| --- | --- | --- |
| [`digits_k230_data_m2_x5`](digits_k230_data_m2_x5/README.md) | 数字检测基础版本 | `4, 5, 3, 6, 7, 8, 1, 2` |
| [`digits_k230_data_m2_x5_20标注框`](digits_k230_data_m2_x5_20标注框/README.md) | 20 标注框版本 | `4, 5, 3, 6, 7, 8, 1, 2` |
| [`medicine_cart_digits_k230_v1`](medicine_cart_digits_k230_v1/README.md) | 药品车数字识别版本 | `3, 4, 5, 6, 7, 8, 1, 2` |

## 共用部署约定

1. 准备自己的 `.kmodel`，文件名要与该项目 `deploy_config.json` 中的 `kmodel_path` 一致。
2. 将 `mp_deployment_source/` 的配置和模型上传到开发板 `/sdcard/mp_deployment_source/`。
3. 根据所选脚本，将依赖库上传到 `/sdcard/libs/`，或使用已包含这些库的 CanMV 部署环境。
4. 上传并运行图像或视频推理脚本。

模型文件已被 Git 忽略，不会随仓库提供或上传。
