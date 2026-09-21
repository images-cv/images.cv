# Dataset package format

This document describes exactly what a dataset download from
[images.cv](https://images.cv) currently contains, and separately what a
planned enrichment format would add. It was written by inspecting the live
`imagescv-app-server` code and by running a real, anonymous download against
production (`https://api.images.cv`) and unzipping the result. Nothing here
is speculative unless explicitly marked **Planned**.

## 1. How a download actually happens today

There is no single "give me a file" endpoint. A dataset download is an
asynchronous job:

1. `POST /download_images` — submits a packaging job for one dataset
   category (`categories: [slug]`) with your chosen options (image size,
   color mode, train/val/test split, optional augmentations). Returns
   `{"data": {"link_id": "<the id you sent>"}}`.
2. `POST /get_link` with `{"link_id": ...}` — poll this every few seconds.
   While the job is running, `data.public_url` is empty. Once the worker
   finishes building the ZIP and uploading it to Google Cloud Storage, the
   same call returns `data.public_url` pointing at the finished archive.
3. `GET` the `public_url` directly. It is a **plain public GCS URL**
   (`storage.googleapis.com/...`), not a signed URL — it does not expire and
   there is no redirect chain involved.

Both `/download_images` and `/get_link` work **anonymously** — no API key,
login, or auth header is required or sent by the production frontend.

There is no dataset "version" concept on this flow (no `latest` alias, no
version field in the response) — every job builds fresh output from
whatever images currently belong to that category. A near-identical repeat
request (same slug/size/color/split/augmentations) may return instantly
because the server has a same-parameters cache (`unique_downloads` in
Firestore) — this is not a bug, just re-use of a prior build.

**Operational gotcha:** the production API sits behind Cloudflare. Requests
without a realistic browser-like `User-Agent` (and ideally `Origin`/
`Referer`) header are blocked with an HTML "Attention Required" page and
HTTP 403, even though the request itself was well-formed. The notebook and
`examples/download_dataset.py` both set these headers and treat an
HTML/non-ZIP response as an error rather than silently corrupting a `.zip`
file. See `docs/notebook-usage.md` for the exact symptom.

## 2. Dataset identifiers ("slugs")

A dataset is identified by its category **key**, e.g. `"pug"`,
`"golden_pheasant"`. Keys are opaque lowercase, underscore-separated
strings — there is no formally documented pattern, treat them as arbitrary
strings. You can discover keys via `POST /search_datasets` with
`{"q": "<query>", "minImages": -1}`, which returns
`[{"data_key": "...", "count": <image_count>, "image": "<thumbnail url>"}, ...]`.

## 3. ZIP contents — verified today

Confirmed by actually downloading and unzipping a real package
(`buoy`, 65 images) on 2026-09-21:

```
images.cv_<opaque_id>/
  meta.json
  data/
    train/<label>/<filename>.jpg
    val/<label>/<filename>.jpg
    test/<label>/<filename>.jpg
```

Notes:

- **`<label>`** is the space-joined list of categories the source image
  belongs to (e.g. `"boat buoy"`), not necessarily the slug you requested.
  Treat each immediate parent directory under `data/{train,val,test}/` as
  a class label — do not assume it equals the requested slug.
- **Filenames** are not guaranteed to have a single clean extension — the
  packaging step appends `.jpg` to whatever basename it fetched, which can
  produce names like `buoy-beacon-water-1661196.jpg.jpg`. Treat the whole
  filename as opaque; don't parse "the extension" out of it.
- Augmented copies (when augmentations are enabled) sit alongside the
  original with an `_aug` suffix, train split only.
- Images are re-encoded JPEGs; requesting `nochange` for size skips
  resizing, any `size_N` value resizes to `N×N` with OpenCV.
- **There is no `index.csv`, no `bboxes/`, no `masks/`, no `coco/`, and no
  `yolo/` in this package.** This is a plain classification (ImageFolder)
  layout only.

### `meta.json` — verified schema

```json
{
  "labels": ["buoy"],
  "amount_of_images": 65,
  "image_color_mode": "color",
  "image_size": "size_32",
  "split": { "train": 48, "val": 12, "test": 5 },
  "split_ratio": { "train": 70, "val": 15, "test": 15 },
  "description": "All the images are in the data folder (70% train / 15% val / 15% test).",
  "total_creation_time": "0:00:58.396162",
  "augmentation": {
    "active": false,
    "augmentation_count": 0,
    "augmentations": [],
    "description": "Augmented images have an _aug suffix."
  },
  "normalization": {
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
    "note": "ImageNet default -- pair with transforms.Normalize(mean, std) in PyTorch or tf.image.per_image_standardization equivalents."
  },
  "about": {
    "provide_by": "www.images.cv",
    "useful_links": ["https://images.cv/how-to-use", "..."]
  }
}
```

`normalization.mean`/`std` are `[0.449]`/`[0.226]` (single channel) when
`image_color_mode` is `"gray"`.

There is **no checksum field anywhere** in this response or the download
job. The notebook and CLI example explicitly say "checksum verification
unavailable" rather than claiming the archive was verified.

## 4. Required vs. optional files

| File/folder | Required today | Notes |
|---|---|---|
| `meta.json` | Yes | Always written before zipping |
| `data/train/`, `data/val/`, `data/test/` | Yes (may be empty) | Always created, even if a split gets 0 images |
| `bboxes/`, `masks/`, `coco/`, `yolo/`, `index.csv` | **Not present** | Planned, see below |

Tooling should detect each capability rather than assume it exists — a
dataset package with an empty `val/`/`test/` split, or with only one label,
is normal, not an error.

## 5. Planned enrichment format (not currently downloadable)

The backend repo (`imagescv-app-server`) contains a fully-built **offline**
annotation pipeline (`tools/annotation_enrichment/`) with real, tested
exporters for canonical pixel-space bounding boxes, COCO (detection +
polygon/RLE segmentation), YOLO detection, YOLO segmentation, and PNG masks
— generated via Grounding DINO + SAM2. It defines an intended package layout:

```
dataset-download/
  index.csv
  meta.json
  data/images/
  bboxes/
  masks/
  coco/
    instances.json
    categories.json
  yolo/
    data.yaml
    detection/labels/
    segmentation/labels/
```

**This layout is not wired to any public route.** The pipeline currently
only writes a `machine_annotations` pointer onto internal Firestore image
documents via an operator-run CLI (`--confirm ... --commit`); no
`server.py` endpoint serves this output to end users, and it is not part
of the `/download_images` → `/get_link` flow described above.

A separate, unrelated, currently-disabled flow (`/get_community_dataset` +
`/get_hosted_dataset_download_url`, gated behind a `HOSTED_UPLOAD_ENABLED`
flag that is `false` in production) returns a **10-minute signed GCS URL**
for admin-approved "hosted dataset" uploads — but those packages are
whatever the uploader zipped, with no enforced COCO/YOLO/mask convention,
and the flag being off means this is not reachable by the public today
either.

A third, real and deployed, but unrelated code path is images.cv's paid
**Studio** feature, which does generate `data/`, `bboxes/`, `masks/`
(SAM-2), `coco/`, `yolo/`, `index.csv`, `meta.json` for a user's own
synthetic Studio project — this is good evidence for what a future catalog
enrichment format could look like, but it is a different product surface
and must not be presented as available for arbitrary catalog datasets.

**Bottom line:** the canonical/planned bbox and mask formats documented in
the starter notebook (pixel XYXY, COCO, YOLO detection/segmentation, PNG
and polygon masks) are written defensively so the same code will work the
day these folders are actually published — but as of this writing, every
real download from `/download_images` is images-only.

## 6. Missing endpoints for a fuller "current" experience

If you want the starter notebook to eventually show license, description,
maintainer, or review/trust-signal fields per dataset, or an instant
GET-by-slug download without a submit/poll job, these do not exist today:

- No endpoint returns per-dataset `license`, `description`, `maintainer`,
  or `source_url` — `/get_items_image_category` returns only thumbnails,
  `sumCounter` (image count), and category names.
- No instant `GET /datasets/<slug>/download` — every download is the
  submit-then-poll job above.
- No public endpoint currently serves bbox/mask/COCO/YOLO annotations for
  catalog datasets (see §5).

These are the exact gaps referenced in the top-level README's
"Missing/unavailable platform APIs" section.
