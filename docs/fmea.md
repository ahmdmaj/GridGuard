# Failure Mode and Effects Analysis (FMEA)

This document analyses potential failures in a real-world GridGuard deployment, answering the critical engineering question: "What happens when this breaks?"

| Subsystem | Failure Mode | Effect on System | Detection | Mitigation in Design | Residual Risk |
|---|---|---|---|---|---|
| **Power Quality Sensor** | Complete failure or comms loss | Telemetry stops arriving at the decision engine. | Watchdog timer in `LocalProtection` expires. | `LocalProtection` node falls back to fixed, rigid voltage rules (UPS style) to protect the critical bus. | Low |
| **Transfer Switch (STS)** | Stuck closed to grid | Inverter cannot island the bus during a sag/outage. | STS state telemetry contradicts command. | Physical breaker trips if overcurrent; GridGuard alarms and requests generator start immediately. | High (hardware limitation) |
| **MQTT Broker** | Network crash / DDOS | All nodes isolated. | LWT (Last Will & Testament) fires; heartbeat timeouts. | Same as sensor failure. `LocalProtection` rules take over locally. | Low |
| **Forecasting (ML)** | Bad data yields wildly inaccurate forecast | ESH calculates survival horizons that are too optimistic. | High prediction error over recent window lowers `confidence` metric. | `ForecastService` gracefully degrades to the `RuleForecastService`. Shadow Twin pessimistic bound protects generator start. | Medium |
| **Generator** | Fails to start | Battery drains faster than expected during outage. | Fuel flow / generator telemetry reports OFF despite START command. | Battery enters rapid discharge. Decision Engine sheds all non-critical load tiers immediately as ESH drops. | High |
| **Battery** | Capacity degradation (aging) | Actual runtime falls short of ESH prediction. | BMS SOC differs from Coulomb counting integration. | Regularly update battery capacity parameters in config. (Future: dynamic capacity estimation). | Medium |
