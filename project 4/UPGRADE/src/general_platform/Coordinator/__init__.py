from typing import Type
import socket
from beanie import Document

from .Manager_Planner import PlannerManager
from .Manager_PostAnalysis import PostAnalManager

__all__ = ["PostAnalManager", "PlannerManager",
           "find_latest_exp_code", "exp_code_generator",
           "sort_exp", "get_training_dataset"]

def find_latest_exp_code():
    # fixme: for general use
    """
    the function was used to find the current exp code to continue the optimization (by check creating time)
    :return:
    """
    from pymongo import MongoClient
    if socket.gethostname() == '':
        DB = database_mongo("BV_data_1", database_uri="mongodb://localhost:27017")
    elif socket.gethostname() == '141.14.52.210':
        DB = database_mongo("BV_data_1", database_uri="mongodb://*:*@141.14.52.210:27017")

    latest_exp = client.BV_data_1.phenylcyclobutanone.find_one(sort=[("created_at", -1)])
    latest_control = client.BV_data_1["phenylcyclobutanone-control"].find_one(sort=[("created_at", -1)])

    if latest_exp and latest_control:
        return int(latest_exp["exp_code"].split("-")[2]), int(latest_control["exp_code"].split("_")[2])
    elif not latest_exp:
        return 0, int(latest_control["exp_code"].split("_")[2])
    elif not latest_control:
        return int(latest_exp["exp_code"].split("-")[2]), 0
    else:
        return 0, 0

def exp_code_generator(exp_start_n: int = 0, exp_max_n: int = 500) -> int:
    for exp in range(exp_start_n, exp_max_n + 1):
        yield exp + 1

def sort_exp(exp_list: list):
    list_exploitation = []
    list_exploration = []
    for exp in exp_list:
        if int(exp.exp_code.split("-")[2]) % 2 == 1:  # odd now exploration....
            list_exploration.append(exp)
        else:
            list_exploitation.append(exp)

    # sort by exp_code
    ordered_list_exploitation = sorted(list_exploitation, key=lambda exp: int(exp.exp_code.split("-")[2]))
    ordered_list_exploration = sorted(list_exploration, key=lambda exp: int(exp.exp_code.split("-")[2]))
    return ordered_list_exploitation, ordered_list_exploration

def get_training_dataset(experiment: Type[Document]) -> dict:
    condition = experiment.exp_condition.dict()
    parsed_result_254 = experiment.hplc_result["parsed_result_254"]
    condition.update(parsed_result_254)
    condition["id"] = str(
        experiment.id)  # not accept PydanticObjectId /Object of type PydanticObjectId is not JSON serializable
    condition["exp_code"] = experiment.exp_code
    return condition

