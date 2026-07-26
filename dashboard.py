import os
import json
import time
import shutil
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from openai import OpenAI
from mcp_tools import BuildingAgentTools

# Configure visual style
st.set_page_config(page_title="Eco-Loop Building Optimization", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for modern light mint-emerald theme matching reference screenshot
st.markdown("""
<style>
    /* Main container background */
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
        font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px 22px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
        margin-bottom: 16px;
    }
    .metric-title {
        color: #64748b;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #0f172a;
        font-size: 30px;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .metric-delta {
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
    }
    .delta-positive {
        background-color: #ecfdf5;
        color: #047857;
    }
    .delta-negative {
        background-color: #fef2f2;
        color: #b91c1c;
    }
    
    /* Terminal Console Box */
    .terminal-box {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        font-family: 'ui-monospace', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace;
        color: #38bdf8;
        font-size: 13px;
        height: 245px;
        overflow-y: auto;
        margin-bottom: 20px;
    }

    /* Primary Mint Green Buttons */
    .stButton>button {
        background-color: #10b981 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25) !important;
        transition: all 0.2s ease !important;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #059669 !important;
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.35) !important;
    }

    /* Section Cards */
    .section-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
        margin-bottom: 20px;
    }

    h1, h2, h3, h4 {
        color: #0f172a !important;
        font-weight: 700 !important;
    }
    
    /* Setpoint Cards */
    .setpoint-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .setpoint-label {
        font-size: 12px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .setpoint-val {
        font-size: 16px;
        font-weight: 700;
        color: #0f172a;
    }
    .setpoint-badge {
        color: #059669;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize paths
output_dir = "d:\\Honeywell Hackathon\\sim_output"
os.makedirs(output_dir, exist_ok=True)
summary_path = os.path.join(output_dir, "summary.json")

# Helpers to load time-series CSVs
def load_single_run_csv(run_id, season):
    csv_path = os.path.join(output_dir, f"run_{run_id}.csv")
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    # Filter for weather run period (month matches)
    m_target = 1 if season == "winter" else 7
    valid_idx = []
    for idx, row in df.iterrows():
        try:
            parts = str(row['Date/Time']).strip().split()
            if len(parts) >= 2:
                m, d = map(int, parts[0].split("/"))
                if m == m_target and d <= 7:
                    valid_idx.append(idx)
        except Exception:
            continue
    return df.loc[valid_idx].copy()

# Header
st.title("Eco-Loop Building Optimization")
st.markdown("Physical AI Autonomous HVAC Control using EnergyPlus and Llama 3.2 3B.")

def load_existing_summary(season_key):
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                data = json.load(f)
                if season_key in data:
                    base_m = data[season_key].get("baseline")
                    opt_m = data[season_key].get("optimal")
                    return base_m, opt_m
        except Exception:
            pass
    return None, None

# Initialize session state for live running
if "running" not in st.session_state:
    st.session_state.running = False
if "history" not in st.session_state:
    st.session_state.history = []
if "season_key" not in st.session_state:
    st.session_state.season_key = "winter"

init_base, init_opt = load_existing_summary(st.session_state.season_key)

if "baseline_metrics" not in st.session_state or st.session_state.baseline_metrics is None:
    st.session_state.baseline_metrics = init_base
if "optimal_metrics" not in st.session_state or st.session_state.optimal_metrics is None:
    st.session_state.optimal_metrics = init_opt
if "logs" not in st.session_state or len(st.session_state.logs) == 0:
    st.session_state.logs = [f"Loaded {st.session_state.season_key.upper()} simulation records from disk."]
if "status_text" not in st.session_state:
    st.session_state.status_text = "Idle (Loaded simulation records)"

# Sidebar configuration
st.sidebar.title("Control Panel")
season_selection = st.sidebar.selectbox("Target Season", ["Winter (Heating focus)", "Summer (Cooling focus)"], disabled=st.session_state.running)
num_iterations = st.sidebar.slider("Optimization Iterations", min_value=1, max_value=5, value=3, disabled=st.session_state.running)

# Determine season key
season_key = "winter" if "Winter" in season_selection else "summer"
if season_key != st.session_state.season_key and not st.session_state.running:
    st.session_state.season_key = season_key
    st.session_state.history = []
    init_base, init_opt = load_existing_summary(season_key)
    st.session_state.baseline_metrics = init_base
    st.session_state.optimal_metrics = init_opt
    st.session_state.logs = [f"Loaded {season_key.upper()} simulation records from disk."]
    st.session_state.status_text = f"Idle (Loaded {season_key} records)"

def add_log(message):
    timestamp = time.strftime("[%H:%M:%S]")
    st.session_state.logs.append(f"{timestamp} {message}")

# Sidebar execution button
if st.sidebar.button("Initialize Optimization Loop", disabled=st.session_state.running):
    st.session_state.running = True
    st.session_state.history = []
    st.session_state.baseline_metrics = None
    st.session_state.optimal_metrics = None
    st.session_state.logs = []
    add_log(f"Initializing Closed-Loop Agent on Llama 3.2 3B client...")
    st.rerun()

# Run the live loop if state is running
if st.session_state.running and len(st.session_state.history) == 0 and st.session_state.baseline_metrics is None:
    st.session_state.status_text = "Running Baseline Simulation..."
    add_log(f"Running Baseline HVAC Control simulation in EnergyPlus...")
    st.rerun()

# Executing simulation phases
if st.session_state.running:
    tools = BuildingAgentTools()
    start_month, start_day, end_month, end_day = (1, 1, 1, 7) if st.session_state.season_key == "winter" else (7, 1, 7, 7)
    
    # PHASE 1: Run Baseline
    if st.session_state.baseline_metrics is None:
        baseline_id = f"{st.session_state.season_key}_baseline"
        
        # Run simulation
        res = tools.run_simulation(
            run_id=baseline_id,
            cool_occ=24.0, cool_unocc=26.7,
            heat_occ=21.0, heat_unocc=15.6,
            start_month=start_month, start_day=start_day,
            end_month=end_month, end_day=end_day,
            occ_start=6, occ_end=22
        )
        
        if res["success"]:
            st.session_state.baseline_metrics = res["metrics"]
            add_log(f"Baseline complete. Energy: {res['metrics']['total_energy_kwh']:.2f} kWh, Comfort Violations: {res['metrics']['comfort_violations_hours']} hours.")
            add_log(f"Data streamed from EnergyPlus to cognitive wrapper.")
        else:
            add_log(f"Baseline simulation failed: {res['error_msg']}")
            st.session_state.running = False
        st.rerun()
        
    # PHASE 2: Iterative LLM optimization
    current_iter = len(st.session_state.history)
    if current_iter < num_iterations:
        st.session_state.status_text = f"LLM Reasoning (Iteration {current_iter+1}/{num_iterations})..."
        add_log(f"Constructing feedback prompt for local LLM...")
        
        # Build prompt payload
        history_str = ""
        for i, h in enumerate(st.session_state.history):
            history_str += f"\nTrial {i+1} (Run ID: {h['run_id']}): Setpoints [Cool Occ: {h['cool_occ']}C, Cool Unocc: {h['cool_unocc']}C, Heat Occ: {h['heat_occ']}C, Heat Unocc: {h['heat_unocc']}C, Start: {h['occ_start']}:00, End: {h['occ_end']}:00] -> Energy: {h['total_energy_kwh']:.2f} kWh, Comfort Violations: {h['comfort_violations_hours']} hrs, Avg PMV: {h['average_pmv']:.3f}."
            
        base = st.session_state.baseline_metrics
        prompt = f"""
We are optimizing setpoint schedules for a small office in Chicago.
Season: {st.session_state.season_key.upper()} (Simulation Period: Month {start_month}/Day {start_day} to Month {end_month}/Day {end_day})

Baseline HVAC Configuration:
  - Cooling Occupied Setpoint: 24.0 C, Unoccupied: 26.7 C
  - Heating Occupied Setpoint: 21.0 C, Unoccupied: 15.6 C
  - Occupancy: Weekdays 06:00 to 22:00
  - Baseline Energy: {base['total_energy_kwh']:.2f} kWh
  - Baseline Comfort Violations: {base['comfort_violations_hours']} hours
  - Outdoor Temp Range: {base['min_outdoor_temp']:.1f} C to {base['max_outdoor_temp']:.1f} C

Previous Trials History:
{history_str if history_str else "No trials yet."}

Propose the NEXT set of setpoint parameters to minimize total energy while keeping comfort violations low.
Select within these bounds:
  - cool_occ: [22.0 to 26.0] C
  - cool_unocc: [26.0 to 30.0] C (>= cool_occ)
  - heat_occ: [19.0 to 23.0] C
  - heat_unocc: [12.0 to 18.0] C (<= heat_occ)
  - occ_start: [5 to 8] (Integer, e.g. 7 for 07:00)
  - occ_end: [17 to 22] (Integer, e.g. 20 for 20:00)

Provide a short reasoning paragraph, then a JSON block containing your proposed values.
```json
{{
  "cool_occ": 24.5,
  "cool_unocc": 27.5,
  "heat_occ": 20.5,
  "heat_unocc": 14.5,
  "occ_start": 7,
  "occ_end": 20
}}
```
"""
        add_log(f"Streaming metrics payload (size: {len(prompt)} chars) to Llama 3.2 3B...")
        
        # Connect to local Ollama
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        try:
            response = client.chat.completions.create(
                model="llama3.2:3b",
                messages=[
                    {"role": "system", "content": "You are a smart building control AI. Output reasoning then a valid JSON block of setpoints."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            resp_text = response.choices[0].message.content
            
            # Parse parameters
            match = re.search(r"```json\s*(\{.*?\})\s*```", resp_text, re.DOTALL)
            if not match:
                match = re.search(r"(\{.*?\})", resp_text, re.DOTALL)
            
            if match:
                params = json.loads(match.group(1))
            else:
                raise ValueError("Could not parse JSON block from model response.")
                
            add_log(f"LLM Reasoning complete. Proposed Setpoints: Cool Occ: {params['cool_occ']}C, Heat Occ: {params['heat_occ']}C. Occupancy: {params['occ_start']}:00-{params['occ_end']}:00")
            
            # PHASE 3: Run simulation with LLM parameters
            st.session_state.status_text = f"Running Simulation Trial {current_iter+1}..."
            add_log(f"Forward-injecting control actions into EnergyPlus IDF...")
            
            run_id = f"{st.session_state.season_key}_opt_iter_{current_iter+1}"
            sim_res = tools.run_simulation(
                run_id=run_id,
                cool_occ=params["cool_occ"], cool_unocc=params["cool_unocc"],
                heat_occ=params["heat_occ"], heat_unocc=params["heat_unocc"],
                start_month=start_month, start_day=start_day,
                end_month=end_month, end_day=end_day,
                occ_start=params["occ_start"], occ_end=params["occ_end"]
            )
            
            if sim_res["success"]:
                metrics = sim_res["metrics"]
                savings_pct = (1.0 - (metrics["total_energy_kwh"] / base["total_energy_kwh"])) * 100.0
                
                # Record to history
                entry = {
                    "run_id": run_id,
                    "cool_occ": params["cool_occ"], "cool_unocc": params["cool_unocc"],
                    "heat_occ": params["heat_occ"], "heat_unocc": params["heat_unocc"],
                    "occ_start": params["occ_start"], "occ_end": params["occ_end"],
                    "savings_pct": savings_pct,
                    "reasoning": resp_text.split("```")[0].strip(),
                    **metrics
                }
                st.session_state.history.append(entry)
                add_log(f"Simulation {current_iter+1} done. Energy savings: {savings_pct:.2f}%. Comfort violations: {metrics['comfort_violations_hours']} hours.")
            else:
                add_log(f"Simulation failed: {sim_res['error_msg']}")
                
        except Exception as e:
            add_log(f"Execution error: {str(e)}")
            st.session_state.running = False
            
        st.rerun()
        
    # PHASE 4: Optimization completed, select best run
    else:
        st.session_state.status_text = "Completed"
        add_log(f"Closed-loop optimization completed.")
        
        # Calculate composite score for each trial to find the best run
        best_score = float('inf')
        best_entry = None
        for h in st.session_state.history:
            score = h["total_energy_kwh"] + 10.0 * h["comfort_violations_hours"]
            if score < best_score:
                best_score = score
                best_entry = h
                
        if best_entry:
            st.session_state.optimal_metrics = best_entry
            add_log(f"Optimal trial identified: {best_entry['run_id']} with savings {best_entry['savings_pct']:.2f}%.")
            
            # Save to summary persistent records
            shutil.copy(
                os.path.join(tools.output_dir, f"run_{best_entry['run_id']}.csv"),
                os.path.join(tools.output_dir, f"{st.session_state.season_key}_optimal.csv")
            )
            
            # Update summary.json
            summary_data = {}
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, "r") as f:
                        summary_data = json.load(f)
                except Exception:
                    pass
            
            summary_data[st.session_state.season_key] = {
                "baseline": st.session_state.baseline_metrics,
                "optimal": best_entry
            }
            # Add run_id explicitly inside baseline
            summary_data[st.session_state.season_key]["baseline"]["run_id"] = f"{st.session_state.season_key}_baseline"
            
            with open(summary_path, "w") as f:
                json.dump(summary_data, f, indent=4)
                
        st.session_state.running = False
        st.rerun()

# Render status in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("System Status")
if st.session_state.running:
    st.sidebar.markdown(f"**Status:** Running (`{st.session_state.status_text}`)")
else:
    st.sidebar.markdown(f"**Status:** Idle (`{st.session_state.status_text}`)")

# Layout: Console log & metrics cards
col_log, col_kpis = st.columns([1.5, 2.5])

with col_log:
    st.subheader("Live Data Log Console")
    log_content = "\n".join(st.session_state.logs[::-1])  # Show newest on top
    st.markdown(f'<div class="terminal-box">{log_content.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

# KPI Cards
with col_kpis:
    st.subheader("Key Performance Metrics")
    kpi_col1, kpi_col2 = st.columns(2)
    kpi_col3, kpi_col4 = st.columns(2)
    
    base = st.session_state.baseline_metrics
    opt = st.session_state.optimal_metrics if st.session_state.optimal_metrics else (st.session_state.history[-1] if st.session_state.history else None)
    
    if base:
        # Energy Card
        with kpi_col1:
            if opt:
                saved_pct = opt["savings_pct"]
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Total Energy Consumed</div>
                    <div class="metric-value">{opt['total_energy_kwh']:.1f} kWh</div>
                    <div class="metric-delta delta-positive">-{saved_pct:.1f}% vs Baseline ({base['total_energy_kwh']:.1f} kWh)</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Total Energy Consumed</div>
                    <div class="metric-value">{base['total_energy_kwh']:.1f} kWh</div>
                    <div class="metric-delta">Baseline Active</div>
                </div>
                """, unsafe_allow_html=True)
                
        # Comfort Card
        with kpi_col2:
            if opt:
                delta_violations = base["comfort_violations_hours"] - opt["comfort_violations_hours"]
                sign = "-" if delta_violations >= 0 else "+"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Occupant Comfort Violations</div>
                    <div class="metric-value">{opt['comfort_violations_hours']} Hours</div>
                    <div class="metric-delta delta-positive">{sign}{abs(delta_violations)} Hours vs Baseline ({base['comfort_violations_hours']} hrs)</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Occupant Comfort Violations</div>
                    <div class="metric-value">{base['comfort_violations_hours']} Hours</div>
                    <div class="metric-delta">Baseline Active</div>
                </div>
                """, unsafe_allow_html=True)
                
        # Carbon Card
        with kpi_col3:
            if opt:
                co2_pct = (1.0 - (opt["co2_kg"] / base["co2_kg"])) * 100.0
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Carbon CO2 Emissions</div>
                    <div class="metric-value">{opt['co2_kg']:.1f} kg</div>
                    <div class="metric-delta delta-positive">-{co2_pct:.1f}% vs Baseline ({base['co2_kg']:.1f} kg)</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Carbon CO2 Emissions</div>
                    <div class="metric-value">{base['co2_kg']:.1f} kg</div>
                    <div class="metric-delta">Baseline Active</div>
                </div>
                """, unsafe_allow_html=True)
                
        # Cost Savings Card
        with kpi_col4:
            if opt:
                cost_saved = (base["total_energy_kwh"] - opt["total_energy_kwh"]) * 0.15
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Estimated Cost Savings</div>
                    <div class="metric-value">${cost_saved:.2f}</div>
                    <div class="metric-delta delta-positive">Savings at $0.15/kWh rate</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Estimated Cost Savings</div>
                    <div class="metric-value">$0.00</div>
                    <div class="metric-delta">Baseline Active</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Metrics will display here once simulation is initialized.")

