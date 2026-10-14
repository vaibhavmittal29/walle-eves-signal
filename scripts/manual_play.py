"""Interactive terminal player for testing the WALL-E simulated environment."""

import argparse
import sys
from pathlib import Path

from walle.actions import Action, ActionType
from walle.config import load_config
from walle.environment import Environment


def manual_play(config_path: str) -> None:
    cfg = load_config(config_path)
    env = Environment(cfg)
    info, obs = env.reset()

    print("=" * 60)
    print(f"WALL-E Environment Manual Play - Mission: {cfg.mission.name}")
    print(f"Grid: {info.width}x{info.height}, Battery: {obs.battery}, Time: {obs.time_left}")
    print(f"Start pos: {obs.position}, Chargers: {info.chargers}")
    print("Commands:")
    print("  w, a, s, d        : Move North / West / South / East")
    print("  sig               : SCAN_SIGNAL")
    print("  area [1|2|3]      : SCAN_AREA with given radius (default 1)")
    print("  charge            : RECHARGE (on charger)")
    print("  dec x y status    : DECLARE (e.g. 'dec 4 12 active')")
    print("  q                 : Quit")
    print("=" * 60)

    while not obs.done:
        print(f"\n[Step {obs.step}] Pos={obs.position} | Battery={obs.battery} | TimeLeft={obs.time_left} | OnCharger={obs.on_charger}")
        if obs.signal:
            print(f"  -> Signal: strength={obs.signal.strength:.4f}" if obs.signal.strength is not None else "  -> Signal: [DROPOUT]")
            if obs.signal.bearing_deg is not None:
                print(f"     Bearing={obs.signal.bearing_deg:.1f} deg")
        if obs.clues:
            for clue in obs.clues:
                print(f"  -> Clue #{clue.clue_id} at {clue.position}: {clue.type}={clue.value}")

        try:
            cmd = input("Action > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue
        if cmd == "q":
            print("Quitting manual play.")
            break

        parts = cmd.split()
        op = parts[0]

        if op == "w":
            action = Action(type=ActionType.MOVE_N)
        elif op == "s":
            action = Action(type=ActionType.MOVE_S)
        elif op == "a":
            action = Action(type=ActionType.MOVE_W)
        elif op == "d":
            action = Action(type=ActionType.MOVE_E)
        elif op == "sig":
            action = Action(type=ActionType.SCAN_SIGNAL)
        elif op == "area":
            r = int(parts[1]) if len(parts) > 1 else 1
            action = Action(type=ActionType.SCAN_AREA, radius=r)
        elif op == "charge":
            action = Action(type=ActionType.RECHARGE)
        elif op == "dec":
            if len(parts) < 4:
                print("Usage: dec <x> <y> <status>")
                continue
            x, y, st = int(parts[1]), int(parts[2]), parts[3]
            action = Action(type=ActionType.DECLARE, declare_x=x, declare_y=y, declare_status=st)
        else:
            print(f"Unknown command '{cmd}'.")
            continue

        obs = env.step(action)
        if obs.bumped:
            print("  [!] Bumped into a wall / obstacle!")
        if not obs.action_succeeded:
            print("  [!] Action failed!")

    print(f"\nMission Ended. Done={obs.done}, Reason={obs.done_reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual terminal play")
    parser.add_argument("--config", default="configs/mission_medium.yaml", help="Path to YAML config")
    args = parser.parse_args()
    manual_play(args.config)
