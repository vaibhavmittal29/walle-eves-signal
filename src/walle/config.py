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
    mobility: Literal["static", "stationary", "random_walk", "diffusion"] = "stationary"
    diffusion_sigma: float = 0.5
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
    mode: Literal["configured", "generated"] = "configured"
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


def _validate_int(val: Any, name: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> None:
    if isinstance(val, bool) or not isinstance(val, int):
        raise ConfigError(f"{name} must be an int, got {type(val).__name__} ({val})")
    if min_val is not None and val < min_val:
        raise ConfigError(f"{name} must be >= {min_val}, got {val}")
    if max_val is not None and val > max_val:
        raise ConfigError(f"{name} must be <= {max_val}, got {val}")


def _validate_float(
    val: Any,
    name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    strict_min: bool = False,
    strict_max: bool = False,
) -> None:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ConfigError(f"{name} must be a float, got {type(val).__name__} ({val})")
    fval = float(val)
    if math.isnan(fval) or math.isinf(fval):
        raise ConfigError(f"Non-finite value detected for {name}: {val}")
    if min_val is not None:
        if strict_min and fval <= min_val:
            raise ConfigError(f"{name} must be > {min_val}, got {val}")
        elif not strict_min and fval < min_val:
            raise ConfigError(f"{name} must be >= {min_val}, got {val}")
    if max_val is not None:
        if strict_max and fval >= max_val:
            raise ConfigError(f"{name} must be < {max_val}, got {val}")
        elif not strict_max and fval > max_val:
            raise ConfigError(f"{name} must be <= {max_val}, got {val}")


def validate_config(cfg: AppConfig) -> None:
    """Validate full mission configuration, raising ConfigError on violation."""
    # 1. Grid
    _validate_int(cfg.mission.grid.width, "grid.width")
    _validate_int(cfg.mission.grid.height, "grid.height")
    w, h = cfg.mission.grid.width, cfg.mission.grid.height
    if w < 3 or h < 3:
        raise ConfigError(f"Grid dimensions must be at least 3x3, got {w}x{h}.")

    # 2. Mission Section
    _validate_int(cfg.mission.seed, "mission.seed")
    if not isinstance(cfg.mission.start, (tuple, list)) or len(cfg.mission.start) != 2:
        raise ConfigError("start must be a 2-tuple of (x, y) coordinates.")
    _validate_int(cfg.mission.start[0], "start.x")
    _validate_int(cfg.mission.start[1], "start.y")
    sx, sy = cfg.mission.start
    if not (0 <= sx < w and 0 <= sy < h):
        raise ConfigError(f"Start cell ({sx}, {sy}) is outside grid bounds {w}x{h}.")

    if not cfg.mission.chargers:
        raise ConfigError("At least one charger must be specified.")
    for idx, c in enumerate(cfg.mission.chargers):
        if not isinstance(c, (tuple, list)) or len(c) != 2:
            raise ConfigError(f"Charger #{idx} must be a 2-tuple of (x, y) coordinates.")
        _validate_int(c[0], f"chargers[{idx}].x")
        _validate_int(c[1], f"chargers[{idx}].y")
        if not (0 <= c[0] < w and 0 <= c[1] < h):
            raise ConfigError(f"Charger #{idx} ({c[0]}, {c[1]}) is outside grid bounds {w}x{h}.")

    # 3. Obstacles
    mode = cfg.mission.obstacles.mode
    if mode not in ("random", "explicit", "ascii"):
        raise ConfigError(f"Unknown obstacles mode '{mode}'. Choose 'random', 'explicit', or 'ascii'.")
    _validate_float(cfg.mission.obstacles.density, "obstacles.density", min_val=0.0, max_val=0.8, strict_max=True)

    if mode == "explicit":
        obs_set = set(cfg.mission.obstacles.explicit)
        for ox, oy in obs_set:
            _validate_int(ox, "obstacles.explicit.x", min_val=0, max_val=w - 1)
            _validate_int(oy, "obstacles.explicit.y", min_val=0, max_val=h - 1)
        if cfg.mission.start in obs_set:
            raise ConfigError(f"Start cell {cfg.mission.start} is inside an explicit obstacle.")
        for cx, cy in cfg.mission.chargers:
            if (cx, cy) in obs_set:
                raise ConfigError(f"Charger ({cx}, {cy}) is placed inside an obstacle.")
    elif mode == "ascii":
        lines = cfg.mission.obstacles.ascii
        if len(lines) != h:
            raise ConfigError(f"ASCII obstacles line count ({len(lines)}) must match grid height ({h}).")
        for y, line in enumerate(lines):
            if len(line) != w:
                raise ConfigError(f"ASCII obstacles line {y} width ({len(line)}) must match grid width ({w}).")
        if lines[cfg.mission.start[1]][cfg.mission.start[0]] == "#":
            raise ConfigError(f"Start cell {cfg.mission.start} is inside an obstacle wall.")

    # 4. EVE
    eve = cfg.mission.eve
    if eve.location != "random":
        if not isinstance(eve.location, (tuple, list)) or len(eve.location) != 2:
            raise ConfigError("eve.location must be 'random' or a 2-tuple (x, y).")
        _validate_int(eve.location[0], "eve.location.x", min_val=0, max_val=w - 1)
        _validate_int(eve.location[1], "eve.location.y", min_val=0, max_val=h - 1)
        if mode == "explicit" and tuple(eve.location) in obs_set:
            raise ConfigError(f"EVE location {eve.location} is inside an explicit obstacle.")
        if tuple(eve.location) == tuple(cfg.mission.start):
            raise ConfigError(f"EVE location {eve.location} cannot be identical to start cell.")
    if eve.status not in ("random", "active", "low_power", "damaged"):
        raise ConfigError(f"Unknown eve.status '{eve.status}'. Choose 'random', 'active', 'low_power', or 'damaged'.")
    if eve.mobility not in ("static", "stationary", "random_walk", "diffusion"):
        raise ConfigError(f"Unknown eve.mobility '{eve.mobility}'. Choose 'static', 'stationary', 'random_walk', or 'diffusion'.")
    _validate_float(eve.diffusion_sigma, "eve.diffusion_sigma", min_val=0.0, strict_min=True)
    if eve.min_distance_from_start > (w + h):
        raise ConfigError(
            f"eve.min_distance_from_start ({eve.min_distance_from_start}) exceeds max grid span ({w+h})."
        )

    # 5. Clues
    _validate_int(cfg.mission.clues.count, "clues.count", min_val=0)
    if cfg.mission.clues.placement not in ("random", "explicit"):
        raise ConfigError(f"Unknown clues.placement '{cfg.mission.clues.placement}'. Choose 'random' or 'explicit'.")
    mix = cfg.mission.clues.type_mix
    for k in ("bearing", "range", "status"):
        if k not in mix:
            raise ConfigError(f"Clue type_mix must contain '{k}'.")
        _validate_float(mix[k], f"clues.type_mix['{k}']", min_val=0.0, max_val=1.0)
    mix_sum = sum(mix.values())
    if abs(mix_sum - 1.0) > 1e-4:
        raise ConfigError(f"Clue type_mix probabilities must sum to 1.0, got {mix_sum} ({mix}).")
    if cfg.mission.clues.placement == "explicit":
        for idx, cl in enumerate(cfg.mission.clues.explicit):
            _validate_int(cl.get("x"), f"clues.explicit[{idx}].x", min_val=0, max_val=w - 1)
            _validate_int(cl.get("y"), f"clues.explicit[{idx}].y", min_val=0, max_val=h - 1)
            if cl.get("type") not in ("bearing", "range", "status"):
                raise ConfigError(f"clues.explicit[{idx}].type must be 'bearing', 'range', or 'status'.")

    # 6. Initial Signal
    sig = cfg.initial_signal
    if sig.mode not in ("configured", "generated", "none"):
        raise ConfigError(f"Unknown initial_signal mode '{sig.mode}'. Choose 'configured', 'generated', or 'none'.")
    if sig.mode == "configured" and sig.bearing_deg is None and sig.coordinates is None and sig.strength is None:
        raise ConfigError("Initial signal must provide at least one of bearing_deg, coordinates, or strength.")
    if sig.bearing_deg is not None:
        _validate_float(sig.bearing_deg, "initial_signal.bearing_deg")
        if not (0.0 <= sig.bearing_deg <= 360.0):
            raise ConfigError(f"Initial signal bearing_deg must be in [0.0, 360.0], got {sig.bearing_deg}.")
    if sig.coordinates is not None:
        if not isinstance(sig.coordinates, (tuple, list)) or len(sig.coordinates) != 2:
            raise ConfigError("initial_signal.coordinates must be a 2-tuple (x, y).")
        _validate_int(sig.coordinates[0], "initial_signal.coordinates.x", min_val=0, max_val=w - 1)
        _validate_int(sig.coordinates[1], "initial_signal.coordinates.y", min_val=0, max_val=h - 1)
        _validate_float(sig.coordinates_sigma, "initial_signal.coordinates_sigma", min_val=0.0, strict_min=True)
    if sig.strength is not None:
        _validate_float(sig.strength, "initial_signal.strength", min_val=0.0)
    _validate_int(sig.timestamp, "initial_signal.timestamp", min_val=0)

    # 7. Resources & Costs
    res = cfg.resources
    _validate_int(res.battery_capacity, "resources.battery_capacity")
    if res.battery_capacity <= 0:
        raise ConfigError(f"Battery capacity must be positive, got {res.battery_capacity}.")
    _validate_int(res.battery_initial, "resources.battery_initial")
    if res.battery_initial <= 0 or res.battery_initial > res.battery_capacity:
        raise ConfigError(
            f"Initial battery ({res.battery_initial}) must be in range [1, capacity ({res.battery_capacity})]."
        )
    _validate_int(res.time_budget, "resources.time_budget", min_val=1)

    _validate_float(res.costs.move.battery, "costs.move.battery", min_val=0.0)
    _validate_float(res.costs.move.time, "costs.move.time", min_val=0.0)
    _validate_float(res.costs.scan_signal.battery, "costs.scan_signal.battery", min_val=0.0)
    _validate_float(res.costs.scan_signal.time, "costs.scan_signal.time", min_val=0.0)
    _validate_float(res.costs.scan_area.battery_base, "costs.scan_area.battery_base", min_val=0.0)
    _validate_float(res.costs.scan_area.battery_per_radius, "costs.scan_area.battery_per_radius", min_val=0.0)
    _validate_float(res.costs.scan_area.time_base, "costs.scan_area.time_base", min_val=0.0)
    _validate_float(res.costs.scan_area.time_per_radius, "costs.scan_area.time_per_radius", min_val=0.0)
    _validate_int(res.costs.scan_area.max_radius, "costs.scan_area.max_radius", min_val=1, max_val=min(w, h))
    _validate_float(res.costs.recharge.battery_gain, "costs.recharge.battery_gain", min_val=0.0, strict_min=True)
    _validate_float(res.costs.recharge.time, "costs.recharge.time", min_val=0.0)

    # 8. Sensor
    sens = cfg.sensor
    _validate_float(sens.noise_scale, "sensor.noise_scale", min_val=0.0, strict_min=True)
    _validate_float(sens.strength_sigma, "sensor.strength_sigma", min_val=0.0, strict_min=True)
    _validate_float(sens.bearing_sigma_base_deg, "sensor.bearing_sigma_base_deg", min_val=0.0)
    _validate_float(sens.bearing_sigma_per_cell_deg, "sensor.bearing_sigma_per_cell_deg", min_val=0.0)
    _validate_float(sens.d0, "sensor.d0", min_val=0.0, strict_min=True)
    for st in ("active", "low_power", "damaged"):
        if st not in sens.amplitude:
            raise ConfigError(f"sensor.amplitude missing '{st}'.")
        _validate_float(sens.amplitude[st], f"sensor.amplitude['{st}']", min_val=0.0, strict_min=True)
        if st not in sens.dropout:
            raise ConfigError(f"sensor.dropout missing '{st}'.")
        _validate_float(sens.dropout[st], f"sensor.dropout['{st}']", min_val=0.0, max_val=1.0)

    _validate_int(sens.decoys.count, "sensor.decoys.count", min_val=0)
    _validate_float(sens.decoys.spoof_probability, "sensor.decoys.spoof_probability", min_val=0.0, max_val=1.0)

    _validate_float(sens.clue_noise.bearing_sigma_deg, "sensor.clue_noise.bearing_sigma_deg", min_val=0.0, strict_min=True)
    _validate_float(sens.clue_noise.range_sigma, "sensor.clue_noise.range_sigma", min_val=0.0, strict_min=True)
    _validate_float(sens.clue_noise.status_accuracy, "sensor.clue_noise.status_accuracy", min_val=0.0, max_val=1.0)
    _validate_float(sens.clue_noise.detect_probability, "sensor.clue_noise.detect_probability", min_val=0.0, max_val=1.0)
    _validate_float(sens.clue_noise.false_clue_probability, "sensor.clue_noise.false_clue_probability", min_val=0.0, max_val=1.0)

    # 9. Agent
    ag = cfg.agent
    if ag.type not in ("bayes_planner", "random", "greedy_bearing"):
        raise ConfigError(f"Unknown agent.type '{ag.type}'. Choose 'bayes_planner', 'random', or 'greedy_bearing'.")
    _validate_int(ag.seed, "agent.seed")
    _validate_float(ag.assumed_spoof_rate, "agent.assumed_spoof_rate", min_val=0.0, max_val=1.0)
    _validate_int(ag.mc_samples, "agent.mc_samples", min_val=5)
    _validate_int(ag.max_candidates, "agent.max_candidates", min_val=1)

    _validate_float(ag.safety.margin_fraction, "agent.safety.margin_fraction")
    if not (0.0 <= ag.safety.margin_fraction < 1.0):
        raise ConfigError(f"Agent safety margin_fraction must be in [0.0, 1.0), got {ag.safety.margin_fraction}.")
    _validate_int(ag.safety.margin_flat, "agent.safety.margin_flat")
    if ag.safety.margin_flat < 0:
        raise ConfigError(f"Agent safety margin_flat cannot be negative, got {ag.safety.margin_flat}.")

    _validate_float(ag.thresholds.track, "agent.thresholds.track", min_val=0.0, max_val=1.0, strict_min=True)
    _validate_float(ag.thresholds.verify, "agent.thresholds.verify", min_val=0.0, max_val=1.0, strict_min=True)
    _validate_float(ag.thresholds.declare_location, "agent.thresholds.declare_location", min_val=0.0, max_val=1.0, strict_min=True)
    _validate_float(ag.thresholds.declare_status, "agent.thresholds.declare_status", min_val=0.0, max_val=1.0, strict_min=True)

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
        mode=sig_data.get("mode", "configured"),
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
