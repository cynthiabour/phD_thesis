"""
temperatual debenzylation exector manager

"""
import datetime
import socket
import asyncio
from loguru import logger
import re

from BV_experiments.src.general_platform.Librarian import DatabaseMongo, ExperimentState
from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize
from BV_experiments.src.general_platform.Executor.Analytical import Async_ClarityRemoteInterface
from BV_experiments.src.general_platform.graph import graph_to_dict_basemodel

from BV_experiments.Example3_debenzylation.db_doc import ExpCondRatio, CtrlExperiment, Experiment
from BV_experiments.Example3_debenzylation.executor import DebenzylExecutor

async def executor_manager(DB: DatabaseMongo,
                           setup,  # FlowSetupDad
                           base_exp_info,  # SecondDebenzylation
                           no_of_exp: int = 0,
                           ):
    """
    This function manages the execution of experiments on the platform.
    It initializes the hardware, starts the HPLC, and runs control experiments.
    :param DB: DatabaseMongo instance for database operations
    :param setup: Flowsetup instance containing the flow setup information
    :param base_exp_info: ChemicalReaction instance containing the base experiment information
    :param no_of_exp: Number of experiments to run, default is 0

    main function to send the new experiment from db to execute
    """
    hplc_commander = Async_ClarityRemoteInterface(remote=True,
                                                  host='192.168.10.11',
                                                  port=10015,
                                                  instrument_number=1)
    executor = DebenzylExecutor(setup=setup,
                                base_exp_info=base_exp_info,
                                hplc_commander=hplc_commander,
                                )

    async def start_platform():
        # Initialize logger
        logger.add(r"..\logger\executor_manager_log.log")

        # Initialize hardware & Librarian
        logger.info(f"initialize hardware")
        await exp_hardware_initialize()
        logger.info(f"initialize database")
        await DB.initialize()

    async def start_hplc():

        """ start the hplc flow and set the method"""
        logger.info(f"start hplc")
        # TODO: switch on both DAD manually
        # strat the hplc flow
        await hplc_commander.slow_flowrate_ramp(base_exp_info.hplc_config_info.START_RAMP["path"],
                                                method_list=base_exp_info.hplc_config_info.START_RAMP["method_list"],
                                                )

    # fixme: ask the user to start the hplc manually
    # await start_hplc()

    await start_platform()
    logger.info(f"complete initialization of all hardware....")

    async def run_ctrl_exp(condition: dict):
        # find all ctrl
        latest_doc = await DB.find_lastest_ctrl()
        match = re.search(r'\d+', latest_doc.exp_code)
        new_ctrl = int(match.group(0)) + 1
        logger.debug(f"lastest time {latest_doc.exp_code} is done. next ctrl is {new_ctrl}.")

        # calculate the setting parameters
        (ctrl_condition, volume_for_loop, inj_loop_flow_rate,
         all_flows, time_schedule, doable, setting_flows) = executor.calc_all_parameters(
            condition)
        # check if the platform can run the control experiment
        if not doable:
            raise ValueError("the platform is not able to run the experiment")

        # run the control experiment
        finish_hplc = await executor.run_and_collect(
            mongo_id=f"ctrl_{new_ctrl}",
            condition=ctrl_condition,
            wait_hplc=True,  # wait for the hplc to finish
        )
        if finish_hplc:
            logger.info(f"the control experiment {new_ctrl} is finished!")
            # fixme: process the hplc results: call the function to process the hplc results

            # after finishing, add the control experiment to the database
            # convert the flow setup graph to dict
            flow_setup_dict = graph_to_dict_basemodel(setup.G)
            # create the control experiment document
            ctrl_exp = DB.create_experiment(
                CtrlExperiment,  # Pass the Beanie Document class
                exp_code=f"ctrl_{new_ctrl}",
                exp_state=ExperimentState.TO_RUN,
                exp_condition=ExpCondRatio(**ctrl_condition),
                opt_algorithm="",
                opt_parameters={},
                exp_category=base_exp_info.exp_description,
                SM_info=base_exp_info.SM_info,
                ddq_info=base_exp_info.oxidant_info_1,
                catalyst_info=base_exp_info.catalyst_info,
                solvent1_info=base_exp_info.solvent_info_1,
                solvent2_info=base_exp_info.solvent_info_2,
                IS_info=base_exp_info.IS_info,
                gas_info=base_exp_info.gas_info,
                flow_setup=flow_setup_dict,
                setup_note=setup.physical_info_setup_list,
                dad_info=base_exp_info.dad_info,
                inj_loop_flow_rate=inj_loop_flow_rate,
                inj_loop_volume=volume_for_loop,
                flow_rate=all_flows,
                time_schedule=time_schedule,
                created_at=datetime.datetime.now(),
                excuted_at=datetime.datetime.now(),
                analysed_at=datetime.datetime.now(),
                analytical_method="hplc",
                analytical_result=base_exp_info.hplc_config_info.model_dump(),
                performance_result={
                    # fixme
                    "raw_peak": {},
                    "assigned_peak": {},
                    "Yield_1": {},
                },
                note={}
            )
        else:
            logger.error(f"the control experiment {new_ctrl} is not finished!")
            raise f"the control experiment {new_ctrl} is not finished!"

        # add the control experiment document to the database
        await DB.insert_ctrl(ctrl_exp)

    # start the main loop
    while True:
        # run control experiment every 10 experiments
        if no_of_exp % 10 == 0:
            logger.info(f"run blank test!")
            await executor.run_blank("1st_blank")
            # fixme: modify the ctrl condition here
            ctrl_condition = {"tbn_equiv": 6, "acn_equiv": 700, "ddq_equiv": 0.25, "dcm_equiv": 0,
                              "gas": "oxygen", "gl_ratio": 1.0,
                              "temperature": 30, "time": 5,
                              'light_wavelength': "440nm", "light_intensity": 24, "pressure": 3}

            await run_ctrl_exp(condition=ctrl_condition)

        # find all experiments
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
        logger.debug(f"get {len(exp_to_run_list)} experiments to run! ")

        # sort by exp_code
        ordered_exp_list = sorted(exp_to_run_list, key=lambda exp: int(exp.exp_code.split("-")[2]))
        sorted_id_list = [exp.id for exp in ordered_exp_list]

        # run exp as order
        for next_to_run_id in sorted_id_list:
            # no need to calc it again but load condition directly from the database
            condition, inj_loop_flow_rate, all_flows, schedule = await DB.load_experiment_param(
                next_to_run_id)

            # calibrate the real operating parameters
            # set_gas_liquid_flow = executor.cali_all_parameters(inj_loop_flow_rate, all_flows)

            # wait the short time for complete the next experiment (22- 9- shortest time)
            platform_sleep = (base_exp_info.hplc_config_info.HPLC_RUNTIME -
                              schedule['purge_system'] - schedule['shortest_before_lc'])
            logger.info(f"wait {platform_sleep} min. "
                        f"Start next experiment {next_to_run_id} "
                        f"at {(datetime.datetime.now() + datetime.timedelta(minutes=platform_sleep)).strftime('%H:%M:%S')}")
            await asyncio.sleep(platform_sleep * 60)

            # start TO RUN the experiment
            logger.info(f"run the experiment!!! total predicting running time: {schedule['total_operation_time']}")
            await DB.change_experiment_state(next_to_run_id, ExperimentState.RUNNING)

            logger.info(f"start to run experiment {next_to_run_id} "
                        f"at {datetime.datetime.now().strftime('%H:%M:%S')}")
            # todo: wait for hplc finish or not
            finished_lc = await executor.run_and_collect(mongo_id=next_to_run_id,
                                                         condition=condition,
                                                         wait_hplc=True)
            logger.info(f"experiment {next_to_run_id} is finished at {datetime.datetime.now().strftime('%H:%M:%S')}")

            # change the state of the experiment in the database
            await DB.change_experiment_state(next_to_run_id, ExperimentState.ANALYSING)
            logger.debug(f"start to analysis the experiment")


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import FlowSetupDad, SecondDebenzylation
    if socket.gethostname() == '':

        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://localhost:27017")

        # fixme: change the no_of_exp to make sure you want to run blank or not
        asyncio.run(
            executor_manager(
                DB=DB,
                setup=FlowSetupDad,
                base_exp_info=SecondDebenzylation,
                no_of_exp=0))

    elif socket.gethostname() == '141.14.52.270':
        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://*:*@141.14.52.270:27017")


