# images.cv

**Discover, evaluate, and share computer vision datasets.**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/images-cv/images.cv/blob/main/notebooks/images_cv_starter.ipynb)

This is the public developer entry point for [images.cv](https://images.cv):
a starter notebook, a Python download example, and documentation for
working with images.cv datasets in code.

## 1. Overview

images.cv hosts **3,000+ labeled classes across 2M+ images**, searchable
and downloadable for machine learning and computer vision work. It is
developing into a community platform for computer vision datasets — not
just a static directory — with dataset search, per-dataset trust/quality
signals, public profiles, collections, and a dataset submission flow, in
addition to the free hosted dataset catalog this repo's notebook downloads
from.

## 2. Why images.cv

- Free, searchable, labeled image datasets spanning everyday objects,
  animals, food, vehicles, and hundreds of other categories.
- A real, working, **anonymous** download path — no account required to
  pull a dataset (see [§5](#5-dataset-package-structure) and the notebook).
- A growing set of community features (below) built around dataset
  discovery and reuse, not just hosting.

## 3. Explore datasets

Browse and search the catalog at [images.cv](https://images.cv). Every
dataset has a short **slug** (its key, e.g. `pug`, `golden_pheasant`)
visible in its URL — that's what you'll use to download it via the
notebook or the Python example.

## 4. Community platform

Confirmed, live site features beyond the dataset catalog itself:

- **Search and discovery** — full dataset search.
- **Dataset trust/quality summary** — each dataset page shows a computed
  trust/quality signal for that dataset.
- **Public profiles** — `images.cv/users/<username>`.
- **Collections** — create and browse curated sets of datasets.
- **Dataset submission/upload** — contribute your own dataset (requires an
  account).
- **Community dataset pages** — a separate, community-contributed dataset
  surface alongside the main catalog.

> Some of these features (e.g. community-contributed dataset hosting) are
> present in the product but not yet enabled for general public use — this
> repository only documents and downloads from what's actually live and
> anonymous today. See `docs/dataset-package-format.md` for the exact
> current-vs-planned breakdown behind the download flow.

## 5. Dataset package structure

**Today, every public dataset download is a classification (ImageFolder)
package: images only.** There is no bounding-box, mask, COCO, or YOLO
annotation data in this flow yet.

```
images.cv_<id>/
  meta.json
  data/
    train/<label>/<file>.jpg
    val/<label>/<file>.jpg
    test/<label>/<file>.jpg
```

> Some datasets may, in the future, include automatically generated
> bounding boxes and segmentation masks. Machine-generated annotations may
> contain errors and should be reviewed before production use. As of this
> writing, this is **not yet part of the public download** — see
> [`docs/dataset-package-format.md`](docs/dataset-package-format.md) for
> the verified current format and the planned enrichment format
> side-by-side.

**Dataset licenses vary.** Review the license and attribution requirements
shown for each dataset on its images.cv page before using or
redistributing it. This does not imply the repository's own software
license (see [§12](#12-license-status)) covers any dataset's contents.

## 6. Open a dataset in Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/images-cv/images.cv/blob/main/notebooks/images_cv_starter.ipynb)

Open any dataset page on images.cv and select **Open in Colab**. The
dataset name is copied automatically. Paste it into the notebook's
`DATASET_SLUG` field, then run the notebook cells in order.

If you open the notebook directly (via the badge above, without coming
from a dataset page first), browse the [images.cv](https://images.cv)
catalog, copy a dataset's slug, and paste it into `DATASET_SLUG` yourself
— the notebook ships with a placeholder value and will not run against a
real dataset until you do this.

The starter notebook downloads the chosen dataset by slug, verifies and
safely extracts it, explores its metadata/images/class distribution, and
visualizes bounding boxes/masks/COCO/YOLO annotations when a package
actually includes them. See
[`docs/notebook-usage.md`](docs/notebook-usage.md) for a full walkthrough,
timing expectations, and troubleshooting.

## 7. Python example

```bash
pip install -r requirements.txt
python examples/download_dataset.py --dataset pug --output ./datasets/pug
```

See [`examples/download_dataset.py`](examples/download_dataset.py) for a
CLI version of the same download → verify → extract → inspect flow used by
the notebook, including `--force` and `--metadata-only`.

## 8. Annotation formats

- **Currently downloadable:** images only (`data/{train,val,test}/<label>/`),
  described above.
- **Planned enrichment format:** canonical pixel-space bounding boxes,
  COCO (detection + polygon/RLE segmentation), YOLO detection, YOLO
  segmentation, and PNG masks. The conversion/visualization code in the
  starter notebook already supports these formats defensively so it will
  work the day they're published — see
  [`docs/dataset-package-format.md`](docs/dataset-package-format.md) §5
  for exactly what exists in code today versus what's wired to a public
  endpoint.

## 9. Contributing

Suggestions and pull requests are welcome — notebook improvements, docs
fixes, or the Python example. Keep new notebooks/examples honest about
what the live API actually returns; don't assume future formats are
already available.

## 10. Reporting issues

Open an issue in this repository for problems with the notebook, the
Python example, or the docs here. For dataset content issues (wrong
label, broken image, etc.), use images.cv's own site tools.

## 11. Project links

- Site: [images.cv](https://images.cv)
- Dataset categories: [images.cv/computer-vision-dataset-categories](https://images.cv/computer-vision-dataset-categories)
- How to use: [images.cv/how-to-use](https://images.cv/how-to-use)
- FAQ: [images.cv/faq](https://images.cv/faq)
- Contact: [images.cv/contact](https://images.cv/contact)

## 12. License status

**This repository does not currently declare a software license.** No
`LICENSE` file exists and none is implied by anything in this README.
Until a license is added, default copyright applies and reuse of this
repository's own code (notebook, examples, docs) beyond personal viewing
is not granted. This is separate from, and does not affect, the licenses
of individual datasets hosted on images.cv, which are shown per-dataset on
the site and vary dataset to dataset.
