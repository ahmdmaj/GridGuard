from typing import TypedDict

class SystemCommand(TypedDict):
    battery_command_kw: float
    generator_run: bool
    connect_critical: bool
    connect_important: bool
    connect_flexible: bool
    decision_reason: str
