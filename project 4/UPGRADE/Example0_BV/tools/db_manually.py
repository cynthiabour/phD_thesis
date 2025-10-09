"""
manual insert or reprocess the data.

1. update note
"""
import asyncio
import json
from pathlib import Path
from beanie import init_beanie, PydanticObjectId
from loguru import logger

# MongoDV driver
from motor.motor_asyncio import AsyncIOMotorClient


from BV_experiments.src.general_platform.Librarian.db_models import *
from BV_experiments.Example0_BV.db_comm import database_mongo


async def get_information():
    # Experiment
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.BV_data_1, document_models=[Experiment])
    exps = await Experiment.find({}).to_list()

    # or retrieve all document by DB class
    # exps= await DB.retrieve_all_documents()


    # Control Experiment
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.BV_data_1, document_models=[ControlExperiment])
    exps = await ControlExperiment.find({}).to_list()

    # save to csv
    import pandas as pd
    save_csv = pd.DataFrame(
        {'concentration': 0.13517330630137067, 'dye_equiv': 0.00835114810615778, 'activator_equiv': 0.3336969316005707,
         'quencher_equiv': 7.98139762878418, 'oxygen_equiv': 1.5498799085617065, 'solvent_equiv': 130.17111206054688,
         'time': 10.0476655960083, 'light': 6.668185234069824, 'pressure': 5.488622665405273,
         'temperature': 10.941827774047852, 'total_flow': 0.28723089681114977, 'liquid_flow': 0.15484021900865305,
         'gas_flow': 0.7266424748751501, 'dilute_flow': 0, 'makeup_flow': 1.9381862161741448, 'code': 'WHH-136-001'},
        index=[0]
    )
    for exp in exps:
        # save to csv
        exp_dict = exp.exp_condition.dict()
        exp_dict_flow = json.loads(json.dumps(exp.flow_rate))
        exp_dict.update(exp_dict_flow)
        # exp_dict["215"] = exp.hplc_result["result_215"]
        exp_dict["code"] = exp.exp_code
        exp_dict["id"] = exp.id
        # exp_dict["254"] = exp.hplc_result["result_254"]
        print(exp_dict)
        df2 = pd.DataFrame(exp_dict, index=[0])
        save_csv = pd.concat([save_csv, df2])

    from datetime import date
    date = date.today().strftime("%Y%m%d")
    save_csv.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\{date}_cruuent_control_date.csv',
                    header=True
                    )

async def old_hplc_method_reprocessing():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.BV_data_1, document_models=[Experiment])
    exps = await Experiment.find(
        Experiment.hplc_result["hplc_method"] == r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET"
    ).to_list()

    for exp in exps:
        exp.exp_state = ExperimentState.ANALYSING
        # exp.hplc_result["hplc_method"] = r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET"
        # gradient_for_30min = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 5: 85, 12: 65, 25: 10, 27: 10, 28: 99, 30: 99}
        # exp.hplc_result["gradient"] = json.loads(json.dumps(gradient_for_30min))
        await exp.save()

async def update_hplc_ctrl(mongo_id: str,
                           control_condition: dict | None = None,
                           n_info: dict | None = None):
    """
    tp update the control experiment with the hplc result

    :param mongo_id:
    :param control_condition:
    :return:
    """
    if not control_condition:
        control_condition = {'dye_equiv': 0.001, 'activator_equiv': 0.020, 'quencher_equiv': 2.0, 'oxygen_equiv': 2.0,
                             'solvent_equiv': 500.0, 'time': 6, 'light': 10, 'pressure': 4.0, 'temperature': 34,
                             }
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        client = AsyncIOMotorClient("mongodb://localhost:27017")
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        client = AsyncIOMotorClient("mongodb://bs-flow:microreactor7@141.14.235.174:27017")

    await init_beanie(database=client.BV_data_1, document_models=[ControlExperiment])

    exp = await ControlExperiment.get(PydanticObjectId(mongo_id))

    hplc_result = exp.hplc_result
    # re-process the hplc result
    result_215 = hplc_result["result_215"]
    result_254 = hplc_result["result_254"]
    # todo: re-process the hplc result or only assign new peak RT

    info = exp.note if exp.note != None else {}
    info.update(n_info)
    exp.note = json.loads(json.dumps(info))
    await exp.save()


