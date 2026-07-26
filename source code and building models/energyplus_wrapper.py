import os
import subprocess
import pandas as pd
import numpy as np

class EnergyPlusWrapper:
    def __init__(self, ep_path="D:\\Programs\\energyplus\\energyplus.exe", weather_path=None):
        if weather_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            weather_path = os.path.join(script_dir, "models", "weather.epw")
        self.ep_path = ep_path
        self.weather_path = weather_path

    def run(self, idf_path, output_dir):
        """
        Runs EnergyPlus on the specified IDF file.
        """
        os.makedirs(output_dir, exist_ok=True)
        cmd = [
            self.ep_path,
            "-w", self.weather_path,
            "-d", output_dir,
            "-r",  # Run ReadVarsESO to generate CSV
            idf_path
        ]
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if run was successful
        err_path = os.path.join(output_dir, "eplusout.err")
        has_errors = False
        error_msg = ""
        if os.path.exists(err_path):
            with open(err_path, "r") as f:
                errors = f.read()
                if "Fatal error" in errors or "EnergyPlus Terminated--Fatal Error Detected" in errors:
                    has_errors = True
                    error_msg = errors
                    
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "has_errors": has_errors,
            "error_msg": error_msg
        }

    def parse_results(self, csv_path, start_month, start_day, end_month, end_day):
        """
        Parses the eplusout.csv file for the specified date range.
        Calculates total electricity, natural gas, comfort violations, and outdoor temperature.
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Simulation output CSV file not found: {csv_path}")

        df = pd.read_csv(csv_path)
        
        # Filter for rows in the weather run period (ignore sizing period days like Jan 21 or Jul 21)
        valid_indices = []
        for idx, row in df.iterrows():
            date_str = str(row['Date/Time'])
            try:
                # Format is: " 01/01  01:00:00"
                parts = date_str.strip().split()
                if len(parts) >= 2:
                    date_part = parts[0]  # "01/01"
                    m, d = map(int, date_part.split("/"))
                    # Check if date is in the range
                    # Note: Since the year is not specified, we check if month is within start and end month
                    # and day is within range. If it spans across months, we handle it simply.
                    if start_month <= m <= end_month:
                        if m == start_month and d < start_day:
                            continue
                        if m == end_month and d > end_day:
                            continue
                        valid_indices.append(idx)
            except Exception:
                continue

        df_filtered = df.loc[valid_indices].copy()
        print(f"Filtered {len(df_filtered)} rows for simulation period {start_month}/{start_day} to {end_month}/{end_day}")

        if df_filtered.empty:
            raise ValueError("No simulation data found in the specified date range.")

        # Find columns
        cols = df_filtered.columns
        
        # Total electricity (facility total)
        elec_col = [c for c in cols if 'Electricity:Facility' in c and 'Hourly' in c]
        elec_j = df_filtered[elec_col[0]].sum() if elec_col else 0.0
        elec_kwh = elec_j / 3.6e6

        # Total natural gas (facility total)
        gas_col = [c for c in cols if 'NaturalGas:Facility' in c and 'Hourly' in c]
        gas_j = df_filtered[gas_col[0]].sum() if gas_col else 0.0
        gas_kwh = gas_j / 3.6e6

        # Total CO2 emissions
        co2_col = [c for c in cols if 'CO2 Emissions Carbon Equivalent' in c and 'Hourly' in c]
        co2_kg = df_filtered[co2_col[0]].sum() if co2_col else 0.0

        # Zone Mean Air Temperatures
        temp_cols = [c for c in cols if 'Zone Mean Air Temperature' in c]
        # Ignore ATTIC zone as it is unoccupied
        occupied_temp_cols = [c for c in temp_cols if 'ATTIC' not in c.upper()]
        
        # PMV columns
        pmv_cols = [c for c in cols if 'Thermal Comfort Fanger Model PMV' in c]
        
        # Calculate comfort violations
        # Standard comfort range is -0.5 to 0.5 (ASHRAE 55) during occupied hours (e.g., 08:00 to 18:00 on weekdays)
        comfort_violations = 0
        occupied_hours_count = 0
        pmv_list = []
        
        for idx, row in df_filtered.iterrows():
            date_str = str(row['Date/Time'])
            parts = date_str.strip().split()
            time_part = parts[1]  # "01:00:00"
            hour = int(time_part.split(":")[0])
            
            # Simple assumption: occupied hours are 08:00 to 18:00 (hour 8 to 18)
            is_occupied_hour = 8 <= hour <= 18
            
            if is_occupied_hour:
                occupied_hours_count += len(pmv_cols)
                for col in pmv_cols:
                    val = row[col]
                    if not np.isnan(val):
                        pmv_list.append(val)
                        if val < -0.5 or val > 0.5:
                            comfort_violations += 1

        avg_pmv = np.mean(pmv_list) if pmv_list else 0.0
        violation_rate = comfort_violations / occupied_hours_count if occupied_hours_count > 0 else 0.0

        # Indoor and outdoor temperatures
        outdoor_temp_col = [c for c in cols if 'Outdoor Air Drybulb Temperature' in c][0]
        outdoor_temps = df_filtered[outdoor_temp_col].values
        
        avg_indoor_temps = []
        for col in occupied_temp_cols:
            avg_indoor_temps.append(df_filtered[col].mean())
        avg_indoor_temp = np.mean(avg_indoor_temps) if avg_indoor_temps else 0.0

        # Hourly data log for visualization
        hourly_data = {
            "timestamps": df_filtered['Date/Time'].tolist(),
            "outdoor_temp": df_filtered[outdoor_temp_col].tolist(),
            "electricity_kwh": (df_filtered[elec_col[0]] / 3.6e6).tolist() if elec_col else [],
            "gas_kwh": (df_filtered[gas_col[0]] / 3.6e6).tolist() if gas_col else [],
            "co2_kg": df_filtered[co2_col[0]].tolist() if co2_col else [],
        }
        
        # Add comfort variables for each zone
        for col in pmv_cols:
            zone_name = col.split(":")[0]
            hourly_data[f"{zone_name}_pmv"] = df_filtered[col].tolist()
            
        for col in occupied_temp_cols:
            zone_name = col.split(":")[0]
            hourly_data[f"{zone_name}_temp"] = df_filtered[col].tolist()

        return {
            "electricity_kwh": elec_kwh,
            "gas_kwh": gas_kwh,
            "total_energy_kwh": elec_kwh + gas_kwh,
            "co2_kg": co2_kg,
            "average_pmv": avg_pmv,
            "comfort_violations_hours": comfort_violations,
            "comfort_violation_rate": violation_rate,
            "average_indoor_temp": avg_indoor_temp,
            "max_outdoor_temp": float(np.max(outdoor_temps)),
            "min_outdoor_temp": float(np.min(outdoor_temps)),
            "hourly_data": hourly_data
        }

if __name__ == "__main__":
    wrapper = EnergyPlusWrapper()
    test_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_out_short", "eplusout.csv")
    metrics = wrapper.parse_results(test_csv, 1, 1, 1, 7)
    print("Test run parse results:")
    print(f"Electricity: {metrics['electricity_kwh']:.2f} kWh")
    print(f"Gas: {metrics['gas_kwh']:.2f} kWh")
    print(f"Total: {metrics['total_energy_kwh']:.2f} kWh")
    print(f"Avg PMV: {metrics['average_pmv']:.2f}")
    print(f"Comfort Violations: {metrics['comfort_violations_hours']} hours")
