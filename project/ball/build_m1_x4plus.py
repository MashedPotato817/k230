"""Build the m1 x4+ steel-ball augmentation dataset in Pascal VOC layout."""

from __future__ import annotations

import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset" / "gangzhu_k230_data_m1"
TARGET = ROOT / "dataset" / "gangzhu_k230_data_m1_x4+"
RNG = random.Random(20260726)
MOSAIC_SIZE = 640
MOSAIC_CELL = MOSAIC_SIZE // 2


def read_objects(xml_path: Path):
    root = ET.parse(xml_path).getroot()
    objects = []
    for obj in root.findall("object"):
        box = obj.find("bndbox")
        objects.append(
            {
                "name": obj.findtext("name", "gangqiu"),
                "bbox": tuple(float(box.findtext(key)) for key in ("xmin", "ymin", "xmax", "ymax")),
            }
        )
    return objects


def clamp_box(box, width, height):
    xmin, ymin, xmax, ymax = box
    xmin = max(0.0, min(float(width), xmin))
    xmax = max(0.0, min(float(width), xmax))
    ymin = max(0.0, min(float(height), ymin))
    ymax = max(0.0, min(float(height), ymax))
    if xmax - xmin < 1.0 or ymax - ymin < 1.0:
        return None
    return (xmin, ymin, xmax, ymax)


def write_xml(path: Path, image_name: str, objects):
    annotation = ET.Element("annotation")
    ET.SubElement(annotation, "anno")
    ET.SubElement(annotation, "filename").text = image_name
    for obj in objects:
        item = ET.SubElement(annotation, "object")
        ET.SubElement(item, "name").text = obj["name"]
        box = ET.SubElement(item, "bndbox")
        for key, value in zip(("ymin", "xmin", "ymax", "xmax"), (obj["bbox"][1], obj["bbox"][0], obj["bbox"][3], obj["bbox"][2])):
            ET.SubElement(box, key).text = str(int(round(value)))
    ET.indent(annotation, space="  ")
    ET.ElementTree(annotation).write(path, encoding="utf-8", xml_declaration=False)


def save_jpeg(image: Image.Image, path: Path, quality=92):
    if image.mode != "RGB":
        background = Image.new("RGB", image.size, "white")
        if image.mode == "RGBA":
            background.paste(image, mask=image.getchannel("A"))
        else:
            background.paste(image.convert("RGB"))
        image = background
    image.save(path, "JPEG", quality=quality)


def transform_points(points, homography):
    transformed = []
    for x, y in points:
        value = homography @ np.array([x, y, 1.0])
        transformed.append((value[0] / value[2], value[1] / value[2]))
    return transformed


def box_from_points(points, width, height):
    return clamp_box((min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points)), width, height)


def perspective_homography(source_points, destination_points):
    equations = []
    values = []
    for (x, y), (u, v) in zip(source_points, destination_points):
        equations.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        values.append(u)
        equations.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        values.append(v)
    parameters = np.linalg.solve(np.array(equations, dtype=float), np.array(values, dtype=float))
    return np.array(
        [[parameters[0], parameters[1], parameters[2]], [parameters[3], parameters[4], parameters[5]], [parameters[6], parameters[7], 1.0]]
    )


def photometric(image):
    result = ImageEnhance.Brightness(image).enhance(RNG.uniform(0.8, 1.2))
    result = ImageEnhance.Contrast(result).enhance(RNG.uniform(0.85, 1.15))
    result = ImageEnhance.Color(result).enhance(RNG.uniform(0.9, 1.1))
    red, green, blue = result.split()
    red_factor = RNG.uniform(0.98, 1.03)
    blue_factor = RNG.uniform(0.97, 1.02)
    red = red.point(lambda value: min(255, max(0, int(value * red_factor))))
    blue = blue.point(lambda value: min(255, max(0, int(value * blue_factor))))
    return Image.merge("RGB", (red, green, blue))


def degraded(image):
    if RNG.random() < 0.5:
        return image.filter(ImageFilter.GaussianBlur(radius=RNG.uniform(0.4, 0.9))), RNG.randint(80, 95)
    size = RNG.choice((3, 5))
    kernel = [0] * (size * size)
    row = RNG.randrange(size)
    for column in range(size):
        kernel[row * size + column] = 1
    return image.filter(ImageFilter.Kernel((size, size), kernel, scale=size)), RNG.randint(80, 95)