async def individual_control_insert(DB: database_mongo,
                                    control_code: str,
                                    control_condition: dict | None = None,
                                    control_finished: bool = False):
    """
    to record the failed control exp into Librarian
    (due to the control is only saved after all process is finish.
    """
    if not control_condition:
        # Example: cotrol_code = control_test_034

        # control_condition = {'dye_equiv': 0.001, 'activator_equiv': 0.020, 'quencher_equiv': 2.0, 'oxygen_equiv': 2.0,
        #                      'solvent_equiv': 700.0, 'time': 6, 'light': 10, 'pressure': 4.0, 'temperature': 31,
        #                      }
        # current control_condition
        control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                             'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34, }
        # old control_condition
        # control_condition = {'dye_equiv': 0.001, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.0,
        #                      'solvent_equiv': 20, 'time': 24, 'light': 13, 'pressure': 4.0, 'temperature': 34,
        #                      }
    from BV_experiments.calc_oper_para import calc_concentration, calc_inj_loop, calc_gas_liquid_flow_rate, calc_time
    control_condition["concentration"] = calc_concentration(control_condition)
    volume_for_loop, loop_flow_rate = calc_inj_loop(control_condition)
    gas_liquid_flow = calc_gas_liquid_flow_rate(control_condition)
    time = calc_time(control_condition, loop_flow_rate, gas_liquid_flow)

    if control_finished:
        # process and save the hplc result to Librarian
        from pathlib import Path
        from BV_experiments.main_anal import processing_hplc_file

        file_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms") / Path(
            f"{control_code} - DAD 2.1L- Channel 2.txt")
        hplc_results = processing_hplc_file(control_code, file_path, control_condition, "tmob")

        # save control by another function
        control_exp_id = await DB.insert_control(experiment_code=control_code,
                                                 condition=control_condition,
                                                 inj_loop_flow=loop_flow_rate,
                                                 gas_liquid_flow=gas_liquid_flow,
                                                 time_schedule=time,
                                                 experiment_state=ExperimentState.FINISHED,
                                                 hplc_result=hplc_results)
    else:
        # save basic hplc information for failing hplc
        from BV_experiments.anal_hplc_chromatogram import (PEAK_RT, PEAK_RT_2, ACCEPTED_SHIFT, HPLC_METHOD,
                                                           HPLC_GRADIENT, HPLC_ELUENT, HPLC_FLOW_RATE)
        assigned_info = {"PEAK_RT": PEAK_RT, "PEAK_RT_2": PEAK_RT_2, "ACCEPTED_SHIFT": ACCEPTED_SHIFT}
        hplc_method_info = {"eluent": HPLC_ELUENT, "gradient": HPLC_GRADIENT, "flow_rate": HPLC_FLOW_RATE}

        hplc_results = {"result_254": False, "result_215": False,
                        "parsed_result_254": False, "parsed_result_215": False,
                        "hplc_method": HPLC_METHOD,
                        "method_info": hplc_method_info,
                        "assigned_PEAKs": assigned_info,
                        }

        # save control by another function
        control_exp_id = await DB.insert_control(experiment_code=control_code,
                                                 condition=control_condition,
                                                 inj_loop_flow=loop_flow_rate,
                                                 gas_liquid_flow=gas_liquid_flow,
                                                 time_schedule=time,
                                                 experiment_state=ExperimentState.FAILED,
                                                 hplc_result=hplc_results)


def save_by_pymongo():  # TODO: unfinished
    from pymongo import MongoClient
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        client = MongoClient('localhost', 27017)
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        client = MongoClient("mongodb://bs-flow:microreactor7@141.14.52.210:27017")

    collection = client.BV_data_1["phenylcyclobutanone-archive"]


async def update_note_ctrl(mongo_id: str, n_info: dict, **kwargs):
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        client = AsyncIOMotorClient("mongodb://localhost:27017")
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        client = AsyncIOMotorClient("mongodb://bs-flow:microreactor7@141.14.52.210:27017")

    await init_beanie(database=client.BV_data_1, document_models=[ControlExperiment])

    exp = await ControlExperiment.get(PydanticObjectId(mongo_id))
    info = exp.note if exp.note != None else {}
    info.update(n_info)
    exp.note = json.loads(json.dumps(info))
    await exp.save()


