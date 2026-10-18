"""Script to generate INTERVIEW_PREP.pdf and DEMO_GUIDE.pdf for VinnovateIT interview preparation."""

from __future__ import annotations

import os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, letter[1] - 25, getattr(self, "doc_title", "WALL-E Interview Guide"))
            self.drawRightString(letter[0] - 36, letter[1] - 25, "VinnovateIT AI/ML Subdomain")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, letter[1] - 28, letter[0] - 36, letter[1] - 28)

        # Running footer (all pages)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 20, page_str)
        self.drawString(36, 20, "Confidential - Candidate: Vaibhav Mittal (First-Year CSE, VIT Vellore)")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 28, letter[0] - 36, 28)

        self.restoreState()


def get_styles():
    """Build comfortable, readable typography styles for phone & print."""
    base = getSampleStyleSheet()

    c_dark = colors.HexColor("#0f172a")
    c_blue = colors.HexColor("#1e3a8a")
    c_sub = colors.HexColor("#334155")

    styles = {
        "DocTitle": ParagraphStyle(
            "DocTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=c_blue,
            spaceAfter=6,
        ),
        "DocSubtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=c_sub,
            spaceAfter=14,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=c_blue,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0f766e"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "H3": ParagraphStyle(
            "H3",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=c_dark,
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=c_dark,
            spaceAfter=5,
        ),
        "BodyBold": ParagraphStyle(
            "BodyBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=c_dark,
            spaceAfter=4,
        ),
        "Bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=c_dark,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=3,
        ),
        "Callout": ParagraphStyle(
            "Callout",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
        ),
        "Code": ParagraphStyle(
            "Code",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#0f172a"),
        ),
        "TableText": ParagraphStyle(
            "TableText",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=c_dark,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.white,
        ),
        "SpeechBox": ParagraphStyle(
            "SpeechBox",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#0369a1"),
        ),
    }
    return styles


def make_callout(text: str, style: ParagraphStyle, bg="#f8fafc", border="#38bdf8") -> Table:
    """Helper to wrap important notes in an attractive visual callout box."""
    p = Paragraph(text, style)
    t = Table([[p]], colWidths=[letter[0] - 72])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(border)),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return t


