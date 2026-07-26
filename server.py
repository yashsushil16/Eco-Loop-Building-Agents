import os
import json
import time
import shutil
import re
import threading
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI
from mcp_tools import BuildingAgentTools

app = FastAPI(title="Eco-Loop Building Optimization API")

# Workspace paths
output_dir = "d:\\Honeywell Hackathon\\sim_output"
os.makedirs(output_dir, exist_ok=True)
summary_path = os.path.join(output_dir, "summary.json")

# Global state for background optimization runs
state_lock = threading.Lock()
execution_state = {
    "running": False,
    "status_text": "Idle",
    "logs": ["Server initialized. Ready for closed-loop optimization."],
    "current_season": "winter",
    "history": [],
    "baseline_metrics": None,
    "optimal_metrics": None
}

def add_log(msg: str):
    timestamp = time.strftime("[%H:%M:%S]")
    with state_lock:
        execution_state["logs"].append(f"{timestamp} {msg}")

def load_summary_data():
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def parse_csv_timeseries(run_id, season):
    csv_path = os.path.join(output_dir, f"run_{run_id}.csv")
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
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
        df_filtered = df.loc[valid_idx].copy()
        
        # Identify columns
        cols = df_filtered.columns
        core_temp_col = [c for c in cols if 'CORE_ZN' in c and 'Zone Mean Air Temperature' in c][0]
        out_temp_col = [c for c in cols if 'Outdoor Air Drybulb Temperature' in c][0]
        elec_col = [c for c in cols if 'Electricity:Facility' in c and 'Hourly' in c][0]
        pmv_cols = [c for c in cols if 'CORE_ZN' in c and 'Thermal Comfort Fanger Model PMV' in c]
        
        timestamps = [str(t).strip() for t in df_filtered['Date/Time'].tolist()]
        core_temps = [round(float(v), 2) for v in df_filtered[core_temp_col].values]
        outdoor_temps = [round(float(v), 2) for v in df_filtered[out_temp_col].values]
        elec_kwh = [round(float(v) / 3.6e6, 3) for v in df_filtered[elec_col].values]
        pmv_values = [round(float(v), 3) for v in df_filtered[pmv_cols[0]].values] if pmv_cols else []
        
        return {
            "timestamps": timestamps,
            "core_temp": core_temps,
            "outdoor_temp": outdoor_temps,
            "electricity_kwh": elec_kwh,
            "pmv": pmv_values
        }
    except Exception as e:
        print(f"Error parsing CSV {csv_path}: {e}")
        return None

# --- API ENDPOINTS ---

@app.get("/api/summary")
def get_summary():
    """Returns the unified summary JSON for baseline vs optimal comparisons."""
    summary_data = load_summary_data()
    return summary_data

@app.get("/api/timeseries/{season}")
def get_timeseries(season: str):
    """Returns baseline and optimal timeseries data for plotting in JS."""
    summary_data = load_summary_data()
    if season not in summary_data:
        # Fallback to default filenames
        base_data = parse_csv_timeseries(f"{season}_baseline", season)
        opt_data = parse_csv_timeseries(f"{season}_optimal", season)
        return {
            "season": season,
            "baseline": base_data,
            "optimal": opt_data
        }
        
    season_info = summary_data[season]
    base_run_id = season_info.get("baseline", {}).get("run_id", f"{season}_baseline")
    opt_run_id = season_info.get("optimal", {}).get("run_id", f"{season}_optimal")
    
    base_data = parse_csv_timeseries(base_run_id, season)
    opt_data = parse_csv_timeseries(opt_run_id, season) or parse_csv_timeseries(f"{season}_optimal", season)
    
    return {
        "season": season,
        "baseline": base_data,
        "optimal": opt_data
    }

@app.get("/api/status")
def get_status():
    """Returns live execution state and logs for frontend polling."""
    with state_lock:
        return {
            "running": execution_state["running"],
            "status_text": execution_state["status_text"],
            "season": execution_state["current_season"],
            "logs": execution_state["logs"][-30:],  # Return last 30 log lines
            "baseline_metrics": execution_state["baseline_metrics"],
            "optimal_metrics": execution_state["optimal_metrics"],
            "history": execution_state["history"]
        }

