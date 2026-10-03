import os

class Dashboard:
    @staticmethod
    def render(step: int, telemetry: dict, twin_state: dict, esh: dict, cmd: dict) -> None:
        os.system("cls" if os.name == "nt" else "clear")
        
        # Battery Bar
        soc = telemetry.get("battery_soc", 0.0)
        filled = int((soc / 100.0) * 20)
        bar = "#" * filled + " " * (20 - filled)
        
        print("============================================================")
        print(f" GRIDGUARD DIGITAL TWIN | STEP {step:03d} | {telemetry.get('timestamp', '')}")
        print("============================================================")
        print(" [ PHYSICAL PLANT ]")
        print(f" Grid Status   : {'AVAILABLE' if telemetry.get('grid_available') else 'OFFLINE'}")
        print(f" Solar Power   : {telemetry.get('solar_kw', 0.0):.2f} kW")
        print(f" Battery Power : {telemetry.get('battery_kw', 0.0):.2f} kW")
        print(f" Generator Pwr : {telemetry.get('generator_kw', 0.0):.2f} kW")
        print(f" Battery SOC   : [{bar}] {soc:.1f}%")
        print("------------------------------------------------------------")
        print(" [ ENERGY SURVIVAL HORIZON (ESH) ]")
        
        def fmt_hrs(h: float) -> str:
            return "inf" if h == float('inf') else f"{h:.2f}"
            
        print(f" Critical Only : {fmt_hrs(esh.get('critical_only_hours', 0.0))} hours")
        print(f" Crit & Import : {fmt_hrs(esh.get('critical_and_important_hours', 0.0))} hours")
        print(f" All Loads     : {fmt_hrs(esh.get('all_loads_hours', 0.0))} hours")
        print("------------------------------------------------------------")
        print(" [ AI DECISION ENGINE ]")
        print(f" Battery Cmd   : {cmd.get('battery_command_kw', 0.0):.2f} kW")
        print(f" Generator Run : {cmd.get('generator_run', False)}")
        print(f" Reason        : {cmd.get('decision_reason', 'N/A')}")
        print("============================================================\n")
