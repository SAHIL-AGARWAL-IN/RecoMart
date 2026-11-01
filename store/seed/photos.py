"""Download product photos once and keep them in MEDIA_ROOT; re-seeding reuses them.

If a photo cannot be downloaded (no internet, or --offline), the main image is drawn
with Pillow instead, so every product always has a picture.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.conf import settings

TIMEOUT_SECONDS = 20
MAX_WORKERS = 8


def _download(url):
    import requests

    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def _ensure(job, offline):
    """Make sure one image file exists. Returns 'cached', 'downloaded', 'generated' or 'skipped'."""
    path = Path(settings.MEDIA_ROOT) / job["path"]
    if path.exists():
        return "cached"
    path.parent.mkdir(parents=True, exist_ok=True)
    if job.get("url") and not offline:
        try:
            path.write_bytes(_download(job["url"]))
            return "downloaded"
        except Exception:  # any network error -> fall back below
            pass
    if job.get("fallback"):
        path.write_bytes(job["fallback"]())
        return "generated"
    return "skipped"


def ensure_images(jobs, offline=False):
    """Run all image jobs in parallel. Returns a {relative_path: status} dict."""
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        statuses = pool.map(lambda job: _ensure(job, offline), jobs)
        return {job["path"]: status for job, status in zip(jobs, statuses)}
