import os
from eppy.modeleditor import IDF

class IDFModifier:
    def __init__(self, idd_path="D:\\Programs\\energyplus\\Energy+.idd"):
        self.idd_path = idd_path
        IDF.setiddname(idd_path)

    def prepare_idf(self, input_idf_path, output_idf_path, start_month, start_day, end_month, end_day):
        """
        Loads the baseline IDF, configures the run period, enables simulation control,
        and adds Output:Variable objects for PMV and CO2 emissions.
        """
        idf = IDF(input_idf_path)
        
        # 1. Update SimulationControl to run weather file periods
        simcontrols = idf.idfobjects['SimulationControl']
        for sc in simcontrols:
            sc.Run_Simulation_for_Weather_File_Run_Periods = "Yes"
            
        # 2. Update RunPeriod dates
        run_periods = idf.idfobjects['RunPeriod']
        for rp in run_periods:
            rp.Begin_Month = start_month
            rp.Begin_Day_of_Month = start_day
            rp.End_Month = end_month
            rp.End_Day_of_Month = end_day
            
        # 3. Add output variables for PMV and CO2 if they don't exist
        existing_vars = {v.Variable_Name.lower(): v for v in idf.idfobjects['Output:Variable']}
        
        target_vars = [
            "Zone Thermal Comfort Fanger Model PMV",
            "Environmental Impact Total CO2 Emissions Carbon Equivalent Mass"
        ]
        
        for tvar in target_vars:
            if tvar.lower() not in existing_vars:
                idf.newidfobject(
                    "Output:Variable",
                    Key_Value="*",
                    Variable_Name=tvar,
                    Reporting_Frequency="Hourly"
                )
                
        # Save the file
        idf.saveas(output_idf_path)
        return idf

    def update_setpoints(self, idf_path, output_idf_path, cool_occ, cool_unocc, heat_occ, heat_unocc, occ_start=6, occ_end=22):
        """
        Modifies cooling and heating schedules in the IDF file.
        Uses eppy's remove and new objects to avoid empty trailing fields.
        """
        idf = IDF(idf_path)
        occ_end_sat = min(18, occ_end)

        # 1. Update cooling setpoint schedule
        clg_scheds = [s for s in idf.idfobjects['Schedule:Compact'] if s.Name == "CLGSETP_SCH"]
        if clg_scheds:
            old_s = clg_scheds[0]
            idf.removeidfobject(old_s)
            
            new_s = idf.newidfobject("Schedule:Compact", Name="CLGSETP_SCH")
            fields_cool = [
                "CLGSETP_SCH", "Temperature",
                "Through: 12/31",
                "For: Weekdays SummerDesignDay",
                f"Until: {occ_start:02d}:00", cool_unocc,
                f"Until: {occ_end:02d}:00", cool_occ,
                "Until: 24:00", cool_unocc,
                "For: Saturday",
                f"Until: {occ_start:02d}:00", cool_unocc,
                f"Until: {occ_end_sat:02d}:00", cool_occ,
                "Until: 24:00", cool_unocc,
                "For: AllOtherDays",
                "Until: 24:00", cool_unocc
            ]
            new_s.obj = ['Schedule:Compact'] + [str(x) for x in fields_cool]

        # 2. Update heating setpoint schedule
        htg_scheds = [s for s in idf.idfobjects['Schedule:Compact'] if s.Name == "HTGSETP_SCH"]
        if htg_scheds:
            old_s = htg_scheds[0]
            idf.removeidfobject(old_s)
            
            new_s = idf.newidfobject("Schedule:Compact", Name="HTGSETP_SCH")
            fields_heat = [
                "HTGSETP_SCH", "Temperature",
                "Through: 12/31",
                "For: Weekdays",
                f"Until: {occ_start:02d}:00", heat_unocc,
                f"Until: {occ_end:02d}:00", heat_occ,
                "Until: 24:00", heat_unocc,
                "For: Saturday",
                f"Until: {occ_start:02d}:00", heat_unocc,
                f"Until: {occ_end_sat:02d}:00", heat_occ,
                "Until: 24:00", heat_unocc,
                "For: WinterDesignDay",
                "Until: 24:00", heat_occ,
                "For: AllOtherDays",
                "Until: 24:00", heat_unocc
            ]
            new_s.obj = ['Schedule:Compact'] + [str(x) for x in fields_heat]
            
        idf.saveas(output_idf_path)
        print(f"Setpoints updated in IDF. Saved to {output_idf_path}")
        return idf
