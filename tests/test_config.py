"""Unit tests for mission configuration loading and validation rules."""

from pathlib import Path
import pytest
import yaml

from walle.config import (
    AgentConfig,
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


def test_non_finite_values_raise_config_error():
    """Non-finite float values (NaN, Inf) must raise ConfigError."""
    import math
    from walle.config import AgentConfig
    cfg = AppConfig(agent=AgentConfig(assumed_spoof_rate=float("nan")))
    with pytest.raises(ConfigError, match="Non-finite value detected"):
        validate_config(cfg)

    cfg_inf = AppConfig(agent=AgentConfig(assumed_spoof_rate=float("inf")))
    with pytest.raises(ConfigError, match="Non-finite value detected"):
        validate_config(cfg_inf)


def test_cross_field_eve_distance_exceeds_bounds():
    """eve.min_distance_from_start exceeding grid span must raise ConfigError."""
    from walle.config import EveConfig
    cfg = AppConfig(mission=MissionSectionConfig(eve=EveConfig(min_distance_from_start=100)))
    with pytest.raises(ConfigError, match="exceeds max grid span"):
        validate_config(cfg)


def test_invalid_bearing_range():
    """Initial signal bearing outside [0, 360] must raise ConfigError."""
    cfg = AppConfig(initial_signal=InitialSignalConfig(bearing_deg=450.0))
    with pytest.raises(ConfigError, match="Initial signal bearing_deg must be in"):
        validate_config(cfg)


def test_invalid_safety_margins():
    """Safety margin fraction >= 1.0 or flat margin < 0 must raise ConfigError."""
    from walle.config import AgentConfig, AgentSafety
    cfg = AppConfig(agent=AgentConfig(safety=AgentSafety(margin_fraction=1.2)))
    with pytest.raises(ConfigError, match="Agent safety margin_fraction"):
        validate_config(cfg)

    cfg_neg = AppConfig(agent=AgentConfig(safety=AgentSafety(margin_flat=-1)))
    with pytest.raises(ConfigError, match="Agent safety margin_flat cannot be negative"):
        validate_config(cfg_neg)


@pytest.mark.parametrize(
    "bad_cfg,err_match",
    [
        (AppConfig(mission=MissionSectionConfig(grid=GridConfig(width=True))), "must be an int"),
        (AppConfig(mission=MissionSectionConfig(grid=GridConfig(height=False))), "must be an int"),
        (AppConfig(mission=MissionSectionConfig(seed=True)), "must be an int"),
        (AppConfig(mission=MissionSectionConfig(start=(True, 2))), "must be an int"),
        (AppConfig(mission=MissionSectionConfig(obstacles=ObstaclesConfig(density=True))), "must be a float"),
        (AppConfig(resources=ResourcesConfig(battery_capacity=True)), "must be an int"),
        (AppConfig(agent=AgentConfig(mc_samples=False)), "must be an int"),
    ],
)
def test_bool_rejected_for_numeric_fields(bad_cfg, err_match):
    """Boolean values passed where numbers are expected must be rejected."""
    with pytest.raises(ConfigError, match=err_match):
        validate_config(bad_cfg)


def test_initial_signal_mode_semantics():
    """Initial signal mode supports 'configured' and 'generated'."""
    # generated mode with all None fields is valid
    cfg_gen = AppConfig(initial_signal=InitialSignalConfig(mode="generated", bearing_deg=None, coordinates=None, strength=None))
    validate_config(cfg_gen)

    # invalid mode raises error
    cfg_bad_mode = AppConfig(initial_signal=InitialSignalConfig(mode="unsupported_mode"))
    with pytest.raises(ConfigError, match="Unknown initial_signal mode"):
        validate_config(cfg_bad_mode)


def test_scan_area_cost_and_radius_bounds():
    """ScanAreaCost max_radius must be in [1, min(w, h)] and costs non-negative."""
    from walle.observations import ScanAreaCost
    from walle.config import CostsConfig
    # max_radius < 1
    cfg_low = AppConfig(resources=ResourcesConfig(costs=CostsConfig(scan_area=ScanAreaCost(max_radius=0))))
    with pytest.raises(ConfigError, match="max_radius"):
        validate_config(cfg_low)

    # max_radius > min(w, h)
    cfg_high = AppConfig(resources=ResourcesConfig(costs=CostsConfig(scan_area=ScanAreaCost(max_radius=50))))
    with pytest.raises(ConfigError, match="max_radius"):
        validate_config(cfg_high)


def test_run_mission_validates_appconfig_directly():
    """Calling run_mission with an invalid AppConfig raises ConfigError directly."""
    from walle.runner import run_mission
    bad_cfg = AppConfig(resources=ResourcesConfig(battery_capacity=-10))
    with pytest.raises(ConfigError, match="Battery capacity must be positive"):
        run_mission(bad_cfg)

