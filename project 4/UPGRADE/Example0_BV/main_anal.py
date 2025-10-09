import asyncio
from pathlib import Path
from loguru import logger
import socket

# import tenacity

from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch
from BV_experiments.src.general_platform.Librarian.db_models import database_mongo
from BV_experiments.src.general_platform.Librarian.db_models import ExperimentState
from BV_experiments.src.general_platform.platform_error import IncompleteAnalysis
from BV_experiments.src.general_platform.Analysis.anal_hplc_result import processing_hplc_file


async def analysis_main():
    # both computer can run this code...
    logger.add(r"..\logger\overall_analysis_running.log")

    logger.info(f"initialize database")
    if socket.gethostname() == '':
        DB = database_mongo("BV_data_1", database_uri="mongodb://localhost:27017")
    elif socket.gethostname() == '141.14.52.210':
        DB = database_mongo("BV_data_1", database_uri="mongodb://*:*@141.14.52.210:27017")

    await DB.initialize()

    # watching folder
    analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"

    while True:
        # find all experiments' state are analysing
        analysing_exps = await DB.find_exps_by_state(exp_state=ExperimentState.ANALYSING)

        if len(analysing_exps) > 1:
            logger.warning(f"two experiments' state are analysing. Check manually.")

        for exp in analysing_exps:
            # general argument
            mongo_id = exp.id
            condition = exp.exp_condition.model_dump()

            # watching file
            filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")

            # wait 31 min.....hplc (30 min) - purging (9min)
            file_existed = await filewatcher.check_file_existence_timeout(
                file_name=f"{exp.id} - DAD 2.1L- Channel 2.txt",
                timeout=1860,  # TODO: change to the hplc analysis method
                check_interval=5)

            if file_existed:
                attempts = 0
                # PermissionError [Errno 13] Permission denied will happened. try 3 time
                # TODO: tenacity
                # @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(10), reraise=True)
                while attempts < 3:
                    try:
                        # process from txt file to yield and conversion.
                        hplc_results = processing_hplc_file(exp.id,
                                                            file_existed,
                                                            exp.exp_condition.model_dump(),
                                                            "tmob",
                                                            analysed_samples_folder)
                        break
                    except PermissionError:
                        attempts += 1
                        logger.error(f"PermissionError")
                        await asyncio.sleep(10)

                if not hplc_results["parsed_result_215"] and not hplc_results["parsed_result_254"]:
                    logger.error(f'hplc analysis was failed at both wavelength...')

                    # TODO: sampling now is better, the reason failing might more likely the assigment is fails
                    await DB.change_experiment_state(mongo_id, ExperimentState.FAILED)

                    await DB.update_analysis_result(mongo_id, hplc_results)
                    failed_exp = await DB.get_experiment(mongo_id)
                    new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=failed_exp.exp_code + "-1",
                                                                          condition=condition,
                                                                          inj_loop_flow=failed_exp.inj_loop_flow_rate,
                                                                          gas_liquid_flow=failed_exp.flow_rate,
                                                                          time_schedule=failed_exp.time_schedule,
                                                                          experiment_state=ExperimentState.TO_RUN)
                    logger.info(f"save a same experiment {new_exp_to_run_id} to database to run again....")

                else:
                    # save result back to exist document
                    await DB.change_experiment_state(mongo_id, ExperimentState.FINISHED)
                    await DB.update_analysis_result(mongo_id, hplc_results)

            else:
                logger.error(f"The hplc file isn't found! check manually...")
                await DB.change_experiment_state(mongo_id, ExperimentState.FAILED)

                # create new experiment and repeat the reaction condition
                # failed_exp = await DB.get_experiment(mongo_id)
                # new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=failed_exp.exp_code + "-1",
                #                                                       condition=condition,
                #                                                       inj_loop_flow=failed_exp.inj_loop_flow_rate,
                #                                                       gas_liquid_flow=failed_exp.flow_rate,
                #                                                       time_schedule=failed_exp.time_schedule,
                #                                                       experiment_state=ExperimentState.TO_RUN)
                # logger.info(f"save a same experiment {new_exp_to_run_id} to Librarian to run again....")
                raise IncompleteAnalysis

        logger.debug(f"sleep 60 sec wait for experiment to start analysis")
        await asyncio.sleep(60)


async def reprocess_exp():
    logger.info(f"initialize database")
    if socket.gethostname() == '':
        DB = database_mongo("BV_data_1", database_uri="mongodb://localhost:27017")
    elif socket.gethostname() == '141.14.52.210':
        DB = database_mongo("BV_data_1", database_uri="mongodb://*:*@141.14.52.210:27017")

    await DB.initialize()

    # client = AsyncIOMotorClient("mongodb://localhost:27017")
    # await init_beanie(Librarian=client.BV_data_1, document_models=[Experiment])
    # exps = await Experiment.find(
    #     Experiment.hplc_result["hplc_method"] == r"..\BV_General_method_r1met_30min_025mlmin.MET"
    # ).to_list()

    # for exp in exps:
    #     exp.exp_state = ExperimentState.ANALYSING
    #     # exp.hplc_result["hplc_method"] = r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET"
    #     # gradient_for_30min = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 5: 85, 12: 65, 25: 10, 27: 10, 28: 99, 30: 99}
    #     # exp.hplc_result["gradient"] = json.loads(json.dumps(gradient_for_30min))
    #     await exp.save()

    # watching folder
    analysed_samples_folder = r"..\exported_chromatograms"

    # # finished_exps
    # all_finished_exps = await DB.find_exps_by_state(exp_state=ExperimentState.FINISHED)
    # for exp in all_finished_exps:
    #     await DB.change_experiment_state(exp.id, n_state=ExperimentState.ANALYSING)

    # # failed_exps
    # all_failed_exps = await DB.find_exps_by_state(exp_state=ExperimentState.FAILED)
    # for exp in all_failed_exps:
    #     await DB.change_experiment_state(exp.id, n_state=ExperimentState.ANALYSING)

    # start to reprocessing...
    analysing_exps = await DB.find_exps_by_state(exp_state=ExperimentState.ANALYSING)
    for exp in analysing_exps:
        # general argument
        mongo_id = exp.id

        file_path = Path(analysed_samples_folder) / Path(f"{mongo_id} - DAD 2.1L- Channel 2.txt")

        # process from txt file to yield and conversion.
        hplc_results = processing_hplc_file(exp.id,
                                            file_path,
                                            exp.exp_condition.model_dump(),
                                            "tmob",
                                            analysed_samples_folder)

        if not hplc_results["parsed_result_254"]:
            logger.error(f'experiment hplc analysis finished but fail to pursing the result......')
            await DB.change_experiment_state(mongo_id, ExperimentState.FAILED)
            await DB.update_analysis_result(mongo_id, hplc_results)

        else:
            # save result back to exist document
            await DB.change_experiment_state(mongo_id, ExperimentState.FINISHED)
            await DB.update_analysis_result(mongo_id, hplc_results)

async def main():
    # await reprocess_exp()
    await analysis_main()
    # if socket.gethostname() == '':
    #     await analysis_main()
    # elif socket.gethostname() == '141.14.10.52':
    #     await analysis_main()


if __name__ == "__main__":
    asyncio.run(main())
