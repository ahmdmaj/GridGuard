from physical.inverter_sts import InverterSTS, InverterMode

inv = InverterSTS({})
print(f"Initial: {inv.current_mode}, time={inv.time_in_mode_s}")
v, d, o = inv.step(InverterMode.ISLAND, 60.0, 0.90, 4.0)
print(f"Step 1: mode={inv.current_mode}, v={v}, time={inv.time_in_mode_s}")
