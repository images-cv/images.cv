#!/usr/bin/env python3
"""Download a public dataset from images.cv.

Uses the real, anonymous, currently-supported API:

    POST /download_images  -> submits a packaging job, returns a link_id
    POST /get_link          -> poll until the job's public_url is ready
    GET  <public_url>       -> stream the finished ZIP

See ../docs/dataset-package-format.md for the verified request/response
schemas and package layout this mirrors.

Examples:
    python download_dataset.py --dataset buoy --output ./datasets/buoy
    python download_dataset.py --dataset pug --metadata-only
    python download_dataset.py --dataset pug --output ./datasets/pug --force
"""
from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

API_BASE_URL = "https://api.images.cv"

# The production API is behind Cloudflare. Requests without a realistic
# browser-like User-Agent (and ideally Origin/Referer) are blocked with an
# HTML "Attention Required" 403 page even though the request is otherwise
# well-formed -- verified empirically. Do not remove these headers.
# The backend runs on Cloud Functions and can take 15-25s to respond on a
# cold start -- observed directly while building this script. 45s gives
# margin above that without hanging forever on a genuinely dead backend.
REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Origin": "https://images.cv",
    "Referer": "https://images.cv/",
}

VALID_SIZES = {"size_16", "size_32", "size_64", "size_128", "size_256", "nochange"}


class DownloadError(RuntimeError):
    """A user-facing, non-traceback-worthy failure."""


def _post(path: str, body: dict[str, Any], timeout: int = 45, retries: int = 2) -> dict[str, Any]:
    # Retries only cover network-level failures (timeouts, connection resets),
    # not application responses -- a real 4xx/invalid-slug response is
    # returned as-is and should not be retried.
    resp = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(f"{API_BASE_URL}{path}", json=body,
                                  headers=REQUEST_HEADERS, timeout=timeout)
            break
        except requests.exceptions.RequestException as exc:
            if attempt == retries:
                raise DownloadError(f"Network error calling {path}: {exc}") from exc
            time.sleep(2 * (attempt + 1))  # 2s, 4s backoff

    content_type = resp.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        snippet = resp.text[:200].replace("\n", " ")
        raise DownloadError(
            f"{path} returned non-JSON ({resp.status_code}, {content_type}). "
            f"This usually means the request was blocked before it reached "
            f"the app (e.g. a Cloudflare challenge page). First bytes: {snippet!r}"
        )
    data = resp.json()
    if resp.status_code != 200 or data.get("isError"):
        raise DownloadError(f"{path} failed ({resp.status_code}): {data}")
    return data


def fetch_metadata(slug: str) -> dict[str, Any]:
    """Best-effort dataset summary. The API does not expose license,
    description or maintainer fields -- only what is actually returned."""
    data = _post("/get_items_image_category", {"category": slug, "start_after": 0})["data"]
    return {
        "slug": slug,
        "image_count": data.get("sumCounter"),
        "categories": data.get("categories"),
        "main_category": data.get("mainCategory"),
        "data_source": data.get("dataSource"),
        "is_premium": data.get("is_premium"),
        "sample_thumbnails": data.get("data", []),
    }


def submit_download_job(slug: str, output_size: str, color_type: str,
                         split_set: list[float]) -> str:
    if output_size not in VALID_SIZES:
        raise DownloadError(f"output_size must be one of {sorted(VALID_SIZES)}, got {output_size!r}")
    if color_type not in {"color", "gray"}:
        raise DownloadError(f"color_type must be 'color' or 'gray', got {color_type!r}")

    link_id = secrets.token_hex(20)  # arbitrary unique id; format is not validated server-side
    body = {
        "output_size": output_size,
        "color_type": color_type,
        "images": [],
        "categories": [slug],
        "augmentations": [],
        "split_set": split_set,
        "link_id": link_id,
        "request_type": "CALL_FROM_SEARCH",
        "user_email": [],
        "user_id": "",
        "augmentation_percent": 30,
    }
    result = _post("/download_images", body)
    returned_id = result.get("data", {}).get("link_id")
    if not returned_id:
        raise DownloadError(f"/download_images did not return a link_id: {result}")
    return returned_id