def run_optimization_worker(season: str, num_iterations: int):
    """Background worker executing the EnergyPlus + Ollama closed loop."""
    tools = BuildingAgentTools()
    start_month, start_day, end_month, end_day = (1, 1, 1, 7) if season == "winter" else (7, 1, 7, 7)
    
    try:
        # 1. Run Baseline
        with state_lock:
            execution_state["status_text"] = "Running Baseline Simulation in EnergyPlus..."
        add_log(f"Starting {season.upper()} Baseline simulation...")
        
        baseline_id = f"{season}_baseline"
        baseline_res = tools.run_simulation(
            run_id=baseline_id,
            cool_occ=24.0, cool_unocc=26.7,
            heat_occ=21.0, heat_unocc=15.6,
            start_month=start_month, start_day=start_day,
            end_month=end_month, end_day=end_day,
            occ_start=6, occ_end=22
        )
        
        if not baseline_res["success"]:
            add_log(f"Baseline simulation failed: {baseline_res['error_msg']}")
            with state_lock:
                execution_state["running"] = False
                execution_state["status_text"] = "Baseline Failed"
            return

        base_metrics = baseline_res["metrics"]
        base_metrics["run_id"] = baseline_id
        with state_lock:
            execution_state["baseline_metrics"] = base_metrics
        add_log(f"Baseline complete. Total Energy: {base_metrics['total_energy_kwh']:.2f} kWh, Comfort Violations: {base_metrics['comfort_violations_hours']} hrs.")

        # 2. Optimization Iterations
        history = []
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        
        for i in range(num_iterations):
            with state_lock:
                execution_state["status_text"] = f"LLM Reasoning (Iteration {i+1}/{num_iterations})..."
            add_log(f"Iteration {i+1}: Constructing prompt payload for Llama 3.2 3B...")
            
            history_str = ""
            for idx, h in enumerate(history):
                history_str += f"\nTrial {idx+1} ({h['run_id']}): Setpoints [Cool Occ: {h['cool_occ']}C, Cool Unocc: {h['cool_unocc']}C, Heat Occ: {h['heat_occ']}C, Heat Unocc: {h['heat_unocc']}C, Start: {h['occ_start']}:00, End: {h['occ_end']}:00] -> Energy: {h['total_energy_kwh']:.2f} kWh, Comfort Violations: {h['comfort_violations_hours']} hrs."

            prompt = f"""
We are optimizing HVAC setpoints for a small office in Chicago.
Season: {season.upper()} (Simulation Period: Month {start_month}/Day {start_day} to Month {end_month}/Day {end_day})

Baseline Metrics:
  - Cooling Setpoints: Occupied 24.0 C, Unoccupied 26.7 C
  - Heating Setpoints: Occupied 21.0 C, Unoccupied 15.6 C
  - Occupancy Hours: Weekdays 06:00 to 22:00
  - Baseline Energy: {base_metrics['total_energy_kwh']:.2f} kWh
  - Baseline Comfort Violations: {base_metrics['comfort_violations_hours']} hours
  - Outdoor Temp Range: {base_metrics['min_outdoor_temp']:.1f} C to {base_metrics['max_outdoor_temp']:.1f} C

Trial History:
{history_str if history_str else "No trials yet."}

Propose the NEXT set of parameters to reduce total energy while keeping comfort violations low.
Search Bounds:
  - cool_occ: [22.0 to 26.0] C
  - cool_unocc: [26.0 to 30.0] C (>= cool_occ)
  - heat_occ: [19.0 to 23.0] C
  - heat_unocc: [12.0 to 18.0] C (<= heat_occ)
  - occ_start: [5 to 8] (Integer)
  - occ_end: [17 to 22] (Integer)

Output a reasoning paragraph followed by a JSON block:
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
            try:
                response = client.chat.completions.create(
                    model="llama3.2:3b",
                    messages=[
                        {"role": "system", "content": "You are a smart building control AI. Output reasoning then JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2
                )
                resp_text = response.choices[0].message.content
                match = re.search(r"```json\s*(\{.*?\})\s*```", resp_text, re.DOTALL) or re.search(r"(\{.*?\})", resp_text, re.DOTALL)
                if match:
                    params = json.loads(match.group(1))
                else:
                    raise ValueError("Could not parse JSON block from model response.")
                    
                add_log(f"Llama 3.2 proposed: Cool Occ {params['cool_occ']}C, Heat Occ {params['heat_occ']}C, Hours {params['occ_start']}:00-{params['occ_end']}:00.")
                
                # Execute simulation
                with state_lock:
                    execution_state["status_text"] = f"Running Simulation Trial {i+1} in EnergyPlus..."
                add_log(f"Forward-injecting setpoints into EnergyPlus IDF...")
                
                run_id = f"{season}_opt_iter_{i+1}"
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
                    savings_pct = (1.0 - (metrics["total_energy_kwh"] / base_metrics["total_energy_kwh"])) * 100.0
                    entry = {
                        "run_id": run_id,
                        "cool_occ": params["cool_occ"], "cool_unocc": params["cool_unocc"],
                        "heat_occ": params["heat_occ"], "heat_unocc": params["heat_unocc"],
                        "occ_start": params["occ_start"], "occ_end": params["occ_end"],
                        "savings_pct": savings_pct,
                        "reasoning": resp_text.split("```")[0].strip(),
                        **metrics
                    }
                    history.append(entry)
                    with state_lock:
                        execution_state["history"] = list(history)
                    add_log(f"Trial {i+1} complete. Energy Savings: {savings_pct:.2f}%, Comfort Violations: {metrics['comfort_violations_hours']} hrs.")
                else:
                    add_log(f"Trial {i+1} simulation failed: {sim_res['error_msg']}")
            except Exception as e:
                add_log(f"Iteration error: {e}")

        # 3. Complete and find optimal run
        best_score = float('inf')
        best_entry = None
        for h in history:
            score = h["total_energy_kwh"] + 10.0 * h["comfort_violations_hours"]
            if score < best_score:
                best_score = score
                best_entry = h

        if best_entry:
            with state_lock:
                execution_state["optimal_metrics"] = best_entry
            add_log(f"Optimization finished. Optimal Run: {best_entry['run_id']} ({best_entry['savings_pct']:.2f}% energy reduction).")
            
            # Save persistent files
            shutil.copy(
                os.path.join(tools.output_dir, f"run_{best_entry['run_id']}.csv"),
                os.path.join(tools.output_dir, f"{season}_optimal.csv")
            )
            
            summary_data = load_summary_data()
            summary_data[season] = {
                "baseline": base_metrics,
                "optimal": best_entry
            }
            with open(summary_path, "w") as f:
                json.dump(summary_data, f, indent=4)
                
    except Exception as e:
        add_log(f"Worker exception: {e}")
    finally:
        with state_lock:
            execution_state["running"] = False
            execution_state["status_text"] = "Completed"

@app.post("/api/optimize")
def start_optimization(payload: dict, background_tasks: BackgroundTasks):
    """Triggers the closed-loop optimization loop in the background."""
    season = payload.get("season", "winter").lower()
    iterations = payload.get("iterations", 3)
    
    with state_lock:
        if execution_state["running"]:
            raise HTTPException(status_code=400, detail="Optimization loop is already running.")
        execution_state["running"] = True
        execution_state["status_text"] = "Initializing..."
        execution_state["current_season"] = season
        execution_state["logs"] = []
        execution_state["history"] = []
        execution_state["baseline_metrics"] = None
        execution_state["optimal_metrics"] = None
        
    add_log(f"Initializing {season.upper()} optimization loop with {iterations} iterations...")
    background_tasks.add_task(run_optimization_worker, season, iterations)
    return {"status": "started", "season": season, "iterations": iterations}

# Serve static files from static directory
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
