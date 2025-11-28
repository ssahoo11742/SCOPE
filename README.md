# SIM-LEO: Realistic 6-Week Implementation Plan

## Project Core

**Research Question:** Does time-varying network topology caused by orbital motion fundamentally alter cyberattack propagation patterns compared to static terrestrial networks?

**Hypothesis:** Worm propagation in orbital networks exhibits oscillating dynamics that differ significantly from the smooth exponential growth observed in static networks, creating temporal attack surface variations.

**Key Contribution:** First empirical comparison of cyberattack propagation in time-varying orbital networks versus static terrestrial networks, validated with physical testbed.

---

## Week 1: Orbital Foundation

### Goal
Get satellites moving in realistic orbits and classified into planes.

### Tasks

**Day 1-2: Orbital Propagation**
- Use Skyfield's SGP4 (industry standard, no custom integration needed)
- Load TLE files from CelesTrak
- Implement `propagate_snapshot(time)` and `propagate_trajectory(start, duration, timestep)`
- Test: Propagate 100 satellites for 2 hours, 5-minute timesteps

**Day 3-4: Orbital Plane Classification**
- Extract orbital elements: inclination, RAAN, mean anomaly
- Group satellites by (inclination, RAAN) buckets
- Sort satellites within planes by mean anomaly
- Validation: Count planes (expect ~72 for Starlink Shell 1 at 53.2°)

**Day 5: Propagation Validation**
- Download TLEs from two dates 7 days apart
- Propagate older TLE forward, compare to newer TLE
- Compute position error statistics
- Target: Mean error <10 km (acceptable for network modeling)
- Document: "SGP4 accuracy sufficient for topology analysis"

**Day 6-7: Eclipse Calculation (Bonus if time permits)**
- For each satellite position, check if Earth blocks line to Sun
- Track shadow state: Sun, Penumbra, Umbra
- Mark eclipse entry/exit times
- Store for future analysis (Week 4)

**Deliverables:**
- ✅ Working propagator for 1000+ satellites
- ✅ Plane classification showing realistic grouping
- ✅ Validation data (7-day error analysis)
- ✅ Trajectories ready for topology generation

---

## Week 2: Network Topology Generation

### Goal
Build realistic time-varying network graphs matching Starlink's +Grid architecture.

### Tasks

**Day 1-2: Distance and Line-of-Sight Functions**
- Implement `compute_distance(pos1, pos2)` using Euclidean distance
- Implement `check_line_of_sight(pos1, pos2)` using parametric line test
  - Find closest approach to Earth center
  - Require distance > 6471 km (Earth radius + 100 km margin)
- Test on sample satellite pairs

**Day 3-4: +Grid Topology Implementation**
- **Intra-plane links:** Connect satellite to (i±1) mod N within same plane
  - These are stable, always exist if distance <700 km
- **Inter-plane links:** For each plane, find nearest satellite in adjacent plane
  - Only create if distance <2500 km AND line-of-sight clear
  - These are dynamic, change as geometry evolves
- Generate NetworkX graph with node/edge attributes

**Day 5: Network Metrics Calculation**
- Implement: number of nodes/edges, average degree, connectivity
- If connected: average shortest path length, diameter
- Compute for single timestep snapshot

**Day 6: Topology Evolution**
- Generate graphs at 25 timesteps over 2 hours (5-minute intervals)
- Track which edges exist at each timestep
- Compute link churn rate: `(edges_added + edges_removed) / total_edges`

**Day 7: Validation Against Literature**
- Compare metrics to Bhattacherjee et al. (CoNEXT 2019):
  - Average degree: Target 3.7-4.0
  - Average path length: Target 13-18 hops
  - Network diameter: Target 28-35 hops
  - Link churn: Target 2-5% per minute
- If metrics off by >20%: Debug topology algorithm
- Document validation in table

**Deliverables:**
- ✅ Topology generator producing realistic graphs
- ✅ Time series of network snapshots (25+ timesteps)
- ✅ Validation table comparing to published data
- ✅ Network is always connected (no fragmentation)

---

## Week 3: Worm Propagation Model

### Goal
Implement simple but realistic worm spreading through time-varying network.

