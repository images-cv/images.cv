# Using the images.cv Colab starter notebook

## Opening it

Click **Open in Colab** at the top of the [README](../README.md), or open
directly:

https://colab.research.google.com/github/images-cv/images.cv/blob/main/notebooks/images_cv_starter.ipynb

This runs the notebook straight from GitHub — no download or account setup
needed. Sign in with a Google account only if you want to save your own
copy (`File > Save a copy in Drive`).

## Running it

1. Edit the form fields in the **Dataset configuration** cell (the only
   cell most people need to touch): set `DATASET_SLUG` to a dataset key
   from [images.cv](https://images.cv) (visible in the dataset's URL),
   pick image size/color/split options, and leave the optional sections
   (`RUN_PYTORCH_EXAMPLE`, `MOUNT_GOOGLE_DRIVE`) off unless you want them.
2. `Runtime > Run all`, or step through with Shift+Enter. Cells must run
   top to bottom — later cells depend on variables set earlier.
3. Watch the **Download dataset** cell — it submits a packaging job and
   polls until it's ready, which can take anywhere from a few seconds to a
   few minutes depending on how large the category is and whether an
   identical package was already built recently (in which case it's
   near-instant).

## What to expect timing-wise

- Metadata and job-submission calls occasionally take 10-25 seconds — the
  backend runs on Cloud Functions, which can cold-start. The notebook
  already sets a 45-second timeout for these; if a cell still times out,
  just re-run it.
- Package-build time scales with how many images are in the category and
  whether resizing/augmentation is requested. A few hundred images
  typically finishes in under a minute; large (1000+ image) categories can
  take several minutes on a first build.
- Everything runs fine on Colab's **free CPU runtime**. A GPU is not
  needed for any default section. If you enable the optional PyTorch
  section, it will use a GPU automatically if the runtime has one, but
  runs fine on CPU too since it only loads one batch — it does not train
  a model.

## Free Colab limitations to keep in mind

- Colab's free tier can disconnect idle sessions and has session-length
  limits. If you're exploring a very large dataset, download once, then
  do your exploration in the same session before it recycles.
- The notebook's workspace (`images_cv_workspace/`) lives on the Colab
  VM's local, ephemeral disk — it's gone when the runtime recycles. Use
  section 16 (**Optional: export to Google Drive**) if you want the
  downloaded package, image index, and capability report to persist.
- Colab's default disk quota is generous for typical dataset sizes here,
  but very large or repeated downloads (especially with `FORCE_DOWNLOAD`
  enabled) can fill it. Delete `images_cv_workspace/` if you hit that.

## Saving a copy to Drive

`File > Save a copy in Drive` saves the *notebook itself* (your edited
form field values, any cells you added). This is separate from section 16,
which exports the *downloaded dataset and generated reports* — use
whichever (or both) you need.

## Dataset license responsibility

Downloading a dataset through this notebook does not grant you any rights
beyond what that dataset's own license allows. **Dataset licenses vary —
review the license and attribution requirements shown for the dataset on
its images.cv page before using or redistributing it.** The images.cv
platform's own terms, and this repository's code license (see the
top-level README's License status section), are separate from any
individual dataset's license.

## Understanding missing annotation sections

Most public datasets on images.cv today are **images-only** — no bounding
boxes, masks, COCO, or YOLO annotations. Sections 11-14 of the notebook
detect this automatically and print a short message instead of failing.
This is expected, not a bug. See
[`dataset-package-format.md`](./dataset-package-format.md) for exactly
what's currently included vs. planned as a future enrichment format.

## Common errors

| Symptom | Likely cause | Fix |
|---|---|---|
| A cell raises "returned non-JSON... Cloudflare" | The API's Cloudflare protection blocked an unusual request | Re-run the cell; if it persists, you may be on a flagged network |
| "Timed out waiting for the package to be built" | Large or first-time category taking longer than the timeout | Increase `DOWNLOAD_TIMEOUT_SECONDS` in the config cell and re-run from the Download section |
| Metadata shows 0 images | `DATASET_SLUG` doesn't match a real dataset key | Double-check the slug from the dataset's URL on images.cv |
| "Downloaded file is not a valid ZIP" | The download response was an error/HTML page, not a ZIP | Re-run; if persistent, the dataset or API may be temporarily unavailable |
| A capability section says "does not include..." | That dataset genuinely doesn't have that annotation type today | Expected — see `dataset-package-format.md` |
| A few images are skipped as "unreadable/corrupted" | A small number of source images failed to decode | Expected and non-fatal; the notebook continues |

## Reporting notebook problems

Open an issue in [images-cv/images.cv](https://github.com/images-cv/images.cv)
with: the dataset slug you used, the form field values, the full error
message/traceback, and whether it happens on a fresh "Run all" from a
freshly opened Colab session.
