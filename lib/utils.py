import zipfile
from pathlib import Path

import img2pdf


def convert_images_to_pdf(image_dir: Path, pdf_path: Path):
    images = sorted(image_dir.glob("*.png"))
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert([str(image) for image in images]))


def convert_images_to_cbz(image_dir: Path, cbz_path: Path):
    images = sorted(image_dir.glob("*.png"))
    with zipfile.ZipFile(cbz_path, "w") as cbz:
        for image in images:
            cbz.write(image, arcname=image.name)
