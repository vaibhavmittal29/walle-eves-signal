"""Unit tests for mission configuration loading and validation rules."""

from pathlib import Path
import pytest
import yaml

from walle.config import (
    AppConfig,
    ConfigError,
    GridConfig,
    InitialSignalConfig,
    MissionSectionConfig,
    ObstaclesConfig,
    ResourcesConfig,
    load_config,
    validate_config,
)


def test_load_valid_configs():
    """Verify that all default YAML configurations load without errors."""
    for name in ("mission_easy.yaml", "mission_medium.yaml", "mission_hard_decoys.yaml"):
        path = Path("configs") / name
        cfg = load_config(path)
        assert cfg.mission.grid.width >= 12
        assert cfg.mission.grid.height >= 12
        assert cfg.resources.battery_initial <= cfg.resources.battery_capacity


def test_invalid_grid_size():
    """Grid smaller than 3x3 must raise ConfigError."""
    cfg = AppConfig(mission=MissionSectionConfig(grid=GridConfig(width=2, height=10)))
    with pytest.raises(ConfigError, match="Grid dimensions must be at least 3x3"):
        validate_config(cfg)


def test_invalid_start_bounds():
    """Start position out of bounds must raise ConfigError."""
    cfg = AppConfig(mission=MissionSectionConfig(start=(25, 5)))
    with pytest.raises(ConfigError, match="Start cell .* is outside grid bounds"):
        validate_config(cfg)


def test_battery_initial_exceeds_capacity():
    """Initial battery greater than capacity must raise ConfigError."""
    cfg = AppConfig(resources=ResourcesConfig(battery_capacity=50, battery_initial=80))
    with pytest.raises(ConfigError, match="Initial battery .* must be in range"):
        validate_config(cfg)


def test_invalid_clue_type_mix():
    """Clue type mix not summing to 1.0 must raise ConfigError."""
    from walle.config import CluesConfig
    cfg = AppConfig(mission=MissionSectionConfig(clues=CluesConfig(type_mix={"bearing": 0.5, "range": 0.1, "status": 0.1})))
    with pytest.raises(ConfigError, match="Clue type_mix probabilities must sum to 1.0"):
        validate_config(cfg)


def test_missing_initial_signal_info():
    """Initial signal missing all fields must raise ConfigError."""
    cfg = AppConfig(initial_signal=InitialSignalConfig(bearing_deg=None, coordinates=None, strength=None))
    with pytest.raises(ConfigError, match="Initial signal must provide at least one"):
        validate_config(cfg)


def test_start_inside_explicit_obstacle():
    """Start placed on an explicit obstacle must raise ConfigError."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            start=(2, 2),
            obstacles=ObstaclesConfig(mode="explicit", explicit=[(2, 2), (5, 5)]),
        )
    )
    with pytest.raises(ConfigError, match="Start cell .* is inside an explicit obstacle"):
        validate_config(cfg)


def test_charger_inside_obstacle():
    """Charger placed on an explicit obstacle must raise ConfigError."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            start=(1, 1),
            chargers=[(5, 5)],
            obstacles=ObstaclesConfig(mode="explicit", explicit=[(5, 5)]),
        )
    )
    with pytest.raises(ConfigError, match="Charger .* is placed inside an obstacle"):
        validate_config(cfg)


def test_inverted_agent_thresholds():
    """Agent thresholds violating track <= verify <= declare must raise ConfigError."""
    from walle.config import AgentConfig, AgentThresholds
    cfg = AppConfig(agent=AgentConfig(thresholds=AgentThresholds(track=0.8, verify=0.6, declare_location=0.9)))
    with pytest.raises(ConfigError, match="Agent thresholds must satisfy"):
        validate_config(cfg)
