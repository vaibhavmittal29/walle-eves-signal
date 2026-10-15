"""Tests verifying strict architectural separation between agent and hidden world state."""

import ast
from pathlib import Path
from walle.config import load_config
from walle.world import World


def test_public_info_contains_no_hidden_truth():
    """Verify that PublicMissionInfo contains zero hidden ground-truth attributes."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    pub = world.public_info()

    # Forbidden ground-truth attribute names
    forbidden_attrs = [
        "eve_location",
        "_eve_location",
        "eve_status",
        "_eve_status",
        "clues",
        "_clues",
        "decoys",
        "_decoys",
        "ground_truth",
        "_ground_truth",
        "TrueClue",
    ]

    for attr in forbidden_attrs:
        assert not hasattr(pub, attr), f"PublicMissionInfo leaks private attribute '{attr}'!"


def test_agent_modules_do_not_import_ground_truth():
    """Verify via AST parsing that agent-side modules never import GroundTruth or World internals."""
    src_dir = Path("src/walle")
    agent_modules = [
        src_dir / "agent.py",
        src_dir / "belief.py",
        src_dir / "planner.py",
        src_dir / "strategies.py",
        src_dir / "info_gain.py",
        src_dir / "baselines.py",
    ]

    for mod_path in agent_modules:
        if not mod_path.exists():
            continue
        with open(mod_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(mod_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "world" in node.module:
                    for alias in node.names:
                        assert alias.name not in (
                            "GroundTruth",
                            "TrueClue",
                            "World",
                        ), f"{mod_path.name} imports forbidden world entity {alias.name}"
            elif isinstance(node, ast.Attribute):
                assert node.attr not in (
                    "_eve_location",
                    "_eve_status",
                    "_clues",
                    "_decoys",
                ), f"{mod_path.name} accesses private world attribute {node.attr}"


def test_runtime_agent_receives_only_public_types():
    """Runtime check ensuring that everything passed into the agent is strictly PublicMissionInfo or Observation."""
    from walle.agent import BayesPlannerAgent
    from walle.environment import Environment
    from walle.observations import Observation, PublicMissionInfo

    cfg = load_config(Path("configs/mission_easy.yaml"))
    env = Environment(cfg)
    info, obs = env.reset()

    # Verify reset argument
    assert isinstance(info, PublicMissionInfo), f"Expected PublicMissionInfo, got {type(info)}"
    assert not hasattr(info, "_eve_location")
    assert not hasattr(info, "eve_location")
    assert not hasattr(info, "ground_truth")

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    # Step through simulation and inspect every input to the agent
    for _ in range(10):
        assert isinstance(obs, Observation), f"Expected Observation, got {type(obs)}"
        assert not hasattr(obs, "_eve_location")
        assert not hasattr(obs, "ground_truth")
        assert not hasattr(obs, "_world")

        action, _ = agent.act(obs)
        if obs.done:
            break
        obs = env.step(action)

