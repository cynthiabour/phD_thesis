"""
test the performmance of gryffin
documentation: https://gryffin.readthedocs.io/en/latest/configuration.html

"""
import datetime
import pickle
import json
# import os
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import pandas as pd
import numpy as np
from gryffin import Gryffin
import time
from loguru import logger
import matplotlib.pyplot as plt
import matplotlib

# import seaborn as sns
# sns.set(context='talk', style='ticks')

# config0 = {
#     "parameters": [
#         {"name": "conc", "type": "continuous", "low": 0.021, "high": 0.025},
#         {"name": "Dye", "type": "continuous", "low": 0.0, "high": 0.10},
#         {"name": "Activator", "type": "continuous", "low": 0.0, "high": 0.40},
#         {"name": "Quencher", "type": "continuous", "low": 0.0, "high": 20.0},
#         {"name": "time", "type": "continuous", "low": 0.5, "high": 100},
#         {"name": "O2", "type": "continuous", "low": 1.0, "high": 4.0},
#         {"name": "light", "type": "continuous", "low": 6.5, "high": 13},
#         {"name": "pressure", "type": "continuous", "low": 1.0, "high": 5.0},
#         {"name": "temperature", "type": "continuous", "low": 0, "high": 70},
#     ],
#     "objectives": [
#         {"name": "Yield_1", "goal": "max"},
#     ],
# }
config = {
    "parameters": [
        # {"name": "concentration", "type": "continuous", "low": 0.010, "high": 1.22},
        {"name": "dye_equiv", "type": "continuous", "low": 0.001, "high": 0.10},
        {"name": "activator_equiv", "type": "continuous", "low": 0.0, "high": 0.50},
        {"name": "quencher_equiv", "type": "continuous", "low": 0.5, "high": 20.0},
        {"name": "oxygen_equiv", "type": "continuous", "low": 1.0, "high": 4.0},
        {"name": "solvent_equiv", "type": "continuous", "low": 0.0, "high": 1000},
        {"name": "time", "type": "continuous", "low": 1.5, "high": 50},
        {"name": "light", "type": "continuous", "low": 6.5, "high": 13},
        {"name": "pressure", "type": "continuous", "low": 0.0, "high": 6.0},
        {"name": "temperature", "type": "continuous", "low": 0, "high": 70},
    ],
    "objectives": [
        # {"name": "Producivity_1", "goal": "max"},
        {"name": "Yield_1", "goal": "max"},
    ],
}

# # find experiments
# def find_exp(params_list):
#     # read in all 25 mM training data
#     file_path = r"W:\BS-FlowChemistry\People\Wei-Hsin\train_25_2.csv"
#     data = pd.read_csv(file_path)
#
#     # set first 5 data as initinal data
#     init_data = data.head()



if __name__ == "__main__":
    logger.add(f"/BV_experiments/log/myapp.log", rotation="10 MB")

    # Initialize gryffin
    config["general"] = {"num_cpus": "all"}
    gryffin = Gryffin(config_dict=config)

    # Given all conducted experiment conditions as initial starting point
    # with open("../training_set_0", "r") as fp:
    #     observations = json.load(fp)
    observations = [
        {'Name': 'whhsu073', 'IS': None,
        'concentration': 0.025, 'dye_equiv': 0.01, 'activator_equiv': 0.02, 'quencher_equiv': 2, 'solvent_equiv': 969.15,
        'time': 10, 'oxygen_equiv': 2.2, 'light': 13.0, 'pressure': 3.0, 'temperature': 31,
        'Acid': 0.0, 'Ester': 0.06, 'Lactone': 0.09, 'Unk_4': 0.26, 'SM': 0.58,
        'Yield_1': 0.15, 'Conv_1': 0.42, 'Producivity_1': 0.381944952,
        'Yield_2': None, 'Conv_2': None, 'Producivity_2': None
        },
    ]

    # # Run optimization for MAX_TIME
    # MAX_TIME = 8 * 60 * 60
    # start_time = time.monotonic()

    # predict result by LASSO
    model_path = r"W:\BS-FlowChemistry\People\Wei-Hsin\LASSO_model_25mM_alpha00001.sav"
    loaded_model = pickle.load(open(model_path, 'rb'))
    # define new data
    # row = [0.025, 0.03, 0.02, 2, 10, 1.2, 13, 3, 31]
    # yhat = loaded_model.predict([row])  #output
    # print('Predicted: %.3f' % yhat)

    # run BS
    for iter_t in range(10):
        logger.info(f"{datetime.datetime.now()}// start {iter_t+1} round")
        # query gryffin for new params
        # query gryffin for new conditions_to_test, 1 exploration 1 exploitation (i.e. lambda 1 and -1)
        conditions_to_test = gryffin.recommend(
            observations=observations, num_batches=1, sampling_strategies=[-1, 1]
        )  # output two dic in a list
        logger.info(f'suggest 2 new_exp_conditions: {conditions_to_test}')

        # evaluate the proposed parameters!
        for conditions in conditions_to_test:
            # Get this from your experiment!
            # conditions["product_ratio_IR"] = run_experiment(**conditions)
            row = list(conditions.values())

            conditions["Yield_1"] = float(loaded_model.predict([row]))
            logger.info(f"{datetime.datetime.now()}// Experiment ended: {conditions}")

        observations.extend(conditions_to_test)
        logger.info(f'{datetime.datetime.now()}//finish {iter_t} round. latest observations: {observations}')
