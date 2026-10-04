from typing import Dict, Any

class ZipModel:
    def __init__(self, a_z: float, a_i: float, a_p: float) -> None:
        # Check sum is 1.0 (or close to it)
        total = a_z + a_i + a_p
        if abs(total - 1.0) > 1e-6:
            raise ValueError("ZIP coefficients must sum to 1.0")
        self.a_z = a_z
        self.a_i = a_i
        self.a_p = a_p

    def get_actual_power_pu(self, v_pu: float) -> float:
        """Returns the actual power as a fraction of nominal power."""
        return self.a_z * (v_pu ** 2) + self.a_i * v_pu + self.a_p

    def get_actual_current_pu(self, v_pu: float) -> float:
        """Returns the actual current as a fraction of nominal current.
           I = P / V
        """
        if v_pu <= 0.01:
            return 0.0 # Prevent div zero
        return self.get_actual_power_pu(v_pu) / v_pu

class LoadModel:
    def __init__(self, config: Dict[str, Any]) -> None:
        # Tiers: critical, important, non_essential (flexible is now non_essential per phase 1 docs but keeping flexible for compatibility or use non_essential as alias)
        
        # Default ZIP parameters
        # Lighting: mostly impedance
        self.zip_lighting = ZipModel(a_z=1.0, a_i=0.0, a_p=0.0)
        # Electronics: mostly constant power
        self.zip_electronics = ZipModel(a_z=0.0, a_i=0.0, a_p=1.0)
        # HVAC: mostly constant power, with extra current draw at low V
        self.zip_hvac = ZipModel(a_z=0.1, a_i=0.1, a_p=0.8)

        self.nominal_kw = {
            "critical": config.get("critical_kw", 4.0),
            "important": config.get("important_kw", 3.0),
            "non_essential": config.get("non_essential_kw", 2.0)
        }
        
        self.connected = {
            "critical": True,
            "important": True,
            "non_essential": True
        }
        
        # Assign load mix for each tier
        self.mix = {
            "critical": {"lighting": 0.2, "electronics": 0.8, "hvac": 0.0},
            "important": {"lighting": 0.5, "electronics": 0.5, "hvac": 0.0},
            "non_essential": {"lighting": 0.0, "electronics": 0.0, "hvac": 1.0}
        }

    def set_connection(self, tier: str, is_connected: bool) -> None:
        if tier in self.connected:
            self.connected[tier] = is_connected

    def get_tier_power_kw(self, tier: str, v_pu: float) -> float:
        if not self.connected.get(tier, False):
            return 0.0
            
        nominal = self.nominal_kw[tier]
        mix = self.mix[tier]
        
        p_light = mix["lighting"] * self.zip_lighting.get_actual_power_pu(v_pu)
        p_elec = mix["electronics"] * self.zip_electronics.get_actual_power_pu(v_pu)
        p_hvac = mix["hvac"] * self.zip_hvac.get_actual_power_pu(v_pu)
        
        return nominal * (p_light + p_elec + p_hvac)
        
    def get_tier_current_pu(self, tier: str, v_pu: float) -> float:
        """Returns the current drawn by a tier, normalized such that nominal current = 1.0"""
        if not self.connected.get(tier, False):
            return 0.0
            
        mix = self.mix[tier]
        i_light = mix["lighting"] * self.zip_lighting.get_actual_current_pu(v_pu)
        i_elec = mix["electronics"] * self.zip_electronics.get_actual_current_pu(v_pu)
        i_hvac = mix["hvac"] * self.zip_hvac.get_actual_current_pu(v_pu)
        
        return i_light + i_elec + i_hvac

    def get_total_power_kw(self, v_pu: float) -> float:
        return sum(self.get_tier_power_kw(t, v_pu) for t in self.nominal_kw.keys())
