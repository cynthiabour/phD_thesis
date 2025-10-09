"""

Gryffin
@article{phoenics,
  title = {Phoenics: A Bayesian Optimizer for Chemistry},
  author = {Florian Häse and Loïc M. Roch and Christoph Kreisbeck and Alán Aspuru-Guzik},
  year = {2018}
  journal = {ACS Central Science},
  number = {9},
  volume = {4},
  pages = {1134--1145}
  }

multi-objective optimization, or used periodic variables,
@article{chimera,
  title = {Chimera: enabling hierarchy based multi-objective optimization for self-driving laboratories},
  author = {Florian Häse and Loïc M. Roch and Alán Aspuru-Guzik},
  year = {2018},
  journal = {Chemical Science},
  number = {9},
  pages = {7642--7655}
  }

NEXTorch

"""
from gryffin import Gryffin
import json
from loguru import logger
import asyncio


class Optimizer:
    """
    Gryffin optimizer for Bayesian optimization in chemical experiments.
    This class initializes the Gryffin optimizer with a given configuration and number of CPUs.
    It can generate new recommendations based on the training data and add new observations to the training set.
    """
    def __init__(self, config: dict, num_cpus: str, training_data: str = None):

        # Initialize gryffin
        config["general"] = {"num_cpus": num_cpus}  # run multiprocessing.cpu_count() to check max num_cpus
        self.gryffin = Gryffin(config_dict=config)

        if not training_data:
            # should hold path to folder that save all log information
            self.training_data = "new_training_set"
            self.observations = []

        else:
            self.training_data = training_data
            with open(self.training_data, "r") as fp:
                self.observations = json.load(fp)

    async def initialize(self):
        pass

    async def new_recommendations(self,
                                  new_training_set: list = None,
                                  batches: int = 2,
                                  sampling_strategies: list = [-1, 1]) -> list[dict]:
        if not new_training_set:
            new_training_set = self.observations
        # train the new recommendations
        conditions_to_test = self.gryffin.recommend(
            observations=new_training_set,
            num_batches=batches,
            sampling_strategies=sampling_strategies)  # output two dic in a list
        # -1: exploitation; 1: exploration; [exploit, explore, exploit, explore]
        logger.info(f'suggest {2 * batches} new_exp_conditions: {conditions_to_test}')
        return conditions_to_test

    async def add_new_observation(self, new_observ: dict):
        self.observations.append(new_observ)
        # update the observation file
        # with open(self.training_data, "w") as fp:  # Pickling
        #     json.dump(self.observations, fp, indent=4)


async def main():
    # logger.add(f"D:\BV\BV_experiments\log\myapp.log", rotation="10 MB")
    from BV_experiments.Example3_debenzylation.db_doc import Optimize_parameters
    optimizer = Optimizer(
        config=Optimize_parameters.config,
        num_cpus="1",
        training_data=None)

    new_training_set = [
        {'tbn_equiv': 0.15441222, 'acn_equiv': 0, 'ddq_equiv': 0.007913082, 'dcm_equiv': 806, 'gas': 'oxygen',
         'gl_ratio': 1, 'temperature': 39.25046, 'time': 5.785883, 'light_wavelength': '440nm', 'light_intensity': 24,
         'pressure': 3, "Yield_1": 0.8}
    ]
    n_recomm = await optimizer.new_recommendations(new_training_set, batches=1)
    for n_condition in n_recomm:
        print(n_condition)


if __name__ == "__main__":
    asyncio.run(main())