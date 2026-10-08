"""Tests that the generated documentation matches the integration."""

from script.generate_docs import OUTPUT, render


def test_models_and_entities_up_to_date() -> None:
    """Test docs/models-and-entities.md is what the code would generate.

    Regenerate it with `python -m script.generate_docs` after changing the
    models, entities or English names.
    """
    assert OUTPUT.read_text() == render()
