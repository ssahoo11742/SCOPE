# SIM-LEO: Streamlined Implementation Plan for MIT THINK

## Project Overview

**Core Research Question:** How do orbital dynamics fundamentally change cyberattack propagation patterns compared to terrestrial networks?

**Key Innovation:** First simulator coupling realistic satellite motion with cyber-physical attack models to prove that orbital mechanics create time-dependent vulnerabilities.

**Timeline:** 6 weeks (focused implementation, validated results, publication-quality paper)

---

## Phase 1: Orbital Foundation (Week 1)

### Goal
Get satellites moving in realistic orbits and classified into orbital planes for topology generation.

### 1.1 Orbital Propagation (Using Skyfield)
**Decision:** Use Skyfield's SGP4 instead of custom numerical integration
- SGP4 is industry-standard, already validated against real satellite data
- Position accuracy (5-10 km over weeks) is sufficient for network topology
- ISL links span 500-2500 km → small position errors don't affect connectivity
- Saves 1-2 weeks vs. implementing custom RK45 integrator

**Implementation:**
- Load TLE files from CelesTrak (real Starlink orbital data)
- Propagate all satellites over time windows (e.g., 2 hours, 5-minute timesteps)
- Extract positions in ECI coordinates (x, y, z in km)
- Convert to lat/lon/altitude for visualization and ground station calculations

**Key Functions:**
```python
propagate_snapshot(time) → list of satellite positions at single moment
propagate_trajectory(start, duration, timestep) → full time-series of positions
```

### 1.2 Orbital Element Extraction & Plane Classification
**Why this matters:** Starlink's topology depends on which satellites are in the same orbital plane

**Process:**
- Extract from each TLE: inclination (53°, 70°, 97.6°), RAAN (0-360°), mean anomaly
- Group satellites: Round RAAN to nearest 5° to account for drift
- Result: Dictionary mapping `(inclination, RAAN)` → list of satellites in that plane
- Sort satellites within each plane by mean anomaly (position along orbit)

**Expected output:**
- Shell 1 (53.2°, 550 km): ~72 planes × 22 satellites = 1,584 satellites
- Shell 2 (53.0°, 540 km): Sparse (early deployment)
- Shell 3 (70°, 570 km): ~36 planes
- Shell 4 (97.6°, 560 km): Polar, ~6 planes

**Validation checkpoint:** 
- Count planes per inclination group
- Check if satellites per plane is uniform (±20%)
- Compare to known Starlink deployment data

### 1.3 Propagation Validation
**Goal:** Prove SGP4 is accurate enough for our research question

**Experiment:**
- Download TLEs from two dates 7 days apart (e.g., Jan 1 and Jan 8, 2025)
- Propagate Jan 1 TLE forward 7 days using SGP4
- Compare predicted position to actual Jan 8 TLE position
- Compute error statistics across 100+ satellites

**Success criteria:**
- Mean error < 10 km (acceptable for network modeling)
- Error represents < 1% of typical ISL range (500-2500 km)
- Document error growth rate (typically ~1 km/day)

**Deliverable:** One paragraph in paper: "We validated propagation accuracy over 7-day windows, achieving mean error of X ± Y km, representing <1% of ISL range and thus negligible for topology modeling."

---

## Phase 2: Realistic Network Topology (Week 2)

### Goal
Generate time-varying network graphs that match real Starlink connectivity patterns.

### 2.1 Starlink +Grid Topology
**What is +Grid?** Starlink's patented ISL architecture:
- **Intra-plane links** (fore/aft): Each satellite connects to neighbors in same orbital plane
  - Distance: 500-700 km
  - Stability: Extremely stable (persist for weeks)
  - Each satellite has 2 intra-plane links (±1 neighbor)
  
