import sys
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image


def candidates(folder):
    files = [path for path in Path(folder).rglob("*") if path.is_file()]
    files.sort()
    middle = len(files) // 2
    return files[middle:] + files[:middle]


def convert(folder, output):
    for path in candidates(folder):
        try:
            dataset = pydicom.dcmread(path)
            pixels = dataset.pixel_array.astype(np.float32)
            if pixels.ndim > 2:
                pixels = pixels[pixels.shape[0] // 2]
            low, high = np.percentile(pixels, (1, 99))
            if high <= low:
                low, high = float(pixels.min()), float(pixels.max())
            if high <= low:
                continue
            normalized = np.clip((pixels - low) / (high - low), 0, 1)
            image = Image.fromarray((normalized * 255).astype(np.uint8), mode="L")
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            print(f"Converted {path.name} -> {output_path}")
            return
        except Exception:
            continue
    raise RuntimeError("No readable DICOM image with pixel data was found.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: dicom_to_png.py <dicom_folder> <output_png>")
    convert(sys.argv[1], sys.argv[2])
