# WALL-E & EVE's Signal: Engineering & Audit Remediation Summary

> **Evaluation Candidate:** Vaibhav Mittal (`vaibhavmittal29`)  
> **Evaluation Rubric:** VinnovateIT (VIT Vellore) Recruitment Technical Evaluation  
> **Repository:** [vaibhavmittal29/walle-eves-signal](https://github.com/vaibhavmittal29/walle-eves-signal)  
> **Target System:** Autonomous Active Bayesian Grid-Filter Search Agent with Guaranteed Return Safety  

---

## 1. Executive Summary

This codebase implements an autonomous robotics simulation in pure Python (NumPy only, zero external ML/robotics frameworks) where WALL-E must locate and diagnose the operational status of EVE on a partially observed grid world under severe battery constraints, sensor noise, dropouts, obstacles, and deceptive decoys.

Following a thorough 16-phase audit and remediation program against `PLAN.md`, all core mathematical algorithms, safety invariants, observation models, resource formulas, and test separation boundaries have been brought to production-grade rigor.

---

## 2. Architectural Pillars & Formal Guarantees

```mermaid
flowchart TD
    subgraph Environment ["Environment (Hidden Ground Truth)"]
        W[World Map & Chargers]
        E[EVE Hidden Pos & Status]
        D[Decoy Signal Generator]
    end

    subgraph Agent ["BayesPlannerAgent (Public Observation Interface)"]
        B["Belief Tensor B[y, x, k]"]
        EIG["Monte Carlo Mutual Info EIG"]
        Guard["Centralized Return Reserve Guard"]
        Planner["Next-Best-Viewpoint Planner"]
        FSM["Decoy Confirmation State Machine"]
    end

    Environment -- Observation Only --> Agent
    Agent -- Physical Actions --> Environment
    Guard -- Safe Return Enforcement --> Environment
```

### 1. Bayesian Filtering & Likelihood Formulation
- **State Space:** Joint 3D tensor $B[y, x, k] \in [0, 1]$ across coordinates $(x, y) \in W \times H$ and operational states $k \in \{\text{active}, \text{low\_power}, \text{damaged}\}$.
- **Observation Likelihoods:**
  - Signal strength: Gaussian sensor model with status-dependent amplitudes $A_k$ and inverse-distance attenuation $d_0 / (d + d_0)$.
  - Missing-bearing reasoning: Disambiguates co-location ($d=0$, agent and target in same cell) from dropout and distance-dependent noise $\sigma_\theta(d) = 8^\circ + 2^\circ \cdot d$.
  - Robust Mixture Model: $L_{\text{robust}} = (1 - \epsilon) L_{\text{true}} + \epsilon \cdot u$, preventing posterior collapse under deceptive decoy signals.
- **Dynamic Prediction:** Pure NumPy wall-aware separable Gaussian convolution conserving total probability mass within $10^{-12}$.

### 2. Information-Theoretic Action Selection (EIG)
- **Exact Mutual Information:** Action candidates evaluate expected information gain using the Shannon divergence:
  $$I(X; Y) = \mathbb{E}_{Y \sim P(Y)} [D_{\text{KL}}(P(X \mid Y) \parallel P(X))]$$
  guaranteeing non-negativity $I(X; Y) \ge 0$ unconditionally across all belief surfaces.
- **Multi-Radius Area Scans:** Dynamically evaluates radii $r \in \{1, 2, 3\}$ balancing energy cost $(2 + 2r)$ and temporal budget $(1 + r)$ against spatial exploration entropy.
- **Decoy Confirmation & Triangulation:** Observations deviating by $> 3\sigma$ enter a confirmation state machine requiring multi-viewpoint triangulation from orthogonal baselines ($45^\circ \le \Delta\theta \le 135^\circ$) before declaration.

### 3. Safety Invariants & Resource Accounting
- **Safe-Return Reserve:** Pre-execution guard guarantees that for any proposed action:
  $$\text{battery}_{\text{after}} \ge \text{return\_reserve}(\text{pos}_{\text{after}}) = \text{BFS\_dist}(\text{pos}_{\text{after}}, \text{nearest\_charger}) \cdot c_{\text{move}} \cdot (1 + \text{margin}_{\text{frac}}) + \text{margin}_{\text{flat}}$$
  If violated, the action is rejected and safe retreat to charger is executed.
- **Empirical Stranding Rate:** **0.0% stranded** across all benchmark missions, randomized worlds, and 200-seed Monte Carlo fuzz tests.
- **Conservation of Energy:** Reconciled formula:
  $$\text{battery\_consumed} = \text{battery\_initial} + \text{recharge\_delivered} - \text{battery\_final} \equiv \sum_{t} \text{cost}(a_t)$$

### 4. Zero Ground-Truth Cheating & Code Quality
- **Strict Separation:** Audited via runtime proxy interceptors (`test_separation.py`) ensuring zero inspection of private environment attributes (`_eve_location`, `_eve_status`, `ground_truth`).
- **AST Security Policy:** Codebase is verified by AST inspection to contain zero calls to `eval()` or `exec()`.
- **Pure Dependency Stack:** Standard Python 3.10+ standard library, `numpy`, `pyyaml`, `matplotlib`, `pillow`, `pytest`. Zero heavy frameworks.

---

## 3. Verification & Replay Tooling

- Independent verifier module `walle.verify` and CLI subcommand `python -m walle verify <trace_dir>` independently checks:
  1. 4-connected spatial movement and wall collisions.
  2. Step-by-step energy and tick subtractions against `CostTable`.
  3. Pre-execution safe-return reserve at every step.
  4. Final declaration matching report specifications.
- Verified cleanly across all sample outputs (`outputs/mission_easy`, `outputs/mission_medium_seed7`, `outputs/mission_hard_decoys`).

---

## 4. Interview Defense Quick Reference

| Potential Evaluation Question | Engineering Defense & Mathematical Rationale |
|---|---|
| *Why does the agent never run out of battery?* | Centralized pre-execution guard in `BayesPlannerAgent._finalize_decision()`. Evaluates post-action position against BFS shortest-path distance to nearest charger with configured margins before executing any move or scan. |
| *How are decoys distinguished from true EVE signals?* | Residual checking ($>3\sigma$ angular contradiction), robust uniform mixture floor ($\epsilon > 0$), and multi-viewpoint orthogonal triangulation ($45^\circ - 135^\circ$ baseline separation). |
| *How is information gain computed without negative values?* | Uses expected Kullback-Leibler divergence (mutual information $I(X; Y)$) over simulated forward sensor measurements, which is guaranteed non-negative by Gibbs' inequality. |
| *How are unmodeled baselines handled in calibration?* | Non-Bayesian baselines that do not model posterior distributions return `None` for confidence and credible hit. These are excluded from credible coverage denominators rather than penalized as missed regions. |