- **Inter-plane links** (left/right): Connect to satellites in adjacent orbital planes
  - Distance: Varies 1000-2500 km based on latitude
  - Stability: Dynamic (change every 5-10 minutes as relative geometry shifts)
  - Form when planes are close (near poles), break when far (near equator)
  - Each satellite has 0-2 inter-plane links depending on geometry

**Result:** Each satellite typically has degree 4 (two intra, two inter) but varies 2-4 dynamically

### 2.2 Link Formation Rules
**Physical constraints that determine if ISL exists:**

1. **Distance check:** Satellites must be within laser range
   - Maximum: 2500 km (optical link budget limitation)
   - Compute: `distance = sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)`

2. **Line-of-sight check:** Link cannot pass through Earth
   - Parametric line from sat A to sat B: `P(t) = posA + t×(posB - posA)`
   - Find closest approach to Earth center
   - Require: `min_distance > R_Earth + 100 km` (atmospheric margin)

3. **Pointing constraint (simplified):** 
   - Real satellites have ±45° gimbal range
   - For THINK scope: Skip gimbal modeling (assume omnidirectional within 2500 km)
   - Future work: Add pointing cones for higher fidelity

### 2.3 Network Graph Generation
**Data structure:** NetworkX graph at each timestep
- **Nodes:** Satellite IDs with position attributes (x, y, z, lat, lon, alt)
- **Edges:** ISL connections with attributes:
  - `distance`: km between satellites
  - `type`: 'intra_plane' or 'inter_plane'
  - `latency`: distance / speed_of_light (in milliseconds)
  - `capacity`: 10-100 Gbps (typical optical ISL bandwidth)

**Algorithm:**
```
For each timestep:
  1. Get all satellite positions at this moment
  2. Intra-plane links:
     - For each plane, connect satellite i to satellite (i+1) mod N
     - These are deterministic (always exist if distance < 2500 km)
  3. Inter-plane links:
     - For each plane, find nearest satellite in adjacent plane
     - Only create edge if distance < 2500 km AND line-of-sight clear
  4. Store graph with timestamp
```

### 2.4 Topology Validation Metrics
**Compare your simulation to published Starlink measurements:**

| Metric | Bhattacherjee et al. (2019) | Your Target |
|--------|----------------------------|-------------|
| Average degree | 3.8 | 3.7-4.0 |
| Avg shortest path | 15.4 hops | 13-18 hops |
| Network diameter | ~31 hops | 28-35 hops |
| Link churn rate | 2-4% per minute | 2-5% per minute |

**Link churn calculation:**
```
At each transition t → t+1:
  edges_added = edges in G(t+1) but not G(t)
  edges_removed = edges in G(t) but not G(t+1)
  churn_rate = (|edges_added| + |edges_removed|) / |edges in G(t)|
```

**Success criteria:**
- Metrics within ±20% of literature values
- Network always connected (no fragmentation)
- Intra-plane links have >99% persistence (very stable)
- Inter-plane links have 70-90% persistence (more dynamic)

### 2.5 Stochastic Link Failures (Optional if Time Permits)
**Reality:** Links don't just fail geometrically, they also fail randomly
- **Pointing jitter:** Laser beam misses receiver (0.001% failure rate)
- **Component failures:** Laser transmitter degrades (MTBF = 10 years)
- **Weather (ground links only):** Clouds block optical, rain attenuates RF

**Implementation:** At each timestep, for each edge, roll random number:
- If `random() < failure_probability`: Remove edge temporarily
- Typical failure probability: 0.0001 (0.01% per timestep)

**For THINK:** Implement simple version (constant failure probability), skip detailed physical modeling

---

## Phase 3: Simplified Routing (Week 3)

### Goal
Get packets flowing through the time-varying network (sufficient for worm propagation modeling).

### 3.1 Why We're Simplifying
**Original plan:** Full Contact Graph Routing (CGR) with:
- Contact plan generation (precompute all future link windows)
- Time-expanded graph (node per satellite per timestep)
- Delay-tolerant networking protocols
- Complex queueing theory