### Tasks

**Day 1-2: SIR Epidemic Model (Network-Based)**
- State per satellite: Susceptible (S), Infected (I), Recovered (R)
- Transition rules:
  - S → I: If neighbor is infected, probabilistic infection (rate β)
  - I → R: If patched by operator (rate γ)
- Implement as agent-based simulation (not differential equations)
  - Each satellite checks neighbors each timestep
  - If neighbor infected, roll random number vs. β

**Day 3-4: Network-Aware Spreading**
- At each timestep:
  1. Get current network graph G(t)
  2. For each infected satellite:
     - List all neighbors (connected via edges in G(t))
     - For each susceptible neighbor:
       - Attempt infection with probability β
       - If success: Mark neighbor as infected next timestep
  3. Update satellite states
- Key: Worm only spreads along existing edges (respects topology)

**Day 5: Packet-Based Propagation (Optional Enhancement)**
- Instead of instant spread, model packets:
  - Infected satellite sends "exploit packet" to neighbor
  - Packet takes time to traverse: `latency = distance / speed_of_light`
  - If link breaks before packet arrives: Packet dropped
- This adds realism but not strictly necessary for core question

**Day 6-7: Initial Testing**
- Run worm on single static graph:
  - 5 initial infected satellites (random placement)
  - β = 0.3 (30% infection probability per contact)
  - Run for 100 timesteps
  - Track: % infected over time, time to 50% infection
- Verify: Should see exponential growth (S-curve)
- Debug any issues

**Deliverables:**
- ✅ Working worm propagation model
- ✅ Clean infection spreading through static network
- ✅ Tracking metrics: infection count over time
- ✅ Ready for comparison experiments

---

## Week 4: Core Experiments

### Goal
Answer the research question with two focused experiments.

### Experiment 1: Orbital vs. Static Network (PRIMARY - Days 1-4)

**Setup:**
- **Network A (Control):** Erdős-Rényi random graph
  - 1000 nodes
  - Average degree 3.8 (match Starlink)
  - Static (never changes)
  
- **Network B (Treatment):** Time-varying orbital network
  - 1000 satellites from real TLEs
  - Topology changes every 5 minutes (25 timesteps over 2 hours)
  - +Grid architecture

- **Worm parameters (identical for both):**
  - 5 initial infected (same positions/IDs in both networks)
  - β = 0.3 (infection rate)
  - No patching (γ = 0) for first experiment

**Procedure:**
- Run 100 Monte Carlo simulations per network
  - Each run: Random selection of 5 initial infected
  - Track infection % at each timestep
- Compute statistics: mean, std, median, 95% confidence intervals

**Metrics:**
- Time to 50% infection (T50)
- Infection growth rate (dI/dt)
- Shape of infection curve (smooth vs. oscillating)
- Final infection percentage at t=2 hours

**Expected Results:**
- Static: Smooth exponential growth → 85% infected by 2 hours
- Orbital: Oscillating growth → 78% infected by 2 hours, with ±15% variation
- Statistical test: t-test on T50 values (p < 0.05 for significance)

**Key Finding:**
"Time-varying topology causes infection rate to oscillate with 23±7% variation correlated to orbital geometry, compared to smooth exponential growth in static networks (p < 0.001)."

### Experiment 2: Eclipse Exploitation (SECONDARY - Days 5-7)

**Setup:**
- Use orbital network only (no static comparison)
- Model eclipse vulnerability: During eclipse transition (±2 min), β increases
  - Normal: β = 0.3
  - Eclipse: β = 0.6 (2× more vulnerable due to power/thermal stress)

**Two conditions:**
- **Condition A (Random):** Worm attacks at random times
  - No knowledge of eclipse schedule
  - Sometimes hits eclipse window by chance
  
- **Condition B (Eclipse-Aware):** Worm times attacks to eclipse entry
  - Has orbital knowledge
  - Waits for target to enter eclipse before attacking

**Procedure:**
- Run 100 simulations per condition
- Track: Attack success rate, time to 50% infection, detection events

**Metrics:**
- Success rate per attack attempt
- Overall propagation speed
- % of attacks that occurred during eclipse windows

