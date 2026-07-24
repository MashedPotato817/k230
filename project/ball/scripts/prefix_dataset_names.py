from __future__ import annotations

import os
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).parent / "dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def prefix_dataset(dataset_name: str, prefix: str, includes_yolo: bool) -> None:
    dataset = ROOT / dataset_name
    images_dir = dataset / "images"
    xml_dir = dataset / "xml"
    labels_dir = dataset / "labels"
    images = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    xmls = {p.stem: p for p in xml_dir.glob("*.xml")}
    yolo = {p.stem: p for p in labels_dir.glob("*.txt")} if includes_yolo else {}
    image_stems = {p.stem for p in images}
    if image_stems != set(xmls) or (includes_yolo and image_stems != set(yolo)):
        raise ValueError(f"Unpaired files in {dataset_name}; nothing was renamed")

    plan = [(image, xmls[image.stem], yolo.get(image.stem), f"{prefix}{index:06d}{image.suffix.lower()}") for index, image in enumerate(images, 1)]
    token = uuid.uuid4().hex
    for image, xml, label, _ in plan:
        for path in (image, xml, label):
            if path:
                os.replace(path, path.with_name(f".__{token}_{path.name}"))
    for image, xml, label, new_image_name in plan:
        old_image = image.with_name(f".__{token}_{image.name}")
        old_xml = xml.with_name(f".__{token}_{xml.name}")
        new_xml_name = Path(new_image_name).with_suffix(".xml").name
        os.replace(old_image, images_dir / new_image_name)
        os.replace(old_xml, xml_dir / new_xml_name)
        if label:
            old_label = label.with_name(f".__{token}_{label.name}")
            os.replace(old_label, labels_dir / Path(new_image_name).with_suffix(".txt").name)
        tree = ET.parse(xml_dir / new_xml_name)
        tree.getroot().find("filename").text = new_image_name
        ET.indent(tree, space="  ")
        tree.write(xml_dir / new_xml_name, encoding="utf-8", xml_declaration=True)


prefix_dataset("dataset_xzh", "x", includes_yolo=True)
prefix_dataset("dataset_ywq", "y", includes_yolo=False)
