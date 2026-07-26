import os
import json
import shutil
from idf_modifier import IDFModifier
from energyplus_wrapper import EnergyPlusWrapper

class BuildingAgentTools:
    def __init__(self, workspace_dir=None):
        if workspace_dir is None:
            workspace_dir = os.path.dirname(os.path.abspath(__file__))
        self.workspace_dir = workspace_dir
        self.models_dir = os.path.join(workspace_dir, "models")
        self.output_dir = os.path.join(workspace_dir, "sim_output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.baseline_path = os.path.join(self.models_dir, "baseline.idf")
        self.weather_path = os.path.join(self.models_dir, "weather.epw")
        self.idd_path = "D:\\Programs\\energyplus\\Energy+.idd"
        self.ep_path = "D:\\Programs\\energyplus\\energyplus.exe"
        
        self.modifier = IDFModifier(self.idd_path)
        self.wrapper = EnergyPlusWrapper(self.ep_path, self.weather_path)

    def run_simulation(self, run_id, cool_occ, cool_unocc, heat_occ, heat_unocc, start_month=1, start_day=1, end_month=1, end_day=7, occ_start=6, occ_end=22):
        """
        Tool to update setpoints in the IDF, execute EnergyPlus, parse the output CSV,
        save the results, and return the summary metrics.
        """
        temp_idf_prepared = os.path.join(self.models_dir, f"temp_prepared_{run_id}.idf")
        run_idf = os.path.join(self.models_dir, f"run_{run_id}.idf")
        run_temp_out = os.path.join(self.workspace_dir, f"temp_out_{run_id}")
        
        try:
            # 1. Prepare IDF with correct simulation period and output variables
            self.modifier.prepare_idf(
                self.baseline_path, 
                temp_idf_prepared, 
                start_month, 
                start_day, 
                end_month, 
                end_day
            )
            
           
            self.modifier.update_setpoints(
                temp_idf_prepared, 
                run_idf, 
                cool_occ, 
                cool_unocc, 
                heat_occ, 
                heat_unocc, 
                occ_start, 
                occ_end
            )
            
            # Remove temp prepared file
            if os.path.exists(temp_idf_prepared):
                os.remove(temp_idf_prepared)
                
            # 3. Run EnergyPlus simulation
            run_result = self.wrapper.run(run_idf, run_temp_out)
            
            if run_result["has_errors"]:
                return {
                    "success": False,
                    "error_msg": f"EnergyPlus simulation failed with errors:\n{run_result['error_msg']}"
                }
                
            if run_result["returncode"] != 0:
                return {
                    "success": False,
                    "error_msg": f"EnergyPlus exited with non-zero code {run_result['returncode']}.\nStderr:\n{run_result['stderr']}"
                }
                
            # 4. Parse results CSV
            csv_path = os.path.join(run_temp_out, "eplusout.csv")
            metrics = self.wrapper.parse_results(csv_path, start_month, start_day, end_month, end_day)
            
            # 5. Save persistent run records for dashboard comparison
            metrics_save_path = os.path.join(self.output_dir, f"metrics_{run_id}.json")
            csv_save_path = os.path.join(self.output_dir, f"run_{run_id}.csv")
            
            # Save configuration parameters inside metrics
            metrics["run_id"] = run_id
            metrics["cool_occ"] = cool_occ
            metrics["cool_unocc"] = cool_unocc
            metrics["heat_occ"] = heat_occ
            metrics["heat_unocc"] = heat_unocc
            metrics["occ_start"] = occ_start
            metrics["occ_end"] = occ_end
            metrics["start_month"] = start_month
            metrics["start_day"] = start_day
            metrics["end_month"] = end_month
            metrics["end_day"] = end_day
            
            with open(metrics_save_path, "w") as f:
                json.dump(metrics, f, indent=4)
                
            shutil.copy(csv_path, csv_save_path)
            
            # Clean up temporary run directory
            if os.path.exists(run_temp_out):
                shutil.rmtree(run_temp_out)
                
            return {
                "success": True,
                "metrics": {
                    "electricity_kwh": metrics["electricity_kwh"],
                    "gas_kwh": metrics["gas_kwh"],
                    "total_energy_kwh": metrics["total_energy_kwh"],
                    "co2_kg": metrics["co2_kg"],
                    "average_pmv": metrics["average_pmv"],
                    "comfort_violations_hours": metrics["comfort_violations_hours"],
                    "comfort_violation_rate": metrics["comfort_violation_rate"],
                    "average_indoor_temp": metrics["average_indoor_temp"],
                    "max_outdoor_temp": metrics["max_outdoor_temp"],
                    "min_outdoor_temp": metrics["min_outdoor_temp"]
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error_msg": f"An unexpected exception occurred during simulation execution: {str(e)}"
            }

if __name__ == "__main__":
    tools = BuildingAgentTools()
    print("Testing tools.py...")
    # Run a test simulation for winter week (Jan 1 to Jan 7)
    res = tools.run_simulation(
        run_id="test_baseline", 
        cool_occ=24.0, 
        cool_unocc=26.7, 
        heat_occ=21.0, 
        heat_unocc=15.6,
        start_month=1, 
        start_day=1, 
        end_month=1, 
        end_day=7
    )
    print("Test baseline run outcome:")
    print(json.dumps(res, indent=4))