async def update_note_exp(identifier: PydanticObjectId, n_info: dict, **kwargs):
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        client = AsyncIOMotorClient("mongodb://localhost:27017")
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        client = AsyncIOMotorClient("mongodb://bs-flow:microreactor7@141.14.52.210:27017")

    await init_beanie(database=client.BV_data_1, document_models=[Experiment])

    exp = await Experiment.get(identifier)
    info = exp.note if exp.note != None else {}
    info.update(n_info)
    exp.note = json.loads(json.dumps(info))
    await exp.save()


def processing_hplc_file_autosampler(mongo_id: str, file_existed: Path, condition: dict,
                                     analysed_samples_folder: str = r"W:\BS-FlowChemistry\data\exported_chromatograms"
                                     ) -> dict:
    """

    :param mongo_id: the name of the hplc document
    :param file_existed: from the file_watcher
    :param condition: from the Librarian, only residence time and concentration were used.
    :param analysed_samples_folder: as the name
    :return: a dictionary to save back to mongodb
    """

    from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import (hplc_txt_to_peaks,
                                                                                     PEAK_RT, PEAK_RT_2, ACCEPTED_SHIFT,
                                                                                     HPLC_METHOD, HPLC_GRADIENT, HPLC_FLOW_RATE, HPLC_ELUENT)
    from BV_experiments.src.general_platform.Analysis.anal_hplc_result import parse_raw_exp_result

    # parse the txt file at 215 nm
    raw_result_215 = hplc_txt_to_peaks(mongo_id, file_existed, "215")
    logger.debug(f"raw result at 215 nm: {raw_result_215}")

    parse_result_215 = parse_raw_exp_result(condition, raw_result_215, "215") if raw_result_215 else False
    logger.debug(f"parsed result at 215 nm: {parse_result_215}")

    # parse the txt file at 254 nm
    raw_result_254 = hplc_txt_to_peaks(mongo_id,
                                       Path(analysed_samples_folder) / Path(f"{mongo_id} - DAD 2.1L- Channel 1.txt"),
                                       "254")
    logger.debug(f"result at 254 nm: {raw_result_254}")
    parse_result_254 = parse_raw_exp_result(condition, raw_result_254, "254") if raw_result_254 else False
    logger.debug(f"parsed result at 254 nm: {parse_result_254}")

    assigned_info = {"PEAK_RT": PEAK_RT, "PEAK_RT_2": PEAK_RT_2, "ACCEPTED_SHIFT": ACCEPTED_SHIFT}
    hplc_method_info = {"eluent": HPLC_ELUENT, "gradient": HPLC_GRADIENT, "flow_rate": HPLC_FLOW_RATE}

    return {"result_254": raw_result_254, "result_215": raw_result_215,
            "parsed_result_254": parse_result_254, "parsed_result_215": parse_result_215,
            "hplc_method": HPLC_METHOD,
            "method_info": hplc_method_info,
            "assigned_PEAKs": assigned_info,
            }


async def change_oper_para(exp_id: str | list, DB: database_mongo):
    # type checking
    if isinstance(exp_id, str):
        exp_id_list = [exp_id]
    elif isinstance(exp_id, list):
        exp_id_list = exp_id

    for mongo_id in exp_id_list:
        exp = await DB.get_experiment(PydanticObjectId(mongo_id))
        # failed_exp.exp_state = ExperimentState.FINISHED
        condition = exp.exp_condition.model_dump()

        from BV_experiments.Example0_BV.calc_oper_para import calc_concentration, calc_inj_loop, calc_gas_liquid_flow_rate, calc_time, \
            calibrate_syringe_rate, calibrate_flow_rate
        logger.info(f"condition: {condition}")
        condition["concentration"] = calc_concentration(condition)
        logger.info(f"theoretically concentration: {condition['concentration']}")

        # calculate the setting parameters
        volume, set_syringe_rate = calc_inj_loop(condition)
        logger.info(f"syringe rate:{set_syringe_rate}")
        logger.info(f"consumed syringe volume:{volume} ")
        exp.inj_loop_flow_rate = json.loads(json.dumps(set_syringe_rate))

        set_gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
        logger.info(f"pump:{set_gas_liquid_flow}")
        exp.flow_rate = json.loads(json.dumps(set_gas_liquid_flow))

        # schedule
        time_period = calc_time(condition, set_syringe_rate, set_gas_liquid_flow)
        logger.info(f"time periods:{time_period}")
        logger.debug(f"Predicted total operation time: {time_period['total_operation_time']}")
        exp.time_schedule = json.loads(json.dumps(time_period))

        # additional
        # from BV_experiments.db_models import General_info
        # exp.solvent_info = General_info.solvent_info

        # calibrate the real operating parameters
        setting_syringe_rate = calibrate_syringe_rate(set_syringe_rate)
        setting_gas_liquid_flow = calibrate_flow_rate(set_gas_liquid_flow)

        # file_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms") / Path(
        #     f"{mongo_id} - DAD 2.1L- Channel 2.txt")
        # hplc_results = processing_hplc_file_autosampler(mongo_id, file_path, condition)
        # exp.hplc_result = json.loads(json.dumps(hplc_results))
        await exp.save()

        # # check the platform setting is doable or not
        # logger.info(check_param_doable(setting_syringe_rate, setting_gas_liquid_flow))
        # new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=failed_exp.exp_code + "-1",
        #                                                       condition=failed_exp.exp_condition.dict(),
        #                                                       inj_loop_flow=set_syringe_rate,
        #                                                       gas_liquid_flow=set_gas_liquid_flow,
        #                                                       time_schedule=time_period,
        #                                                       experiment_state=ExperimentState.TO_RUN)