**Reality check:** CGR takes 2-3 weeks to implement correctly, and your research question doesn't require it

**Your actual need:** Show that packets can route through network, paths change over time

### 3.2 Time-Slice Routing (Sufficient for THINK)
**Approach:** Treat network as sequence of static snapshots
- At each timestep, compute shortest paths on current graph
- Use standard Dijkstra's algorithm (NetworkX has this built-in)
- Recompute paths every 60 seconds (when topology changes)

**Algorithm:**
```
For each packet:
  1. Check current time t
  2. Get network graph G(t) at this timestep
  3. Compute shortest path: source → destination using Dijkstra
  4. Forward packet one hop along path
  5. At next timestep, recompute if topology changed
```

**Key insight:** This captures the essential dynamic: *paths change as satellites move*

### 3.3 Basic Packet Model
**Each packet contains:**
- `source_id`: Origin satellite
- `destination_id`: Target satellite  
- `size`: Bytes (typically 1500 bytes)
- `creation_time`: When packet was generated
- `current_location`: Which satellite currently holds it
- `hops_taken`: Number of hops so far (for analysis)

**Forwarding logic:**
```
At each timestep, for each satellite:
  1. Look at packets in buffer
  2. For each packet:
     - Compute next hop on shortest path to destination
     - If next hop reachable via ISL:
       - Send packet (update current_location)
     - Else:
       - Drop packet (topology changed, path broken)
```

### 3.4 Simple Buffer Management
**Each satellite has finite buffer:** 100 MB = ~66,000 packets
- When buffer full: Drop new arrivals (tail drop policy)
- Priority ordering: Control packets > user data (for worm modeling)

**For THINK scope:** Don't model detailed queueing, bandwidth allocation, or congestion control
- Assume infinite bandwidth on links (packets transfer instantly)
- Focus: Does packet reach destination before topology changes?

### 3.5 Ground Station Contact Windows
**Purpose:** Worms need to "phone home" to attacker's ground station for command & control

**Calculation:**
- Ground station at (latitude, longitude)
- For each satellite, check: Is elevation angle > 25° (minimum for reliable link)?
- Compute when satellite rises and sets relative to ground station
- Result: Contact windows (start_time, end_time, max_elevation)

**Key finding for your research:** 
- Satellites pass over any ground station every ~90 minutes
- Contact duration: 4-8 minutes per pass
- Some satellites NEVER see attacker's ground station (wrong orbital plane)
- **This is orbital-cyber coupling:** Attacker's control limited by orbital geometry

---

## Phase 4: Cyber-Physical Attack Models (Week 4)

### Goal
Model worm propagation and show that orbital mechanics create exploitable vulnerability patterns.

### 4.1 Basic Worm Model (SIR Epidemic)
**Epidemiology adapted to satellites:**
- **S (Susceptible):** Uninfected satellites, vulnerable to attack
- **I (Infected):** Compromised satellites, actively spreading worm
- **R (Recovered):** Patched satellites, immune to infection

**State transitions:**
```
S → I: When infected satellite sends exploit to susceptible neighbor
       Probability β (infection rate) per contact
       
I → R: When operator patches satellite
       Rate γ (patching rate) = satellites_patched / hour
```

**Differential equations:**
```
dS/dt = -β × S × (I/N)     [Susceptibles getting infected]
dI/dt = β × S × (I/N) - γ × I   [New infections minus recoveries]
dR/dt = γ × I              [Patched satellites]

Where N = total satellites
```

### 4.2 Routing-Aware Worm Implementation
**How worm spreads through network:**

**Step 1 - Reconnaissance (infected satellite scans neighbors):**
- Look at current ISL connections (edges in network graph)
- Identify neighbors that are susceptible (not infected, not patched)
- Takes 30 seconds per neighbor to scan

**Step 2 - Exploitation (infected satellite attacks vulnerable neighbor):**
- Send exploit packet via ISL (uses normal routing)
- Packet must traverse multiple hops if neighbor not directly connected
- Each hop introduces delay + detection risk

