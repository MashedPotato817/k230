"""Small offline Pascal VOC annotator for project/ball/dataset/dataset_zhn.

Run from the repository root:
    python project/ball/annotate_dataset_zhn.py

Controls:
  Drag with left mouse button: create a gangqiu bounding box
  Right mouse button / Delete: remove the selected or nearest box
  Ctrl+S: save current image
  D / Right: save and move to next image
  A / Left: save and move to previous image
  N: jump to next image whose empty XML has not been confirmed
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk


LABEL = "gangqiu"
DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset" / "dataset_zhn"


def read_boxes(xml_path: Path) -> list[tuple[float, float, float, float]]:
    if not xml_path.exists():
        return []
    root = ET.parse(xml_path).getroot()
    boxes = []
    for obj in root.findall("object"):
        box = obj.find("bndbox")
        if box is None:
            continue
        try:
            xmin = float(box.findtext("xmin", ""))
            ymin = float(box.findtext("ymin", ""))
            xmax = float(box.findtext("xmax", ""))
            ymax = float(box.findtext("ymax", ""))
        except ValueError:
            continue
        if xmin < xmax and ymin < ymax:
            boxes.append((xmin, ymin, xmax, ymax))
    return boxes


def is_pending(xml_path: Path) -> bool:
    """Return true for an image that has not yet been reviewed by this tool."""
    if not xml_path.exists():
        return True
    root = ET.parse(xml_path).getroot()
    return not root.findall("object") and root.findtext("verified") != "true"


def write_voc(xml_path: Path, image_path: Path, image_size: tuple[int, int], boxes: list[tuple[float, float, float, float]]) -> None:
    width, height = image_size
    root = ET.Element("annotation")
    ET.SubElement(root, "filename").text = image_path.name
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(width)
    ET.SubElement(size, "height").text = str(height)
    ET.SubElement(size, "depth").text = "3"
    ET.SubElement(root, "verified").text = "true"
    for xmin, ymin, xmax, ymax in boxes:
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = LABEL
        box = ET.SubElement(obj, "bndbox")
        for key, value in (("xmin", xmin), ("ymin", ymin), ("xmax", xmax), ("ymax", ymax)):
            ET.SubElement(box, key).text = str(round(value, 2))
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)


class Annotator(tk.Tk):
    def __init__(self, dataset: Path) -> None:
        super().__init__()
        self.dataset = dataset
        self.images_dir = dataset / "images"
        self.xml_dir = dataset / "xml"
        self.xml_dir.mkdir(exist_ok=True)
        self.images = sorted(p for p in self.images_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if not self.images:
            raise FileNotFoundError(f"No images found in {self.images_dir}")
        self.index = self.first_empty_index()
        self.boxes: list[tuple[float, float, float, float]] = []
        self.selected: int | None = None
        self.draw_start: tuple[float, float] | None = None
        self.preview_id: int | None = None
        self.scale = 1.0
        self.image_size = (0, 0)

        self.title("dataset_zhn 钢球标注器")
        self.geometry("980x760")
        self.minsize(720, 560)
        self.status = tk.StringVar()
        tk.Label(self, textvariable=self.status, anchor="w", padx=10).pack(fill="x")
        self.canvas = tk.Canvas(self, bg="#202124", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        tk.Label(self, text="拖拽左键画框 | 右键/Del 删除框 | Ctrl+S 保存 | A/D 或 ←/→ 切图 | N 下一张空标图", anchor="w", padx=10).pack(fill="x")

        self.canvas.bind("<ButtonPress-1>", self.begin_box)
        self.canvas.bind("<B1-Motion>", self.preview_box)
        self.canvas.bind("<ButtonRelease-1>", self.finish_box)
        self.canvas.bind("<Button-3>", self.remove_nearest)
        self.bind("<Control-s>", lambda _event: self.save())
        self.bind("<Delete>", lambda _event: self.delete_selected())
        self.bind("d", lambda _event: self.change(1))
        self.bind("a", lambda _event: self.change(-1))
        self.bind("<Right>", lambda _event: self.change(1))
        self.bind("<Left>", lambda _event: self.change(-1))
        self.bind("n", lambda _event: self.next_empty())
        self.bind("<Configure>", lambda _event: self.after_idle(self.render))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.load_current()

    @property
    def image_path(self) -> Path:
        return self.images[self.index]

    @property
    def xml_path(self) -> Path:
        return self.xml_dir / f"{self.image_path.stem}.xml"

    def first_empty_index(self) -> int:
        for index, image in enumerate(self.images):
            if is_pending(self.xml_dir / f"{image.stem}.xml"):
                return index
        return 0

    def load_current(self) -> None:
        self.boxes = read_boxes(self.xml_path)
        self.selected = None
        self.render()

    def render(self) -> None:
        if not self.images:
            return
        source = Image.open(self.image_path).convert("RGB")
        self.image_size = source.size
        max_width = max(self.canvas.winfo_width() - 20, 1)
        max_height = max(self.canvas.winfo_height() - 20, 1)
        self.scale = min(max_width / source.width, max_height / source.height, 1.0)
        shown = source.resize((round(source.width * self.scale), round(source.height * self.scale)))
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        for index, box in enumerate(self.boxes):
            self.draw_box(box, "#ffca28" if index == self.selected else "#00e676")
        self.status.set(
            f"{self.index + 1}/{len(self.images)}  {self.image_path.name}  "
            f"钢球框: {len(self.boxes)}  类别: {LABEL}"
        )

    def draw_box(self, box: tuple[float, float, float, float], color: str) -> None:
        x1, y1, x2, y2 = (value * self.scale for value in box)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)
        self.canvas.create_text(x1 + 3, y1 + 3, text=LABEL, fill=color, anchor="nw")

    def canvas_to_image(self, x: float, y: float) -> tuple[float, float]:
        width, height = self.image_size
        return max(0, min(x / self.scale, width)), max(0, min(y / self.scale, height))

    def begin_box(self, event: tk.Event) -> None:
        self.draw_start = self.canvas_to_image(event.x, event.y)
        self.selected = None

    def preview_box(self, event: tk.Event) -> None:
        if self.draw_start is None:
            return
        if self.preview_id is not None:
            self.canvas.delete(self.preview_id)
        x1, y1 = self.draw_start
        x2, y2 = self.canvas_to_image(event.x, event.y)
        self.preview_id = self.canvas.create_rectangle(x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale, outline="#ffca28", width=2)

    def finish_box(self, event: tk.Event) -> None:
        if self.draw_start is None:
            return
        x1, y1 = self.draw_start
        x2, y2 = self.canvas_to_image(event.x, event.y)
        self.draw_start = None
        if abs(x2 - x1) >= 4 and abs(y2 - y1) >= 4:
            self.boxes.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            self.selected = len(self.boxes) - 1
        self.preview_id = None
        self.render()

    def remove_nearest(self, event: tk.Event) -> None:
        x, y = self.canvas_to_image(event.x, event.y)
        inside = [i for i, (x1, y1, x2, y2) in enumerate(self.boxes) if x1 <= x <= x2 and y1 <= y <= y2]
        if inside:
            self.selected = inside[-1]
            self.delete_selected()

    def delete_selected(self) -> None:
        if self.selected is not None:
            self.boxes.pop(self.selected)
            self.selected = None
            self.render()

    def save(self) -> None:
        write_voc(self.xml_path, self.image_path, self.image_size, self.boxes)
        self.status.set(f"已保存：{self.image_path.name}，钢球框 {len(self.boxes)} 个")

    def change(self, step: int) -> None:
        self.save()
        self.index = (self.index + step) % len(self.images)
        self.load_current()

    def next_empty(self) -> None:
        self.save()
        for offset in range(1, len(self.images) + 1):
            candidate = (self.index + offset) % len(self.images)
            xml_path = self.xml_dir / f"{self.images[candidate].stem}.xml"
            if is_pending(xml_path):
                self.index = candidate
                self.load_current()
                return
        messagebox.showinfo("标注器", "没有找到空标注图片。请复核负样本是否需要钢球框。")

    def close(self) -> None:
        self.save()
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Pascal VOC annotator")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    Annotator(args.dataset.resolve()).mainloop()


if __name__ == "__main__":
    main()
