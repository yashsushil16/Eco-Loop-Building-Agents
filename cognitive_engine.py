import os
import json
import argparse
import sys
import re
import shutil
from openai import OpenAI
from mcp_tools import BuildingAgentTools

class BuildingCognitiveEngine:
    def __init__(self, model_name="llama3.2:3b", api_url="http://localhost:11434/v1"):
        self.model_name = model_name
        self.api_url = api_url
        self.client = OpenAI(base_url=self.api_url, api_key="ollama")
        self.tools = BuildingAgentTools()

    def query_llm(self, prompt):
        """
        Sends the prompt to Ollama LLM and returns the response.
        """
        try:
            print(f"Sending prompt to local LLM ({self.model_name})...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert Energy Management System (EMS) AI. Your job is to optimize building heating and cooling temperature setpoints and occupancy schedules to minimize energy consumption (kWh) while maintaining occupant thermal comfort (Predicted Mean Vote PMV between -0.5 and 0.5)."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error communicating with local LLM: {e}")
            sys.exit(1)

    def parse_llm_json(self, response_text):
        """
        Extracts the JSON block from the LLM's response.
        """
        # Search for ```json ... ``` blocks first
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if not match:
            # Fallback to search for any JSON-like dict in the text
            match = re.search(r"(\{.*?\})", response_text, re.DOTALL)
            
        if match:
            try:
                data = json.loads(match.group(1))
                # Validate fields
                required_keys = ["cool_occ", "cool_unocc", "heat_occ", "heat_unocc", "occ_start", "occ_end"]
                for k in required_keys:
                    if k not in data:
                        raise ValueError(f"Missing key in JSON: {k}")
                return data
            except Exception as e:
                print(f"Failed to parse JSON from match: {e}")
                
        print("Raw response text was:")
        print(response_text)
        return None

    def build_prompt(self, season, start_month, start_day, end_month, end_day, history, baseline_metrics):
        """
        Constructs the detailed prompt for the LLM.
        """
        history_str = ""
        for i, h in enumerate(history):
            history_str += f"""
Trial {i+1} (Run ID: {h['run_id']}):
  - Cooling Occupied Setpoint: {h['cool_occ']} C
  - Cooling Unoccupied Setpoint: {h['cool_unocc']} C
  - Heating Occupied Setpoint: {h['heat_occ']} C
  - Heating Unoccupied Setpoint: {h['heat_unocc']} C
  - Occupancy Start Hour: {h['occ_start']}:00, End Hour: {h['occ_end']}:00
  - Electricity Consumed: {h['electricity_kwh']:.2f} kWh
  - Gas Consumed: {h['gas_kwh']:.2f} kWh
  - Total Energy Consumed: {h['total_energy_kwh']:.2f} kWh (Savings vs Baseline: {h['savings_pct']:.1f}%)
  - Comfort PMV (Occupied Hours Average): {h['average_pmv']:.3f}
  - Occupied Comfort Violations: {h['comfort_violations_hours']} hours (Violation Rate: {h['comfort_violation_rate']*100:.1f}%)
"""

        prompt = f"""
We are optimizing the temperature setpoint schedules for a 1-story commercial small office building in Chicago.
Current Season: {season.upper()} (Simulation Period: Month {start_month}/Day {start_day} to Month {end_month}/Day {end_day})

Baseline HVAC Configuration:
  - Cooling Occupied Setpoint: 24.0 C
  - Cooling Unoccupied Setpoint: 26.7 C
  - Heating Occupied Setpoint: 21.0 C
  - Heating Unoccupied Setpoint: 15.6 C
  - Occupancy Schedule: Weekdays 06:00 to 22:00, Saturday 06:00 to 18:00
  - Baseline Electricity Consumed: {baseline_metrics['electricity_kwh']:.2f} kWh
  - Baseline Gas Consumed: {baseline_metrics['gas_kwh']:.2f} kWh
  - Baseline Total Energy Consumed: {baseline_metrics['total_energy_kwh']:.2f} kWh
  - Baseline Comfort Violations: {baseline_metrics['comfort_violations_hours']} hours (Violation Rate: {baseline_metrics['comfort_violation_rate']*100:.1f}%)
  - Weather Outdoor Temp Range: {baseline_metrics['min_outdoor_temp']:.1f} C to {baseline_metrics['max_outdoor_temp']:.1f} C

History of Previous Optimization Trials:
{history_str if history_str else "No trials yet."}

Your task:
Analyze the results from the trials and propose the NEXT set of setpoints and occupancy hours to test.
Our target is to reduce total energy (kWh) compared to the baseline while keeping occupied hours comfort violations as close to 0 as possible. 
Note: The Predicted Mean Vote (PMV) thermal comfort index ranges from -3 (cold) to +3 (hot). Comfort boundary is [-0.5, 0.5]. 
- If average PMV is negative (e.g. -0.8), occupants are cold, meaning heating occupied setpoints are too low or occupancy starts too late.
- If average PMV is positive (e.g. +0.8), occupants are hot, meaning cooling occupied setpoints are too high or occupancy starts too late.

Please adhere to the following physical boundaries:
  - Cooling occupied setpoint (`cool_occ`): [22.0 to 26.0] C
  - Cooling unoccupied setpoint (`cool_unocc`): [26.0 to 30.0] C (Must be >= cool_occ)
  - Heating occupied setpoint (`heat_occ`): [19.0 to 23.0] C
  - Heating unoccupied setpoint (`heat_unocc`): [12.0 to 18.0] C (Must be <= heat_occ)
  - Occupancy start hour (`occ_start`): [5 to 8] (Integer representing 24h format, e.g. 7 means 07:00)
  - Occupancy end hour (`occ_end`): [17 to 22] (Integer representing 24h format, e.g. 20 means 20:00)

Provide a short reasoning (1 paragraph) explaining the physics-based changes you are making (e.g. widening deadbands, shifting hours, or adjust night setbacks), followed by a JSON block containing your proposed values.

Example Output format:
Reasoning: Since the average PMV in Trial 1 was -0.88, the building was too cold. I will increase the occupied heating setpoint to 20.5 C and shift the occupancy start hour to 07:00 to preheat the building, while lowering the unoccupied heating setpoint to 14.5 C to save overnight energy.
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
        return prompt

    def optimize_season(self, season="winter", iterations=3):
        """
        Runs the closed-loop optimization for the specified season.
        """
        print(f"\n==========================================")
        print(f"Starting {season.upper()} Optimization Loop")
        print(f"==========================================")
        
        # Define simulation dates
        if season.lower() == "winter":
            start_month, start_day, end_month, end_day = 1, 1, 1, 7
        else:
            start_month, start_day, end_month, end_day = 7, 1, 7, 7

        # 1. Run Baseline Simulation
        baseline_id = f"{season}_baseline"
        print(f"Running baseline simulation: {baseline_id}")
        baseline_res = self.tools.run_simulation(
            run_id=baseline_id,
            cool_occ=24.0,
            cool_unocc=26.7,
            heat_occ=21.0,
            heat_unocc=15.6,
            start_month=start_month,
            start_day=start_day,
            end_month=end_month,
            end_day=end_day,
            occ_start=6,
            occ_end=22
        )
        
        if not baseline_res["success"]:
            print(f"Baseline simulation failed: {baseline_res['error_msg']}")
            sys.exit(1)
            
        baseline_metrics = baseline_res["metrics"]
        print(f"Baseline Energy: {baseline_metrics['total_energy_kwh']:.2f} kWh (Elec: {baseline_metrics['electricity_kwh']:.2f}, Gas: {baseline_metrics['gas_kwh']:.2f})")
        print(f"Baseline Comfort Violations: {baseline_metrics['comfort_violations_hours']} hours (Rate: {baseline_metrics['comfort_violation_rate']*100:.1f}%)")

        history = []
        best_score = float('inf')
        best_run = None

        # 2. Iterate Optimization Loop
        for i in range(iterations):
            print(f"\n--- Iteration {i+1} of {iterations} ---")
            prompt = self.build_prompt(season, start_month, start_day, end_month, end_day, history, baseline_metrics)
            
            # Query LLM
            llm_response = self.query_llm(prompt)
            
            # Parse parameters
            params = self.parse_llm_json(llm_response)
            if not params:
                print("Failed to get valid JSON from LLM. Retrying with a simpler request...")
                # Fallback to default baseline changes
                params = {
                    "cool_occ": 24.5 if season == "summer" else 24.0,
                    "cool_unocc": 27.5 if season == "summer" else 26.7,
                    "heat_occ": 20.0 if season == "winter" else 21.0,
                    "heat_unocc": 14.5 if season == "winter" else 15.6,
                    "occ_start": 7,
                    "occ_end": 20
                }
                
            print(f"LLM proposed parameters: {params}")
            
            # Run simulation with LLM parameters
            run_id = f"{season}_opt_iter_{i+1}"
            sim_res = self.tools.run_simulation(
                run_id=run_id,
                cool_occ=params["cool_occ"],
                cool_unocc=params["cool_unocc"],
                heat_occ=params["heat_occ"],
                heat_unocc=params["heat_unocc"],
                start_month=start_month,
                start_day=start_day,
                end_month=end_month,
                end_day=end_day,
                occ_start=params["occ_start"],
                occ_end=params["occ_end"]
            )
            
            if not sim_res["success"]:
                print(f"Simulation trial failed: {sim_res['error_msg']}")
                # We record it as a failed run and keep going
                continue
                
            metrics = sim_res["metrics"]
            savings_pct = (1.0 - (metrics["total_energy_kwh"] / baseline_metrics["total_energy_kwh"])) * 100.0
            
            # Add to history
            metrics_entry = {
                "run_id": run_id,
                "cool_occ": params["cool_occ"],
                "cool_unocc": params["cool_unocc"],
                "heat_occ": params["heat_occ"],
                "heat_unocc": params["heat_unocc"],
                "occ_start": params["occ_start"],
                "occ_end": params["occ_end"],
                "savings_pct": savings_pct,
                **metrics
            }
            history.append(metrics_entry)
            
            print(f"Trial Result - Total Energy: {metrics['total_energy_kwh']:.2f} kWh (Savings: {savings_pct:.2f}%)")
            print(f"Trial Result - Comfort Violations: {metrics['comfort_violations_hours']} hours (Rate: {metrics['comfort_violation_rate']*100:.1f}%)")
            
            # Evaluate Performance Score
            # Penalty for comfort violations: 10 kWh per violation hour
            # Objective: Minimize Score = Energy_kWh + 10 * Violations
            score = metrics["total_energy_kwh"] + 10.0 * metrics["comfort_violations_hours"]
            print(f"Composite Performance Score: {score:.2f} (Lower is better)")
            
            if score < best_score:
                best_score = score
                best_run = metrics_entry
                
        # 3. Complete loop and save optimal
        print(f"\n=== {season.upper()} Optimization Finished ===")
        if best_run:
            print(f"Optimal Run ID: {best_run['run_id']}")
            print(f"Optimal Energy: {best_run['total_energy_kwh']:.2f} kWh (Savings vs Baseline: {best_run['savings_pct']:.2f}%)")
            print(f"Optimal Comfort Violations: {best_run['comfort_violations_hours']} hours")
            
            # Copy optimal results file to standard output path
            shutil.copy(
                os.path.join(self.tools.output_dir, f"run_{best_run['run_id']}.csv"),
                os.path.join(self.tools.output_dir, f"{season}_optimal.csv")
            )
            with open(os.path.join(self.tools.output_dir, f"metrics_{season}_optimal.json"), "w") as f:
                json.dump(best_run, f, indent=4)
        else:
            print("No successful optimization runs completed.")
            
        return {
            "baseline": baseline_metrics,
            "optimal": best_run
        }

    def run_full_pipeline(self, iterations=3):
        """
        Executes both winter and summer optimizations and writes a final summary file.
        """
        winter_res = self.optimize_season("winter", iterations=iterations)
        summer_res = self.optimize_season("summer", iterations=iterations)
        
        # Save unified summary
        summary = {
            "winter": {
                "baseline": winter_res["baseline"],
                "optimal": winter_res["optimal"]
            },
            "summer": {
                "baseline": summer_res["baseline"],
                "optimal": summer_res["optimal"]
            }
        }
        
        summary_path = os.path.join(self.tools.output_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=4)
            
        print("\n==========================================")
        print("Closed-loop Building Optimization Summary")
        print("==========================================")
        
        w_base = summary["winter"]["baseline"]
        w_opt = summary["winter"]["optimal"]
        if w_opt:
            print(f"Winter (Heating) Savings: {w_base['total_energy_kwh']:.2f} kWh -> {w_opt['total_energy_kwh']:.2f} kWh ({w_opt['savings_pct']:.1f}% reduction)")
            print(f"  Comfort Violations: {w_base['comfort_violations_hours']} hrs -> {w_opt['comfort_violations_hours']} hrs")
            
        s_base = summary["summer"]["baseline"]
        s_opt = summary["summer"]["optimal"]
        if s_opt:
            print(f"Summer (Cooling) Savings: {s_base['total_energy_kwh']:.2f} kWh -> {s_opt['total_energy_kwh']:.2f} kWh ({s_opt['savings_pct']:.1f}% reduction)")
            print(f"  Comfort Violations: {s_base['comfort_violations_hours']} hrs -> {s_opt['comfort_violations_hours']} hrs")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eco-Loop Building Agent Orchestrator")
    parser.add_argument("--test", action="store_true", help="Pings the LLM API to check connectivity")
    parser.add_argument("--iter", type=int, default=3, help="Number of optimization iterations (default: 3)")
    args = parser.parse_args()

    engine = BuildingCognitiveEngine()
    
    if args.test:
        print("Testing connection to local Ollama API...")
        res = engine.query_llm("Respond with exactly: 'Ollama is online and responsive.'")
        print(f"LLM Response: {res}")
    else:
        engine.run_full_pipeline(iterations=args.iter)