async def change_expstate_exp(id: str,
                              DB: database_mongo,
                              exp_state: ExperimentState = ExperimentState.TO_RUN):
    exp = await DB.get_experiment(PydanticObjectId(id))
    exp.exp_state = exp_state
    await exp.save()


async def ctrl_beanie():
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        client = AsyncIOMotorClient("mongodb://localhost:27017")
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        client = AsyncIOMotorClient("mongodb://bs-flow:microreactor7@141.14.52.270:27017")

    # control
    await init_beanie(database=client.BV_data_1, document_models=[ControlExperiment])

    from BV_experiments.anal_hplc_result import parse_raw_exp_result
    # x = 40
    # while x < 41:
    #     x += 1
    #     ctrl_code = f"control_test_{x:03}"
    #     ctrl_exp = await ControlExperiment.find_one(ControlExperiment.exp_code == ctrl_code)
    #     print(ctrl_exp)

    # ctrls = ["65d4ffc8e4cc9f1ba8ee862f"]
    ctrls = ["65c9fce35c0557baa023c3b1", "65cb77ac84cf8c5518388fd9", "65cbbf9abbf0c02da3d7a9f2"]
    # n_note = {"20240219": "reprocess the hplc result"}
    for x in ctrls:
        exp = await ControlExperiment.get(x)
        print(exp.exp_code)
        print(exp.hplc_result["parsed_result_254"])
        print(exp.hplc_result["parsed_result_215"])
        condition = exp.exp_condition.model_dump()
        print("__tmob__")
        parse_result_254 = parse_raw_exp_result(condition, exp.hplc_result["result_254"], "254", "tmob")
        parse_result_215 = parse_raw_exp_result(condition, exp.hplc_result["result_215"], "215", "tmob")
        print(parse_result_254)
        print(parse_result_215)
        exp.hplc_result["parsed_result_254"] = parse_result_254
        exp.hplc_result["parsed_result_215"] = parse_result_215
        # org_note = exp.note if exp.note != None else {}
        # org_note.update(n_note)
        # exp.note = json.loads(json.dumps(org_note))
        exp.analysed_at = datetime.now()
        await exp.save()


        # mongo_id = exp.exp_code
        # folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms")
        # file_name = f"{mongo_id} - DAD 2.1L- Channel 2.txt"
        # txt_file_existed = folder_path / Path(file_name)
        # n_result = processing_hplc_file(mongo_id, txt_file_existed, exp.exp_condition.model_dump(), cc_is="tmob")
        # print(n_result['parsed_result_215'])
        # print(n_result['parsed_result_254'])
        # exp.hplc_result = json.loads(json.dumps(n_result))
        # await exp.save()

    # exp = await ControlExperiment.get(PydanticObjectId("65cbbf9abbf0c02da3d7a9f2"))  #ctrl-047

    # # experiment
    # await init_beanie(Librarian=client.BV_data_1, document_models=[Experiment])
    #
    # exp = await Experiment.get(PydanticObjectId("64934a0d6914fda49518162a"))
    # exp.exp_state = ExperimentState.TO_RUN


