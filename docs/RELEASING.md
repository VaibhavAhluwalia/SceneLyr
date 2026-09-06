# Public release checklist

SceneLyr 0.1.0 is the initial release. Release notes must state the supported input
boundary and known extraction limitations clearly.

## Required before publishing

- Confirm the MIT license and copyright notice remain included in source distributions.
- Review and commit the Python migration as one coherent change.
- Confirm the Ubuntu and macOS jobs pass on Python 3.11 and 3.12.
- Build and install the wheel in a clean environment.
- Validate the repository Codex plugin and marketplace manifests.
- Confirm no personal images, generated imports, credentials, or local paths are tracked.
- Publish a test-fixture provenance note for every redistributed image.
- Describe the release as “SceneLyr 0.1.0 — Initial Release” and state that extraction
  requires human review.

## Accuracy statement

SceneLyr uses deterministic OpenCV geometry. On macOS, printed-text OCR optionally uses
Apple Vision locally; this is an on-device model and must not be described as purely
rule-based. No cloud model is required. Shape, text, connector, and direction recovery
are not guaranteed, particularly for small, dense, crossed, hand-drawn, or photographic
inputs.

## Suggested release sequence

1. Select the license.
2. Review the working-tree diff.
3. Commit and push the migration.
4. Wait for the full CI matrix.
5. Tag the first public build as `v0.1.0` with the title “Initial Release”.
6. Publish the plugin installation instructions with the matching source revision.