**Step 3 - Infection success probability:**
```
P(success) = β × (1 - P_detect)^num_hops

Where:
  β = base infection rate (0.3 typical)
  P_detect = intrusion detection probability per hop (0.1 if IDS present)
  num_hops = length of path from infected to target
```

**Step 4 - Propagation (newly infected satellite repeats):**
- New infected satellite waits for next timestep
- Scans its neighbors
- Exponential growth: 1 → 3 → 9 → 27 → 81...

### 4.3 Eclipse-Timed Attack (Key Experiment)
**Hypothesis:** Attacks succeed more often during eclipse transitions due to thermal/power stress

**Eclipse calculation:**
- For each satellite, check if line from satellite to Sun passes through Earth
- If yes: Satellite in shadow (eclipse)
- Track transitions: Sun → Eclipse (entering) and Eclipse → Sun (exiting)

**Vulnerability modeling:**
- Normal conditions: β = 0.3 (30% infection success rate)
- During eclipse transition (±2 minutes): β = 0.6 (60% success rate!)
- Reason: CPU throttled, security checks slower, thermal stress on components

**Experiment design:**
```
Condition A (Control): 
  - Worm attacks at random times
  - Run 500 Monte Carlo simulations
  - Measure: Time to 50% infection (T50)

Condition B (Eclipse-timed):
  - Worm waits for targets to enter eclipse before attacking
  - Run 500 Monte Carlo simulations  
  - Measure: T50

Statistical test: t-test comparing T50 between conditions
Hypothesis: T50(eclipse-timed) < T50(random) with p < 0.05
```

**This proves orbital mechanics affect cyberattack effectiveness!**

### 4.4 Command & Control (C2) Constraint
**Realistic worm behavior:** Infected satellites must periodically contact attacker's ground station
- Receive new commands
- Exfiltrate stolen data
- Get software updates

**Orbital constraint:**
- Satellite only sees attacker's ground station during contact windows
- If no contact for > 2 hours: Worm goes dormant (stops spreading)
- Some satellites NEVER see attacker's ground (wrong inclination)

**Implementation:**
```
For each infected satellite at each timestep:
  1. Check: Am I currently visible from attacker's ground station?
  2. If yes: Reset C2 timer, receive commands, stay active
  3. If no C2 for > 2 hours: Go dormant (infection stalls)
```

**Key insight:** Orbital geometry limits attacker's operational effectiveness

### 4.5 Defense Mechanisms

**Defense 1 - Intrusion Detection System (IDS):**
- Deployed on 30% of satellites (random or high-centrality nodes)
- Detection probability: 0.3 per packet crossing IDS node
- Response: Alert sent to NOC via ground station (5-30 minute delay)

**Defense 2 - Patching:**
- Operator pushes patch via ground stations
- Rate-limited by contact windows: ~200-300 satellites/hour achievable
- Infected satellites prioritized first

**Defense 3 - Network Segmentation:**
- Divide constellation into zones (by orbital plane or geographic region)
- Inter-zone traffic passes through firewall satellites
- Firewall detection rate: 0.7 (blocks 70% of malicious packets)

---

## Phase 5: Validation & Key Experiments (Week 5)

### Goal
Prove your simulator is realistic and answer the core research question.

### 5.1 Baseline Comparison (CRITICAL - This is Your Main Result)
**The experiment that proves orbital dynamics matter:**

**Setup:**
- **Network A (Control):** Static Erdős-Rényi graph, 1000 nodes, avg degree 3.8
- **Network B (Treatment):** Time-varying orbital topology, 1000 satellites, avg degree 3.8
- Same worm parameters: β=0.3, 5 initial infected, run for 24 hours

**Measure:**
- Time to 50% infection (T50)
- Infection growth rate (dI/dt)
- Final infection percentage

