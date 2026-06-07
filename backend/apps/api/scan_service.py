import base64
import json
from pathlib import Path

from django.conf import settings

SCANS_FILE = settings.BASE_DIR / "scans.json"
SCANS_DIR = settings.BASE_DIR / "media" / "scans"


class ScanNotFoundError(ValueError):
    pass


def load_scans():
    return json.loads(SCANS_FILE.read_text(encoding="utf-8"))


def serialize_scan(scan):
    return {**scan, "imageUrl": f"/api/scans/{scan['id']}/image"}


def list_scans():
    fields = ("id", "title", "modality", "bodyPart", "symptoms", "symptomsSource", "userComplaint", "clinicalContext", "focusHint", "imageUrl")
    return [{field: scan[field] for field in fields} for scan in map(serialize_scan, load_scans())]


def get_scan(scan_id):
    scan = next((item for item in load_scans() if item["id"] == scan_id), None)
    if not scan:
        raise ScanNotFoundError("Scan case not found.")
    return serialize_scan(scan)


def scan_image_path(scan):
    path = SCANS_DIR / Path(scan["imageFile"]).name
    if not path.exists():
        raise FileNotFoundError("Scan image is missing.")
    return path


def scan_image_data_url(scan):
    path = scan_image_path(scan)
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
