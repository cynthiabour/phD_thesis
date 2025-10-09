"""
Lev deprotection experiment

for example        RM-deliver(p)                            waste
                           |                                  |
        L-deliver(p) -- loop(v) --- reactor --- BPR --- collector(v) -- vial
"""
import asyncio

if __name__ == "__main__":
    # import the setup information
    from BV_experiments.Example5_lev_deprotection.setup_info import (devices_names_02, tube_information_02,
                                                                     sugar_information_kyt, valve_information_02,
                                                                     valve_information_03)
    from BV_experiments.Example5_lev_deprotection.run_experiment_01 import metadata

    # condition should only include the information that is needed for the experiment. For instance:
    condition = {"time": 5, "temperature": "22°C", "equiv_hydrazine": 3}
    from BV_experiments.Example5_lev_deprotection.run_experiment_01 import DeprotectionExperiment

    exp_kyt = DeprotectionExperiment(
        devices_names_02, tube_information_02, valve_information_02, sugar_information_kyt, metadata)
    asyncio.run(exp_kyt.initialize())
    asyncio.run(exp_kyt.run_experiment(condition, "test_run_01"))

    exp_kyt = DeprotectionExperiment(
        devices_names_02, tube_information_02, valve_information_03, sugar_information_kyt, metadata)
    condition = {"time": 5, "temperature": "40°C", "equiv_hydrazine": 3}
    asyncio.run(exp_kyt.initialize())
    asyncio.run(exp_kyt.run_experiment(condition, "test_run_02"))