**Expected results:**
- Static graph: Smooth exponential growth, T50 = X hours
- Orbital graph: **Oscillating growth** with periodic bursts, T50 = Y hours
- Difference: 20-40% (proves orbital dynamics create different propagation pattern)

**This is Figure 1 in your paper - most important result!**

### 5.2 Eclipse Vulnerability Experiment
**Question:** Do eclipse-timed attacks succeed more often?

**Results to show:**
- Control (random timing): T50 = X hours, detection rate = 30%
- Eclipse-timed: T50 = 0.7X hours (30% faster), detection rate = 20%
- Statistical significance: p < 0.01 (t-test)

**Interpretation:** Attackers who exploit orbital mechanics gain significant advantage

### 5.3 Critical Patching Rate
**Question:** What patching rate is required to contain outbreak?

**Method:**
- Vary patching rate: 0, 50, 100, 150, 200, 250, 300, 400, 500 sats/hour
- For each rate: Run 200 simulations, track infection over time

**Expected result:**
- Below 200 sats/hour: Infection grows to >80% (outbreak wins)
- Above 300 sats/hour: Infection declines to <10% (defense wins)
- Critical threshold: ~250 sats/hour (phase transition)

**Implication:** Operators need ground station network capable of 300+ sats/hour

### 5.4 Network Segmentation Trade-off
**Question:** Does dividing constellation into zones slow attacks?

**Test:** 1, 2, 4, 8, 16 zones with firewall detection at boundaries

**Results:**
- 1 zone: 90% infected in 6 hours
- 4 zones: 50% infected in 24 hours (optimal trade-off)
- 16 zones: 15% infected but +35% latency penalty (too costly)

**Recommendation:** 4-8 zones balances security vs. performance

### 5.5 Sensitivity Analysis
**Vary key parameters, measure impact on T50:**
- Infection rate β: 0.1 to 1.0 → Expect sigmoid relationship
- IDS coverage: 0% to 100% → Expect linear decrease in final infection
- Number of initial seeds: 1 to 100 → Expect threshold behavior
- Detection probability: 0.0 to 1.0 → Expect exponential relationship

**Deliverable:** Table showing which parameters most affect outcomes

---

## Phase 6: Paper & Documentation (Week 6)

### Goal
Publication-quality paper + open-source release.

### 6.1 Paper Structure (8-10 pages, IEEE format)

**Abstract (150 words):**
- Problem statement
- Gap in existing work
- Your solution
- Key findings (quantitative results)

**1. Introduction (1 page):**
- Motivation: LEO mega-constellations as critical infrastructure
- Challenge: Orbital dynamics create time-varying topology
- Research question: Do orbital mechanics change cyberattack propagation?
- Contributions: (1) First validated simulator, (2) Proof of eclipse vulnerabilities, (3) Optimal defense strategies

**2. Background (1 page):**
- LEO constellation basics
- Starlink architecture  
- Worm propagation models
- Related work (cite 3-5 key papers)

**3. System Design (2 pages):**
- Architecture diagram
- Orbital propagation (SGP4 + validation)
- Topology generation (+Grid algorithm)
- Simplified routing (time-slice Dijkstra)
- Worm model (SIR + routing-aware spreading)

**4. Validation (1 page):**
- Topology metrics vs. Bhattacherjee paper (table)
- Propagation accuracy (7-day TLE comparison)

**5. Experiments & Results (3 pages):**
- **5.1 Baseline:** Orbital vs. static topology (Figure: infection curves)
- **5.2 Eclipse timing:** Success rate comparison (Figure: bar chart)
- **5.3 Patching rate:** Critical threshold (Figure: phase transition)
- **5.4 Segmentation:** Security vs. latency trade-off (Figure: dual-axis)
- **5.5 Sensitivity:** Parameter importance (Table)

**6. Discussion (0.5 pages):**
- Implications for operators
- Limitations (simplified routing, no hardware failures)
- Future work

