"""Tests that the documentation matches the integration."""

import re

import yaml

from script.generate_docs import OUTPUT, ROOT, render


def test_models_and_entities_up_to_date() -> None:
    """Test docs/models-and-entities.md is what the code would generate.

    Regenerate it with `python -m script.generate_docs` after changing the
    models, entities or English names.
    """
    assert OUTPUT.read_text() == render()


def test_changelog_links_are_absolute() -> None:
    """Test the changelog's links still work as GitHub release notes.

    The release workflow copies each section into the release, where a link
    relative to the repository no longer resolves.
    """
    links = re.findall(r"\]\(([^)]+)\)", (ROOT / "CHANGELOG.md").read_text())

    assert [link for link in links if not link.startswith("https://")] == []


def test_model_report_follows_the_checklist() -> None:
    """Test the model report asks about each section of the test checklist."""
    template = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "model_report.yml").read_text()
    )
    worked = next(field for field in template["body"] if field.get("id") == "worked")
    sections = re.findall(
        r"^## (\d+)\. (.+)$", (ROOT / "docs" / "testing.md").read_text(), re.MULTILINE
    )

    assert [
        option["label"].split(":")[0] for option in worked["attributes"]["options"]
    ] == [f"{number}. {title}" for number, title in sections]
