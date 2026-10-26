"""Storage abstraction + safe image handling. Swap LocalStorage for an S3/Azure Blob implementation in production."""
import io
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.exceptions import AppError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
SAFE_NAME = re.compile(r"^[a-f0-9]{32}\.jpg$")
FOLDERS = {"customers", "visits"}


class Storage(ABC):
    @abstractmethod
    def save(self, folder: str, name: str, data: bytes) -> None: ...

    @abstractmethod
    def open_path(self, folder: str, name: str) -> Path | None: ...


class LocalStorage(Storage):
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, folder: str, name: str) -> Path:
        if folder not in FOLDERS or not SAFE_NAME.match(name):
            raise AppError("Invalid file reference")
        p = (self.root / folder / name).resolve()
        if self.root not in p.parents:
            raise AppError("Invalid file reference")
        return p

    def save(self, folder: str, name: str, data: bytes) -> None:
        p = self._path(folder, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def open_path(self, folder: str, name: str) -> Path | None:
        p = self._path(folder, name)
        return p if p.is_file() else None  # a DB reference does not guarantee the file exists


def get_storage() -> Storage:
    return LocalStorage(get_settings().upload_dir)


def process_image(raw: bytes) -> bytes:
    """Validate, strip metadata (EXIF/GPS), downscale and re-encode as JPEG. Never trusts client filename/type."""
    s = get_settings()
    if not raw:
        raise AppError("Empty file")
    if len(raw) > s.max_upload_bytes:
        raise AppError(f"File too large (max {s.max_upload_bytes // (1024 * 1024)} MB)")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ALLOWED_FORMATS:
            raise AppError("Only JPEG, PNG or WEBP images are allowed")
        img.load()
    except (UnidentifiedImageError, OSError):
        raise AppError("File is not a valid image")
    img = img.convert("RGB")
    img.thumbnail((s.image_max_dimension, s.image_max_dimension))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def store_image(folder: str, raw: bytes) -> str:
    data = process_image(raw)
    name = f"{uuid.uuid4().hex}.jpg"
    get_storage().save(folder, name, data)
    return f"/api/v1/files/{folder}/{name}"