**7. Conclusion (0.5 pages):**
- Summary of findings
- Impact: Operators need orbital-aware security

**References:** 30-40 citations

### 6.2 Key Figures (Publication Quality)

**Figure 1 - Main Result (Orbital vs. Static Comparison):**
- X-axis: Time (hours)
- Y-axis: % of satellites infected
- Two curves: Static (smooth exponential) vs. Orbital (oscillating)
- Annotate: "Orbital dynamics create periodic vulnerability windows"

**Figure 2 - Eclipse Attack Effectiveness:**
- Bar chart comparing random timing vs. eclipse-timed
- Metrics: Time to 50% infection, detection rate
- Error bars from Monte Carlo runs

**Figure 3 - Critical Patching Rate:**
- X-axis: Patching rate (sats/hour)
- Y-axis: Final infection %
- Shows sharp drop at critical threshold (~250 sats/hour)

**Figure 4 - Network Segmentation Trade-off:**
- X-axis: Number of zones
- Left Y-axis: Infection % (bars, decreasing)
- Right Y-axis: Latency increase (line, increasing)
- Optimal: 4-8 zones

**Figure 5 - 3D Visualization:**
- Earth with orbital paths
- Satellites colored by state: Green (clean), Red (infected), Blue (patched)
- Animation showing infection spreading along orbital planes

### 6.3 GitHub Repository
**Structure:**
```
sim-leo/
├── README.md (installation, quick start, example usage)
├── docs/ (architecture, API reference, tutorial)
├── src/
│   ├── propagator.py (orbital mechanics)
│   ├── topology.py (network generation)
│   ├── routing.py (simplified packet forwarding)
│   ├── worm.py (attack model)
│   └── defense.py (IDS, patching, segmentation)
├── examples/
│   ├── 01_basic_propagation.ipynb
│   ├── 02_topology_generation.ipynb
│   ├── 03_worm_simulation.ipynb
│   └── 04_eclipse_attack.ipynb
├── data/ (sample TLEs, ground station locations)
└── results/ (figures, validation data)
```

**Key features:**
- Jupyter notebooks for reproducibility
- Command-line interface for batch experiments
- Configuration files (YAML) for parameter sweeps
- Visualization utilities (matplotlib, optional CesiumJS)

---

## Success Criteria Summary

### Week 1: ✅ Orbital Foundation
- TLE loading works for 1000+ satellites
- Propagation generates realistic trajectories
- Plane classification shows ~72 planes for Shell 1

### Week 2: ✅ Network Topology
- Topology metrics match literature (degree ~3.8, path ~15 hops)
- Link churn rate 2-5% per minute
- Network always connected

### Week 3: ✅ Routing
- Packets successfully route source → destination
- Paths change as topology evolves
- Ground station contact windows computed

### Week 4: ✅ Attack Models
- Worm spreads exponentially through network
- Eclipse timing affects success rate
- C2 constraints limit attacker effectiveness

### Week 5: ✅ Validation
- Baseline comparison proves orbital dynamics matter (20-40% difference)
- Eclipse attack experiment shows statistical significance
- Critical patching rate identified (~250 sats/hour)

### Week 6: ✅ Paper & Release
- 8-10 page paper with 5+ figures
- Open-source code on GitHub
- Reproducible experiments via Jupyter notebooks

---

## What Makes This Graduate-Level

1. **Novel Research Question:** First to quantify orbital-cyber coupling
2. **Rigorous Validation:** Topology metrics match published measurements
3. **Statistical Analysis:** Monte Carlo simulations (500+ runs per experiment)
4. **Theoretical Grounding:** SIR epidemic model adapted to time-varying networks
5. **Actionable Results:** Optimal defense strategies (patching rate, segmentation)
6. **Open Science:** Fully reproducible, open-source implementation

**Feasibility:** Each phase is 1 week, focuses on essential components only, prioritizes validation over perfection.