def wait_for_download_url(link_id: str, timeout_seconds: int = 600,
                           poll_interval: float = 3.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = _post("/get_link", {"link_id": link_id})
        public_url = result.get("data", {}).get("public_url") or ""
        if public_url:
            return public_url
        time.sleep(poll_interval)
    raise DownloadError(
        f"Timed out after {timeout_seconds}s waiting for the dataset package to be built. "
        f"Large or first-time categories can take longer -- try increasing --timeout."
    )


def stream_download(url: str, dest_zip: Path) -> None:
    try:
        resp = requests.get(url, stream=True, timeout=60)
    except requests.exceptions.RequestException as exc:
        raise DownloadError(f"Network error downloading package: {exc}") from exc

    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or "html" in content_type.lower():
        snippet = resp.text[:200].replace("\n", " ") if not resp.raw.closed else ""
        raise DownloadError(
            f"Package download returned {resp.status_code} ({content_type}), "
            f"expected a ZIP file. First bytes: {snippet!r}"
        )

    total = int(resp.headers.get("Content-Length", 0))
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        from tqdm import tqdm
        progress = tqdm(total=total or None, unit="B", unit_scale=True, desc="Downloading")
    except ImportError:
        progress = None

    with open(dest_zip, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            fh.write(chunk)
            written += len(chunk)
            if progress:
                progress.update(len(chunk))
    if progress:
        progress.close()

    # Reject HTML/error pages that slipped through without a Content-Type
    # header, or empty files, before we ever call this a valid ZIP.
    with open(dest_zip, "rb") as fh:
        magic = fh.read(4)
    if magic[:2] != b"PK":
        dest_zip.unlink(missing_ok=True)
        raise DownloadError(
            "Downloaded file is not a valid ZIP (missing 'PK' signature). "
            "The response was likely an error page rather than the package."
        )

    print(f"Downloaded {written / (1024 * 1024):.1f} MB -> {dest_zip}")
    print("Note: the API does not provide a checksum for this package; "
          "integrity verification beyond the ZIP signature is unavailable.")


def safe_extract(zip_path: Path, dest_dir: Path) -> int:
    """Extract dest_dir, refusing any member that would escape it."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted_bytes = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = (dest_dir / member.filename).resolve()
            if not str(member_path).startswith(str(dest_dir.resolve())):
                raise DownloadError(f"Refusing to extract unsafe path: {member.filename!r}")
        zf.extractall(dest_dir)
        extracted_bytes = sum(m.file_size for m in zf.infolist())
    print(f"Extracted {extracted_bytes / (1024 * 1024):.1f} MB -> {dest_dir}")
    return extracted_bytes


def inspect_package(dataset_dir: Path) -> dict[str, bool]:
    """Report which known package capabilities are present. Never treat a
    missing capability as an error -- most packages today are images-only."""
    roots = list(dataset_dir.glob("*"))
    pkg_root = roots[0] if len(roots) == 1 and roots[0].is_dir() else dataset_dir

    meta_path = pkg_root / "meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    data_dir = pkg_root / "data"
    has_images = any(data_dir.rglob("*.jpg")) or any(data_dir.rglob("*.jpeg")) or any(data_dir.rglob("*.png"))
    has_labels = any((data_dir / split).is_dir() and any((data_dir / split).iterdir())
                      for split in ("train", "val", "test") if (data_dir / split).is_dir())

    capabilities = {
        "Images": has_images,
        "Labels (class folders)": has_labels,
        "Bounding boxes": (pkg_root / "bboxes").is_dir(),
        "Masks": (pkg_root / "masks").is_dir(),
        "COCO": (pkg_root / "coco").is_dir(),
        "YOLO detection": (pkg_root / "yolo" / "detection").is_dir() or (pkg_root / "yolo" / "labels").is_dir(),
        "YOLO segmentation": (pkg_root / "yolo" / "segmentation").is_dir(),
        "index.csv": (pkg_root / "index.csv").is_file(),
    }

    print("\nPackage capability summary:")
    print(f"{'Capability':<24} Available")
    for name, available in capabilities.items():
        print(f"{name:<24} {'Yes' if available else 'No'}")

    if meta:
        print(f"\nmeta.json: {meta.get('amount_of_images')} images, "
              f"labels={meta.get('labels')}, split={meta.get('split')}")
    return capabilities


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Dataset slug/key, e.g. 'pug' or 'buoy'")
    parser.add_argument("--output", default=None,
                         help="Output directory (default: ./datasets/<dataset>)")
    parser.add_argument("--size", default="size_128", choices=sorted(VALID_SIZES),
                         help="Image resize option (default: size_128)")
    parser.add_argument("--color", default="color", choices=("color", "gray"))
    parser.add_argument("--split", default="0.7,0.15,0.15",
                         help="train,val,test ratios summing to 1.0 (default: 0.7,0.15,0.15)")
    parser.add_argument("--force", action="store_true", help="Re-download even if a package already exists")
    parser.add_argument("--metadata-only", action="store_true",
                         help="Only fetch and print dataset metadata; do not download")
    parser.add_argument("--timeout", type=int, default=600,
                         help="Max seconds to wait for the packaging job (default: 600)")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else Path("datasets") / args.dataset
    zip_path = output_dir / f"{args.dataset}.zip"
    extract_dir = output_dir / "package"

    try:
        meta = fetch_metadata(args.dataset)
        print(f"Dataset '{args.dataset}': {meta['image_count']} images, "
              f"categories={meta['categories']}, premium={meta['is_premium']}")

        if args.metadata_only:
            return 0

        if zip_path.exists() and not args.force:
            print(f"{zip_path} already exists, reusing it (use --force to re-download).")
        else:
            split_set = [float(x) for x in args.split.split(",")]
            if len(split_set) != 3 or abs(sum(split_set) - 1.0) > 1e-6:
                raise DownloadError(f"--split must be three ratios summing to 1.0, got {args.split!r}")

            print(f"Submitting packaging job for '{args.dataset}' "
                  f"(size={args.size}, color={args.color}, split={split_set})...")
            link_id = submit_download_job(args.dataset, args.size, args.color, split_set)
            print(f"Job accepted (link_id={link_id}). Waiting for it to finish "
                  f"(this can take from seconds to several minutes)...")
            public_url = wait_for_download_url(link_id, timeout_seconds=args.timeout)
            stream_download(public_url, zip_path)

        if extract_dir.exists() and args.force:
            shutil.rmtree(extract_dir)
        if not extract_dir.exists():
            safe_extract(zip_path, extract_dir)
        inspect_package(extract_dir)

    except DownloadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