async def save_data_to_csv(is_ctrl_data: bool = False):
    """get current control experiment/regular experiment condition data to csv"""
    if is_ctrl_data:
        # Control Experiment
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        await init_beanie(database=client.BV_data_1, document_models=[ControlExperiment])
        exps = await ControlExperiment.find({}).to_list()
    else:
        # Experiment
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        await init_beanie(database=client.BV_data_1, document_models=[Experiment])
        exps = await Experiment.find({}).to_list()

    # or retrieve all document by DB class
    # exps= await DB.retrieve_all_documents()

    # save to csv
    import pandas as pd
    save_csv = pd.DataFrame(
        {'concentration': 0.0, 'dye_equiv': 0.0, 'activator_equiv': 0.0,
         'quencher_equiv': 0.0, 'oxygen_equiv': 0.0, 'solvent_equiv': 0.0,
         'time': 0.0, 'light': 0, 'pressure': 0.0,
         'temperature': 0, 'total_flow': 0.0, 'liquid_flow': 0.0,
         'gas_flow': 0.0, 'dilute_flow': 0, 'makeup_flow': 1.9381862161741448,
         'code': 'WHH-136-001', 'id': '65c9fce35c0557baa023c3b1',
         'Yield_1': 0.0, 'Conversion_1': 0.0, 'Productivity_1': 0.0,
         'Yield_2': 0.0, 'Conversion_2': 0.0, 'Productivity_2': 0.0,
         'Yield_3': 0.0, 'Conversion_3': 0.0, 'Productivity_3': 0.0},
          index=[0]
    )
    for exp in exps:
        exp_dict = exp.exp_condition.model_dump()
        exp_dict_flow = json.loads(json.dumps(exp.flow_rate))
        exp_dict.update(exp_dict_flow)
        # exp_dict["215"] = exp.hplc_result["result_215"]
        exp_dict["code"] = exp.exp_code
        exp_dict["id"] = exp.id
        exp_dict["Yield_1"] = exp.hplc_result["parsed_result_254"]["Yield_1"]
        exp_dict["Conversion_1"] = exp.hplc_result["parsed_result_254"]["Conversion_1"]
        exp_dict["Productivity_1"] = exp.hplc_result["parsed_result_254"]["Productivity_1"]
        exp_dict["Yield_2"] = exp.hplc_result["parsed_result_254"]["Yield_2"]
        exp_dict["Conversion_2"] = exp.hplc_result["parsed_result_254"]["Conversion_2"]
        exp_dict["Productivity_2"] = exp.hplc_result["parsed_result_254"]["Productivity_2"]
        exp_dict["Yield_3"] = exp.hplc_result["parsed_result_215"]["Yield_3"]
        exp_dict["Conversion_3"] = exp.hplc_result["parsed_result_215"]["Conversion_3"]
        exp_dict["Productivity_3"] = exp.hplc_result["parsed_result_215"]["Productivity_3"]

        print(exp_dict)
        df2 = pd.DataFrame(exp_dict, index=[0])
        save_csv = pd.concat([save_csv, df2])

    from datetime import date
    date = date.today().strftime("%Y%m%d")
    save_csv.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\{date}_crruent_control_date.csv',
                    header=True
                    )


