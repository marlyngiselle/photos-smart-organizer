from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from photosorg import config
from photosorg.config import Config, ConfigError
from photosorg.models import MediaType

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "config.toml"


def test_example_config_matches_defaults_plus_one_geofence() -> None:
    cfg = config.load(EXAMPLE)
    defaults = Config()
    assert cfg.albums == defaults.albums
    assert cfg.favourites == defaults.favourites
    assert cfg.trips == defaults.trips
    assert cfg.home == defaults.home
    assert [g.name for g in cfg.geofences] == ["Golden Gate Park"]
    assert cfg.media == (MediaType.PHOTO, MediaType.LIVE)


def test_missing_default_file_means_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "DEFAULT_CONFIG_PATH", tmp_path / "nope.toml")
    assert config.load() == Config()


def test_explicit_missing_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        config.load(tmp_path / "nope.toml")


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ("[albums]\nby_planet = true", "unknown key 'config.albums.by_planet'"),
        ("[albums]\nby_city = 1", "must be true or false"),
        ("[favourites.weights]\naesthetic = 0.9", "must add up to 1.0"),
        ("[[geofences]]\nname = 'x'\nlat = 99\nlon = 0", "invalid coordinates"),
        ("[[geofences]]\nname = 'x'\nlat = 1", "missing 'lon'"),
        ("[schedule]\ninterval_minutes = 1", "between 5 and 1440"),
        ("[library]\nmedia = ['hologram']", "library.media"),
        ("[favourites]\ngroup_by = 'week'", "group_by"),
        ("[favourites]\ntop_n_per_event = 0", "at least 1"),
    ],
)
def test_invalid_config(toml: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        config.parse(tomllib.loads(toml))


def test_ints_are_accepted_for_floats() -> None:
    cfg = config.parse(tomllib.loads("[home]\nlat = 48\nlon = 2\nradius_km = 10"))
    assert cfg.home.lat == 48.0
    assert isinstance(cfg.home.radius_km, float)
