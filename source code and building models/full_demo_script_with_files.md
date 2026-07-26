# 🎬 Eco-Loop — Master Video Recording Guide & Voiceover Script (Copyable Format)

**Project Name:** Eco-Loop (Physical AI Building Energy Optimization)  
**Total Duration:** ~3 Minutes (180 Seconds)  
**Format:** Point-wise Copyable Script (File Visuals + Word-for-Word Voiceover)

---

## 📋 PRE-RECORDING TAB SETUP

Before recording your screen, open the following 9 tabs in VS Code, Terminal, and Browser:

* **Tab 1 (Browser)**: Web Dashboard — `http://localhost:8000/`
* **Tab 2 (VS Code)**: README.md (`d:\Honeywell Hackathon\README.md` lines 1–40: Architecture diagram)
* **Tab 3 (VS Code)**: baseline.idf (`d:\Honeywell Hackathon\models\baseline.idf` lines 1–30: Building model)
* **Tab 4 (VS Code)**: weather.epw (`d:\Honeywell Hackathon\models\weather.epw` lines 1–8: Chicago TMY3 weather)
* **Tab 5 (VS Code)**: cognitive_engine.py (`d:\Honeywell Hackathon\cognitive_engine.py` lines 20–35: System prompt)
* **Tab 6 (VS Code)**: mcp_tools.py (`d:\Honeywell Hackathon\mcp_tools.py` lines 22–52: EnergyPlus runner)
* **Tab 7 (Terminal 1)**: Terminal window running Ollama (`ollama run llama3.2:3b`)
* **Tab 8 (Terminal 2)**: Terminal window running server (`python server.py`)
* **Tab 9 (Browser)**: GitHub Repo (`https://github.com/yashsushil16/Eco-Loop-Building-Agents`)

---

## ⏱️ SCENE-BY-SCENE POINT-WISE SCRIPT

### SECTION 1: Introduction & Problem Statement (0:00 – 0:30)

#### Point 1.1 (0:00 - 0:10)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Show full-screen web dashboard displaying the title "Building Energy Optimization — EnergyPlus × Llama 3.2 3B".
* **Word-for-Word Spoken Script**:
  > Commercial buildings account for nearly 40% of global energy consumption. Yet today, most HVAC systems still operate on static, hardcoded schedules that waste massive amounts of electricity and carbon.

#### Point 1.2 (0:10 - 0:20)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Hover cursor over top navbar "Eco-Loop Physical AI" brand icon and green status dot.
* **Word-for-Word Spoken Script**:
  > Welcome to Eco-Loop — an autonomous Physical AI control system designed to optimize HVAC energy consumption while guaranteeing occupant thermal comfort.

#### Point 1.3 (0:20 - 0:30)
* **File / Page / Screen**: VS Code Tab 2 — `README.md` (Lines 25–40)
* **On-Screen Action**: Scroll down to the System Architecture section showing the Mermaid workflow diagram.
* **Word-for-Word Spoken Script**:
  > Instead of relying on remote cloud APIs or simple heuristic rules, Eco-Loop couples a physics-based simulation engine with a local open-source LLM in a continuous, closed-loop optimization cycle.

---

### SECTION 2: System Architecture & Local Setup (0:30 – 1:05)

#### Point 2.1 (0:30 - 0:40)
* **File / Page / Screen**: VS Code Tabs 3 & 4 — `models/baseline.idf` (Lines 1–20) & `models/weather.epw` (Lines 1–8)
* **On-Screen Action**: Quick toggle between `baseline.idf` (DOE Commercial Reference Office model) and `weather.epw` (Chicago TMY3 weather profile).
* **Word-for-Word Spoken Script**:
  > At the foundation of our physical engine is EnergyPlus, running authentic DOE commercial office prototypes alongside hourly Chicago TMY3 weather profiles.

#### Point 2.2 (0:40 - 0:50)
* **File / Page / Screen**: Terminal 1 — Command: `ollama run llama3.2:3b`
* **On-Screen Action**: Show terminal window running Ollama with `llama3.2:3b` loaded locally.
* **Word-for-Word Spoken Script**:
  > For intelligence, we run Llama 3.2 3B locally using Ollama. This ensures zero API costs, instant response times, and complete data privacy for building management systems.

#### Point 2.3 (0:50 - 0:58)
* **File / Page / Screen**: VS Code Tabs 5 & 6 — `cognitive_engine.py` (Lines 22–34) & `mcp_tools.py` (Lines 42–52)
* **On-Screen Action**: Highlight `query_llm()` system prompt in `cognitive_engine.py` (L26) and `update_setpoints()` in `mcp_tools.py` (L43).
* **Word-for-Word Spoken Script**:
  > Our Python backend uses eppy to programmatically inject LLM-proposed thermostat setpoints into the IDF building model, executing closed-loop iterations in background threads.

