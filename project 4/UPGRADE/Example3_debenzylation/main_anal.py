"""Temperal debenzylation experiment analysis script"""

import asyncio
from pathlib import Path
from loguru import logger
import socket

from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch

from BV_experiments.src.general_platform.Librarian import DatabaseMongo, ExperimentState
from BV_experiments.src.general_platform.platform_error import IncompleteAnalysis


async def analysis_manager(DB: DatabaseMongo,
                           ):
    """
    the main function to run the analysis manager.
    This function will run in the background and check the database for experiments that are in the ANALYSING state.
    If there are any experiments in the ANALYSING state, it will check if the hplc file is available.
    If the hplc file is available, it will process the hplc file and update the experiment state to FINISHED.
    """

    # both computer can run this code...
    logger.add(r"..\BV_data\logger\overall_analysis_running.log")

    logger.info(f"initialize database")
    await DB.initialize()

    # watching folder
    analysed_samples_folder = r"\exported_chromatograms"

    while True:
        # find all experiments' state are analysing
        analysing_exps = await DB.find_exps_by_state(exp_state=ExperimentState.ANALYSING)

        if len(analysing_exps) > 1:
            logger.warning(f"two experiments' state are analysing. Check manually.")

        for exp in analysing_exps:
            # general argument
            mongo_id = exp.id
            condition = exp.exp_condition.model_dump()

            # fixme: check
            hplc_runtime = exp.analysis_info["HPLC_RUNTIME"]

            # watching file
            filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")

            file_existed = await filewatcher.check_file_existence_timeout(
                file_name=f"{exp.id} - DAD 2.1L- Channel 3.txt",
                timeout=hplc_runtime * 60,
                check_interval=5)

            if file_existed:
                attempts = 0
                # PermissionError [Errno 13] Permission denied will happened. try 3 time
                while attempts < 3:
                    try:
                        # process from txt file to yield and conversion.
                        # fixme
                        hplc_results = total_analysis(mongo_id)
                        break
                    except PermissionError:
                        attempts += 1
                        logger.error(f"PermissionError")
                        await asyncio.sleep(10)

                # fixme: set the fail
                if not hplc_results["parsed_result_280"]:
                    logger.error(f'hplc analysis was failed at both wavelength...')

                    # TODO: the reason failing might more likely the assigment is fails
                    await DB.change_experiment_state(mongo_id, ExperimentState.FAILED)
                    await DB.update_analysis_result(mongo_id, hplc_results)
                    failed_exp = await DB.get_experiment(mongo_id)
                    # create a new experiment with the same condition
                    # DB.create_new_experiment()
                    # logger.info(f"save a same experiment {new_exp_id} to database to run again....")

                else:
                    # save result back to exist document
                    await DB.change_experiment_state(mongo_id, ExperimentState.FINISHED)
                    await DB.update_analysis_result(mongo_id, hplc_results)

            else:
                logger.error(f"The hplc file isn't found! check manually...")
                await DB.change_experiment_state(mongo_id, ExperimentState.FAILED)
                raise IncompleteAnalysis

        logger.debug(f"sleep 60 sec wait for experiment to start analysis")
        await asyncio.sleep(60)


def total_analysis(mongo_id: str,
                   condition: dict,
                   cc_is: str = None,
                   ) -> dict:
    # todo: process from txt file to yield and conversion.

    performance_result_254 = {"Yield_1": 0.8, "Conversion_1": 0.9, "Selectivity_1": 0.95, "Space_time_yield_1": 0.7}

    hplc_results = {"channel_1": {"raw": raw_result_254, "parsed": parse_result_254, "result": performance_result_254},
                    "channel_2": {"raw": raw_result_215, "parsed": parse_result_215, "result": performance_result},
                    "channel_3": {"raw": raw_result_280, "parsed": parse_result_280, "result": performance_result}}
    return hplc_results


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import Experiment, CtrlExperiment

    if socket.gethostname() == '':

        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://localhost:27017")

        # fixme: change the no_of_exp to make sure you want to run blank or not

    elif socket.gethostname() == '141.14.52.270':
        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://*:*@141.14.52.270:27017")

    asyncio.run(analysis_manager(DB))