# Setpoint Parameter Badges
if opt:
    st.subheader("Optimized Control Parameters")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown(f"""
        <div class="setpoint-card">
            <div class="setpoint-label">Cooling Occupied</div>
            <div class="setpoint-val">24.0°C → <span class="setpoint-badge">{opt['cool_occ']}°C</span></div>
        </div>
        """, unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="setpoint-card">
            <div class="setpoint-label">Cooling Unoccupied</div>
            <div class="setpoint-val">26.7°C → <span class="setpoint-badge">{opt['cool_unocc']}°C</span></div>
        </div>
        """, unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""
        <div class="setpoint-card">
            <div class="setpoint-label">Heating Occupied</div>
            <div class="setpoint-val">21.0°C → <span class="setpoint-badge">{opt['heat_occ']}°C</span></div>
        </div>
        """, unsafe_allow_html=True)
    with sc4:
        st.markdown(f"""
        <div class="setpoint-card">
            <div class="setpoint-label">Heating Unoccupied</div>
            <div class="setpoint-val">15.6°C → <span class="setpoint-badge">{opt['heat_unocc']}°C</span></div>
        </div>
        """, unsafe_allow_html=True)

# LLM Reasoning Feeds
if st.session_state.history:
    st.subheader("LLM Cognitive Reasoning Log")
    for idx, h in enumerate(st.session_state.history):
        with st.expander(f"Trial {idx+1} Reasoning ({h['run_id']})"):
            st.markdown(f"**Parameters set:** Cool Occ: {h['cool_occ']}°C, Heat Occ: {h['heat_occ']}°C. Occupancy: {h['occ_start']}:00-{h['occ_end']}:00")
            st.info(h["reasoning"])