def build_interview_prep_pdf(output_path: str = "INTERVIEW_PREP.pdf"):
    """Generate the complete 11-section INTERVIEW_PREP.pdf."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    doc.canvasmaker = NumberedCanvas
    styles = get_styles()
    story = []

    # Title & Header
    story.append(Paragraph("WALL-E & EVE's Signal: Interview Master Guide", styles["DocTitle"]))
    story.append(Paragraph(
        "<b>Role:</b> First-Year CSE Fresher | <b>Club:</b> VinnovateIT (AI/ML Subdomain) | <b>Duration:</b> 10 Minutes<br/>"
        "<i>Comprehensive technical preparation, spoken pitch scripts, line-by-line code walk, and 25 Q&amp;As.</i>",
        styles["DocSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # SECTION 1: The Project in 60 Seconds
    story.append(Paragraph("1. The Project in 60 Seconds", styles["H1"]))
    story.append(Paragraph(
        "<b>What is this project?</b> It is an autonomous AI robot simulation built in pure Python. The robot, WALL-E, is placed in an unknown, obstacle-filled 2D grid world. Somewhere on this grid is EVE, who is emitting faint, noisy radio signals.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>The Challenge:</b> WALL-E has a limited battery (100 units). The sensors are noisy (bearing angles are off by up to 20 degrees, signal strength fluctuates, signals randomly drop out), and deceptive 'decoy' beacons try to fool him. If WALL-E runs out of battery before returning to a charger, he gets permanently stranded.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "<b>How it solves it:</b> Instead of guessing, WALL-E uses <b>Active Bayesian Grid Filtering</b>. He maintains a 3D probability map over every possible cell and every possible status (active, low power, damaged). At every single step, he calculates <b>Expected Information Gain (EIG)</b> to choose the next best viewpoint, while a <b>Centralized Safe-Return Reserve Guard</b> guarantees he always has enough battery to reach the nearest charging station.",
        styles["Body"],
    ))
    story.append(make_callout(
        "<b>Real-Life Analogy:</b> Imagine playing 'Hot and Cold' in a pitch-black warehouse with walls. You have a noisy walkie-talkie that beeps louder when you get closer and points a faint arrow. Every step drains your phone battery, but there are power outlets on the walls. You don't just blindly run toward the beeps; you mathematically track where the sound is most likely coming from on a notepad, while always keeping enough battery to walk back to the nearest outlet.",
        styles["Callout"],
        bg="#eff6ff",
        border="#3b82f6",
    ))
    story.append(Spacer(1, 8))

    # SECTION 2: Pitches You Can Say Aloud
    story.append(Paragraph("2. Spoken Pitches (Natural First-Year Student Voice)", styles["H1"]))
    story.append(Paragraph("<b>The 30-Second Elevator Pitch:</b>", styles["H2"]))
    story.append(make_callout(
        '"Hi! I built an autonomous Bayesian search agent called WALL-E that locates and diagnoses a lost robot, EVE, in a partially observed, obstacle-filled world. What makes it special is that it solves two hard problems together: it handles noisy, deceptive sensor signals using mathematical probability updates, and it strictly guarantees zero battery stranding using dynamic shortest-path return reserves. In 100 benchmark tests, it achieved a 98% search success rate while baselines struggled below 10%."',
        styles["SpeechBox"],
        bg="#f0fdf4",
        border="#22c55e",
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>The 2-Minute Deep Pitch:</b>", styles["H2"]))
    story.append(make_callout(
        '"Good morning! As a first-year student, I wanted to understand how real-world autonomous robots make decisions under extreme uncertainty without needing giant neural networks. So I implemented WALL-E &amp; EVE\'s Signal in pure Python and NumPy.<br/><br/>'
        'The scenario is simple: WALL-E is in a 20x20 maze with battery limits. EVE is hidden somewhere, and her status could be active, low power, or damaged. When WALL-E scans, he gets noisy distance and bearing readings, occasional dropouts, and even spoofed decoy signals.<br/><br/>'
        'To solve this, I built three core systems:<br/>'
        'First, a <b>Bayesian Grid Filter</b> that maintains a joint probability distribution over 1,200 possible states. Every sensor reading updates this belief using Bayes\' Theorem.<br/>'
        'Second, an <b>Active Planner</b> using Mutual Information. Instead of wandering randomly, WALL-E evaluates candidate viewpoints and moves where he expects to gain the most information.<br/>'
        'Third, a <b>Safe-Return Invariant Guard</b> based on Breadth-First Search. Before executing any move or scan, the planner calculates the exact battery needed to reach the nearest charger with safety margins. If an action would strand him, it is automatically blocked.<br/><br/>'
        'Across 100 randomized test worlds, WALL-E localized EVE with an average error of just 0.3 cells and maintained a 0% stranding rate. I also built a trace replay verifier and full visual analytics pipeline."',
        styles["SpeechBox"],
        bg="#f8fafc",
        border="#0284c7",
    ))
    story.append(Spacer(1, 8))

    # SECTION 3: Step-by-Step System Flow & Diagram
    story.append(Paragraph("3. How It Works Step by Step (System Architecture)", styles["H1"]))
    story.append(Paragraph(
        "Here is the exact lifecycle of a simulation step, from input to output:",
        styles["Body"],
    ))

    flow_text = (
        "+-----------------------------------------------------------------------------------------+\n"
        "|  1. CONFIG & WORLD SETUP                                                                |\n"
        "|     YAML loaded -> 20x20 grid, walls, chargers, EVE hidden location & status            |\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "                                          |\n"
        "                                          v\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "|  2. OBSERVATION GENERATION (Environment)                                                |\n"
        "|     Sensors compute: Signal strength (1/d), Bearing angle (+noise), Dropouts, Clues     |\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "                                          |\n"
        "                                          v\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "|  3. BAYESIAN BELIEF UPDATE (Belief Tensor B[y, x, k])                                    |\n"
        "|     Posterior = (Prior * Likelihood) / Evidence  -> Normalized over all free cells      |\n"
        "|     Calculates: Spatial Entropy (bits), MAP Estimate, 90% Highest-Density Region        |\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "                                          |\n"
        "                                          v\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "|  4. DECISION & ACTIVE PLANNING (Planner & Agent)                                        |\n"
        "|     - Generate candidate viewpoints (move steps, signal scans, area scans r=1,2,3)      |\n"
        "|     - Score each candidate: Utility = EIG(action) / Resource_Cost                       |\n"
        "|     - PRE-EXECUTION SAFETY GUARD: battery_after >= return_reserve(pos_after)           |\n"
        "|       * If safe: pick highest utility candidate                                         |\n"
        "|       * If unsafe: force retreat to nearest charging station                            |\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "                                          |\n"
        "                                          v\n"
        "+-----------------------------------------------------------------------------------------+\n"
        "|  5. VERIFICATION & ARTIFACT PIPELINE                                                    |\n"
        "|     - trace.jsonl step telemetry  -> walle verify audits energy & physics               |\n"
        "|     - report.md audit document    -> run.gif, summary.png, metrics_dashboard.png        |\n"
        "+-----------------------------------------------------------------------------------------+"
    )
    story.append(make_callout(flow_text.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["Code"], bg="#0f172a", border="#334155"))
    story.append(Spacer(1, 8))

    # SECTION 4: File-by-File Guide
    story.append(Paragraph("4. File-by-File Guide", styles["H1"]))
    story.append(Paragraph("What every file does in 1 to 2 lines, so you never get lost if asked about project structure:", styles["Body"]))

    files_data = [
        ["File / Folder", "Exact Responsibility in Codebase"],
        ["src/walle/agent.py", "Agent state machine (EXPLORE->TRACK->VERIFY->DECLARE), clue tracking, and decision safety wrapper."],
        ["src/walle/belief.py", "3D Bayesian grid tensor B[y,x,k], likelihood multiplication, entropy calculation, and 90% credible regions."],
        ["src/walle/planner.py", "Candidate viewpoint generation, Monte Carlo Expected Information Gain (EIG), and return reserve calculation."],
        ["src/walle/signal_model.py", "Physical sensor model: inverse distance signal decay, angular noise, dropouts, and robust decoy mixture likelihood."],
        ["src/walle/world.py", "Grid world generator: builds connected obstacle maps, places chargers, and hides EVE and clues."],
        ["src/walle/environment.py", "Simulation loop: executes agent moves, checks wall bumps, deducts battery, and delivers sensor observations."],
        ["src/walle/runner.py", "Mission runner: loads YAML, loops steps, enforces timeouts, logs telemetry, and compiles final metrics."],
        ["src/walle/viz.py", "Visualization engine: renders summary panels, 2D paths, 3D space-time plots, belief heatmaps, and animated GIFs."],
        ["src/walle/verify.py", "Independent trace verifier (CLI: walle verify) that replays mission logs to verify physics and energy conservation."],
        ["src/walle/benchmark.py", "Generalization benchmark harness: runs 100 missions across 3 architectures, writes CSVs, and plots CDF/reliability charts."],
        ["src/walle/config.py", "Strict dataclass schemas: validates all YAML parameters, rejects negative costs, and prevents bool-as-int bugs."],
        ["src/walle/observations.py", "Data classes defining what the agent perceives (position, battery, signal reading, clues, status)."],
        ["src/walle/actions.py", "Data classes defining legal agent action types (MOVE_N/S/E/W, SCAN_SIGNAL, SCAN_AREA, RECHARGE, DECLARE)."],
        ["src/walle/baselines.py", "Comparison baseline agents (RandomAgent and GreedyBearingAgent) to benchmark against our BayesPlanner."],
        ["src/walle/geometry.py", "Pure math helpers: Euclidean distance, angle wrapping (-180 to +180), and grid adjacency."],
        ["scripts/calibration_study.py", "Evaluates statistical calibration across 200 seeds; outputs calibration.md and reliability diagram."],
        ["scripts/ablation_decoys.py", "50-seed paired experiment showing the robust agent (+30% success) vs naive agent under decoys."],
        ["scripts/manual_play.py", "Interactive terminal game allowing a human to play as WALL-E using w/a/s/d keys."],
    ]

    t_files = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(files_data)], colWidths=[140, letter[0] - 72 - 140])
    t_files.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_files)
    story.append(Spacer(1, 8))

    # SECTION 5: Tech Stack
    story.append(Paragraph("5. Tech Stack: Tools, Libraries & Alternatives", styles["H1"]))
    story.append(Paragraph("Know what each tool does, why we chose it, and one simple alternative:", styles["Body"]))

    stack_data = [
        ["Tool / Library", "What It Is", "Why We Used It Here", "One Alternative"],
        ["Python 3.10+", "Programming language", "Readable, standard in AI/ML, rich built-in libraries (dataclasses, typing).", "C++ or Julia"],
        ["NumPy", "Numerical tensor library", "Vectorized 3D array math for exact Bayesian updates; fast pure-Python convolution.", "PyTorch or SciPy"],
        ["Matplotlib", "Plotting & chart library", "Generates publication-quality 6-panel summary plots, CDF curves, and heatmaps.", "Seaborn or Plotly"],
        ["Pillow (PIL)", "Image manipulation", "Stitches per-step visualization frames into a smooth animated GIF (run.gif).", "OpenCV"],
        ["PyYAML", "Config parser", "Human-readable mission configuration files (grid size, battery, noise).", "JSON or TOML"],
        ["Pytest", "Testing framework", "Automated unit tests, 200-seed fuzz testing, and AST separation checking.", "Unittest"],
    ]

    t_stack = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(stack_data)], colWidths=[90, 100, letter[0] - 72 - 280, 90])
    t_stack.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_stack)
    story.append(Spacer(1, 8))

    # SECTION 6: Beginner Glossary
    story.append(Paragraph("6. Beginner Glossary of Core Technical Terms", styles["H1"]))
    story.append(Paragraph("Clear, simple definitions with real-life analogies:", styles["Body"]))

    glossary = [
        ("Prior Probability", "Your belief before seeing any new evidence.", "Before rolling a die, you assume every face has a 1/6 chance. That is your prior."),
        ("Likelihood", "How probable an observation is, assuming a specific hypothesis is true.", "If it is raining outside, seeing wet footprints is very likely; if sunny, wet footprints are unlikely."),
        ("Posterior Probability", "Your updated belief after combining the prior with the new observation.", "Seeing wet footprints shifts your belief that it rained from 10% to 90%."),
        ("Bayes' Theorem", "The mathematical formula: Posterior = (Prior * Likelihood) / Total Evidence.", "The scientific rule for updating your mind when new facts arrive."),
        ("Belief Tensor", "A 3D numerical grid B[y, x, k] storing probability mass for each cell and status.", "Think of a spreadsheet where every grid square has 3 numbers: active %, low-power %, damaged %."),
        ("MAP (Maximum A Posteriori)", "The single cell and status that currently has the highest probability.", "Picking the MVP player with the highest score on the leaderboard."),
        ("Shannon Entropy", "A mathematical measure of uncertainty, measured in bits.", "If you have no clue where EVE is, entropy is high (~10 bits). When you pinpoint her, entropy drops to near 0."),
        ("Expected Information Gain (EIG)", "How many bits of uncertainty you expect to eliminate by taking an action.", "Deciding whether to open Door A or Door B based on which one reveals the most answers."),
        ("Return Reserve", "The minimum battery required to safely reach the nearest charger from your position.", "Driving a car and knowing you must reach a petrol pump before the fuel light hits zero."),
        ("Breadth-First Search (BFS)", "An algorithm that finds the shortest path on a grid by exploring ring by ring.", "Like ripples spreading outward in water until they touch the nearest charging station."),
        ("Decoy / Spoofing", "A fake signal designed to mislead the searcher.", "A prankster shouting 'over here!' from behind a tree when the real person is elsewhere."),
        ("Robust Mixture Likelihood", "A formula adding a small uniform probability floor (eps=0.15) to prevent zero-lock.", "Never saying '100% impossible' so a single fake signal cannot completely trick you."),
        ("Credible Region (90%)", "The smallest set of grid cells that contains 90% of the total probability mass.", "Drawing a circle on a treasure map and being 90% confident the chest is inside."),
    ]

    for term, definition, analogy in glossary:
        p_text = f"<b>{term}:</b> {definition} <i>Analogy: {analogy}</i>"
        story.append(Paragraph(p_text, styles["Bullet"]))
    story.append(Spacer(1, 8))

    # SECTION 7: 25 Most Likely Interview Questions
    story.append(Paragraph("7. The 25 Most Likely Interview Questions & Answers", styles["H1"]))
    story.append(Paragraph("Grouped by category, with spoken answers, simple explanations, and follow-up defenses:", styles["Body"]))

    qa_list = [
        # Group 1: Basic
        ("Q1 (Basic): What is the core problem this project solves?",
         "It solves autonomous search under uncertainty with strict resource limits: finding a lost target using noisy, deceptive sensors without running out of battery.",
         "Most search algorithms either ignore noise or run out of power. WALL-E combines Bayesian probability filtering with a guaranteed safe-return battery guard.",
         "Follow-up: Why not just use Dijkstra or A* directly?",
         "Dijkstra and A* require knowing the destination coordinates in advance. In our problem, the destination is completely hidden and must be inferred from noisy sensors."),

        ("Q2 (Basic): What was your specific role in this project?",
         "I designed the problem specifications, configured the mission environments, verified the algorithms against edge cases, and audited the code for zero-cheating compliance.",
         "As a fresher working with Antigravity, my focus was ensuring architectural correctness: making sure the agent never peeks at ground truth and strictly satisfies the safe return invariant.",
         "Follow-up: How did you ensure the agent didn't cheat?",
         "We wrote an automated AST code scanner and runtime proxy interceptor (test_separation.py) that strictly forbids the agent from accessing private world attributes."),

        ("Q3 (Basic): How is EVE's status represented, and why does it matter?",
         "EVE has three operational states: active, low power, and damaged. Each state produces different signal strengths (1.0, 0.6, 0.35) and different dropout probabilities (5%, 25%, 50%).",
         "The status affects how easily EVE can be heard. A damaged EVE emits faint signals that drop out half the time, requiring WALL-E to get closer before making a confident diagnosis.",
         "Follow-up: Can WALL-E declare the right location but the wrong status?",
         "Yes, that counts as a failure. A mission is only successful if BOTH the location is within 2 cells AND the operational status is correctly identified."),

        ("Q4 (Basic): What are the charging stations, and how do they work?",
         "Charging stations are dedicated cells on the grid. When WALL-E executes the RECHARGE action while on a station, he gains +20 battery units over 2 time ticks, up to capacity.",
         "Chargers allow WALL-E to operate indefinitely on large maps as long as he returns to recharge before his battery drops below the return reserve.",
         "Follow-up: Can WALL-E recharge anywhere?",
         "No. Recharging off a charger is rejected by the environment as an invalid action, consuming ticks without giving energy."),

        ("Q5 (Basic): What are clues, and how do they differ from signal scans?",
         "Signal scans are long-range radio readings that can be done anywhere. Clues are physical objects hidden in specific cells that are discovered only when WALL-E performs an AREA_SCAN.",
         "Clues give high-accuracy evidence (bearing hints, range hints, or status diagnostic logs) to resolve ambiguities.",
         "Follow-up: Does WALL-E know where the clues are placed?",
         "No, clue coordinates are completely hidden from the agent. He only discovers them when his area scan radius covers that cell."),

        # Group 2: Technical
        ("Q6 (Technical): How does the Bayesian Grid Filter update beliefs?",
         "It treats each grid cell and status as a hypothesis. When a reading arrives, it multiplies the prior probability by the likelihood of getting that reading, and renormalizes so the sum equals 1.",
         "This is exact discrete Bayes: Posterior[y,x,k] = Prior[y,x,k] * Likelihood(reading | y,x,k) / Evidence.",
         "Follow-up: Why not use a continuous Kalman Filter?",
         "A Kalman Filter assumes a single Gaussian 'bell curve'. But on a grid with obstacles and decoys, belief is multimodal (it has multiple peaks in different rooms). A discrete grid filter handles any shape."),

        ("Q7 (Technical): How does the Safe-Return Invariant work mathematically?",
         "Before every action, the planner computes: battery_after >= shortest_path_to_charger * move_cost * (1 + margin_fraction) + margin_flat. If false, the action is blocked.",
         "We run a Breadth-First Search (BFS) from the proposed position to all charger cells to find the exact shortest obstacle-free path distance.",
         "Follow-up: What happens if WALL-E is already in an unsafe state?",
         "The safety guard immediately intercepts decision-making, clears all planned exploration, and commands the shortest-path move toward the nearest charger."),

        ("Q8 (Technical): How does WALL-E decide what action to take next?",
         "He evaluates up to 25 candidate actions, estimates their Expected Information Gain (EIG) using Monte Carlo sampling, divides by action cost, and picks the highest safe scorer.",
         "This is 'Next-Best-Viewpoint' active sensing. Actions that clarify the most uncertainty for the least energy get prioritized.",
         "Follow-up: Why divide EIG by cost?",
         "Because a scan with radius 3 gives high information but costs 8 battery, while radius 1 costs 4. Dividing by cost gives the 'bang for the buck' efficiency."),

        ("Q9 (Technical): How does the system handle decoys and spoofed signals?",
         "We use a robust mixture likelihood with a uniform floor (eps=0.15) and a 3-attempt confirmation state machine that forces triangulation from orthogonal viewpoints.",
         "If a signal contradicts the current confident belief by >3 standard deviations, it is flagged as suspicious. The agent moves 45 to 135 degrees away to verify it from a different angle before declaring.",
         "Follow-up: What is the benefit in numbers?",
         "In our 50-seed ablation study, the robust agent achieved 90% success on hard decoy missions, compared to only 60% for a naive agent."),

        ("Q10 (Technical): What are the different area scan radii and how are they chosen?",
         "WALL-E can scan radius 1 (costs 4 battery), radius 2 (costs 6 battery), or radius 3 (costs 8 battery). The planner evaluates all 3 and picks based on battery budget and unscanned cells.",
         "Radius 1 is chosen when battery is tight; radius 3 is chosen in open spaces when battery is plentiful to sweep wide areas.",
         "Follow-up: Does WALL-E rescan the same area repeatedly?",
         "No. The agent maintains a spatial memory mask of scanned cells. Scanning already-cleared cells yields 0 information gain, naturally suppressing redundant scans."),

        # Group 3: AI/ML Concepts Explained from Zero
        ("Q11 (AI/ML): What is Shannon Entropy and why is it used?",
         "Entropy measures how uncertain the agent is, in bits. High entropy means probability is spread flat across the whole map; low entropy means it is concentrated on one spot.",
         "Formula: H = - sum(p * log2(p)). It gives the planner a single number to track search progress. When entropy drops below 2 bits, WALL-E knows he has narrowed down the search.",
         "Follow-up: What is the theoretical maximum entropy on a 20x20 grid with 3 statuses?",
         "There are 20 * 20 * 3 = 1,200 states. Uniform log2(1200) is approximately 10.23 bits of entropy."),

        ("Q12 (AI/ML): What is Expected Information Gain (EIG)?",
         "EIG is the expected drop in entropy before taking an action: the Mutual Information between the target location and the future sensor reading.",
         "Mathematically: I(X; Y) = E[ D_KL(P(X|Y) || P(X)) ]. By Gibbs' inequality, this is mathematically guaranteed to never be negative.",
         "Follow-up: How do you compute it if you haven't taken the action yet?",
         "We simulate 25 possible sensor readings using Monte Carlo sampling from our current belief, compute the hypothetical posterior for each, and take the weighted average."),

        ("Q13 (AI/ML): What is a 90% Credible Region?",
         "It is the Bayesian version of a confidence interval: the smallest set of cells whose cumulative posterior probability sums to at least 0.90.",
         "In classical statistics, a confidence interval is about repeated experiments. In Bayesian statistics, a credible region directly means: 'There is a 90% chance the target is inside this box.'",
         "Follow-up: How do you verify if the credible region is accurate?",
         "Through calibration testing across 200 random missions: we checked if EVE actually fell inside the 90% region at least 90% of the time. Our empirical result was 93%."),

        ("Q14 (AI/ML): What is Kullback-Leibler (KL) Divergence?",
         "KL divergence measures how much one probability distribution differs from another, expressed in bits.",
         "Formula: D_KL(P || Q) = sum(P * log2(P / Q)). We use it to measure the exact amount of information a new clue or initial signal adds relative to a uniform prior.",
         "Follow-up: What if P and Q are identical?",
         "If P equals Q everywhere, the log ratio is log2(1) = 0, so the KL divergence is exactly 0.0 bits."),

        ("Q15 (AI/ML): What is the difference between this Bayesian approach and Reinforcement Learning (RL)?",
         "RL requires thousands of training episodes to learn a policy via trial and error. Bayesian active planning requires ZERO training; it computes optimal decisions on the fly using exact probability theory.",
         "For safety-critical tasks with battery constraints, Bayesian planning gives formal guarantees (0% stranding) that neural RL networks cannot guarantee without extensive guardrails.",
         "Follow-up: When would RL be better?",
         "If the world had complex continuous physics, visual camera pixels, or unknown dynamic opponents, RL with deep neural networks could learn features that simple grid filters cannot."),

        # Group 4: Code-Level Line-by-Line
        ("Q16 (Code): Explain Belief.update() in belief.py line by line.",
         "It takes a 3D likelihood array L, multiplies it element-wise with our prior tensor self._b, calculates total evidence S = np.sum(new_b), and normalizes new_b / S.",
         "If total evidence is zero (impossible observation), it preserves the prior to prevent division by zero. It also computes exact KL divergence to record the information bits gained.",
         "Follow-up: What is the shape of self._b?",
         "It is (height, width, 3), representing (y, x, status). For a 20x20 grid, it has exactly 1,200 floating point numbers."),

        ("Q17 (Code): Explain return_reserve() in planner.py line by line.",
         "It calls bfs_distance_to_nearest() to find the shortest obstacle-free cell distance to the closest charger, multiplies by move cost (1), applies (1 + margin_fraction), and adds margin_flat.",
         "Code: d = bfs_distance(pos, chargers, walls); reserve = int(ceil(d * cost * (1.0 + frac))) + flat. If already on a charger, the reserve is strictly 0.",
         "Follow-up: Why use ceil()?",
         "Because battery units are discrete integers. Using ceil ensures we round up, never underestimating the energy needed to survive."),

        ("Q18 (Code): Explain build_signal_likelihood() in signal_model.py.",
         "It creates a 3D likelihood tensor across all (y, x, status). For each cell, it calculates distance d to agent, expected strength A_k * d0 / (d + d0), and computes normal PDF values for strength and bearing.",
         "It handles dropouts by assigning status-specific dropout probabilities uniformly across cells, and handles co-location (d=0) where bearing is physically undefined.",
         "Follow-up: How is the decoy spoof rate blended in?",
         "L_robust = (1 - eps) * L_true + eps * (1.0 / num_free_cells). This uniform mixture prevents any cell from having absolute 0 probability."),

        ("Q19 (Code): Explain the decoy confirmation state machine in agent.py.",
         "When an observation has >3 sigma angular error, agent sets pending_confirmation=True. Candidate viewpoints with orthogonal angles (45-135 deg) get a 2.5x utility bonus.",
         "If 3 attempts from distinct cells fail to confirm, the reading is permanently marked confirmed_decoy. Crucially, the agent is strictly prohibited from declaring while pending_confirmation is True.",
         "Follow-up: Why must the confirmation be from a distinct cell?",
         "Because scanning from the exact same cell would just repeat the same directional perspective, causing circular self-reinforcement of the fake signal."),

        ("Q20 (Code): Explain walle verify in verify.py.",
         "It loads trace.jsonl, report.json, and config.yaml, and replays every action step independently without calling the agent code.",
         "It verifies: (1) moves are 4-connected and do not cross walls, (2) battery decreases by exact cost table values, (3) recharge only happens on chargers, and (4) battery >= reserve at every step.",
         "Follow-up: Why is this important?",
         "It proves the simulation results are 100% authentic and mathematically honest. Evaluators can verify any run without trusting our word."),

        # Group 5: Challenges, Limitations & Improvements
        ("Q21 (Challenges): What was the hardest bug you encountered and fixed?",
         "In runner.py, min_battery_margin was comparing post-step battery against pre-step reserve. When moving toward a charger, battery dropped by 1 but reserve also dropped by 1, falsely looking like a margin decrease.",
         "We fixed it to evaluate battery against the post-step reserve at the new position. That reconciled the accounting and proved zero invariant violations.",
         "Follow-up: How was this caught?",
         "By running our 200-seed Monte Carlo fuzz tests and the trace replay verifier."),

        ("Q22 (Challenges): What are the current limitations of this project?",
         "It operates on a discrete 2D grid with known wall locations. In real robotics, walls have sensor noise (SLAM is needed) and motion is continuous (angles, velocity, wheel slip).",
         "Also, while 20x20 runs in milliseconds, scaling to 1000x1000 would require particle filtering or octree spatial partitioning rather than dense 3D tensors.",
         "Follow-up: What would you improve next if you had another month?",
         "I would implement Particle Filtering (Monte Carlo Localization) to handle continuous coordinates and test multi-agent cooperation (two WALL-Es searching together)."),

        ("Q23 (Challenges): What if EVE moves around?",
         "We already implemented and tested discrete random walk and Gaussian diffusion mobility in belief.predict() using pure NumPy wall-aware separable convolution.",
         "At each step, probability mass diffuses slightly to neighbor cells, conserving total mass to 10^-12 while widening belief until a fresh scan tightens it.",
         "Follow-up: How do you handle target motion around obstacles?",
         "The diffusion kernel is strictly wall-aware: mass that would diffuse into obstacle cells is truncated and renormalized across free neighbor cells."),

        # Group 6: Tricky / Pressure Questions
        ("Q24 (Pressure): Did you build this yourself or did an AI build it?",
         "Antigravity helped generate boilerplate, run large automated test suites, and format documentation. But I drove the architecture, debugged the core safety invariants, and understand every equation and module.",
         "I can walk you through any function in this codebase right now line by line, explain the mathematical derivations, and modify any parameter live in front of you.",
         "Follow-up: What is one architectural decision you personally made?",
         "Choosing exact mutual information EIG instead of simple entropy differences. Simple entropy differences can be negative on unnormalized samples; mutual information is mathematically guaranteed to be non-negative."),

        ("Q25 (Pressure): Why should VinnovateIT select a first-year student like you?",
         "Because I don't just import high-level libraries and treat AI as a black box. I took the initiative to learn core mathematical fundamentals—Bayesian inference, information theory, state machines, and formal safety verification.",
         "I have demonstrated engineering rigor: 139 passing unit tests, automated fuzzing, and production-grade documentation. I am passionate, eager to learn from seniors, and ready to contribute to club projects from Day 1.",
         "Follow-up: Which domain projects in VinnovateIT are you most excited about?",
         "Autonomous robotics, reinforcement learning, and applying probabilistic AI to real-world edge devices.")
    ]

    for q, ans, exp, fq, fa in qa_list:
        card = [
            Paragraph(f"<b>{q}</b>", styles["H3"]),
            Paragraph(f"<b>Say aloud:</b> <i>\"{ans}\"</i>", styles["SpeechBox"]),
            Paragraph(f"<b>The concept behind it:</b> {exp}", styles["Body"]),
            Paragraph(f"<b>Likely follow-up:</b> {fq}<br/><b>Follow-up answer:</b> {fa}", styles["Callout"]),
            Spacer(1, 4),
        ]
        story.append(KeepTogether(card))

    story.append(Spacer(1, 8))

    # SECTION 8: Honest Answer Guide for "Did you use AI?"
    story.append(Paragraph("8. Honest AI Disclosure & Defensibility Guide", styles["H1"]))
    story.append(Paragraph(
        "VinnovateIT interviewers respect honesty and deep technical understanding far more than pretending you wrote 10,000 lines from scratch in Notepad. Here is how to answer with complete confidence:",
        styles["Body"],
    ))
    story.append(make_callout(
        '<b>When asked: "Did you use AI to build this?"</b><br/><br/>'
        '<b>Answer with poise:</b><br/>'
        '<i>"Yes, absolutely. I used Google Antigravity as an advanced AI pair-programming assistant, much like professional engineers use GitHub Copilot or cursor today. However, I didn\'t treat it as a code generator that I blindly copy-pasted.<br/><br/>'
        'I directed the design: defining the Bayesian belief update equations, enforcing strict agent/environment separation so WALL-E cannot cheat, and debugging the return reserve invariants when edge cases failed.<br/><br/>'
        'I can explain every file, write tests for any module, and explain the math behind the code. To me, AI is a force multiplier for learning complex concepts faster."</i>',
        styles["Body"],
        bg="#f0fdf4",
        border="#16a34a",
    ))
    story.append(Spacer(1, 8))

    # SECTION 9: 10-Minute Interview Plan
    story.append(Paragraph("9. 10-Minute Interview Time Allocation", styles["H1"]))
    story.append(Paragraph("How to manage your 10 minutes so you don't get cut off before showing your best work:", styles["Body"]))

    time_data = [
        ["Time Window", "Stage", "Goal & Action"],
        ["0:00 - 1:30 (1.5 min)", "Introduction & Pitch", "Introduce yourself, give the 60-second pitch, state the problem and core Bayesian solution."],
        ["1:30 - 4:30 (3.0 min)", "Live Demonstration", "Run walle run --ascii in terminal. Show real-time belief convergence and open summary.png."],
        ["4:30 - 8:30 (4.0 min)", "Technical Q&A", "Answer questions on Bayesian updates, BFS safe-return reserve, and decoy handling."],
        ["8:30 - 10:00 (1.5 min)", "Closing & Why VinnovateIT", "Share your learnings, explain your passion for AI/ML, and thank the interviewers."],
    ]

    t_time = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(time_data)], colWidths=[110, 120, letter[0] - 72 - 230])
    t_time.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_time)
    story.append(Spacer(1, 8))

    # SECTION 10: Last-Page Cheat Sheet
    story.append(Paragraph("10. Last-Minute Interview Cheat Sheet", styles["H1"]))
    story.append(Paragraph("<b>15 Key Facts, Metrics & Formulas to Memorize:</b>", styles["BodyBold"]))

    cheat_points = [
        "1. Grid Dimensions: Default 20x20 grid with 4-connected moves (North, South, East, West).",
        "2. State Space: 20 x 20 x 3 = 1,200 joint states (X, Y, Status: active, low_power, damaged).",
        "3. Battery & Costs: 100 capacity. MOVE costs 1; SCAN_SIGNAL costs 2; SCAN_AREA costs 2+2r; RECHARGE gives +20.",
        "4. Signal Physics: Amplitude A_k in {1.0, 0.6, 0.35}. Strength = A_k * d0 / (d + d0) with d0=6.0 cells.",
        "5. Sensor Noise: Bearing error sigma_theta = 8 deg + 2 deg * distance. Signal strength noise sigma_s = 0.05.",
        "6. Dropouts: Probability of missed signal: Active = 5%, Low Power = 25%, Damaged = 50%.",
        "7. Decoys & Spoofing: Hard mission has 2 decoys and 15% spoof chance. Robust mixture uses uniform floor eps=0.15.",
        "8. Safe Return Guarantee: battery_after >= bfs_distance_to_nearest_charger * 1 * (1 + 0.10) + 3.",
        "9. Benchmark Performance: BayesPlanner achieves 98.0% success vs 6.0% for Greedy Bearing and 3.0% for Random.",
        "10. Stranded Rate: Exactly 0.0% stranded across all 100 benchmark missions and 200 fuzz tests.",
        "11. Localization Accuracy: 0.30 cells mean error for BayesPlanner (median 0.00 cells).",
        "12. Information Gain: Shannon Mutual Information I(X;Y) = E[D_KL(P(X|Y) || P(X))] >= 0 bits.",
        "13. Credible Coverage: 93.0% empirical coverage for nominal 90% credible regions across 200 calibration seeds.",
        "14. Verification Command: python -m walle verify outputs/mission_medium_seed7 audits physics & battery step by step.",
        "15. Zero Cheating: Environment hides EVE pos/status; audited by AST scanner and runtime attribute proxy.",
    ]

    for cp in cheat_points:
        story.append(Paragraph(cp, styles["Bullet"]))
    story.append(Spacer(1, 8))

    # SECTION 11: Learn Tonight
    story.append(Paragraph("11. 'Learn Tonight': The 5 Must-Know Concepts", styles["H1"]))
    story.append(Paragraph("If you only have time to understand 5 things tonight, master these 5 simple explanations:", styles["Body"]))

    learn_tonight = [
        ("1. Bayes' Theorem in 5 Lines",
         "Bayes' theorem is how an AI updates its beliefs when new clues arrive.<br/>"
         "You start with a Prior (what you believed before).<br/>"
         "You multiply by the Likelihood (how well the clue matches that spot).<br/>"
         "You divide by Evidence so all probabilities sum to 1.0 (100%).<br/>"
         "The result is the Posterior: your new, smarter map of where EVE is."),

        ("2. Safe-Return Reserve in 5 Lines",
         "WALL-E must never die in the field from battery depletion.<br/>"
         "Breadth-First Search (BFS) finds the exact step count to the nearest charger around walls.<br/>"
         "Reserve = (Steps * 1) + 10% safety buffer + 3 emergency units.<br/>"
         "Before any step, WALL-E asks: 'Will my battery after this action stay above the reserve?'<br/>"
         "If no, exploration is cancelled and WALL-E retreats directly to recharge."),

        ("3. Shannon Entropy in 5 Lines",
         "Entropy measures total confusion or ignorance, measured in bits.<br/>"
         "If EVE could be in any of the 1,200 states equally, entropy is maximum (~10 bits).<br/>"
         "Every scan eliminates unlikely cells and lowers entropy.<br/>"
         "When entropy drops below 2 bits, WALL-E has narrowed EVE down to a tiny neighborhood.<br/>"
         "When entropy is near 0, WALL-E is confident enough to declare the mission finished."),

        ("4. Expected Information Gain (EIG) in 5 Lines",
         "Instead of moving blindly, WALL-E thinks ahead one step.<br/>"
         "He imagines: 'If I scan from Position A, what readings might I get?'<br/>"
         "He simulates 25 possible readings and calculates how much entropy would drop.<br/>"
         "This expected drop is the Expected Information Gain.<br/>"
         "WALL-E picks the candidate that delivers the most information per battery spent."),

        ("5. Decoy Triangulation in 5 Lines",
         "A decoy is a fake radio transmitter placed to trick WALL-E into wasting power.<br/>"
         "If a signal points 90 degrees away from where EVE was already confirmed, it is flagged suspicious.<br/>"
         "WALL-E does not declare immediately; he schedules a confirmation scan.<br/>"
         "He deliberately moves 45 to 135 degrees to the side to view it from a right angle.<br/>"
         "If the fake signal doesn't line up from both angles, it gets discounted as a confirmed decoy."),
    ]

    for title, desc in learn_tonight:
        card = [
            Paragraph(f"<b>{title}</b>", styles["H2"]),
            Paragraph(desc, styles["Body"]),
            Spacer(1, 4),
        ]
        story.append(KeepTogether(card))

    # Build PDF
    doc.build(story)
    print(f"[SUCCESS] Built: {output_path}")


def build_demo_guide_pdf(output_path: str = "DEMO_GUIDE.pdf"):
    """Generate the complete 9-section DEMO_GUIDE.pdf."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    doc.canvasmaker = NumberedCanvas
    styles = get_styles()
    story = []

    # Title & Header
    story.append(Paragraph("WALL-E Live Demo Guide & Presentation Script", styles["DocTitle"]))
    story.append(Paragraph(
        "<b>Audience:</b> VinnovateIT Technical Interviewers | <b>Demo Duration:</b> 3 Minutes Max | <b>Platform:</b> Local Terminal & Browser<br/>"
        "<i>Pre-flight checklist, spoken script table, 'wow moment' walkthrough, troubleshooting, and offline backups.</i>",
        styles["DocSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f766e"), spaceAfter=10))

    # SECTION 1: Before the Demo Checklist
    story.append(Paragraph("1. Before-the-Demo Pre-Flight Checklist", styles["H1"]))
    story.append(Paragraph(
        "Follow these exact steps before you enter the interview room so your demo runs flawlessly in 5 seconds:",
        styles["Body"],
    ))

    preflight_steps = [
        "<b>1. Open Terminal in Project Root:</b> Open PowerShell or VS Code terminal in <code>c:\\Programming\\Projects of antigravity\\project_5_aiml_vinnovateit_walleai</code>.",
        "<b>2. Activate Virtual Environment:</b> Run <code>.\\.venv\\Scripts\\Activate.ps1</code>. Verify <code>(.venv)</code> appears in prompt.",
        "<b>3. Zero API Keys Needed:</b> The entire simulation and math run locally in pure Python. No internet connection, OpenAI keys, or external servers required!",
        "<b>4. Pre-Open Generated Visuals:</b> In your file explorer, have <code>outputs/mission_medium_seed7/summary.png</code> and <code>run.gif</code> ready in an image viewer tab.",
        "<b>5. Test Live Command:</b> Run <code>python -m walle run --config configs/mission_easy.yaml --ascii</code> once to ensure it executes smoothly (takes 2 seconds).",
        "<b>6. Clean Screen:</b> Close WhatsApp, Discord, and personal tabs. Put laptop in 'Do Not Disturb' mode.",
    ]

    for ps in preflight_steps:
        story.append(Paragraph(ps, styles["Bullet"]))
    story.append(Spacer(1, 8))

    # SECTION 2: 3-Minute Two-Column Demo Script
    story.append(Paragraph("2. Three-Minute Live Demo Script (Two-Column Table)", styles["H1"]))
    story.append(Paragraph(
        "Start with your one-line intro, perform the screen action, and read the spoken dialogue naturally:",
        styles["Body"],
    ))

    script_rows = [
        ["What You Do On Screen", "What You Say Aloud to Interviewers"],
        [
            "Open terminal showing clean project directory. Have command typed: python -m walle run --config configs/mission_easy.yaml --ascii",
            '"To demonstrate how WALL-E works in real time, I\'m running an autonomous search mission with live ASCII terminal telemetry. Notice how the agent starts at charger C with 100 battery."'
        ],
        [
            "Press Enter. The live ASCII frames stream on screen. W moves, heat map characters change, step counters tick.",
            '"As WALL-E moves east and south, watch the belief heat map on the bottom right. The dots and symbols show probability density. In Step 12, he executes a SIGNAL SCAN, and the posterior sharply concentrates around EVE\'s coordinates."'
        ],
        [
            "Point to terminal output as strategy switches: EXPLORE -> TRACK -> VERIFY -> DECLARE.",
            '"Here you see the finite state machine in action: he transitioned from EXPLORE into TRACK, verified the coordinates, and declared EVE active at position (7, 11) with only 1 cell error, consuming just 15 battery units."'
        ],
        [
            "Open outputs/mission_medium_seed7/summary.png on screen. Show the 6 panels.",
            '"Now let\'s look at a more complex mission on a 20x20 grid. This 6-panel dashboard shows WALL-E\'s complete journey. Panel 1 is the 2D path map around obstacles. Panel 2 shows how belief entropy drops from 10 bits down to zero."'
        ],
        [
            "Point to Panel 5 (Energy & Return Reserve Curve) in summary.png.",
            '"This bottom panel is our critical safety guarantee: the blue line is current battery, and the orange dashed line is the minimum return reserve to reach the charger. Notice the blue line never touches the orange line—stranding is mathematically prevented."'
        ],
        [
            "Switch back to terminal and run: python -m walle verify outputs/mission_medium_seed7",
            '"Finally, to prove that our simulation is 100% honest and never cheated, I built an independent verifier. Running walle verify replays every step, checking energy conservation and wall collisions. It passes with zero violations."'
        ],
    ]

    t_script = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(script_rows)], colWidths=[180, letter[0] - 72 - 180])
    t_script.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_script)
    story.append(Spacer(1, 8))

    # SECTION 3: The Wow Moment
    story.append(Paragraph("3. The 'Wow Moment' of Your Demo", styles["H1"]))
    story.append(make_callout(
        "<b>The Ultimate Wow Moment:</b><br/>"
        "Point to <b>Panel 5 (Battery vs Return Reserve)</b> in <code>summary.png</code> and say:<br/>"
        "<i>'Many student robotics simulations let agents run until they succeed or run out of juice. In our project, WALL-E calculates the Breadth-First Shortest Path to the nearest charger before every single step. In over 200 randomized stress tests with tight batteries, WALL-E had exactly <b>ZERO stranded failures (0.0%)</b>. Even if sensors lie or decoys distract him, his survival invariant is mathematically protected.'</i><br/><br/>"
        "<b>Why this impresses interviewers:</b> AI/ML evaluators see dozens of models with high accuracy that fail in deployment. Showing a formal, guaranteed safety constraint proves you understand <i>reliability in production</i>, not just toy accuracy.",
        styles["Body"],
        bg="#eff6ff",
        border="#2563eb",
    ))
    story.append(Spacer(1, 8))

    # SECTION 4: Exact Sample Inputs & Outputs
    story.append(Paragraph("4. Exact Sample Commands & Expected Outputs", styles["H1"]))
    story.append(Paragraph("Copy-paste these exact commands in your rehearsal:", styles["Body"]))

    commands_data = [
        ["Purpose", "Exact Command to Type", "Expected Output / What to Look For"],
        [
            "1. Fast Live ASCII Run",
            "python -m walle run --config configs/mission_easy.yaml --ascii",
            "Prints 15 grid frames live in 2.5s. Ends with: Outcome: DECLARED, Success: SUCCESS, Location Error: 1.00 cells."
        ],
        [
            "2. Independent Verification",
            "python -m walle verify outputs/mission_medium_seed7",
            "Replays 21 steps. Prints: WALL-E TRACE REPLAY VERIFICATION: mission_medium_seed7 -> Status: [PASSED]."
        ],
        [
            "3. Render Visuals",
            "python -m walle viz --run outputs/mission_medium_seed7",
            "Generates summary.png, run.gif, path_map.png, path_3d.png, belief_evolution.png, metrics_dashboard.png."
        ],
        [
            "4. Quick Benchmark Check",
            "pytest tests/test_benchmark.py -v",
            "Runs in 20 seconds. All 8 tests pass, proving calibration bin means, CSV reconciliation, and paired seeds."
        ],
    ]

    t_cmds = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(commands_data)], colWidths=[100, 180, letter[0] - 72 - 280])
    t_cmds.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_cmds)
    story.append(Spacer(1, 8))

    # SECTION 5: What to Avoid in Demo
    story.append(Paragraph("5. Features to Skip or Avoid During the Live Demo", styles["H1"]))
    story.append(Paragraph("Do not attempt these during your 3-minute window:", styles["Body"]))

    avoid_list = [
        "<b>DO NOT run the full 100-mission benchmark live:</b> Running <code>python -m walle benchmark --n 100</code> evaluates 300 missions and takes about 2 to 3 minutes. It will burn your entire interview time! Instead, show the pre-generated <code>outputs/benchmark/benchmark_chart.png</code>.",
        "<b>DO NOT run the 200-seed calibration script live:</b> <code>scripts/calibration_study.py</code> takes ~4 minutes. Point to <code>outputs/calibration.md</code> and <code>outputs/calibration.png</code> instead.",
        "<b>DO NOT run the full pytest suite with fuzz tests:</b> Running <code>pytest -q</code> executes 200 randomized fuzz tests taking 13 minutes. If asked about tests, run fast tests: <code>pytest tests/test_benchmark.py</code> (20 seconds).",
        "<b>DO NOT edit YAML configs live:</b> A typo in indentation could cause a YAML parse error while under pressure. Use the existing validated configs.",
    ]

    for av in avoid_list:
        story.append(Paragraph(av, styles["Bullet"]))
    story.append(Spacer(1, 8))

    # SECTION 6: Troubleshooting Table
    story.append(Paragraph("6. If Something Breaks: Quick Fixes & Calm Spoken Lines", styles["H1"]))
    story.append(Paragraph("Stay calm. Interviewers love seeing a student troubleshoot professionally:", styles["Body"]))

    trouble_data = [
        ["Failure Scenario", "Immediate Quick Fix", "What to Say Calmly to Interviewers"],
        [
            "'python : command not found' or module error",
            "Run: .\\.venv\\Scripts\\Activate.ps1 or use .\\.venv\\Scripts\\python.exe directly.",
            "\"Let me quickly activate the local virtual environment where NumPy and dependencies are installed.\""
        ],
        [
            "Terminal execution is lagging or frozen",
            "Press Ctrl + C to terminate, then rerun without --ascii: python -m walle run --config configs/mission_easy.yaml",
            "\"The terminal ASCII renderer buffer had a small delay; let me run the headless mission directly—it takes under 1 second.\""
        ],
        [
            "Image file won't open in viewer",
            "Open it directly in your browser: drag outputs/mission_medium_seed7/summary.png into a Chrome or Edge window.",
            "\"Let me drag the generated PNG directly into Chrome for a crisp high-resolution view.\""
        ],
        [
            "Accidental typo in command",
            "Press Up Arrow on your keyboard to recall the last working command and press Enter.",
            "\"Pardon the typo; pulling up the validated command from terminal history.\""
        ],
    ]

    t_trouble = Table([[Paragraph(c, styles["TableHeader"] if i == 0 else styles["TableText"]) for c in row] for i, row in enumerate(trouble_data)], colWidths=[120, 160, letter[0] - 72 - 280])
    t_trouble.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b91c1c")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_trouble)
    story.append(Spacer(1, 8))

    # SECTION 7: Backup Plan & Pre-Captured Artifacts
    story.append(Paragraph("7. Backup Plan: What If Your Laptop Completely Glitches?", styles["H1"]))
    story.append(Paragraph(
        "If your laptop restarts or crashes, don't panic. You can present directly from pre-rendered static artifacts on your phone or pen drive:",
        styles["Body"],
    ))

    backup_items = [
        "<b>1. Pre-Rendered Animated GIF:</b> Keep <code>outputs/mission_medium_seed7/run.gif</code> saved on your phone or Google Drive. You can show WALL-E moving in the browser tab.",
        "<b>2. Summary Dashboard:</b> <code>outputs/mission_medium_seed7/summary.png</code> contains all 6 panels (Path Map, Entropy, Belief Marginal, Confidence, Battery vs Reserve, Evidence Log).",
        "<b>3. Benchmark Chart:</b> <code>outputs/benchmark/benchmark_chart.png</code> compares all 3 architectures on Success, Error, Battery, and Stranded rate.",
        "<b>4. Markdown Audit Report:</b> <code>outputs/mission_medium_seed7/report.md</code> contains the complete audit trail and evidence ledger.",
        "<b>5. Verbal Walkthrough:</b> If screen is completely dead, open the code in VS Code and walk through the 5 functions from Section 7 of INTERVIEW_PREP.pdf.",
    ]

    for bi in backup_items:
        story.append(Paragraph(bi, styles["Bullet"]))
    story.append(Spacer(1, 8))

    # SECTION 8: Questions Interviewers Ask DURING the Demo
    story.append(Paragraph("8. Questions Interviewers Ask DURING the Demo", styles["H1"]))

    demo_qa = [
        ("Interviewer: 'What do the symbols like @, #, %, and : mean in the terminal?'",
         "The '#' are obstacles/walls. 'C' is a charging station. 'W' is WALL-E. The dots, colons, pluses, and '@' symbols represent the belief intensity ramp from low to high probability. '@' is the peak hypothesis where the agent thinks EVE is."),
        ("Interviewer: 'Where does the initial signal come from?'",
         "At step 0, EVE emits a faint broadcast before the mission starts. In generated mode, the environment samples this signal from EVE's actual location using the physical sensor equation with noise."),
        ("Interviewer: 'How does WALL-E know when to stop and declare?'",
         "In agent.py, the agent monitors his location confidence and status confidence. When location confidence exceeds 0.90 and status confidence exceeds 0.70—and there are no pending decoy confirmations—he triggers the DECLARE action."),
        ("Interviewer: 'What happens if battery runs completely out?'",
         "Because of our centralized return reserve guard, battery never runs out in normal missions. If time runs out (250 ticks), the runner forces a declaration using his current best MAP estimate."),
        ("Interviewer: 'Why does the battery line go up in the middle of mission_hard_decoys?'",
         "Because on that hard mission, WALL-E detected his battery dropping toward the reserve, navigated back to charger C, executed 5 RECHARGE actions (+20 battery each), and then continued the mission fully charged."),
    ]

    for q, a in demo_qa:
        card = [
            Paragraph(f"<b>{q}</b>", styles["H3"]),
            Paragraph(f"<b>Answer:</b> <i>\"{a}\"</i>", styles["SpeechBox"]),
            Spacer(1, 3),
        ]
        story.append(KeepTogether(card))

    story.append(Spacer(1, 8))

    # SECTION 9: One-Page Demo Day Checklist
    story.append(Paragraph("9. One-Page 'Demo Day' Final Checklist", styles["H1"]))
    story.append(make_callout(
        "<b>DEMO DAY MORNING CHECKLIST (Print or Review on Phone):</b><br/><br/>"
        "[ ] Laptop charged to 100% and power brick in bag.<br/>"
        "[ ] Project cloned and tested in local directory.<br/>"
        "[ ] VS Code open with terminal in <code>(.venv)</code>.<br/>"
        "[ ] Browser window open with tabs: <code>summary.png</code> and <code>run.gif</code>.<br/>"
        "[ ] Terminal font size bumped up (Ctrl + Plus) so interviewers sitting 3 feet away can read it easily.<br/>"
        "[ ] Notifications, Slack, WhatsApp, and auto-sleep disabled.<br/>"
        "[ ] Backup copy of <code>INTERVIEW_PREP.pdf</code>, <code>DEMO_GUIDE.pdf</code>, and PNGs on your phone or pen drive.<br/>"
        "[ ] Remember to take a deep breath, smile, speak at a steady pace, and enjoy sharing what you learned!",
        styles["Body"],
        bg="#f8fafc",
        border="#1e3a8a",
    ))

    # Build PDF
    doc.build(story)
    print(f"[SUCCESS] Built: {output_path}")


if __name__ == "__main__":
    build_interview_prep_pdf("INTERVIEW_PREP.pdf")
    build_demo_guide_pdf("DEMO_GUIDE.pdf")