async def save_ctrl_hplc_data_to_csv():
    import pandas as pd
    table = pd.DataFrame(
        [0, 0, 0, 0, 0, 0, 0,
         0, 0, 0,
         0, 0, 0,
         0, 0, 0, 0, 0, 0, 0,
         0, 0, 0,
         "test"
         ],
        index=["acid", "ester", "lactone", "unk_4", "SM", "tmob", "tol",
               "Yield_1", "Conversion_1", "Productivity_1",
               "Yield_2", "Conversion_2", "Productivity_2",
               "Acid", "Ester", "Lactone", "Unk_4", "SM", "Tmob", "Tol",
               "Yield_3", "Conversion_3", "Productivity_3",
               "mongo_id"
               ],
        columns=[0]
    ).T

    x = 40
    while x < 41:
        x += 1
        ctrl_code = f"control_test_{x:03}"
        ctrl_exp = await ControlExperiment.find_one(ControlExperiment.exp_code == ctrl_code)
        print(ctrl_exp)
        if ctrl_exp == None:
            continue
        result_215 = ctrl_exp.hplc_result["parsed_result_215"]
        result_254 = ctrl_exp.hplc_result["parsed_result_254"]
        if not result_254 or not result_215:
            logger.warning(f"{ctrl_code} : result 254 or 215 is False")
            continue

        if not "tmob" in result_254:
            logger.warning("no tmob assigned")
            result_215["tmob"] = 0
            result_254["tmob"] = 0

        table = pd.concat(
            [table,
             pd.DataFrame(
                 [result_254["acid"], result_254["ester"], result_254["lactone"], result_254["unk_4"], result_254["SM"],
                  result_254["tmob"], result_254["tol"],
                  result_254["Yield_1"], result_254["Conversion_1"], result_254["Productivity_1"],
                  result_254["Yield_2"], result_254["Conversion_2"], result_254["Productivity_2"],
                  result_215["acid"], result_215["ester"], result_215["lactone"], result_215["unk_4"], result_215["SM"],
                  result_215["tmob"], result_215["tol"],
                  result_215["Yield_3"], result_215["Conversion_3"], result_215["Productivity_3"],
                  ctrl_exp.id
                  ],
                 index=["acid", "ester", "lactone", "unk_4", "SM", "tmob", "tol",
                        "Yield_1", "Conversion_1", "Productivity_1",
                        "Yield_2", "Conversion_2", "Productivity_2",
                        "Acid", "Ester", "Lactone", "Unk_4", "SM", "Tmob", "Tol",
                        "Yield_3", "Conversion_3", "Productivity_3",
                        "mongo_id"
                        ],
                 columns=[x],
             ).T
             ]
        )

    table.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\20230825_table_2.csv',
                 header=True
                 )


async def save_finished_to_csv(DB: database_mongo):
    # save to csv
    import pandas as pd
    save_csv = pd.DataFrame(
        {'concentration': 0.0, 'dye_equiv': 0.0, 'activator_equiv': 0.0,
         'quencher_equiv': 0.0, 'oxygen_equiv': 0.0, 'solvent_equiv': 0.0,
         'time': 0.0, 'light': 0, 'pressure': 0.0,
         'temperature': 0, 'total_flow': 0.0, 'liquid_flow': 0.0,
         'gas_flow': 0.0, 'dilute_flow': 0, 'makeup_flow': 1.9381862161741448,
         'code': 'WHH-136-000', 'id': '0000000000000000000000000',
         "created_time": "00-00-00 00:00:00",
         'Yield_1': 0.0, 'Conversion_1': 0.0, 'Productivity_1': 0.0,
         'Yield_2': 0.0, 'Conversion_2': 0.0, 'Productivity_2': 0.0,
         'Yield_3': 0.0, 'Conversion_3': 0.0, 'Productivity_3': 0.0},
        index=[0]
    )

    exps = await DB.find_exps_by_state(ExperimentState.FINISHED)
    for exp in exps:
        # logger.info(exp.id)
        # logger.info(exp.exp_code)
        # logger.info(exp.exp_condition)
        # logger.info(exp.created_at)
        # logger.info(exp.excuted_at)
        # logger.info(exp.hplc_result['parsed_result_254'])
        # logger.info(exp.hplc_result['parsed_result_215'])
        exp_dict = exp.exp_condition.model_dump()
        exp_dict_flow = json.loads(json.dumps(exp.flow_rate))
        exp_dict.update(exp_dict_flow)
        # exp_dict["215"] = exp.hplc_result["result_215"]
        exp_dict["code"] = exp.exp_code
        exp_dict["id"] = exp.id
        exp_dict["created_time"] = exp.created_at.strftime("%Y-%m-%d %H:%M:%S")
        exp_dict["Yield_1"] = exp.hplc_result["parsed_result_254"]["Yield_1"]
        exp_dict["Conversion_1"] = exp.hplc_result["parsed_result_254"]["Conversion_1"]
        exp_dict["Productivity_1"] = exp.hplc_result["parsed_result_254"]["Productivity_1"]
        exp_dict["Yield_2"] = exp.hplc_result["parsed_result_254"]["Yield_2"]
        exp_dict["Conversion_2"] = exp.hplc_result["parsed_result_254"]["Conversion_2"]
        exp_dict["Productivity_2"] = exp.hplc_result["parsed_result_254"]["Productivity_2"]
        exp_dict["Yield_3"] = exp.hplc_result["parsed_result_215"]["Yield_3"]
        exp_dict["Conversion_3"] = exp.hplc_result["parsed_result_215"]["Conversion_3"]
        exp_dict["Productivity_3"] = exp.hplc_result["parsed_result_215"]["Productivity_3"]

        df2 = pd.DataFrame(exp_dict, index=[0])
        save_csv = pd.concat([save_csv, df2])

    from datetime import date
    date = date.today().strftime("%Y%m%d")
    save_csv.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\{date}_crruent_succeed_data.csv',
                    header=True
                    )