**Expected Results:**
- Random: 35% attack success rate (weighted avg of normal and eclipse)
- Eclipse-aware: 52% attack success rate (targets eclipse windows)
- Time to 50% infection: 15% faster with eclipse timing

**Key Finding:**
"Attackers with orbital knowledge can exploit eclipse transitions to achieve 1.5× higher infection success rate compared to timing-agnostic attacks."

**Deliverables:**
- ✅ Two complete experiments with statistical analysis
- ✅ Raw data files (CSV format) for reproducibility
- ✅ Key findings validated with confidence intervals
- ✅ Clear evidence orbital dynamics matter

---

## Week 5: Validation & Analysis

### Goal
Validate simulation accuracy and analyze results thoroughly.

### Tasks

**Day 1-2: Literature Comparison**
- Create validation table:
  - Your topology metrics vs. Bhattacherjee et al.
  - Your propagation rate vs. classical SIR model predictions
  - Document where they match (validates simulator)
  - Document where they differ (explain why)
- Write "Validation" section for paper

**Day 3-4: Sensitivity Analysis**
- Test robustness of findings by varying parameters:
  - Infection rate β: 0.1, 0.2, 0.3, 0.4, 0.5
  - Number of initial seeds: 1, 3, 5, 10, 20
  - Network size: 500, 1000, 2000 satellites (if computational time allows)
- Create table showing: How much does result change?
- Key question: Does your main finding hold across parameter ranges?

**Day 5: Visualization**
- **Figure 1 (Main Result):** Infection curves
  - X-axis: Time (minutes)
  - Y-axis: % infected
  - Two lines: Static (smooth) vs. Orbital (oscillating)
  - Shaded regions: 95% confidence intervals
  - Annotation: "Orbital dynamics cause ±15% oscillation"

- **Figure 2 (Eclipse Exploitation):**
  - Bar chart: Success rate (Random vs. Eclipse-aware)
  - Error bars from 100 simulations
  - Statistical significance indicator (p-value)

- **Figure 3 (Topology Validation):**
  - Table comparing your metrics to literature
  - Shows simulator produces realistic networks

**Day 6-7: Hardware Testbed Design (Optional)**
- If time permits: Design physical validation experiment
- Specification document:
  - 3 Raspberry Pi 4 boards ($150)
  - 6 laser communication modules ($600)
  - Rotating platform with stepper motor ($150)
  - Power supplies, cables ($100)
- Test plan: How to validate topology dynamics with hardware
- Leave as "proposed future work" if no time to build

**Deliverables:**
- ✅ Complete validation analysis
- ✅ Sensitivity analysis showing robustness
- ✅ Publication-quality figures (3 main figures)
- ✅ Hardware testbed design (for THINK proposal justification)

---

## Week 6: Paper Writing & GitHub Release

### Goal
Complete 6-8 page paper and release open-source code.

### Paper Structure (IEEE Format)

**Abstract (150 words) - Day 1 morning**
- Problem: LEO mega-constellations are critical infrastructure, but orbital dynamics create time-varying topology
- Gap: No prior work on how topology dynamics affect cyberattack propagation
- Method: Built simulator, compared orbital vs. static networks, tested eclipse exploitation
- Finding: Time-varying topology causes 23±7% oscillation in infection rate; eclipse-aware attacks achieve 1.5× higher success
- Implication: Orbital-aware security strategies are necessary

**1. Introduction (1 page) - Day 1 afternoon**
- Motivation: Starlink has 6000+ satellites, vulnerable to worms
- Problem: Satellites move → network changes → existing security models inadequate
- Research Question: Does time-varying topology alter propagation?
- Contributions:
  1. First comparison of orbital vs. static network propagation
  2. Quantified oscillating infection dynamics
  3. Demonstrated eclipse exploitation potential
  4. Open-source simulator for community

**2. Background & Related Work (1 page) - Day 2 morning**
- 2.1: LEO constellation basics (orbits, ISLs, +Grid topology)
- 2.2: Epidemic models (SIR framework, network-based propagation)
- 2.3: Related work:
  - Satellite networking: Bhattacherjee et al., Handley et al.
  - Network worms: Kephart & White, Staniford et al.
  - Space security: Pavur et al., Willbold et al.
  - Gap: No work on orbital topology effects on cyber propagation

