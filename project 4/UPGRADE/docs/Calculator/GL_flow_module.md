# Gas-Liquid Flow Rate Calculation Module

## Overview
This module, `calc_gl_para`, provides tools for gas-liquid flow rate calculations and system preparation in chemical experiments. It is designed to ensure precise control of flow rates and system stability, which are critical for experimental success.

## Features
- **Flow Rate Calculations**: Compute total, liquid, and gas flow rates based on experimental conditions.
- **System Stability**: Prepare systems for stable operation by setting appropriate gas-liquid ratios.
- **Feasibility Checks**: Verify if operating parameters are within feasible limits.
- **Unit-Aware Calculations**: Support for unit-aware flow rate calculations using the `pint` library.
- **Utility Functions**: Add units to experimental conditions for consistency and accuracy.

## Classes
### `GLcalculator_db`
Handles gas-liquid flow rate calculations and system preparation.
- **Methods**:
  - `calc_gas_liquid_flow_rate`: Calculates total, liquid, and gas flow rates.
  - `calc_stable_system`: Prepares the system for stable operation.
  - `calc_rxn_flow`: Calculates flow rates for a reaction.
  - `calc_all_flow_rate`: Calculates all flow rates, including dilution and makeup flows.
  - `check_param_doable`: Checks if the operating parameters are feasible.

### `GLcalculator_unit`
Provides unit-aware calculations for gas-liquid flow rates.
- **Methods**:
  - `calc_gas_liquid_flow_rate`: Calculates flow rates with unit awareness.
  - `calc_stable_system`: Prepares the system for stable operation with unit awareness.
  - `check_param_doable`: Checks if the operating parameters are feasible.

### `add_units`
A utility function to add units to experimental conditions.

## Usage
This module is intended for use in chemical experiment setups where precise control of gas-liquid flow rates and system stability is required. It supports:
- Reaction flow rate calculations.
- System preparation for stable operation.
- Integration with unit-aware libraries like `pint`.

## Dependencies
- `loguru`: For logging.
- `pint`: For unit-aware calculations.
- `os`: For environment variable handling.
- `BV_experiments/src/general_platform/ureg`: Custom unit registry.

## Example
```python
from calc_gl_para import GLcalculator_db, add_units

# Define experimental conditions
condition = {
    'concentration': 0.3,
    'oxygen_equiv': 1.5,
    'time': 5,
    'pressure': 2.5,
    'temperature': 52
}

# Initialize the calculator
setup_vol_dict = {"REACTOR": [1.1]}  # Example setup volume
calculator = GLcalculator_db(setup_vol_dict)

# Calculate flow rates
flow_rates = calculator.calc_gas_liquid_flow_rate(condition)
print("Flow Rates:", flow_rates)

# Check system stability
stable_system = calculator.calc_stable_system(condition, flow_rates)
print("Stable System Parameters:", stable_system)