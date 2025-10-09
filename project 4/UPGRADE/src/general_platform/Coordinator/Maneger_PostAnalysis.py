"""
add the cl loop (database + process hplc)
"""
import asyncio
from pathlib import Path

from beanie import PydanticObjectId
from loguru import logger
import socket
import time

import math

from BV_experiments.src.general_platform import IncompleteAnalysis, DatabaseError
from BV_experiments.src.general_platform.Analysis import FileWatch
from BV_experiments.src.general_platform.Librarian import DatabaseMongo
from BV_experiments.src.general_platform.Analysis import DadChromatogram
from BV_experiments.src.general_platform.Librarian.db_models import ExperimentState


class PostAnalManeger:
    logger.add(r"..\logger\overall_analysis_running.log")

    def __init__(self,
                 DB: DatabaseMongo,
                 base_exp_info,
                 analysed_folder: str = r"..\exported_chromatograms",
                 ):

        self._base_exp_info = base_exp_info
        self.DB = DB
        self.analysed_info = base_exp_info.hplc_config_info.model_dump()
        self.analysed_folder = analysed_folder

    def txt_to_peaks(self,
                     mongo_id: str | PydanticObjectId,
                     channel: int | None = None) -> dict:
        chrom = DadChromatogram(mongo_id,
                                self._base_exp_info.hplc_config_info,
                                channel=channel)
        # {3.911666666666666: 18.718628756766925, 7.485: 70.24261115428475,
        # 7.903333333333332: 2.0332566029157366,
        # 8.59: 1.679635659626054, 9.26666666666667: 5.739512237518956}
        return chrom.txt_to_peaks()

    def parse_exp_result(self,
                         raw_peak_dict: dict) -> dict | bool:
        pass

    async def update_analysis_result(self,
                                     mongo_id: PydanticObjectId,
                                     hplc_results: dict,
                                     ):
        """
        update the analysis result to the database
        """
        # update the analysis result to the database
        await self.DB.update_analysis_result(mongo_id, hplc_results)
        logger.info(f"update analysis result to database {mongo_id}")
        return True

    # run the analysis forever
    async def run(self,
                  timeout: int = math.inf):

        await self.DB.initialize()
        logger.info(f"initialize database")

        # start watching folder
        starting_time = time.monotonic()
        while timeout - starting_time > 0:
            analysing_exps = await self.DB.find_exps_by_state(exp_state=ExperimentState.ANALYSING)
            if len(analysing_exps) > 1:
                # todo: check
                raise DatabaseError(f"two experiments' state are analysing. Check manually.")

            for exp in analysing_exps:
                # general argument
                mongo_id = exp.id
                condition = exp.exp_condition.model_dump()

                # watching file
                filewatcher = FileWatch(folder_path=self.analysed_folder,
                                        file_extension="txt")
                file_existed: Path | bool = await filewatcher.check_file_existence_timeout(
                    file_name=f"{exp.id} - DAD 2.1L- Channel 3.txt",
                    timeout=(self.analysed_info.HPLC_RUNTIME * 60),
                    check_interval=5)

                if file_existed:
                    attempts = 0
                    # PermissionError [Errno 13] Permission denied will happened. try 3 time
                    # TODO: tenacity
                    # @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(10), reraise=True)
                    while attempts < 3:
                        try:
                            # fixme: process from txt file to yield and conversion.
                            hplc_raw = self.txt_to_peaks(mongo_id,
                                                         channel=3)
                            hplc_results = self.parse_exp_result(hplc_raw)
                            break
                        except PermissionError:
                            attempts += 1
                            logger.error(f"PermissionError. wait 10 sec to retry... ")
                            await asyncio.sleep(10)

                    if not hplc_results["parsed_result_215"] and not hplc_results["parsed_result_254"]:
                        logger.error(f'hplc analysis was failed at both wavelength...')
                        await self.DB.change_experiment_state(mongo_id, ExperimentState.FAILED)
                        await self.DB.update_analysis_result(mongo_id, hplc_results)
                        await self.create_new_exp(mongo_id)

                    else:
                        # save result back to exist document
                        await self.DB.change_experiment_state(mongo_id, ExperimentState.FINISHED)
                        await self.DB.update_analysis_result(mongo_id, hplc_results)

                else:
                    logger.error(f"The hplc file isn't found after timeout! check manually...")
                    await self.DB.change_experiment_state(mongo_id, ExperimentState.FAILED)
                    raise IncompleteAnalysis

                logger.debug(f"sleep 60 sec wait for experiment to start analysis")
                await asyncio.sleep(60)

    async def create_new_exp(self, mongo_id: PydanticObjectId):
        # create new experiment and repeat the reaction condition
        failed_exp = await self.DB.get_experiment(mongo_id)
        new_exp_to_run_id = await self.DB.insert_one_exp_condition(experiment_code=failed_exp.exp_code + "-1",
                                                                   condition=failed_exp.exp_condition.model_dump(),
                                                                   inj_loop_flow=failed_exp.inj_loop_flow_rate,
                                                                   gas_liquid_flow=failed_exp.flow_rate,
                                                                   time_schedule=failed_exp.time_schedule,
                                                                   experiment_state=ExperimentState.TO_RUN)
        logger.info(f"save a same experiment {new_exp_to_run_id} to Librarian to run again....")
        return new_exp_to_run_id


if __name__ == "__main__":

    from BV_experiments.Example3_debenzylation.db_doc import Experiment, CtrlExperiment
    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation

    if socket.gethostname() == '':

        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://localhost:27017")

    elif socket.gethostname() == '141.14.52.270':
        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://*:*@141.14.52.270:27017")

    # start the analysis
    anal_manger = PostAnalManeger(DB, base_exp_info=SecondDebenzylation.hplc_config_info)
    await anal_manger.run(timeout=60 * 60 * 24)
