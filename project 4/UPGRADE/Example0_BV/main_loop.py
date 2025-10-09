"""
This is the main loop for the BV_experiments project.
It is designed to run the optimization and experiment processes in an asynchronous manner.

"""
import datetime
import socket
import asyncio
from loguru import logger
from pathlib import Path
import time

from BV_experiments.src.general_platform.Executor import HardwareCalibrator
from BV_experiments.src.general_platform.Planner.Optimization_Gryffin import Optimizer
from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import collect_dad_given_time
from BV_experiments.src.general_platform.Librarian.db_models import ExperimentState
from BV_experiments.src.general_platform.Librarian import DatabaseMongo

from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize, platform_standby
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface
from BV_experiments.Example0_BV.calc_oper_para import (calc_concentration, calc_inj_loop, calc_gas_liquid_flow_rate, calc_time,
                                                       exp_code_generator, calibrate_syringe_rate, calibrate_flow_rate,
                                                       check_param_doable)
from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import HPLC_METHOD, HPLC_RUNTIME
from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.src.general_platform.Executor.Experiment.log_experiment import system_log
from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import adj_bpr, overall_run, run_experiment
from BV_experiments.src.general_platform.Executor.Experiment.log_flow import flow_log


from BV_experiments.src.general_platform.Coordinator import find_latest_exp_code, exp_code_generator, sort_exp

exp_sp, con_sp = find_latest_exp_code()
# if exp_sp % 2 != 0:
    # raise DatabaseError(f"the exp_sp is {exp_sp}, not a even!") if socket.gethostname() == 'BSPC-8WSHWS2' else None
exp_code = exp_code_generator(exp_sp, 500)
modeltest_code = exp_code_generator(con_sp, 200)



