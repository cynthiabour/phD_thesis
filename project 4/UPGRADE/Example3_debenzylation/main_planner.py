"""
Temperal Planner for Debenzylation Experiment
"""
from typing import Type, TypeVar

from beanie import Document
import asyncio
from loguru import logger
import socket
import datetime

from BV_experiments.src.general_platform.Coordinator import find_latest_exp_code, exp_code_generator
from BV_experiments.src.general_platform.Librarian import DatabaseMongo, ExperimentState
from BV_experiments.src.general_platform.Planner import Optimizer

from BV_experiments.Example3_debenzylation.executor import calc_all_parameters
from BV_experiments.src.general_platform.graph import graph_to_dict_basemodel


T = TypeVar("T", bound=Document)
exp_sp, con_sp = find_latest_exp_code()

exp_code = exp_code_generator(exp_sp, 500)
modeltest_code = exp_code_generator(con_sp, 200)



def parse_to_train_obs(experiment) -> dict:

    observation = experiment.exp_condition.model_dump()

    # fixme: the training objective need to be add into observation
    objective = experiment.performance_result["channel_3"]["result"]

    observation.update(objective)
    observation["id"] = str(
        experiment.id)  # not accept PydanticObjectId /Object of type PydanticObjectId is not JSON serializable
    observation["exp_code"] = experiment.exp_code
    return observation

def convert_sugg_to_full(suggestion: dict) -> dict:

    fix_condition = {'tbn_equiv': 1, 'acn_equiv': 0, 'ddq_equiv': 0.5, 'dcm_equiv': 806,
                     'gas': 'oxygen', 'gl_ratio': 1,
                     'temperature': 28, 'time': 2, 'light_wavelength': '440nm',
                     'light_intensity': 24, 'pressure': 3}

    # convert the suggestion to a full condition
    condition = {**fix_condition, **suggestion}
    return condition

async def planner_manager(DB: DatabaseMongo,
                          setup: object,
                          base_exp_info: object,
                          opt_info: object,
                          num_cpus: int = 1,
                          ):

    logger.add(r"..\logger\overall_optimizer_running.log")

    # Initialize Planner & Librarian
    logger.info(f"initialize database and optimizer")
    optimizer = Optimizer(config=opt_info.config,
                          num_cpus=num_cpus)
    await DB.initialize()

    async def watch_2_exp(watch_1: Document, watch_2: Document):
        """watch two experiments and wait until both are finished."""

        logger.info(f"start to watch exp_code: {watch_1.exp_code} ({watch_1.id}) "
                    f"& WHH-136-{watch_2.exp_code} ({watch_2.id})")
        total_watching_time = watch_1.time_schedule["total_operation_time"] + watch_2.time_schedule[
            "total_operation_time"] + 66  # TODO: the hplc method change....
        exp_1, exp_2 = await asyncio.gather(
            DB.get_finished_experiment_timeout(watch_1.id, total_watching_time),
            DB.get_finished_experiment_timeout(watch_2.id, total_watching_time), )

        logger.debug(f"experiment {watch_1.id} succeed.") if exp_1 else logger.error(
            f"ExperimentError: {watch_1.id} state shows {watch_1.exp_state}")
        logger.debug(f"experiment {watch_2.id} succeed.") if exp_2 else logger.error(
            f"ExperimentError: {watch_2.id} state shows {watch_2.exp_state}")

    while True:
        # import all finished observations
        finished_observations = []
        finished_exps: list[Document] = await DB.find_exps_by_state(ExperimentState.FINISHED)

        # process the finished experiments and convert to dict
        for exp in finished_exps:
            # convert the experiment to a dict
            n_obs = parse_to_train_obs(exp)
            finished_observations.append(n_obs)

        new_training_set = optimizer.observations + finished_observations

        # decide num of sugg by waiting experiments fixme don't know this is required or not
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)

        # suggest new experiments:
        if len(exp_to_run_list) > 4:
            # via this, you can ctrl the num of output and sampling_strategies
            conds_to_test = await optimizer.new_recommendations(
                new_training_set=new_training_set,
                batches=1,
                sampling_strategies=[-1, 1]  # -1: exploitation; 1: exploration
            )  # [exploit, explore]
        else:
            conds_to_test = await optimizer.new_recommendations(
                new_training_set=new_training_set,
                batches=2,
                sampling_strategies=[-1, 1]  # -1: exploitation; 1: exploration
            )  # [exploit, explore, exploit, explore]

        logger.info(f"_____________________________________")
        logger.info(f"Suggest {len(conds_to_test)} new experiments to run: {conds_to_test}")


        n = 0
        # check the condition is doable and save to db
        for sugg_cond in conds_to_test:


            # auto-generate experiment code
            code = next(exp_code)
            # Todo: to start from specific number
            experiment_code = f'yxy-001-{code:03}'

            # note: the first experiment is exploitation, the second is exploration
            n += 1
            sampling_strategy = "exploitation" if n % 2 == 1 else "exploration"

            # convert the suggestions to a full condition
            full_cond = convert_sugg_to_full(sugg_cond)

            # calculate all the parameters
            (condition,
             volume_for_loop, inj_loop_flow_rate,
             all_flows, time_schedule,
             doable, setting_syringe_rate) = calc_all_parameters(full_cond, setup, base_exp_info)

            # check the condition is doable
            if doable:
                # logger.info(f"the condition is doable: {condition}")
                exp_state = ExperimentState.TO_RUN
            else:
                logger.error(f"the suggested condition [ {condition}] could not be operated in current system")
                exp_state = ExperimentState.INVALID

            # convert the flow setup graph to dict
            flow_setup_dict = graph_to_dict_basemodel(setup.G)

            # create the control experiment document
            new_sug = DB.create_experiment(
                Experiment,  # Pass the Beanie Document class
                exp_code=experiment_code,
                exp_state=exp_state,
                exp_condition=ExpCondRatio(**condition),
                opt_algorithm=opt_info.algorithm_package,
                opt_parameters=opt_info.config.model_dump() if isinstance(opt_info, Document) else opt_info.config,
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
                analytical_method="hplc",
                analytical_result=base_exp_info.hplc_config_info.model_dump(),
                note={"opt_strategy": sampling_strategy,  # specific for gryffin
                      "sampling_strategies": [-1, 1]   # specific for gryffin
                      }
            )
            await DB.insert_new_exp(new_sug)


        logger.info(f"save {len(conds_to_test)} new experiments to Librarian")
        logger.info(f"_____________________________________")

        # decide next two experiments to conduct....
        exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
        logger.debug(f"{len(exp_to_run_list)} experiments on the watching list!")

        # sort by exp_code
        ordered_exp_list = sorted(exp_to_run_list, key=lambda exp: int(exp.exp_code.split("-")[2]))
        exps_id_list = [exp.id for exp in ordered_exp_list]

        # wait two experiment, fixme: don't know if this is required or not
        await watch_2_exp(ordered_exp_list[0], ordered_exp_list[1])


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import Experiment, CtrlExperiment, ExpCondRatio, Optimize_parameters

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

    from BV_experiments.Example3_debenzylation.db_doc import FlowSetupDad, SecondDebenzylation
    asyncio.run(
        planner_manager(
            DB=DB,
            setup=FlowSetupDad,
            base_exp_info=SecondDebenzylation,
            opt_info=Optimize_parameters,
        ))