**3. System Design (1.5 pages) - Day 2 afternoon**
- 3.1: Architecture overview (diagram)
- 3.2: Orbital propagation (Skyfield/SGP4)
- 3.3: Topology generation (+Grid algorithm)
- 3.4: Worm model (SIR on time-varying graph)
- 3.5: Implementation details (Python, NetworkX, 1000 satellites, 2-hour simulations)

**4. Validation (0.5 pages) - Day 3 morning**
- Table: Topology metrics vs. literature
- Propagation accuracy: 7-day TLE comparison
- Conclusion: Simulator produces realistic networks

**5. Experiments & Results (2.5 pages) - Day 3 afternoon + Day 4**
- **5.1: Orbital vs. Static Network (1.5 pages)**
  - Setup, procedure, metrics
  - Figure 1: Infection curves showing oscillation
  - Statistical analysis: t-test results
  - Finding: 23±7% oscillation, p < 0.001
  
- **5.2: Eclipse Exploitation (1 page)**
  - Setup, two conditions (random vs. eclipse-aware)
  - Figure 2: Success rate comparison
  - Finding: 1.5× advantage with orbital knowledge
  
- **5.3: Sensitivity Analysis (brief)**
  - Table: Results across parameter ranges
  - Confirms findings are robust

**6. Discussion (0.75 pages) - Day 5 morning**
- Interpretation: Why does oscillation occur? (Orbital geometry creates periods of high/low connectivity)
- Implications for operators: Need temporal awareness in defense strategies
- Limitations:
  - Simplified routing (no Contact Graph Routing)
  - No hardware validation yet (but designed testbed)
  - Single constellation (Starlink only)
- Threat model assumptions

**7. Future Work (0.5 pages) - Day 5 afternoon**
- Hardware testbed validation (3-satellite platform)
- C2 constraint modeling (ground station visibility)
- Defense strategies (patching, segmentation)
- Multi-constellation interactions
- Advanced routing protocols

**8. Conclusion (0.25 pages) - Day 5 afternoon**
- Summary: Time-varying topology fundamentally alters propagation
- Key result: Quantified oscillating dynamics
- Impact: Demonstrates need for orbital-aware security
- Open-source release enables future research

**References (0.5 pages) - Ongoing**
- Target: 25-35 references
- Categories:
  - Orbital mechanics (5 refs)
  - Satellite networking (8 refs)
  - Epidemic models (5 refs)
  - Cybersecurity (7 refs)
  - Space security (5 refs)

### GitHub Repository - Day 6-7

**Directory structure:**
```
sim-leo/
├── README.md
│   - Installation instructions
│   - Quick start example
│   - Link to paper
│   - How to reproduce results
│
├── requirements.txt
│   - skyfield
│   - numpy
│   - networkx
│   - matplotlib
│   - pandas
│
├── src/
│   ├── propagator.py          (orbital mechanics)
│   ├── topology.py             (network generation)
│   ├── worm.py                 (SIR propagation)
│   ├── analysis.py             (metrics computation)
│   └── visualization.py        (plotting functions)
│
├── experiments/
│   ├── exp1_orbital_vs_static.py
│   └── exp2_eclipse_exploitation.py
│
├── data/
│   ├── starlink_tles.txt       (sample TLE file)
│   └── results/                (CSV outputs from experiments)
│
├── notebooks/
│   ├── 01_propagation_demo.ipynb
│   ├── 02_topology_demo.ipynb
│   └── 03_worm_demo.ipynb
│
└── docs/
    ├── architecture.md
    ├── usage.md
    └── validation.md
```

**Documentation priorities:**
- README with clear example: "Run experiment in 3 commands"
- Docstrings for all functions
- Jupyter notebooks showing key results
- Comments explaining non-obvious code

**Deliverables:**
- ✅ 6-8 page IEEE format paper
- ✅ 3 publication-quality figures
- ✅ Open-source GitHub repository
- ✅ Reproducible experiments
- ✅ Clean, documented code

---

## MIT THINK Proposal Components