async def optimizer_main():
    def parse_Exp_to_dict(experiment: Experiment) -> dict:
        condition = experiment.exp_condition.dict()
        parsed_result_254 = experiment.hplc_result["parsed_result_254"]
        condition.update(parsed_result_254)
        condition["id"] = str(
            experiment.id)  # not accept PydanticObjectId /Object of type PydanticObjectId is not JSON serializable
        condition["exp_code"] = experiment.exp_code
        return condition

    # logger.add(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\overall_optimizer_running.log")
    #
    # # Initialize optimizer & Librarian
    # logger.info(f"initialize database and optimizer")
    # e = 0
    #
    # # Initialize Librarian and the optimizer
    # if socket.gethostname() == 'BSMC-YMEF002121':
    #     DB = database_mongo(database_name="BV_data_1", database_uri="mongodb://localhost:27017")
    #     optimizer = Optimizer(num_cpus="1", training_data="training_set")  # training_set save old data of cyclobutanone
    #
    # elif socket.gethostname() == 'BSPC-8WSHWS2':
    #     DB = database_mongo(database_name="BV_data_1",
    #                         database_uri="mongodb://bs-flow:microreactor7@141.14.52.210:27017")
    #     optimizer = Optimizer(num_cpus="7", training_data="training_set")
    #
    # await DB.initialize()
    #
    # async def watch_2_exp(watch_1, watch_2):
    #     logger.info(f"start to watch exp_code: {watch_1.exp_code} ({watch_1.id}) "
    #                 f"& WHH-136-{watch_2.exp_code} ({watch_2.id})")
    #     total_watching_time = watch_1.time_schedule["total_operation_time"] + watch_2.time_schedule[
    #         "total_operation_time"] + 66  # TODO: the hplc method change....
    #     exp_1, exp_2 = await asyncio.gather(
    #         DB.get_finished_experiment_timeout(watch_1.id, total_watching_time),
    #         DB.get_finished_experiment_timeout(watch_2.id, total_watching_time), )
    #
    #     logger.debug(f"experiment {watch_1.id} succeed.") if exp_1 else logger.error(
    #         f"ExperimentError: {watch_1.id} state shows {watch_1.exp_state}")
    #     logger.debug(f"experiment {watch_2.id} succeed.") if exp_2 else logger.error(
    #         f"ExperimentError: {watch_2.id} state shows {watch_2.exp_state}")

    # Run optimization for MAX_TIME/comsuming all materials
    # MAX_TIME = 8 * 60 * 60
    # start_time = time.monotonic()
    # while time.monotonic() < (start_time + MAX_TIME):
    while True:
        # import all finished observations
        finished_observations = []
        finished_exps = await DB.find_exps_by_state(ExperimentState.FINISHED)
        for exp in finished_exps:
            n_obs = parse_Exp_to_dict(exp)
            finished_observations.append(n_obs)

        new_training_set = optimizer.observations + finished_observations

        # decide number of recommendation by waiting experiments
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
        if len(exp_to_run_list) > 4:
            conditions_to_test = await optimizer.new_recommendations(
                new_training_set=new_training_set, batches=1
            )   #[exploit, explore]
        else:
            conditions_to_test = await optimizer.new_recommendations(
                new_training_set=new_training_set, batches=2
            )   # [exploit, explore, exploit, explore]

        n = 0
        # check the condition is doable and save to db
        for condition in conditions_to_test:
            n += 1
            # auto-generate experiment code
            code = next(exp_code)
            # Todo: to start from specific number
            experiment_code = f'WHH-136-{code:03}'

            # calc concentration
            condition["concentration"] = calc_concentration(condition)
            # calculate the operating parameters
            volume_for_loop, inj_loop_flow_rate = calc_inj_loop(condition)
            gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
            time_schedule = calc_time(condition, inj_loop_flow_rate, gas_liquid_flow)

            # calibrate the real operating parameters
            setting_syringe_rate = calibrate_syringe_rate(inj_loop_flow_rate)
            setting_gas_liquid_flow = calibrate_flow_rate(gas_liquid_flow)

            if n % 2 == 1:
                sampling_strategy = "exploitation"
            else:
                sampling_strategy = "exploration"

            # check operating param in the operating range
            if check_param_doable(setting_syringe_rate, setting_gas_liquid_flow):

                # save recommend exp condition to Librarian
                new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=experiment_code,
                                                                      condition=condition,
                                                                      inj_loop_flow=inj_loop_flow_rate,
                                                                      gas_liquid_flow=gas_liquid_flow,
                                                                      time_schedule=time_schedule,
                                                                      experiment_state=ExperimentState.TO_RUN,
                                                                      sampling_strategy=sampling_strategy
                                                                      )

                logger.info(f"save recommended experiment {new_exp_to_run_id} to database!")

            else:
                new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=experiment_code,
                                                                      condition=condition,
                                                                      inj_loop_flow=inj_loop_flow_rate,
                                                                      gas_liquid_flow=gas_liquid_flow,
                                                                      time_schedule=time_schedule,
                                                                      experiment_state=ExperimentState.INVALID,
                                                                      sampling_strategy=sampling_strategy
                                                                      )
                logger.warning(f"InputNotValid: "
                               f"the suggested experiment {new_exp_to_run_id} could not be operated in current system.")

        logger.info(f"_____________________________________")

        # decide next two experiments to conduct....
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
        logger.debug(f"{len(exp_to_run_list)} experiments on the watching list!")

        # sort by exp_code
        ordered_exp_list = sorted(exp_to_run_list, key=lambda exp: int(exp.exp_code.split("-")[2]))
        exps_id_list = [exp.id for exp in ordered_exp_list]
        # exps_code_list = [exp.exp_code for exp in ordered_exp_list]

        # wait two experiment
        await watch_2_exp(exps_id_list[0], exps_id_list[1])
        # list_exploitation, list_exploration = sort_exp(exp_to_run_list)

        # TODO: change the code to made the exploration exp doable
        # if len(list_exploitation) > 0 and len(list_exploration) > 0:
        #     logger.debug(f"both Exploitation and Exploration have doable experiment.")
        #     n_exploit = list_exploitation[0]
        #     n_explore = list_exploration[0]
        #     await watch_2_exp(n_exploit, n_explore)
        #
        # elif len(exp_to_run_list) >= 2:
        #     logger.warning(f"both experiment come form same method (exploitation/exploration")
        #     await watch_2_exp(exp_to_run_list[0], exp_to_run_list[1])
        #     e += 1
        # else:
        #     logger.warning(f"suggested experiments is less than 1....")
        #     e += 1
        #
        # if e > 6:
        #     logger.error(f"{e}time the experiments less than 1 or only one method experiment.")
        #     logger.error(f"stop all calculation and check the boundary of optimization.")
        #     break