# Time-series charts comparison
if base:
    st.subheader("Performance Analytics")
    
    # Load csv data frames
    base_df = load_single_run_csv(f"{st.session_state.season_key}_baseline", st.session_state.season_key)
    
    opt_run_id = None
    if st.session_state.optimal_metrics:
        opt_run_id = st.session_state.optimal_metrics["run_id"]
    elif st.session_state.history:
        opt_run_id = st.session_state.history[-1]["run_id"]
        
    opt_df = load_single_run_csv(opt_run_id, st.session_state.season_key) if opt_run_id else None
    
    if base_df is not None:
        # Get column names
        core_temp_col = [c for c in base_df.columns if 'CORE_ZN' in c and 'Zone Mean Air Temperature' in c][0]
        out_temp_col = [c for c in base_df.columns if 'Outdoor Air Drybulb Temperature' in c][0]
        elec_col_b = [c for c in base_df.columns if 'Electricity:Facility' in c and 'Hourly' in c][0]
        pmv_cols = [c for c in base_df.columns if 'CORE_ZN' in c and 'Thermal Comfort Fanger Model PMV' in c]
        
        tab_temp, tab_pmv, tab_energy = st.tabs(["Temperature Profiles", "Occupant Comfort (PMV)", "Hourly Power Load"])
        
        # Configure crisp light theme for Matplotlib charts
        plt.rcParams['font.sans-serif'] = 'Inter'
        plt.rcParams['axes.edgecolor'] = '#e2e8f0'
        plt.rcParams['axes.linewidth'] = 1.0

        with tab_temp:
            fig, ax = plt.subplots(figsize=(12, 4.5))
            fig.patch.set_facecolor('#ffffff')
            ax.set_facecolor('#ffffff')
            
            plt.plot(base_df['Date/Time'].values, base_df[core_temp_col].values, label='Baseline Core Temp', color='#94a3b8', linestyle='--', linewidth=1.5)
            if opt_df is not None:
                plt.plot(opt_df['Date/Time'].values, opt_df[core_temp_col].values, label='AI-Optimized Core Temp', color='#10b981', linewidth=2.2)
                # Fill area under optimized temp curve
                plt.fill_between(range(len(opt_df)), opt_df[core_temp_col].values, alpha=0.08, color='#10b981')
            plt.plot(base_df['Date/Time'].values, base_df[out_temp_col].values, label='Outdoor Temperature', color='#64748b', alpha=0.4, linestyle=':')
            
            plt.xticks(np.arange(0, len(base_df), 24), labels=base_df['Date/Time'].values[::24], rotation=0, color='#64748b', fontsize=10)
            plt.yticks(color='#64748b', fontsize=10)
            plt.ylabel("Temperature (°C)", color='#0f172a', fontweight='600')
            plt.grid(True, linestyle='--', alpha=0.4, color='#e2e8f0')
            plt.legend(facecolor='#ffffff', edgecolor='#e2e8f0', labelcolor='#0f172a')
            
            # Spines
            for spine in ax.spines.values():
                spine.set_color('#e2e8f0')
                
            st.pyplot(fig)
            
        with tab_pmv:
            if pmv_cols:
                pmv_col = pmv_cols[0]
                fig2, ax2 = plt.subplots(figsize=(12, 4.5))
                fig2.patch.set_facecolor('#ffffff')
                ax2.set_facecolor('#ffffff')
                
                plt.plot(base_df['Date/Time'].values, base_df[pmv_col].values, label='Baseline PMV', color='#94a3b8', linestyle='--', linewidth=1.5)
                if opt_df is not None:
                    plt.plot(opt_df['Date/Time'].values, opt_df[pmv_col].values, label='AI-Optimized PMV', color='#10b981', linewidth=2.2)
                    plt.fill_between(range(len(opt_df)), opt_df[pmv_col].values, alpha=0.08, color='#10b981')
                plt.axhline(0.5, color='#ef4444', alpha=0.5, linestyle=':', label='Comfort Window (+0.5 / -0.5)')
                plt.axhline(-0.5, color='#ef4444', alpha=0.5, linestyle=':')
                
                plt.xticks(np.arange(0, len(base_df), 24), labels=base_df['Date/Time'].values[::24], rotation=0, color='#64748b', fontsize=10)
                plt.yticks(color='#64748b', fontsize=10)
                plt.ylabel("PMV Index", color='#0f172a', fontweight='600')
                plt.grid(True, linestyle='--', alpha=0.4, color='#e2e8f0')
                plt.legend(facecolor='#ffffff', edgecolor='#e2e8f0', labelcolor='#0f172a')
                
                for spine in ax2.spines.values():
                    spine.set_color('#e2e8f0')
                    
                st.pyplot(fig2)
            else:
                st.warning("PMV comfort variables not found in output files.")
                
        with tab_energy:
            fig3, ax3 = plt.subplots(figsize=(12, 4.5))
            fig3.patch.set_facecolor('#ffffff')
            ax3.set_facecolor('#ffffff')
            
            x_indices = np.arange(len(base_df))
            plt.bar(x_indices - 0.2, base_df[elec_col_b].values / 3.6e6, width=0.4, label='Baseline Hourly Energy', color='#cbd5e1', alpha=0.8)
            if opt_df is not None:
                plt.bar(x_indices + 0.2, opt_df[elec_col_b].values / 3.6e6, width=0.4, label='AI-Optimized Hourly Energy', color='#10b981', alpha=0.9)
                
            plt.xticks(np.arange(0, len(base_df), 24), labels=base_df['Date/Time'].values[::24], rotation=0, color='#64748b', fontsize=10)
            plt.yticks(color='#64748b', fontsize=10)
            plt.ylabel("Electricity (kWh)", color='#0f172a', fontweight='600')
            plt.grid(True, linestyle='--', alpha=0.4, color='#e2e8f0')
            plt.legend(facecolor='#ffffff', edgecolor='#e2e8f0', labelcolor='#0f172a')
            
            for spine in ax3.spines.values():
                spine.set_color('#e2e8f0')
                
            st.pyplot(fig3)