def geometric(image, objects):
    width, height = image.size
    zoom = RNG.uniform(1.02, 1.10)
    crop_width, crop_height = int(width / zoom), int(height / zoom)
    crop_x = RNG.randint(0, width - crop_width)
    crop_y = RNG.randint(0, height - crop_height)
    result = image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)).resize((width, height), Image.Resampling.BICUBIC)
    scaled_objects = []
    for obj in objects:
        xmin, ymin, xmax, ymax = obj["bbox"]
        box = clamp_box(((xmin - crop_x) * zoom, (ymin - crop_y) * zoom, (xmax - crop_x) * zoom, (ymax - crop_y) * zoom), width, height)
        if box:
            scaled_objects.append({"name": obj["name"], "bbox": box})

    inset_x, inset_y = width * 0.02, height * 0.02
    source_points = [(0, 0), (width, 0), (width, height), (0, height)]
    destination_points = [
        (RNG.uniform(-inset_x, inset_x), RNG.uniform(-inset_y, inset_y)),
        (width + RNG.uniform(-inset_x, inset_x), RNG.uniform(-inset_y, inset_y)),
        (width + RNG.uniform(-inset_x, inset_x), height + RNG.uniform(-inset_y, inset_y)),
        (RNG.uniform(-inset_x, inset_x), height + RNG.uniform(-inset_y, inset_y)),
    ]
    forward = perspective_homography(source_points, destination_points)
    inverse = np.linalg.inv(forward)
    inverse /= inverse[2, 2]
    coefficients = tuple(inverse.flatten()[:8])
    result = result.transform((width, height), Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC, fillcolor=(128, 128, 128))
    transformed_objects = []
    for obj in scaled_objects:
        xmin, ymin, xmax, ymax = obj["bbox"]
        points = transform_points([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)], forward)
        box = box_from_points(points, width, height)
        if box:
            transformed_objects.append({"name": obj["name"], "bbox": box})
    return result, transformed_objects


def occlusion_and_light(image):
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(overlay)
    if RNG.random() < 0.5:
        drawer.rectangle((0, 0, RNG.randint(width // 3, width), height), fill=(0, 0, 0, RNG.randint(18, 42)))
    else:
        radius = RNG.randint(min(width, height) // 5, min(width, height) // 2)
        center = (RNG.randint(0, width), RNG.randint(0, height))
        drawer.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=(255, 255, 255, RNG.randint(12, 34)))
    occ_width = RNG.randint(max(8, width // 10), max(9, width // 5))
    occ_height = RNG.randint(max(8, height // 10), max(9, height // 5))
    left = RNG.randint(0, max(0, width - occ_width))
    top = RNG.randint(0, max(0, height - occ_height))
    drawer.rectangle((left, top, left + occ_width, top + occ_height), fill=(45, 45, 45, RNG.randint(120, 180)))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def copy_originals(images_dir: Path, xml_dir: Path):
    records = []
    for image_path in sorted((SOURCE / "images").iterdir()):
        if not image_path.is_file():
            continue
        xml_path = SOURCE / "xml" / f"{image_path.stem}.xml"
        if not xml_path.exists():
            raise FileNotFoundError(f"Missing XML: {xml_path}")
        shutil.copy2(image_path, images_dir / image_path.name)
        shutil.copy2(xml_path, xml_dir / xml_path.name)
        records.append((image_path, read_objects(xml_path)))
    shutil.copy2(SOURCE / "labels.txt", TARGET / "labels.txt")
    return records


def build():
    if TARGET.exists():
        raise FileExistsError(f"Target already exists: {TARGET}")
    images_dir = TARGET / "images"
    xml_dir = TARGET / "xml"
    images_dir.mkdir(parents=True)
    xml_dir.mkdir()
    records = copy_originals(images_dir, xml_dir)
    augmented = []
    for image_path, objects in records:
        with Image.open(image_path) as opened:
            original = opened.convert("RGB")
        base = image_path.stem
        variants = []
        variants.append(("a01", photometric(original), objects, 92))
        degraded_image, quality = degraded(original)
        variants.append(("a02", degraded_image, objects, quality))
        geometric_image, geometric_objects = geometric(original, objects)
        variants.append(("a03", geometric_image, geometric_objects, 92))
        variants.append(("a04", occlusion_and_light(original), objects, 92))
        for suffix, image, variant_objects, quality in variants:
            image_name = f"{base}_{suffix}.jpg"
            save_jpeg(image, images_dir / image_name, quality)
            write_xml(xml_dir / f"{base}_{suffix}.xml", image_name, variant_objects)
            augmented.append((images_dir / image_name, variant_objects))

    for index in range(1, 31):
        selected = RNG.sample(augmented, 4)
        mosaic = Image.new("RGB", (MOSAIC_SIZE, MOSAIC_SIZE), "white")
        mosaic_objects = []
        for cell_index, (image_path, objects) in enumerate(selected):
            with Image.open(image_path) as opened:
                source_image = opened.convert("RGB")
            width, height = source_image.size
            offset_x = (cell_index % 2) * MOSAIC_CELL
            offset_y = (cell_index // 2) * MOSAIC_CELL
            mosaic.paste(source_image.resize((MOSAIC_CELL, MOSAIC_CELL), Image.Resampling.BICUBIC), (offset_x, offset_y))
            scale_x, scale_y = MOSAIC_CELL / width, MOSAIC_CELL / height
            for obj in objects:
                xmin, ymin, xmax, ymax = obj["bbox"]
                box = clamp_box((xmin * scale_x + offset_x, ymin * scale_y + offset_y, xmax * scale_x + offset_x, ymax * scale_y + offset_y), MOSAIC_SIZE, MOSAIC_SIZE)
                if box:
                    mosaic_objects.append({"name": obj["name"], "bbox": box})
        image_name = f"m{index:06d}.jpg"
        save_jpeg(mosaic, images_dir / image_name)
        write_xml(xml_dir / f"m{index:06d}.xml", image_name, mosaic_objects)

    print(f"Created {TARGET}")
    print(f"Original: {len(records)}, standard augmentations: {len(augmented)}, mosaics: 30")


if __name__ == "__main__":
    build()