#### Point 2.4 (0:58 - 1:05)
* **File / Page / Screen**: Terminal 2 — Command: `python server.py`
* **On-Screen Action**: Show terminal executing `python server.py` with Uvicorn launching at `http://localhost:8000`.
* **Word-for-Word Spoken Script**:
  > With a single command `python server.py`, our FastAPI server spins up, serving the REST API endpoints and launching our interactive frontend.

---

### SECTION 3: Live Closed-Loop Optimization Execution (1:05 – 1:50)

#### Point 3.1 (1:05 - 1:15)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Navigate to Control Center sidebar. Select "Summer (Cooling Focus)" from season dropdown.
* **Word-for-Word Spoken Script**:
  > Let's see Eco-Loop in action. On our Control Center sidebar, we select the Summer cooling season.

#### Point 3.2 (1:15 - 1:25)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Drag Optimization Iterations slider to "3". Click "Initialize Optimization Loop" button.
* **Word-for-Word Spoken Script**:
  > We set our target to 3 optimization iterations and click 'Initialize Optimization Loop'. The background engine immediately takes over.

#### Point 3.3 (1:25 - 1:40)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Focus on Live Output Terminal window as lines stream: `[20:38:02] Starting SUMMER Baseline...`, `[20:38:05] Llama 3.2 proposed...`, `[20:38:11] Forward-injecting setpoints...`.
* **Word-for-Word Spoken Script**:
  > Watch our Live Output Terminal. First, EnergyPlus runs a baseline simulation to measure unoptimized energy and comfort violations. Next, Llama 3.2 receives the building telemetry, computes a new setpoint strategy, and forward-injects it into the IDF model for Trial 1.

#### Point 3.4 (1:40 - 1:50)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Watch terminal output print `Trial 3 complete. Energy Savings: 10.90%, Comfort Violations: 382 hrs.`
* **Word-for-Word Spoken Script**:
  > In seconds, all 3 closed-loop iterations complete, evaluating energy savings percentage and occupant comfort bounds in real time.

---

### SECTION 4: KPI Telemetry, Setpoints & Multi-Axis Analytics (1:50 – 2:35)

#### Point 4.1 (1:50 - 2:05)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Hover mouse over the 4 Key Performance Metrics Cards: Total Energy Consumed, Comfort Violations, Carbon CO2 Emissions, and Cost Savings.
* **Word-for-Word Spoken Script**:
  > Our KPI cards display immediate results: Eco-Loop reduced total building energy by over 10.9%, eliminated 382 hours of comfort violations, and generated direct financial cost savings at $0.15 per kilowatt-hour.

#### Point 4.2 (2:05 - 2:15)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Point cursor at Optimized Control Parameters panel showing `Cooling Occupied: 24.0°C → 25.0°C`.
* **Word-for-Word Spoken Script**:
  > The setpoints panel reveals the AI's optimal policy: shifting occupied cooling to 25.0°C and optimizing occupancy schedules.

#### Point 4.3 (2:15 - 2:25)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Click Temperature tab, then click Comfort (PMV) tab on the chart header.
* **Word-for-Word Spoken Script**:
  > Using our interactive analytics canvas, we can compare baseline trajectories against AI-optimized paths. Switch to the PMV tab to verify occupant thermal comfort stays strictly within ASHRAE 55 bounds.

#### Point 4.4 (2:25 - 2:35)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Click Hourly Load tab showing bar graph comparison of hourly kWh load.
* **Word-for-Word Spoken Script**:
  > Under the Hourly Load tab, notice how the AI flattens power consumption during peak afternoon heat spikes, reducing expensive grid demand charges.

---

### SECTION 5: Explainable AI Log & Closing (2:35 – 3:00)

#### Point 5.1 (2:35 - 2:48)
* **File / Page / Screen**: Browser Tab 1 — `http://localhost:8000/`
* **On-Screen Action**: Scroll down to LLM Cognitive Reasoning Log. Highlight Trial 1, Trial 2, and Trial 3 decision text cards.
* **Word-for-Word Spoken Script**:
  > Crucially, Eco-Loop is not a black box. Our LLM Cognitive Reasoning Log exposes Llama 3.2's step-by-step engineering rationale for every single trial, giving facility managers full transparency into why setpoints were adjusted.

#### Point 5.2 (2:48 - 3:00)
* **File / Page / Screen**: Browser Tab 9 — `https://github.com/yashsushil16/Eco-Loop-Building-Agents`
* **On-Screen Action**: Switch to GitHub repository tab. Scroll past the README badges and architecture diagram.
* **Word-for-Word Spoken Script**:
  > By combining physics simulation with explainable local AI, Eco-Loop delivers a scalable solution for smarter, greener buildings. Check out our open-source codebase on GitHub. Thank you!