async def experiment_main():
    logger.add(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\overall_platform_running.log")
    # run blank and control...
    n = 0
    # Initialize hardware & Librarian
    logger.info(f"initialize hardware")
    await exp_hardware_initialize()

    # TODO: switch on both DAD manually
    hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015, instrument_number=1)

    async def run_blank(code: int | str, c_time: datetime):
        date_ymd = c_time.strftime("%Y%m%d")
        # run a blank (42 min)
        await hplc_commander.load_method(HPLC_METHOD)
        await hplc_commander.set_sample_name(f"blank_{code}_{date_ymd}")
        await hplc_commander.run()  # delay 2 sec.....
        logger.info(
            f"blank run will finished at {(c_time + datetime.timedelta(minutes=HPLC_RUNTIME)).strftime('%H:%M:%S')}")
        # hplc method change to 40 min... control experiment only required 15 min, sleep 15 min before run control
        await asyncio.sleep(1200)

    # await startup_hplc(hplc_commander)
    # c_time = datetime.datetime.now()
    # await run_blank(code="starting_run", c_time=c_time)

    # Initialize Librarian
    DB = database_mongo(database_name="BV_data_1", database_uri="mongodb://localhost:27017")
    await DB.initialize()
    logger.info(f"complete initialization of all hardware....")

    async def controltest_systemStablility(n: int):
        # control test every 10 exp....
        code = next(modeltest_code)

        c_time = datetime.datetime.now()
        date_ymd = c_time.strftime("%Y%m%d")

        # run blank
        # await run_blank(code, c_time)

        control_code = f"control_test_{code:03}"
        log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date_ymd}_{control_code}.log")
        # i = logger.add(log_path, rotation="10 MB")
        # same reaction condition was used for control experiment
        control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 2, 'oxygen_equiv': 2.2,
                             'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34, }
        control_condition["concentration"] = calc_concentration(control_condition)
        volume_for_loop, loop_flow_rate = calc_inj_loop(control_condition)
        gas_liquid_flow = calc_gas_liquid_flow_rate(control_condition)
        time = calc_time(control_condition, loop_flow_rate, gas_liquid_flow)

        # todo: overall_run testing
        hplc_results = await overall_run(control_code, control_condition, hplc_commander)
        control_exp_id = await DB.insert_control(experiment_code=control_code,
                                                 condition=control_condition,
                                                 inj_loop_flow=loop_flow_rate,
                                                 gas_liquid_flow=gas_liquid_flow,
                                                 time_schedule=time,
                                                 experiment_state=ExperimentState.FINISHED,
                                                 hplc_result=hplc_results)
        logger.info(f"{control_code} (id: {control_exp_id}): {hplc_results}")
        n += 1
        # logger.remove(i)

    while True:
        # run control experiment every 10 experiments
        if n % 10 == 0:
            await controltest_systemStablility(n)

        # load new experiment: decide next two experiments to conduct....
        # without cooler....
        # exp_to_run_list = await Experiment.find(Experiment.exp_state == ExperimentState.TO_RUN,
        #                                         Experiment.exp_condition.temperature > 32).to_list()

        # find all experiments
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
        logger.debug(f"get {len(exp_to_run_list)} experiments to run! ")

        # sort by exp_code
        ordered_exp_list = sorted(exp_to_run_list, key=lambda exp: int(exp.exp_code.split("-")[2]))

        exps_id_list = [exp.id for exp in ordered_exp_list]  # exps_code_list = [exp.exp_code for exp in ordered_exp_list]
        # list_exploitation, list_exploration = sort_exp(exp_to_run_list)

        for next_exp_to_run_id in exps_id_list:  # run exp as order
            # load condition
            condition, inj_loop_flow_rate, gas_liquid_flow, schedule = await DB.load_experiment_param(
                next_exp_to_run_id)

            # calibrate the real operating parameters
            set_gas_liquid_flow = calibrate_flow_rate(gas_liquid_flow)

            # wait the short time for complete the next experiment (42- 9- shortest time)
            platform_sleep = HPLC_RUNTIME - schedule['purge_system'] - schedule['shortest_before_lc']
            logger.info(f"wait {platform_sleep} min. "
                        f"Start next experiment {next_exp_to_run_id} at {(datetime.datetime.now() + datetime.timedelta(minutes=platform_sleep)).strftime('%H:%M:%S')}")
            await asyncio.sleep(platform_sleep * 60)

            # run experiment!
            date = datetime.date.today().strftime("%Y%m%d")
            log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date}_{next_exp_to_run_id}.log")
            i = logger.add(log_path)
            logger.info("_________________________________________________________")
            logger.info(f"condition of {next_exp_to_run_id}: {condition}")

            logger.info(f"start to adjust the system pressure for new experiment.....")
            reach_p = await adj_bpr(condition["pressure"], schedule["adj_press"])

            if not reach_p:
                logger.error(f"the pressure could not reach the required conditions.... Something is wrong!!!")
                await platform_standby(hplc_commander)
                logger.info("platform standby. Wait until hardware being checked!")
                logger.remove(i)
                raise PlatformError

            logger.info(f"run the experiment!!! total predicting running time: {schedule['total_operation_time']}")
            await DB.change_experiment_state(next_exp_to_run_id, ExperimentState.RUNNING)

            tasks = [run_experiment(
                    next_exp_to_run_id,
                    condition,
                    inj_loop_flow_rate,
                    set_gas_liquid_flow,
                    schedule,
                    hplc_commander,
                    wait_hplc=False
                ),
                system_log(date, next_exp_to_run_id, schedule["total_operation_time"]),
                collect_dad_given_time(date, next_exp_to_run_id, schedule["total_operation_time"]),
                flow_log(date, next_exp_to_run_id, schedule["total_operation_time"])
            ]

            # Use asyncio.as_completed to gather results as they complete
            for coro in asyncio.as_completed(tasks):
                result = await coro
                logger.info(f"Function completed: {result}")
                if result:
                    break  # Stop the loop after the first function completes
                elif result is None:
                    # FIXME
                    logger.error(f'result: {result}. wait 20 min')
                    await asyncio.sleep(1200)
            await DB.change_experiment_state(next_exp_to_run_id, ExperimentState.ANALYSING)
            # await asyncio.sleep(600)  # 10 min
            logger.debug(f"start to analysis the experiment, finish the logging")
            # close logger
            logger.remove(i)


async def main():
    if socket.gethostname() == 'BSMC-YMEF002121':
        await experiment_main()
        # await optimizer_main()
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        await optimizer_main()
        # logger.error("the experiment platform is not on this computer...")


if __name__ == "__main__":
    asyncio.run(main())
