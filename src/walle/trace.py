"""Structured logging of action traces (JSONL and readable text) and belief snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from walle.agent import Decision
from walle.belief import Belief
from walle.observations import Observation


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.integer, np.int64, np.int32)):
        return int(o)
    if isinstance(o, (np.floating, np.float64, np.float32)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {type(o)} is not JSON serializable")


class TraceLogger:
    """Manages structured JSONL, human-readable text traces, and belief tensor snapshots."""

    def __init__(self, out_dir: Union[str, Path]):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_path = self.out_dir / "trace.jsonl"
        self.txt_path = self.out_dir / "trace.txt"
        self.npz_path = self.out_dir / "belief_frames.npz"

        # Clear existing logs
        if self.jsonl_path.exists():
            self.jsonl_path.unlink()
        if self.txt_path.exists():
            self.txt_path.unlink()

        self._jsonl_file = open(self.jsonl_path, "w", encoding="utf-8")
        self._txt_file = open(self.txt_path, "w", encoding="utf-8")

        self._belief_frames: Dict[str, np.ndarray] = {}
        self._frame_steps: List[int] = []

    def log_step(
        self,
        step: int,
        tick: int,
        strategy: str,
        strategy_change: Optional[Dict[str, Any]],
        state_before: Dict[str, Any],
        decision: Decision,
        observation: Observation,
        belief: Belief,
        is_suspicious: bool = False,
    ) -> None:
        """Record a single step into JSONL, human text log, and periodic array frame."""
        # 1. Build observation representation
        obs_sig: Optional[Dict[str, Any]] = None
        if observation.signal is not None:
            obs_sig = {
                "strength": (
                    round(observation.signal.strength, 4)
                    if observation.signal.strength is not None
                    else None
                ),
                "bearing_deg": (
                    round(observation.signal.bearing_deg, 2)
                    if observation.signal.bearing_deg is not None
                    else None
                ),
                "dropout": observation.signal.dropout,
                "suspicious": is_suspicious,
            }

        obs_clues = [
            {
                "clue_id": c.clue_id,
                "position": [c.position[0], c.position[1]],
                "type": c.type,
                "value": (
                    round(float(c.value), 2)
                    if isinstance(c.value, (int, float, np.floating))
                    else str(c.value)
                ),
            }
            for c in observation.clues
        ]

        obs_dict = {
            "pos": [observation.position[0], observation.position[1]],
            "battery": observation.battery,
            "signal": obs_sig,
            "clues": obs_clues,
            "bumped": observation.bumped,
        }

        # 2. Build decision representation
        top_cands = [
            {
                "goal": cs.goal,
                "eig_bits": cs.eig_bits,
                "cost": cs.cost,
                "utility": cs.utility,
                "safe": cs.safe,
            }
            for cs in decision.top_candidates
        ]

        dec_dict = {
            "action": decision.action.type.value,
            "plan": decision.plan,
            "top_candidates": top_cands,
            "reasoning": decision.reasoning,
        }

        # 3. Build belief snapshot
        map_x, map_y = belief.map_estimate()
        loc_marg = belief.location_marginal()
        belief_dict = {
            "map": [map_x, map_y],
            "map_prob": round(float(loc_marg[map_y, map_x]), 4),
            "entropy_bits": round(belief.entropy(), 3),
            "info_gain_bits": round(belief.last_kl_divergence, 3),
            "location_confidence": round(belief.mass_within((map_x, map_y), radius=1.5), 3),
            "status_probs": {st: round(p, 4) for st, p in belief.status_marginal().items()},
        }

        # 4. JSONL entry
        record = {
            "step": step,
            "tick": tick,
            "strategy": strategy,
            "strategy_change": strategy_change,
            "state_before": state_before,
            "decision": dec_dict,
            "observation": obs_dict,
            "belief_after": belief_dict,
        }
        self._jsonl_file.write(json.dumps(record, default=_json_default) + "\n")
        self._jsonl_file.flush()

        # 5. Readable text entry
        if strategy_change:
            self._txt_file.write(
                f"[EVENT | tick {tick:03d}] Strategy changed from {strategy_change['from']} "
                f"to {strategy_change['to']}: {strategy_change['trigger']}\n"
            )

        decoy_tag = " [SUSPECTED DECOY]" if is_suspicious else ""
        sig_txt = (
            f"STR={obs_sig['strength']:.3f} BRG={obs_sig['bearing_deg']:.1f}°{decoy_tag}"
            if obs_sig and obs_sig["strength"] is not None and obs_sig["bearing_deg"] is not None
            else ("DROPOUT" if obs_sig and obs_sig["dropout"] else "None")
        )
        clue_txt = f"{len(obs_clues)} found" if obs_clues else "None"

        txt_line = (
            f"[step {step:03d} | tick {tick:03d} | {strategy:<7}] "
            f"POS={state_before['pos']} BAT={state_before['battery']:03d} RES={state_before['reserve']:02d} -> "
            f"ACTION={dec_dict['action']}\n"
            f"       REASON: {dec_dict['reasoning']}\n"
            f"       OBS:    POS={obs_dict['pos']} BAT={obs_dict['battery']:03d} BUMP={obs_dict['bumped']} "
            f"SIG=[{sig_txt}] CLUES=[{clue_txt}]\n"
            f"       BELIEF: MAP=({map_x},{map_y}) P={belief_dict['map_prob']:.4f} "
            f"ENTROPY={belief_dict['entropy_bits']:.2f}b CONF={belief_dict['location_confidence']:.2f} "
            f"STATUS={belief_dict['status_probs']}\n"
        )
        self._txt_file.write(txt_line)
        self._txt_file.flush()

        # 6. Save belief frame every 2 steps or on final declaration
        if step % 2 == 0 or observation.done:
            self._belief_frames[f"frame_{step}"] = loc_marg.copy()
            self._frame_steps.append(step)

    def close(self) -> None:
        """Close log files and write belief_frames.npz."""
        if not self._jsonl_file.closed:
            self._jsonl_file.close()
        if not self._txt_file.closed:
            self._txt_file.close()

        # Save compressed belief frames
        if self._belief_frames:
            self._belief_frames["steps"] = np.array(self._frame_steps, dtype=np.int32)
            np.savez_compressed(self.npz_path, **self._belief_frames)