### What You Need from THINK

**Budget Justification ($1000):**
- **Hardware validation testbed:** $900
  - 3× Raspberry Pi 4 (8GB): $225
  - 6× VL53L1X laser ranging modules: $180
  - Stepper motor + driver for rotation: $80
  - Power supplies (3× 5V 3A): $45
  - Structural components (3D printing, mounting): $120
  - Cables, connectors, breadboards: $80
  - USB WiFi adapters for ISL simulation: $90
  - microSD cards (3× 64GB): $45
  - Enclosures for "satellites": $35

- **Cloud computing (if needed):** $100
  - AWS/GCP credits for large-scale simulations
  - 10,000+ satellite constellations, 1000 Monte Carlo runs

**Mentorship Needs:**
- **Technical guidance:** MIT Space Systems Lab or CSAIL faculty
  - Validate orbital mechanics assumptions
  - Review network topology model
  - Guidance on cybersecurity threat modeling
  
- **Experimental design:** Statistics/ML faculty
  - Proper Monte Carlo methodology
  - Statistical significance testing
  - Parameter selection justification

- **Paper writing:** Help structuring results, literature review
- **Hardware design:** Advice on testbed construction, sensor selection

**Timeline:**
- **Weeks 1-6 (Pre-THINK decision):** Build simulation, run core experiments
- **THINK support period (3 months):** Build hardware, validate, finalize paper
- **Deliverable:** Published paper + open-source tool + physical demo

---

## Success Metrics

### Minimum Viable Project (Must Have):
- ✅ Working simulator (1000 satellites, 2 hours)
- ✅ Experiment 1 complete (orbital vs. static comparison)
- ✅ Statistical significance (p < 0.05)
- ✅ One key finding quantified with confidence intervals
- ✅ 6-page paper draft
- ✅ Code on GitHub

### Target Project (Should Have):
- ✅ Everything above
- ✅ Experiment 2 complete (eclipse exploitation)
- ✅ Validation against literature (topology metrics)
- ✅ Sensitivity analysis
- ✅ 3 publication-quality figures
- ✅ 8-page paper
- ✅ Clean, documented code

### Stretch Goals (Nice to Have):
- ✅ Everything above
- ✅ Hardware testbed designed (specs, budget, test plan)
- ✅ Preliminary hardware results (if built during THINK period)
- ✅ Submission to conference/journal
- ✅ Interactive visualization (CesiumJS web demo)

---

## Week-by-Week Checklist

### Week 1: ☐ Orbital propagation working ☐ Plane classification ☐ Validation complete
### Week 2: ☐ Topology generator ☐ 25 network snapshots ☐ Metrics match literature
### Week 3: ☐ Worm model ☐ Clean spreading on static graph ☐ Ready for experiments
### Week 4: ☐ Experiment 1 done ☐ Experiment 2 done ☐ Statistical analysis
### Week 5: ☐ Validation ☐ Figures ☐ Hardware design
### Week 6: ☐ Paper complete ☐ GitHub release ☐ Reproducible results

---

## What Makes This Achievable

**Compared to original plan:**
- ❌ Cut: Custom numerical integrator (use SGP4)
- ❌ Cut: Contact Graph Routing (use simple time-slices)
- ❌ Cut: 5 experiments (do 2 focused ones)
- ❌ Cut: C2 modeling, patching strategies, segmentation (future work)
- ❌ Cut: Complex attack vectors (focus on basic worm)
- ✅ Keep: Core research question (topology dynamics)
- ✅ Keep: Validation (metrics + statistical tests)
- ✅ Keep: Hardware component (designed, built if THINK supports)

**This matches successful THINK project scope:**
- One clear question
- Two focused experiments
- Solid validation
- Realistic timeline
- Hardware justifies budget/mentorship

---

## The Honest Truth

This plan is **aggressive but achievable** for a strong student with good coding skills. You'll work hard, but you won't need to cut sleep or compromise quality.

**If you fall behind:** Drop Experiment 2 (eclipse). The baseline comparison (Experiment 1) alone is publishable.

**If you're ahead:** Build the hardware testbed early, validate in real-time.

Ready to start Week 1?
