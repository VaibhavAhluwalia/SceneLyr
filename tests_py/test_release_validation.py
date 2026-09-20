import json

from scenelyr.release_validation import run_release_validation


def test_release_fixture_matrix_passes_and_writes_review_report(tmp_path):
    report = run_release_validation(tmp_path / "release")

    assert report["passed"] is True
    assert report["summary"] == {"total": 10, "passed": 10, "checksTotal": 70, "checksPassed": 70}
    assert (tmp_path / "release" / "report.html").is_file()
    saved = json.loads((tmp_path / "release" / "report.json").read_text())
    assert saved["provenance"].startswith("All fixture images are generated")
    assert {item["id"] for item in saved["fixtures"]} == {
        "straight-filled", "bent-filled", "one-to-many-branch", "many-to-one-join",
        "clean-crossing", "ambiguous-three-way",
        "pale-filled", "lightly-broken-elbow", "open-v", "diagonal-route",
    }
