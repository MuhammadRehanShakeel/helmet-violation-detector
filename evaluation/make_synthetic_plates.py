"""
make_synthetic_plates.py - Creates fake (but realistic) Pakistani number plates for testing the OCR.

Why synthetic? There is no public, labelled dataset of Pakistani MOTORCYCLE plates.
Generating them lets us know the exact right answer for every image, and control
how hard they are (small, blurry, tilted, dark, low-quality JPEG) - like a real
traffic camera 10-20 metres away.

Styles made (based on real plate layouts):
  * Punjab car        white, "PUNJAB" on top, LEA 1234
  * Punjab motorcycle white, two lines: LEZ / 1234 (the most common bike plate)
  * Islamabad (ICT)   white with green "ICT ISLAMABAD" strip, AB 123
  * Sindh             yellow, "SINDH", BJV 456
  * Year plates       LEA 19 1234 (the small year is not part of the number)

Run:  python evaluation/make_synthetic_plates.py   (writes data/synthetic_plates_dev and _test)
"""
import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FONTS = [os.path.join(HERE, "fonts", f) for f in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
                                                  "DejaVuSansCondensed-Bold.ttf")]
LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"
PUNJAB_CODES = ["LEA", "LEB", "LEC", "LED", "LEF", "LEZ", "LHR", "RIK", "RIL", "RIM", "FDA", "GAA", "MNA", "SGA",
                "BWA", "SKA", "ATK", "JLM", "CHK", "GRW"]
SINDH_CODES = ["BJV", "BKR", "AKB", "BMX", "BNG", "AZB", "KHI", "HYD"]


def font(size, choice=None):
    return ImageFont.truetype(choice or random.choice(FONTS), size)


def text_center(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x1 + (x2 - x1 - (r - l)) / 2 - l, y1 + (y2 - y1 - (b - t)) / 2 - t), text, font=fnt, fill=fill)


def plate_image(style):
    fnt_name = random.choice(FONTS)
    if style == "punjab_bike":
        letters, number = random.choice(PUNJAB_CODES), str(random.randint(1, 9999))
        img = Image.new("RGB", (240, 170), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([3, 3, 236, 166], outline="black", width=5)
        text_center(d, (0, 6, 240, 36), "PUNJAB", font(22, fnt_name), (20, 90, 30))
        text_center(d, (0, 36, 240, 98), letters, font(54, fnt_name), "black")
        text_center(d, (0, 98, 240, 164), number, font(58, fnt_name), "black")
        return img, f"{letters}-{number}"

    if style == "ict":
        letters = random.choice(LETTERS) + random.choice(LETTERS)
        number = str(random.randint(1, 999))
        img = Image.new("RGB", (420, 120), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 60, 120], fill=(0, 110, 50))
        text_center(d, (0, 20, 60, 100), "ICT", font(22, fnt_name), "white")
        d.rectangle([2, 2, 417, 117], outline="black", width=4)
        text_center(d, (60, 10, 420, 115), f"{letters} {number}", font(70, fnt_name), "black")
        return img, f"{letters}-{number}"

    if style == "sindh":
        letters, number = random.choice(SINDH_CODES), str(random.randint(1, 999))
        img = Image.new("RGB", (420, 130), (250, 215, 40))
        d = ImageDraw.Draw(img)
        d.rectangle([2, 2, 417, 127], outline="black", width=4)
        text_center(d, (0, 4, 420, 32), "SINDH", font(22, fnt_name), "black")
        text_center(d, (0, 30, 420, 125), f"{letters}-{number}", font(70, fnt_name), "black")
        return img, f"{letters}-{number}"

    # punjab car, with or without the small year
    letters, number = random.choice(PUNJAB_CODES), str(random.randint(1, 9999))
    img = Image.new("RGB", (440, 130), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 437, 127], outline="black", width=4)
    text_center(d, (0, 4, 440, 32), "PUNJAB", font(22, fnt_name), (20, 90, 30))
    if style == "punjab_year":
        year = random.choice(["15", "17", "19", "21", "23", "25"])
        text_center(d, (0, 30, 440, 125), f"{letters} {year} {number}", font(62, fnt_name), "black")
    else:
        text_center(d, (0, 30, 440, 125), f"{letters} {number}", font(70, fnt_name), "black")
    return img, f"{letters}-{number}"


def degrade(img, level):
    """level 0 = clean close-up ... 3 = far, blurry, tilted, dark camera."""
    w, h = img.size
    angle = random.uniform(-3, 3) * (level + 1) / 2
    img = img.rotate(angle, expand=True, fillcolor=(90, 90, 90))
    target_h = {0: 90, 1: 55, 2: 38, 3: 28}[level] + random.randint(-4, 6)
    img = img.resize((max(20, int(img.width * target_h / img.height)), target_h), Image.BILINEAR)
    if level >= 1:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.2, 0.5 * level)))
    arr = np.asarray(img).astype(np.float32)
    if level >= 2:
        arr = arr * random.uniform(0.55, 1.0) + random.uniform(-20, 15)              # dark / washed out
        arr += np.random.normal(0, 4 * level, arr.shape)                              # sensor noise
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    border = Image.new("RGB", (img.width + 16, img.height + 12), tuple(random.randint(40, 120) for _ in range(3)))
    border.paste(img, (8, 6))
    return border


def main(split="test", count_per_level=100):
    """split="dev" (seed 42) was used while writing the clean-up rules; "test" (seed 7) is only
    used for the final numbers, so the reported accuracy is not tuned to the test plates."""
    seed = 42 if split == "dev" else 7
    random.seed(seed)
    np.random.seed(seed)
    out = os.path.join(DATA, f"synthetic_plates_{split}")
    os.makedirs(out, exist_ok=True)
    styles = ["punjab_car", "punjab_bike", "punjab_year", "ict", "sindh"]
    labels = []
    for level in range(4):
        for i in range(count_per_level):
            style = styles[i % len(styles)]
            img, truth = plate_image(style)
            img = degrade(img, level)
            name = f"L{level}_{i:03d}_{style}.jpg"
            img.save(os.path.join(out, name), quality=random.randint(45, 85) if level >= 2 else 90)
            labels.append({"file": name, "plate": truth, "style": style, "level": level})
    with open(os.path.join(out, "labels.json"), "w") as f:
        json.dump(labels, f, indent=1)
    print(f"Wrote {len(labels)} plates to {out}")


if __name__ == "__main__":
    main("dev")
    main("test")