def correct_right_condition(org_inj_flow_rate: dict,
                            org_flow_rate: dict,
                            org_condition: dict,
                            ):
    """
    reprocess all data
    e.g. due to the swap of two syringe (1.0 ml SMIS vs 2.5 ml EY)
    e.g. the concentration of SMIS was wrong

    :param org_flow_rate:
    :param org_inj_flow_rate:
    :param org_condition:
    :return:
    """
    # syringe25 = [7.28, 2.5]
    # syringe10 = [4.61, 1.0]
    # space25 = syringe25[0] ** 2
    # space10 = syringe10[0] ** 2
    # corr_ratio_eosinY = space25 / space10
    # corr_ratio_sm = space10 / space25
    # org_inj_flow_rate["SMIS"] = org_inj_flow_rate["SMIS"] * corr_ratio_sm
    # org_inj_flow_rate["Dye"] = org_inj_flow_rate["Dye"] * corr_ratio_eosinY

    # condition
    SOLN = {"EY": 0.05, "H3BO3": 1.00}  # in M (mol/L = mmol/ml)
    SUB = {"SM": {"MW": 146.19, "density": 1.230},
           "Tol": {"MW": 92.14, "density": 0.866},
           "TMOB": {"MW": 168.19},
           "DIPEA": {"MW": 129.25, "density": 0.742},
           }  # {MW in g/mol, density in g/mL}
    SOL = {"MeOH": {"MW": 32.04, "density": 0.792}, "MeCN": {"MW": 41.05, "density": 0.786}}

    # # vol_ratio : 1 mmol SM
    # ratio_by_flow = {
    #     "SMIS": org_inj_flow_rate['SMIS'] * 1.0912 / (
    #                 SUB["SM"]["MW"] + SUB["Tol"]["MW"] + SUB["TMOB"]["MW"]) / 0.001,  # todo: 0.5 equiv is correct....
    #     # "SMIS": org_inj_flow_rate['SMIS'] / (
    #     #             SUB["SM"]["MW"] / SUB["SM"]["density"] + SUB["Tol"]["MW"] / SUB["Tol"]["density"]) / 0.001,
    #     "dye_equiv": org_inj_flow_rate['Dye'] * SOLN["EY"],
    #     "activator_equiv": org_inj_flow_rate['Activator'] * SOLN["H3BO3"],
    #     "quencher_equiv": org_inj_flow_rate["Quencher"] * SUB["DIPEA"]["density"] / SUB["DIPEA"]["MW"] / 0.001,
    #     "solvent_equiv": org_inj_flow_rate["Solvent"] * SOL["MeOH"]["density"] / SOL["MeOH"]["MW"] / 0.001
    # }
    #
    # # Todo: check calculation....sth wrong.....
    # real_condition = {k: v / ratio_by_flow["SMIS"] for k, v in ratio_by_flow.items()}
    # del real_condition["SMIS"]

    from BV_experiments.calc_oper_para import calc_concentration, reagent_vol_ratio, cor_reagent_vol_ratio

    w_vol_ratio = reagent_vol_ratio(org_condition)
    wrong_ = 0.001 * (SUB["SM"]["MW"] + SUB["Tol"]["MW"] + SUB["TMOB"]["MW"]) / 1.0912

    r_vol_ratio = cor_reagent_vol_ratio(org_condition)
    right_ = 0.001 * (SUB["SM"]["MW"] + SUB["Tol"]["MW"] + SUB["TMOB"]["MW"] * 0.5) / 1.0912

    w_eq = w_vol_ratio["SMIS"] / wrong_
    r_eq = w_vol_ratio['SMIS'] / right_
    print(f"unfortunately, {r_eq / w_eq} of SM was added to each experiment")

    print("original condition")
    print(org_condition)

    real_condition = org_condition.copy()
    real_condition['dye_equiv'] = org_condition['dye_equiv'] / r_eq
    real_condition['activator_equiv'] = org_condition['activator_equiv'] / r_eq
    real_condition['quencher_equiv'] = org_condition['quencher_equiv'] / r_eq
    real_condition['solvent_equiv'] = org_condition['solvent_equiv'] / r_eq
    real_condition['concentration'] = calc_concentration(real_condition)

    # o2 equiv
    vol_ratio_Gtol = org_flow_rate["gas_flow"] / org_flow_rate["liquid_flow"]
    Oxygen_volume_per_mol = 22.4
    real_condition['oxygen_equiv'] = vol_ratio_Gtol / Oxygen_volume_per_mol / real_condition['concentration']

    # real_condition['time'] = org_condition['time']
    # real_condition['light'] = org_condition['light']
    # real_condition['pressure'] = org_condition['pressure']
    # real_condition['temperature'] = org_condition['temperature']

    print("real condition")
    print(real_condition)

    return real_condition

