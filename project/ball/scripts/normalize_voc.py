from __future__ import annotations

import os
import shutil
import struct
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).parent / "dataset"
CLASS_NAME = "gangqiu"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def image_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        pos = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while pos < len(data) - 9:
            while pos < len(data) and data[pos] == 0xFF:
                pos += 1
            marker = data[pos]
            pos += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            length = struct.unpack(">H", data[pos : pos + 2])[0]
            if marker in sof:
                return struct.unpack(">HH", data[pos + 3 : pos + 7])[::-1]
            pos += length
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8 ":
            return struct.unpack("<HH", data[26:30])
        if kind == b"VP8X":
            return (
                int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1,
            )
        if kind == b"VP8L":
            b1, b2, b3, b4 = data[21:25]
            return 1 + (b1 | ((b2 & 0x3F) << 8)), 1 + ((b2 >> 6) | (b3 << 2) | ((b4 & 0x0F) << 10))
    raise ValueError(f"Unsupported image format: {path}")


def write_xzh_xml(image: Path, label: Path, output: Path) -> None:
    width, height = image_size(image)
    root = ET.Element("annotation")
    ET.SubElement(root, "filename").text = image.name
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(width)
    ET.SubElement(size, "height").text = str(height)
    ET.SubElement(size, "depth").text = "3"
    ET.SubElement(root, "segmented").text = "0"
    for number, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5 or parts[0] != "0":
            raise ValueError(f"Invalid YOLO label at {label}:{number}")
        _, cx, cy, box_width, box_height = map(float, parts)
        xmin = max(0, int((cx - box_width / 2) * width))
        ymin = max(0, int((cy - box_height / 2) * height))
        xmax = min(width, int(-(-(cx + box_width / 2) * width // 1)))
        ymax = min(height, int(-(-(cy + box_height / 2) * height // 1)))
        if xmax <= xmin or ymax <= ymin:
            raise ValueError(f"Invalid bounding box at {label}:{number}")
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = CLASS_NAME
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        box = ET.SubElement(obj, "bndbox")
        for key, value in (("xmin", xmin), ("ymin", ymin), ("xmax", xmax), ("ymax", ymax)):
            ET.SubElement(box, key).text = str(value)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def update_ywq_xml(path: Path, image_name: str) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    root.find("filename").text = image_name
    for obj in root.findall("object"):
        obj.find("name").text = CLASS_NAME
    ET.indent(root, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def rename_pairs(dataset: Path) -> None:
    images_dir, xml_dir = dataset / "images", dataset / "xml"
    images = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    xmls = {p.stem: p for p in xml_dir.glob("*.xml")}
    image_stems = {p.stem for p in images}
    if image_stems != set(xmls):
        raise ValueError(f"Unpaired images/XML in {dataset.name}")

    token = uuid.uuid4().hex
    plan = [(image, xmls[image.stem], f"{index:06d}{image.suffix.lower()}") for index, image in enumerate(images, 1)]
    for image, xml, _ in plan:
        image.rename(images_dir / f".__{token}_{image.name}")
        xml.rename(xml_dir / f".__{token}_{xml.name}")
    for image, xml, new_image_name in plan:
        temp_image = images_dir / f".__{token}_{image.name}"
        temp_xml = xml_dir / f".__{token}_{xml.name}"
        new_xml = Path(new_image_name).with_suffix(".xml").name
        temp_image.rename(images_dir / new_image_name)
        temp_xml.rename(xml_dir / new_xml)
        update_ywq_xml(xml_dir / new_xml, new_image_name)


def main() -> None:
    xzh = ROOT / "dataset_xzh"
    ywq = ROOT / "dataset_ywq"
    for dataset in (xzh, ywq):
        (dataset / "labels.txt").write_text(CLASS_NAME + "\n", encoding="utf-8")

    xzh_images = {p.stem: p for p in (xzh / "images").iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}
    xzh_labels = {p.stem: p for p in (xzh / "labels").glob("*.txt")}
    if set(xzh_images) != set(xzh_labels):
        raise ValueError("Unpaired images/YOLO labels in dataset_xzh")
    xzh_xml = xzh / "xml"
    if xzh_xml.exists():
        raise ValueError("dataset_xzh/xml already exists; refusing to overwrite it")
    xzh_xml.mkdir()
    try:
        for stem, image in xzh_images.items():
            write_xzh_xml(image, xzh_labels[stem], xzh_xml / f"{stem}.xml")
    except Exception:
        shutil.rmtree(xzh_xml)
        raise

    rename_pairs(xzh)
    rename_pairs(ywq)
    print("Normalized dataset_xzh and dataset_ywq successfully.")


if __name__ == "__main__":
    main()
