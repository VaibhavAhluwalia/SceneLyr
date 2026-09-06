# Deterministic pixel import

This importer uses local OpenCV thresholding, enclosed contours, connected pixels,
and on-device Apple Vision OCR on macOS. It never sends an image to a cloud provider.
The geometric stage uses fixed rules; Apple Vision OCR is a trained local recognizer.

Install Python 3.11+ in a local virtual environment (prefer the internal disk for
dependencies when the repository is on an external drive):

```sh
python3 -m venv /tmp/scenelyr-python
/tmp/scenelyr-python/bin/pip install -e '.[dev]'
/tmp/scenelyr-python/bin/scenelyr import-pixels diagram.png extracted.scene.json
/tmp/scenelyr-python/bin/pytest
```

Supported baseline: enclosed rectangles, ellipses, diamonds and filled-color objects,
including transparent or dark backgrounds, with continuous connectors. OCR text inside
detected objects becomes the label when available; confidence and source bounds are retained.
Types remain generic assets. These are geometric
objects, not inferred services or databases. The operation fails on missing/invalid files.

The importer compares connector ink at both endpoints and marks direction as `inferred`
only when one endpoint is materially arrowhead-like. Otherwise it records `unknown`.
All imported connections retain `requiresReview: true`; deterministic inference is not
the same as guaranteed correctness.

Limitations: OCR is macOS-only and can fail on unusual fonts or low-resolution text;
there is no reliable arrow recognition in all styles, automatic deskew, nested group
recovery, photo segmentation or general object recognition. Fixed pixel thresholds
mean results depend on resolution. More than two objects touching one connector are
withheld as ambiguous. Objects without enclosed borders may be missed. Large shapes
can suppress nested shapes. This is an explicit CLI mode; existing image import is unchanged.

The synthetic benchmark checks repeated extraction for determinism and reports actual
counts against ground truth. Clean, faint, blurred, seeded-noise, small-gap and
10/20-degree rotation fixtures recover 2 objects and 1 connection. The observed
limits are a 50-pixel border gap, a 60-pixel connector gap, and 30-degree rotation.
These results describe these fixtures only and are not accuracy claims for real images.

The public WebNots flowchart fixture used during development recovers 6 objects and 6
connector paths, repeatably. On macOS the current sample recovers all six printed object
labels. It does not infer semantic service/database types.