async def manually_db():
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        DB = database_mongo("BV_data_1", database_uri="mongodb://localhost:27017")
    elif socket.gethostname() == 'BSPC-8WSHWS2':
        DB = database_mongo("BV_data_1", database_uri="mongodb://bs-flow:microreactor7@141.14.52.210:27017")
    await init_beanie(database=DB._client.BV_data_1, document_models=[ControlExperiment, Experiment])
    await individual_control_insert(DB, "control_test_073", control_finished=False)
    # await save_finished_to_csv(DB)
    # control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
    #                      'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34, }
    # await individual_control_insert(DB, "control_test_050", control_condition, control_finished=False)
    # ctrl_exp = await ControlExperiment.find_one(ControlExperiment.exp_code == "control_test_050")

    # Change exp state
    # await change_expstate_exp("65cab892ef4a6beb1b012ed0", DB, ExperimentState.INVALID)
    # n_info = {"exp_state_invalid" : "Suggestion was provided based on wrong condition (wrong operation parameters used before.)"}
    # await update_note_exp(PydanticObjectId("65cab892ef4a6beb1b012ed0"), n_info)

    # exps_to_run = await DB.find_exps_by_state(ExperimentState.TO_RUN)
    # all_id = [exp.id for exp in exps_to_run]
    # await change_oper_para(all_id, DB)
    # file_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms") / Path(
    #     f"{exp_code} - DAD 2.1L- Channel 2.txt")
    # results = processing_hplc_file(f"{exp_code}", file_path, condition)
    # exp.hplc_result = json.loads(json.dumps(results))
    # info = exp.note if exp.note != None else {}
    # n_info = {"exp_failed": "forget deactivating autosampler."}
    # info.update(n_info)
    # exp.note = json.loads(json.dumps(info))
    # await exp.save()
    # exp = await DB.get_experiment(PydanticObjectId(mongo_id))
    # exp.exp_state = ExperimentState.FAILED
    # note = {"note": }
    # control.note = json.loads(json.dumps(note))
    # await exp.save()

    # from calc_oper_para import calc_gas_liquid_flow_rate
    # exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)

    # exp_to_run_list = await Experiment.find(Experiment.exp_state == ExperimentState.TO_RUN, Experiment.exp_condition.temperature > 32).to_list()
    # from main_loop import sort_exp
    # list_exploitation, list_exploration = sort_exp(exp_to_run_list)

    # for exp in waiting_list:
    #
    #     n_rate = calc_gas_liquid_flow_rate(exp.exp_condition.dict())
    #     o_rate = exp.flow_rate
    #     o_rate["dilute factor"] = 1
    #     note = {"current_dilute factor": "0.2", "old_flow": o_rate, "modified_flow_rate": str(datetime.now())}
    #     exp.flow_rate = n_rate
    #     exp.note = json.loads(json.dumps(note))
    #
    #     await exp.save()


    # for failed_exp in failed_exps:
    #
    #     new_exp_to_run_id = await DB.insert_one_exp_condition(experiment_code=failed_exp.exp_code + "-1",
    #                                                           condition=failed_exp.exp_condition.dict(),
    #                                                           inj_loop_flow=failed_exp.inj_loop_flow_rate,
    #                                                           gas_liquid_flow=failed_exp.flow_rate,
    #                                                           time_schedule=failed_exp.time_schedule,
    #                                                           experiment_state=ExperimentState.TO_RUN)

if __name__ == "__main__":
    # asyncio.run(ctrl_beanie())
    asyncio.run(manually_db())
