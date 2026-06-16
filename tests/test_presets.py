from kino.presets import get_preset, preset_names


def test_social_presets_are_available():
    assert preset_names() == ["landscape-web", "portrait-feed", "square-social", "vertical-social"]


def test_vertical_social_dimensions_and_ratio():
    preset = get_preset("vertical-social")

    assert preset.dimensions == (1080, 1920)
    assert preset.ratio == "9:16"
    assert preset.aspect_fraction.numerator == 9
    assert preset.aspect_fraction.denominator == 16
