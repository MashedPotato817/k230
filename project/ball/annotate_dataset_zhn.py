"""Small offline Pascal VOC annotator for project/ball/dataset/dataset_zhn.

Run from the repository root:
    python project/ball/annotate_dataset_zhn.py

Controls:
  Drag with left mouse button: create a gangqiu bounding box
  Click an existing box: select it; Ctrl + drag: force-create an overlapping box
  Mouse wheel / + / - / 0: zoom in, zoom out, fit image to window
  Drag with middle mouse button: pan a zoomed image
  Tab / Shift+Tab: choose a box; H: switch its active corner
  Arrow keys: nudge the active corner by one pixel (Shift + Arrow: five pixels)
  Right mouse button / Delete: remove the selected or nearest box
  Ctrl+S: save current image
  D / A: save and move to next/previous image
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
AUTOSAVE_MS = 900


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
        self.index = self.first_pending_index()
        self.boxes: list[tuple[float, float, float, float]] = []
        self.selected: int | None = None
        self.active_corner = 0  # 0 = top-left, 1 = bottom-right
        self.draw_start: tuple[float, float] | None = None
        self.preview_id: int | None = None
        self.image_size = (0, 0)
        self.fit_scale = 1.0
        self.scale = 1.0
        self.zoom = 1.0
        self.dirty = False
        self.autosave_job: str | None = None

        self.title("dataset_zhn 精细钢球标注器")
        self.geometry("1080x800")
        self.minsize(720, 560)
        self.status = tk.StringVar()
        tk.Label(self, textvariable=self.status, anchor="w", padx=10).pack(fill="x")
        self.canvas = tk.Canvas(self, bg="#202124", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        tk.Label(self, text="滚轮缩放 | 中键拖动 | Tab 选框 | H 切换左上/右下端点 | 方向键微调（Shift=5px） | A/D 切图 | 自动保存 0.9 秒", anchor="w", padx=10).pack(fill="x")

        self.canvas.bind("<ButtonPress-1>", self.begin_box)
        self.canvas.bind("<B1-Motion>", self.preview_box)
        self.canvas.bind("<ButtonRelease-1>", self.finish_box)
        self.canvas.bind("<Button-3>", self.remove_nearest)
        self.canvas.bind("<ButtonPress-2>", lambda event: self.canvas.scan_mark(event.x, event.y))
        self.canvas.bind("<B2-Motion>", lambda event: self.canvas.scan_dragto(event.x, event.y, gain=1))
        self.canvas.bind("<MouseWheel>", self.mouse_wheel)
        self.bind("<Control-s>", lambda _event: self.save())
        self.bind("<Delete>", lambda _event: self.delete_selected())
        self.bind("d", lambda _event: self.change(1))
        self.bind("a", lambda _event: self.change(-1))
        self.bind("n", lambda _event: self.next_pending())
        self.bind("<Tab>", lambda _event: self.select_relative(1))
        self.bind("<Shift-Tab>", lambda _event: self.select_relative(-1))
        self.bind("h", lambda _event: self.toggle_corner())
        self.bind("<Left>", lambda event: self.nudge(-1, 0, 5 if event.state & 0x0001 else 1))
        self.bind("<Right>", lambda event: self.nudge(1, 0, 5 if event.state & 0x0001 else 1))
        self.bind("<Up>", lambda event: self.nudge(0, -1, 5 if event.state & 0x0001 else 1))
        self.bind("<Down>", lambda event: self.nudge(0, 1, 5 if event.state & 0x0001 else 1))
        self.bind("+", lambda _event: self.zoom_at_center(1.25))
        self.bind("=", lambda _event: self.zoom_at_center(1.25))
        self.bind("-", lambda _event: self.zoom_at_center(0.8))
        self.bind("0", lambda _event: self.reset_zoom())
        self.bind("<Configure>", lambda _event: self.after_idle(self.render))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.load_current()

    @property
    def image_path(self) -> Path:
        return self.images[self.index]

    @property
    def xml_path(self) -> Path:
        return self.xml_dir / f"{self.image_path.stem}.xml"

    def first_pending_index(self) -> int:
        for index, image in enumerate(self.images):
            if is_pending(self.xml_dir / f"{image.stem}.xml"):
                return index
        return 0

    def load_current(self) -> None:
        self.boxes = read_boxes(self.xml_path)
        self.selected = None
        self.active_corner = 0
        self.zoom = 1.0
        self.dirty = False
        self.render()

    def render(self) -> None:
        if not self.images:
            return
        source = Image.open(self.image_path).convert("RGB")
        self.image_size = source.size
        max_width = max(self.canvas.winfo_width() - 20, 1)
        max_height = max(self.canvas.winfo_height() - 20, 1)
        self.fit_scale = min(max_width / source.width, max_height / source.height, 1.0)
        self.scale = self.fit_scale * self.zoom
        shown = source.resize((round(source.width * self.scale), round(source.height * self.scale)))
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, shown.width, shown.height))
        for index, box in enumerate(self.boxes):
            self.draw_box(box, "#ffca28" if index == self.selected else "#00e676")
        corner = "左上" if self.active_corner == 0 else "右下"
        changed = "  未保存" if self.dirty else "  已保存"
        selected = "无" if self.selected is None else f"{self.selected + 1}（{corner}端点）"
        self.status.set(f"{self.index + 1}/{len(self.images)}  {self.image_path.name}  框:{len(self.boxes)}  选中:{selected}  缩放:{self.zoom:.2f}x{changed}")

    def draw_box(self, box: tuple[float, float, float, float], color: str) -> None:
        x1, y1, x2, y2 = (value * self.scale for value in box)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)
        self.canvas.create_text(x1 + 3, y1 + 3, text=LABEL, fill=color, anchor="nw")
        if self.selected is not None and self.boxes[self.selected] == box:
            px, py = (x1, y1) if self.active_corner == 0 else (x2, y2)
            self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#ffca28", outline="")

    def canvas_to_image(self, x: float, y: float) -> tuple[float, float]:
        width, height = self.image_size
        x = self.canvas.canvasx(x)
        y = self.canvas.canvasy(y)
        return max(0, min(x / self.scale, width)), max(0, min(y / self.scale, height))

    def box_at(self, x: float, y: float) -> int | None:
        matches = [i for i, (x1, y1, x2, y2) in enumerate(self.boxes) if x1 <= x <= x2 and y1 <= y <= y2]
        return matches[-1] if matches else None

    def begin_box(self, event: tk.Event) -> None:
        x, y = self.canvas_to_image(event.x, event.y)
        existing = self.box_at(x, y)
        if existing is not None and not (event.state & 0x0004):
            self.selected = existing
            self.draw_start = None
            self.render()
            return
        self.draw_start = (x, y)
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
            self.active_corner = 1
            self.mark_dirty()
        self.preview_id = None
        self.render()

    def remove_nearest(self, event: tk.Event) -> None:
        x, y = self.canvas_to_image(event.x, event.y)
        selected = self.box_at(x, y)
        if selected is not None:
            self.selected = selected
            self.delete_selected()

    def delete_selected(self) -> None:
        if self.selected is not None:
            self.boxes.pop(self.selected)
            self.selected = None
            self.mark_dirty()
            self.render()

    def select_relative(self, step: int) -> str:
        if not self.boxes:
            return "break"
        self.selected = 0 if self.selected is None else (self.selected + step) % len(self.boxes)
        self.render()
        return "break"

    def toggle_corner(self) -> None:
        if self.selected is not None:
            self.active_corner = 1 - self.active_corner
            self.render()

    def nudge(self, dx: int, dy: int, step: int) -> str:
        if self.selected is None:
            return "break"
        x1, y1, x2, y2 = self.boxes[self.selected]
        width, height = self.image_size
        if self.active_corner == 0:
            x1 = max(0, min(x1 + dx * step, x2 - 1))
            y1 = max(0, min(y1 + dy * step, y2 - 1))
        else:
            x2 = min(width, max(x2 + dx * step, x1 + 1))
            y2 = min(height, max(y2 + dy * step, y1 + 1))
        self.boxes[self.selected] = (x1, y1, x2, y2)
        self.mark_dirty()
        self.render()
        return "break"

    def mark_dirty(self) -> None:
        self.dirty = True
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
        self.autosave_job = self.after(AUTOSAVE_MS, self.autosave)

    def autosave(self) -> None:
        self.autosave_job = None
        if self.dirty:
            self.save()

    def save(self) -> None:
        write_voc(self.xml_path, self.image_path, self.image_size, self.boxes)
        self.dirty = False
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
            self.autosave_job = None
        self.render()

    def change(self, step: int) -> None:
        self.save()
        self.index = (self.index + step) % len(self.images)
        self.load_current()

    def next_pending(self) -> None:
        self.save()
        for offset in range(1, len(self.images) + 1):
            candidate = (self.index + offset) % len(self.images)
            xml_path = self.xml_dir / f"{self.images[candidate].stem}.xml"
            if is_pending(xml_path):
                self.index = candidate
                self.load_current()
                return
        messagebox.showinfo("标注器", "没有找到待确认图片。请复核已确认的负样本与标注框。")

    def mouse_wheel(self, event: tk.Event) -> str:
        factor = 1.25 if event.delta > 0 else 0.8
        old_scale = self.scale
        focus_x = self.canvas.canvasx(event.x) / old_scale
        focus_y = self.canvas.canvasy(event.y) / old_scale
        self.zoom = max(0.25, min(self.zoom * factor, 8.0))
        self.render()
        image_width, image_height = (self.image_size[0] * self.scale, self.image_size[1] * self.scale)
        self.canvas.xview_moveto(max(0, (focus_x * self.scale - event.x) / image_width))
        self.canvas.yview_moveto(max(0, (focus_y * self.scale - event.y) / image_height))
        return "break"

    def zoom_at_center(self, factor: float) -> None:
        self.zoom = max(0.25, min(self.zoom * factor, 8.0))
        self.render()

    def reset_zoom(self) -> None:
        self.zoom = 1.0
        self.render()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

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
