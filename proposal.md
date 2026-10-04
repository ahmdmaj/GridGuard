# Project Proposal: GridGuard

## 1. Project Title
**GridGuard: AI-Driven Microgrid Digital Twin and Autonomous Load Management**

## 2. Problem Statement
As extreme weather events and aging infrastructure increasingly threaten grid stability, local microgrids (solar + battery + generator) are becoming essential for commercial and critical facilities. However, managing these microgrids during unexpected grid sags (brownouts) or complete communication loss requires split-second, intelligent decision-making. Standard rule-based relays are brittle—often causing unnecessary blackouts or failing to prioritize critical loads when solar generation unexpectedly drops.

## 3. Solution Overview
GridGuard is an autonomous, AI-driven Digital Twin designed to manage and protect microgrids in real-time. By bridging a high-fidelity physical simulation engine with a predictive Machine Learning (ML) Decision Engine, GridGuard acts as an intelligent local controller that continuously monitors grid health, predicts future energy shortfalls, and dynamically orchestrates hardware (inverters, batteries, generators, and load shedding) to ensure 100% uptime for critical infrastructure.

## 4. Key Features & Architecture
- **Interactive Digital Twin (State Machine):** A fully decoupled, tick-based physics simulation engine that models complex electrical behaviors (feeder impedance, ZIP load models, voltage sags).
- **Predictive ML Forecasting:** Utilizes an integrated Random Forest model (`MLForecastService`) to predict solar generation and load demand based on diurnal cycles, weather conditions, and time-of-day.
- **Expected Survival Hours (ESH) AI:** The core `DecisionEngine` calculates how long the microgrid can survive off-grid based on current SOC (State of Charge) and ML forecasts. It proactively triggers load-shedding tiers (Flexible → Important) and starts emergency generators before the battery is depleted.
- **Resilient IoT Fallbacks (Watchdog):** Incorporates local protection relays that instantly island the microgrid during voltage collapses or MQTT communication failures, ensuring physical safety even when the software layer goes dark.
- **Live Interactive Dashboard:** A Streamlit-based UI that allows users to act as "chaos engineers," injecting live grid outages, voltage sags, and solar collapses to watch the AI adapt in real-time.

## 5. Technical Stack
- **Core Engine:** Python 3 (Object-Oriented Physical Simulation)
- **Machine Learning:** Scikit-Learn (Random Forest Regressor), Pandas, NumPy
- **Interactive UI:** Streamlit (Tick-based animation loop and real-time state injection)
- **Data Architecture:** Time-series telemetry tracking and dynamic DataFrame charting.

## 6. Business Value & Impact
GridGuard transitions microgrid management from reactive to highly predictive. By autonomously balancing load shedding with forecasted generation, facilities can extend their survival time during extended outages, minimize generator fuel costs during normal operations, and prevent hardware damage from grid instability—all without requiring human intervention.
