"""practical information for the setup of the experiment
for example        RM-deliver(p)                            waste
                           |                                  |
        L-deliver(p) -- loop(v) --- reactor --- BPR --- collector(v) -- vial

"""

devices_names_01 = {
    "r2_power": ["r2", "Power"],
    "hplc_pump": ["r2", "Pump_A"],
    "loop_valve": ["r2", "InjectionValve_A"],
    "sugar_pump": ["syr5", 'pump'],
    "hydrazine_pump": ["syr3", 'pump'],
    "reactor": ["r2", "reactor-1"],
    "collect_valve": ["r2", "CollectionValve"],
}

# define connection
tube_information_01 = {
    "Y_mixer": 0.0017,
    "mixer_to_loop": 0.05,
    "loop": 2.0,
    "tube_loop_to_reactor": 0.40 * 0.7854,
    "reactor": 5.0,
    "bpr": 0.125,
    "tube_reactor_to_collector": 1.0 * 0.070686,
    "tube_collector_to_vial": 0.1 * 0.070686,
}
valve_information_01 = {
    "loop_valve": {"load": "load", "inject": "inject"},
    "collector_valve": {"waste": "Solvent", "collect": "Reagent"},
}


devices_names_02 = {
    "hplc_pump": ["r2", "Pump_B"],
    "loop_valve": ["r2", "InjectionValve_B"],
    "sugar_pump": ["syr0", 'pump'],
    "hydrazine_pump": ["syr4", 'pump'],
    "reactor": ["r2", "reactor-3"],
    "collect_valve": ["6PortValve", "distribution-valve"],
}

tube_information_02 = {
    "Y_mixer": 0.0017,
    "mixer_to_loop": 0.25 * 0.7854,
    "loop": 2.0,
    "tube_loop_to_reactor": 0.32 * 0.070686,
    "reactor": 5.0,
    "bpr": 0.125,
    "tube_reactor_to_collector": 0.36 * 0.7854,
    "tube_collector_to_vial": 0.12 * 0.070686,
}

valve_information_02 = {
    "loop_valve": {"load": "load", "inject": "inject"},
    "collector_valve": {"waste": "2", "collect": "1"},
}

valve_information_03 = {
    "loop_valve": {"load": "load", "inject": "inject"},
    "collector_valve": {"waste": "2", "collect": "6"},
}

sugar_information_mei: dict = {
    "code": "sugar_mei",
    "name": "4-Methylphenyl 6-O-benzyl-2-deoxy-"
            "2-[(p-Nitrobenzyloxycarbony)amino]-4-O-(9-fluorenylmethoxycarbonyl)"
            "-3-O-levulinoyl-1-thio-β-D-glucopyranoside",
    "MW": 860.94,
    "smile": "O=C(O[C@H]1[C@H](OC(CCC(C)=O)=O)[C@@H](NC(OC2=CC=C([N+]([O-])=O)C=C2)=O)[C@H](SC3=CC=C(C)C=C3)O[C@@H]1COCC4=CC=CC=C4)OCC5C(C=CC=C6)=C6C7=C5C=CC=C7",
}

sugar_information_kyt: dict = {
    "code": "sugar_kyt",
    "name": "4-Methylphenyl 2-O-benzoyl-4,6-di-O-levulinoyl-"
            "3-O-(9-fluorenylmethoxycarbonyl)-1-thio-beta-D-galactopyranoside",
    "MW": 808.90,
    "smile": "O=C(O[C@@H]1[C@@H](OC(OCC2C(C=CC=C3)=C3C4=C2C=CC=C4)=O)[C@H](OC(CCC(C)=O)=O)[C@H](O[C@H]1SC5=CC=C(C)C=C5)COC(CCC(C)=O)=O)C6=CC=CC=C6",
}


graph = {}
