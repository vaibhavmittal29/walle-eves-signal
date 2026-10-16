"""Mission configuration loading, schema validation, and typed dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import yaml

from walle.observations import (
    CostTable,
    InitialSignal,
    MoveCost,
    RechargeCost,
    ScanAreaCost,
    ScanSignalCost,
    SensorPrior,
)


class ConfigError(ValueError):
    """Raised when mission configuration violates validation rules."""
    pass


@dataclass(frozen=True)
class GridConfig:
    width: int = 20
    height: int = 20


@dataclass(frozen=True)
class ObstaclesConfig:
    mode: Literal["random", "explicit", "ascii"] = "random"
    density: float = 0.10
    explicit: List[Tuple[int, int]] = field(default_factory=list)
    ascii: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class EveConfig:
    location: Union[Literal["random"], Tuple[int, int]] = "random"
    status: Union[Literal["random"], Literal["active", "low_power", "damaged"]] = "random"
    mobility: Literal["static", "random_walk"] = "static"
    min_distance_from_start: int = 8


@dataclass(frozen=True)
class CluesConfig:
    count: int = 5
    placement: Literal["random", "explicit"] = "random"
    explicit: List[Dict[str, Any]] = field(default_factory=list)
    type_mix: Dict[str, float] = field(
        default_factory=lambda: {"bearing": 0.5, "range": 0.3, "status": 0.2}
    )


@dataclass(frozen=True)
class MissionSectionConfig:
    name: str = "mission_default"
    seed: int = 7
    grid: GridConfig = field(default_factory=GridConfig)
    start: Tuple[int, int] = (2, 2)
    obstacles: ObstaclesConfig = field(default_factory=ObstaclesConfig)
    chargers: List[Tuple[int, int]] = field(default_factory=lambda: [(2, 2)])
    eve: EveConfig = field(default_factory=EveConfig)
    clues: CluesConfig = field(default_factory=CluesConfig)


@dataclass(frozen=True)
class InitialSignalConfig:
    bearing_deg: Optional[float] = 60.0
    coordinates: Optional[Tuple[int, int]] = None
    coordinates_sigma: float = 4.0
    strength: Optional[float] = 0.35
    timestamp: int = 0


@dataclass(frozen=True)
class CostsConfig:
    move: MoveCost = field(default_factory=MoveCost)
    scan_signal: ScanSignalCost = field(default_factory=ScanSignalCost)
    scan_area: ScanAreaCost = field(default_factory=ScanAreaCost)
    recharge: RechargeCost = field(default_factory=RechargeCost)

    def to_cost_table(self) -> CostTable:
        return CostTable(
            move=self.move,
            scan_signal=self.scan_signal,
            scan_area=self.scan_area,
            recharge=self.recharge,
        )


@dataclass(frozen=True)
class ResourcesConfig:
    battery_capacity: int = 100
    battery_initial: int = 100
    time_budget: int = 250
    costs: CostsConfig = field(default_factory=CostsConfig)


@dataclass(frozen=True)
class DecoyConfig:
    count: int = 0
    spoof_probability: float = 0.0


@dataclass(frozen=True)
class ClueNoiseConfig:
    bearing_sigma_deg: float = 15.0
    range_sigma: float = 2.0
    status_accuracy: float = 0.8
    detect_probability: float = 0.9
    false_clue_probability: float = 0.0


@dataclass(frozen=True)
class SensorConfig:
    noise_scale: float = 1.0
    strength_sigma: float = 0.05
    bearing_sigma_base_deg: float = 8.0
    bearing_sigma_per_cell_deg: float = 2.0
    d0: float = 6.0
    amplitude: Dict[str, float] = field(
        default_factory=lambda: {"active": 1.0, "low_power": 0.6, "damaged": 0.35}
    )
    dropout: Dict[str, float] = field(
        default_factory=lambda: {"active": 0.05, "low_power": 0.25, "damaged": 0.50}
    )
    decoys: DecoyConfig = field(default_factory=DecoyConfig)
    clue_noise: ClueNoiseConfig = field(default_factory=ClueNoiseConfig)

    def to_sensor_prior(self, assumed_spoof_rate: float = 0.0) -> SensorPrior:
        return SensorPrior(
            noise_scale=self.noise_scale,
            strength_sigma=self.strength_sigma,
            bearing_sigma_base_deg=self.bearing_sigma_base_deg,
            bearing_sigma_per_cell_deg=self.bearing_sigma_per_cell_deg,
            d0=self.d0,
            amplitude=dict(self.amplitude),
            dropout=dict(self.dropout),
            clue_bearing_sigma_deg=self.clue_noise.bearing_sigma_deg,
            clue_range_sigma=self.clue_noise.range_sigma,
            clue_status_accuracy=self.clue_noise.status_accuracy,
            clue_detect_probability=self.clue_noise.detect_probability,
            assumed_spoof_rate=assumed_spoof_rate,
        )


@dataclass(frozen=True)
class AgentThresholds:
    track: float = 0.50
    verify: float = 0.75
    declare_location: float = 0.90
    declare_status: float = 0.70


@dataclass(frozen=True)
class AgentSafety:
    margin_fraction: float = 0.10
    margin_flat: int = 3


@dataclass(frozen=True)
class AgentConfig:
    type: Literal["bayes_planner", "random", "greedy_bearing"] = "bayes_planner"
    seed: int = 123
    assumed_spoof_rate: float = 0.0
    mc_samples: int = 40
    max_candidates: int = 25
    thresholds: AgentThresholds = field(default_factory=AgentThresholds)
    safety: AgentSafety = field(default_factory=AgentSafety)


@dataclass(frozen=True)
class AppConfig:
    mission: MissionSectionConfig = field(default_factory=MissionSectionConfig)
    initial_signal: InitialSignalConfig = field(default_factory=InitialSignalConfig)
    resources: ResourcesConfig = field(default_factory=ResourcesConfig)
    sensor: SensorConfig = field(default_factory=SensorConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


def validate_config(cfg: AppConfig) -> None:
    """Validate full mission configuration, raising ConfigError on violation."""
    # 0. Non-finite value assertions
    for name, val in [
        ("obstacles.density", cfg.mission.obstacles.density),
        ("sensor.noise_scale", cfg.sensor.noise_scale),
        ("sensor.strength_sigma", cfg.sensor.strength_sigma),
        ("sensor.d0", cfg.sensor.d0),
        ("sensor.bearing_sigma_base_deg", cfg.sensor.bearing_sigma_base_deg),
        ("sensor.bearing_sigma_per_cell_deg", cfg.sensor.bearing_sigma_per_cell_deg),
        ("agent.assumed_spoof_rate", cfg.agent.assumed_spoof_rate),
        ("agent.safety.margin_fraction", cfg.agent.safety.margin_fraction),
        ("agent.thresholds.track", cfg.agent.thresholds.track),
        ("agent.thresholds.verify", cfg.agent.thresholds.verify),
        ("agent.thresholds.declare_location", cfg.agent.thresholds.declare_location),
        ("agent.thresholds.declare_status", cfg.agent.thresholds.declare_status),
    ]:
        if math.isnan(val) or math.isinf(val):
            raise ConfigError(f"Non-finite value detected for {name}: {val}")

    if cfg.initial_signal.bearing_deg is not None:
        if math.isnan(cfg.initial_signal.bearing_deg) or math.isinf(cfg.initial_signal.bearing_deg):
            raise ConfigError("Non-finite value for initial_signal.bearing_deg")
    if cfg.initial_signal.strength is not None:
        if math.isnan(cfg.initial_signal.strength) or math.isinf(cfg.initial_signal.strength):
            raise ConfigError("Non-finite value for initial_signal.strength")

    w, h = cfg.mission.grid.width, cfg.mission.grid.height
    if w < 3 or h < 3:
        raise ConfigError(f"Grid dimensions must be at least 3x3, got {w}x{h}.")

    if cfg.mission.eve.min_distance_from_start > (w + h):
        raise ConfigError(
            f"eve.min_distance_from_start ({cfg.mission.eve.min_distance_from_start}) exceeds max grid span ({w+h})."
        )

    sx, sy = cfg.mission.start
    if not (0 <= sx < w and 0 <= sy < h):
        raise ConfigError(f"Start cell ({sx}, {sy}) is outside grid bounds {w}x{h}.")

    if not cfg.mission.chargers:
        raise ConfigError("At least one charger must be specified.")

    for idx, (cx, cy) in enumerate(cfg.mission.chargers):
        if not (0 <= cx < w and 0 <= cy < h):
            raise ConfigError(f"Charger #{idx} ({cx}, {cy}) is outside grid bounds {w}x{h}.")

    # Obstacles mode validation
    mode = cfg.mission.obstacles.mode
    if mode not in ("random", "explicit", "ascii"):
        raise ConfigError(f"Unknown obstacles mode '{mode}'. Choose 'random', 'explicit', or 'ascii'.")

    if mode == "explicit":
        obs_set = set(cfg.mission.obstacles.explicit)
        if cfg.mission.start in obs_set:
            raise ConfigError(f"Start cell {cfg.mission.start} is inside an explicit obstacle.")
        for cx, cy in cfg.mission.chargers:
            if (cx, cy) in obs_set:
                raise ConfigError(f"Charger ({cx}, {cy}) is placed inside an obstacle.")
    elif mode == "random":
        dens = cfg.mission.obstacles.density
        if not (0.0 <= dens < 0.8):
            raise ConfigError(f"Obstacle density must be in [0.0, 0.8), got {dens}.")

    # Clues validation
    if cfg.mission.clues.count < 0:
        raise ConfigError(f"Clues count cannot be negative, got {cfg.mission.clues.count}.")

    mix = cfg.mission.clues.type_mix
    mix_sum = sum(mix.values())
    if abs(mix_sum - 1.0) > 1e-4:
        raise ConfigError(f"Clue type_mix probabilities must sum to 1.0, got {mix_sum} ({mix}).")
    for k in ("bearing", "range", "status"):
        if k not in mix or mix[k] < 0:
            raise ConfigError(f"Clue type_mix must contain non-negative '{k}'.")

    # Initial signal validation
    sig = cfg.initial_signal
    if sig.bearing_deg is None and sig.coordinates is None and sig.strength is None:
        raise ConfigError(
            "Initial signal must provide at least one of 'bearing_deg', 'coordinates', or 'strength'."
        )
    if sig.bearing_deg is not None and not (0.0 <= sig.bearing_deg <= 360.0):
        raise ConfigError(f"Initial signal bearing_deg must be in [0.0, 360.0], got {sig.bearing_deg}.")
    if sig.coordinates is not None:
        cx, cy = sig.coordinates
        if not (0 <= cx < w and 0 <= cy < h):
            raise ConfigError(f"Initial signal coordinates ({cx}, {cy}) outside grid bounds {w}x{h}.")
        if sig.coordinates_sigma <= 0:
            raise ConfigError("Initial signal coordinates_sigma must be positive.")

    # Resources validation
    res = cfg.resources
    if res.battery_capacity <= 0:
        raise ConfigError(f"Battery capacity must be positive, got {res.battery_capacity}.")
    if res.battery_initial <= 0 or res.battery_initial > res.battery_capacity:
        raise ConfigError(
            f"Initial battery ({res.battery_initial}) must be in range [1, capacity ({res.battery_capacity})]."
        )
    if res.time_budget <= 0:
        raise ConfigError(f"Time budget must be positive, got {res.time_budget}.")
    if res.costs.move.battery < 0 or res.costs.move.time < 0:
        raise ConfigError("Move costs cannot be negative.")
    if res.costs.recharge.battery_gain <= 0:
        raise ConfigError("Recharge battery gain must be positive.")

    # Sensor validation
    sens = cfg.sensor
    if sens.noise_scale <= 0:
        raise ConfigError("Sensor noise_scale must be positive.")
    if sens.strength_sigma <= 0:
        raise ConfigError("Sensor strength_sigma must be positive.")
    if sens.d0 <= 0:
        raise ConfigError("Sensor d0 range scale must be positive.")
    for st in ("active", "low_power", "damaged"):
        if st not in sens.amplitude or sens.amplitude[st] <= 0:
            raise ConfigError(f"Sensor amplitude for status '{st}' must be positive.")
        if st not in sens.dropout or not (0.0 <= sens.dropout[st] <= 1.0):
            raise ConfigError(f"Sensor dropout probability for '{st}' must be in [0.0, 1.0].")

    # Decoy validation
    if not (0.0 <= sens.decoys.spoof_probability <= 1.0):
        raise ConfigError("Decoy spoof_probability must be in [0.0, 1.0].")
    if not (0.0 <= sens.clue_noise.detect_probability <= 1.0):
        raise ConfigError("Clue detect_probability must be in [0.0, 1.0].")
    if not (0.0 <= sens.clue_noise.status_accuracy <= 1.0):
        raise ConfigError("Clue status_accuracy must be in [0.0, 1.0].")

    # Agent validation
    ag = cfg.agent
    if ag.mc_samples < 5:
        raise ConfigError(f"Agent mc_samples must be at least 5, got {ag.mc_samples}.")
    if ag.max_candidates < 1:
        raise ConfigError(f"Agent max_candidates must be at least 1, got {ag.max_candidates}.")
    if not (0.0 <= ag.assumed_spoof_rate <= 1.0):
        raise ConfigError(f"Agent assumed_spoof_rate must be in [0.0, 1.0], got {ag.assumed_spoof_rate}.")
    if not (0.0 <= ag.safety.margin_fraction < 1.0):
        raise ConfigError(f"Agent safety margin_fraction must be in [0.0, 1.0), got {ag.safety.margin_fraction}.")
    if ag.safety.margin_flat < 0:
        raise ConfigError(f"Agent safety margin_flat cannot be negative, got {ag.safety.margin_flat}.")
    if not (0 < ag.thresholds.track <= ag.thresholds.verify <= ag.thresholds.declare_location <= 1.0):
        raise ConfigError(
            f"Agent thresholds must satisfy 0 < track ({ag.thresholds.track}) "
            f"<= verify ({ag.thresholds.verify}) <= declare_location ({ag.thresholds.declare_location}) <= 1.0."
        )


def _to_tuple(val: Any) -> Any:
    if isinstance(val, list) and len(val) == 2:
        return (val[0], val[1])
    return val


def load_config(path: Union[str, Path]) -> AppConfig:
    """Load, parse, and validate YAML mission configuration from file."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Parse mission section
    m_data = data.get("mission", {})
    grid_data = m_data.get("grid", {})
    grid = GridConfig(
        width=int(grid_data.get("width", 20)),
        height=int(grid_data.get("height", 20)),
    )

    obs_data = m_data.get("obstacles", {})
    explicit_obs = [tuple(p) for p in obs_data.get("explicit", [])]
    obstacles = ObstaclesConfig(
        mode=obs_data.get("mode", "random"),
        density=float(obs_data.get("density", 0.10)),
        explicit=explicit_obs,
        ascii=obs_data.get("ascii", []),
    )

    eve_data = m_data.get("eve", {})
    eve_loc = eve_data.get("location", "random")
    if isinstance(eve_loc, list):
        eve_loc = (int(eve_loc[0]), int(eve_loc[1]))

    eve = EveConfig(
        location=eve_loc,
        status=eve_data.get("status", "random"),
        mobility=eve_data.get("mobility", "static"),
        min_distance_from_start=int(eve_data.get("min_distance_from_start", 8)),
    )

    clues_data = m_data.get("clues", {})
    clues = CluesConfig(
        count=int(clues_data.get("count", 5)),
        placement=clues_data.get("placement", "random"),
        explicit=clues_data.get("explicit", []),
        type_mix={k: float(v) for k, v in clues_data.get("type_mix", {"bearing": 0.5, "range": 0.3, "status": 0.2}).items()},
    )

    chargers = [tuple(c) for c in m_data.get("chargers", [(2, 2)])]
    start = tuple(m_data.get("start", (2, 2)))

    mission = MissionSectionConfig(
        name=str(m_data.get("name", "mission")),
        seed=int(m_data.get("seed", 7)),
        grid=grid,
        start=start,
        obstacles=obstacles,
        chargers=chargers,
        eve=eve,
        clues=clues,
    )

    # Parse initial signal
    sig_data = data.get("initial_signal", {})
    sig_coords = sig_data.get("coordinates")
    if isinstance(sig_coords, list):
        sig_coords = (int(sig_coords[0]), int(sig_coords[1]))

    initial_signal = InitialSignalConfig(
        bearing_deg=float(sig_data["bearing_deg"]) if sig_data.get("bearing_deg") is not None else None,
        coordinates=sig_coords,
        coordinates_sigma=float(sig_data.get("coordinates_sigma", 4.0)),
        strength=float(sig_data["strength"]) if sig_data.get("strength") is not None else None,
        timestamp=int(sig_data.get("timestamp", 0)),
    )

    # Parse resources
    res_data = data.get("resources", {})
    costs_data = res_data.get("costs", {})
    move_c = MoveCost(**costs_data.get("move", {}))
    scan_sig_c = ScanSignalCost(**costs_data.get("scan_signal", {}))
    scan_area_c = ScanAreaCost(**costs_data.get("scan_area", {}))
    recharge_c = RechargeCost(**costs_data.get("recharge", {}))
    costs = CostsConfig(
        move=move_c,
        scan_signal=scan_sig_c,
        scan_area=scan_area_c,
        recharge=recharge_c,
    )
    resources = ResourcesConfig(
        battery_capacity=int(res_data.get("battery_capacity", 100)),
        battery_initial=int(res_data.get("battery_initial", 100)),
        time_budget=int(res_data.get("time_budget", 250)),
        costs=costs,
    )

    # Parse sensor
    sens_data = data.get("sensor", {})
    decoy_data = sens_data.get("decoys", {})
    decoys = DecoyConfig(
        count=int(decoy_data.get("count", 0)),
        spoof_probability=float(decoy_data.get("spoof_probability", 0.0)),
    )
    clue_n_data = sens_data.get("clue_noise", {})
    clue_noise = ClueNoiseConfig(
        bearing_sigma_deg=float(clue_n_data.get("bearing_sigma_deg", 15.0)),
        range_sigma=float(clue_n_data.get("range_sigma", 2.0)),
        status_accuracy=float(clue_n_data.get("status_accuracy", 0.8)),
        detect_probability=float(clue_n_data.get("detect_probability", 0.9)),
        false_clue_probability=float(clue_n_data.get("false_clue_probability", 0.0)),
    )
    sensor = SensorConfig(
        noise_scale=float(sens_data.get("noise_scale", 1.0)),
        strength_sigma=float(sens_data.get("strength_sigma", 0.05)),
        bearing_sigma_base_deg=float(sens_data.get("bearing_sigma_base_deg", 8.0)),
        bearing_sigma_per_cell_deg=float(sens_data.get("bearing_sigma_per_cell_deg", 2.0)),
        d0=float(sens_data.get("d0", 6.0)),
        amplitude={k: float(v) for k, v in sens_data.get("amplitude", {"active": 1.0, "low_power": 0.6, "damaged": 0.35}).items()},
        dropout={k: float(v) for k, v in sens_data.get("dropout", {"active": 0.05, "low_power": 0.25, "damaged": 0.50}).items()},
        decoys=decoys,
        clue_noise=clue_noise,
    )

    # Parse agent
    agent_data = data.get("agent", {})
    thresh_data = agent_data.get("thresholds", {})
    thresholds = AgentThresholds(
        track=float(thresh_data.get("track", 0.50)),
        verify=float(thresh_data.get("verify", 0.75)),
        declare_location=float(thresh_data.get("declare_location", 0.90)),
        declare_status=float(thresh_data.get("declare_status", 0.70)),
    )
    safety_data = agent_data.get("safety", {})
    safety = AgentSafety(
        margin_fraction=float(safety_data.get("margin_fraction", 0.10)),
        margin_flat=int(safety_data.get("margin_flat", 3)),
    )
    agent = AgentConfig(
        type=agent_data.get("type", "bayes_planner"),
        seed=int(agent_data.get("seed", 123)),
        assumed_spoof_rate=float(agent_data.get("assumed_spoof_rate", 0.0)),
        mc_samples=int(agent_data.get("mc_samples", 40)),
        max_candidates=int(agent_data.get("max_candidates", 25)),
        thresholds=thresholds,
        safety=safety,
    )

    cfg = AppConfig(
        mission=mission,
        initial_signal=initial_signal,
        resources=resources,
        sensor=sensor,
        agent=agent,
    )

    validate_config(cfg)
    return cfg
