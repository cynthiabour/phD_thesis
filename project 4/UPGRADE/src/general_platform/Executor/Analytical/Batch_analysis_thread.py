"""
The universal code here is used to control the transfer syringe.

"""
import asyncio
import time
import os
from pathlib import Path
from loguru import logger

from dotenv import load_dotenv
from math import floor

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.src.general_platform.platform_error import PlatformError

dotenv_path = Path(r"/BV_experiments/Example2_methionie/.env")

syringe_condition_infuse = True
# global syringe_condition_infuse


# def continue_pump(
#         volumn_limit
# ):
#     pass
#
# def async_to_sync(sync=False):
#     def decorator(async_func):
#         def wrapper(*args, **kwargs):
#             if sync:
#                 return asyncio.run(async_func(*args, **kwargs))
#             else:
#                 loop = asyncio.new_event_loop()
#                 asyncio.set_event_loop(loop)
#                 result = loop.run_until_complete(async_func(*args, **kwargs))
#                 loop.close()
#                 return result
#
#         return wrapper
#
#     return decorator
def empty_vial(transfer_speed: float = 1.0,
                     vial_vol: float = 4.9,
                     transfer_vol: float = 1.0,
                     execute: bool = True):
    """
    transfer speed, the flow rate to transfer solution (1.0 ml/min)
    vial, the size for the vial (5 ml)
    """
    deliver_specific_vol(vial_vol, True, "1", "waste", transfer_speed, transfer_speed, transfer_vol, execute)


def deliver_specific_vol(
        volume: float,
        last_full_withdraw: bool,
        withdraw_p: str = "1",
        infuse_p: str = "6",
        withdraw_spd: float = 1.0,
        infuse_spd: float = 1.0,
        transfer_vol: float = 1.0,
        execute: bool = False):
    """

    :param volume: deliver volume in ml
    :param last_full_withdraw: control the last withdraw is full syringe or rest volume
    :param withdraw_p: control valve position (input)
    :param infuse_p: deliver valve position (output)
    :param withdraw_spd: withdraw speed (ml/min)
    :param infuse_spd: infuse speed (ml/min)
    :param transfer_vol: define the transfer each time
    :param execute: execute real transfer or only for calculate
    :param wait_to_finish_infuse:

    :return:
    withdraw_t: total time of withdraw
    infuse_t: total time of infuse
    last_w_vol-volume: provide info of rest volume in syringe
    """
    full_transfer_n = floor(volume / transfer_vol)  # 無條件捨去
    last_transfer = volume % transfer_vol
    tol_withdraw_t = 0
    tol_infuse_t = 0

    for i in range(full_transfer_n):
        logger.debug(f"{i + 1} time of transfer. Still {full_transfer_n - i - 1} time")
        w, i = transfer(withdraw_p, infuse_p, withdraw_spd, infuse_spd, transfer_vol, transfer_vol, execute)
        volume -= transfer_vol
        tol_withdraw_t += w
        tol_infuse_t += i

    if last_transfer == 0:
        return tol_withdraw_t, tol_infuse_t, 0

    # last deliver
    last_w_vol = transfer_vol if last_full_withdraw else volume
    w, i = transfer(withdraw_p=withdraw_p, infuse_p=infuse_p,
                    withdraw_speed=withdraw_spd, infuse_speed=infuse_spd,
                    withdraw_vol=last_w_vol, infuse_vol=volume, execute=execute,
                    )
    tol_withdraw_t += w
    tol_infuse_t += i
    # logger.info(f"finish delivering {transfer_vol * full_transfer_n + volume} ml.")
    logger.info(f"still {last_w_vol - volume} ml left in syringe.")
    return tol_withdraw_t, tol_infuse_t, last_w_vol - volume


def transfer(
        withdraw_p: str = "1",
        infuse_p: str = "6",
        withdraw_speed: float = 1.0,
        infuse_speed: float = 1.0,
        withdraw_vol: float = 0.25,
        infuse_vol: float = 0.25,
        execute: bool = False):
    """
    transfer single unit (per syringe) without change flow rate

    :param withdraw_p:
    :param infuse_p:
    :param withdraw_speed: flow rate to transfer solution (1.0 ml/min)
    :param infuse_speed: flow rate to transfer solution (1.0 ml/min)
    :param withdraw_vol: the maximum transfer volume
    :param infuse_vol:
    :param execute:
    :return:
    """
    # check the volume is doable
    load_dotenv(dotenv_path=dotenv_path)
    TRANSFER_SYRINGE = float(os.environ.get("TRANSFER_SYRINGE"))

    if withdraw_vol > TRANSFER_SYRINGE or infuse_vol > TRANSFER_SYRINGE:
        raise PlatformError(f"the max transfer vol only {TRANSFER_SYRINGE} ml. Check required transfer vol")

    # current available position
    position_mapping = {"analysis": "6", "vial": "1", "waste": "2"}
    withdraw_p = position_mapping[withdraw_p] if not withdraw_p.isnumeric() else withdraw_p
    infuse_p = position_mapping[infuse_p] if not infuse_p.isnumeric() else infuse_p

    withdraw_time = withdraw_vol / withdraw_speed
    infuse_time = infuse_vol / infuse_speed

    if not execute:
        logger.debug(f"time of withdraw: {withdraw_time} min; time of infuse: {infuse_time} min.")
        return withdraw_time, infuse_time

    # real transfer
    logger.info("____ one transfer ____")
    with command_session() as sess:
        # withdraw from vial
        syringe_condition_infuse = False
        sess.put(sixportvalve_endpoint + "/distribution-valve/position", params={"position": withdraw_p})
        sess.put(syr3_endpoint + "/pump/withdraw",
                 params={"rate": f"{withdraw_speed} ml/min",
                         "volume": f"{withdraw_vol} ml"})
        time.sleep(withdraw_time * 60)

        # infuse to
        syringe_condition_infuse = True
        sess.put(sixportvalve_endpoint + "/distribution-valve/position", params={"position": infuse_p})
        sess.put(syr3_endpoint + "/pump/infuse",
                 params={"rate": f"{infuse_speed} ml/min",
                         "volume": f"{infuse_vol} ml"})
        time.sleep(infuse_time * 60)

    logger.debug(f"complete transfer.")
    return withdraw_time, infuse_time


def clean_vial(rinse_speed: float = 3.0,
               rinse_vol: float = 2.8,
               transfer_speed: float = 1.0,
               infuse_p: str = "waste",
               transfer_vol: float = 1.0,
               execute: bool = False):
    # pump M wash
    rinse_vial_time = rinse_vol / rinse_speed
    if execute:
        logger.info("____ wash system ____")
        with command_session() as sess:
            sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})
            # fill the vial
            sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"{rinse_speed} ml/min"})
            await asyncio.sleep(rinse_vial_time * 60)
            sess.put(pumpM_endpoint + "/pump/stop")
            sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})

    # empty the vial
    t_w, t_i, rest_vol = deliver_specific_vol(volume=rinse_vol, last_full_withdraw=False,
                                              withdraw_p="vial", infuse_p=infuse_p,
                                              withdraw_spd=transfer_speed, infuse_spd=transfer_speed,
                                              transfer_vol=transfer_vol, execute=execute)

    logger.debug(f"time of rinse: {rinse_vial_time} min; time of empty: {t_w + t_i} min.")
    return rinse_vial_time, t_w + t_i

async def wash_system(
        left_volume: float,
        empty_n: int = 1,
        clean_n: int = 3,
        transfer_speed: float = 1.5,
        transfer_vol: float = 1.0,
        execute: bool = True):
    # check the volume is doable
    load_dotenv(dotenv_path=dotenv_path)
    max_vial = float(os.environ.get("COLLECTED_VIAL"))

    if left_volume > max_vial:
        raise PlatformError(f"the max transfer vol only {max_vial} ml. Check required transfer vol.")

    logger.info(f"____ empty vial times____")
    [deliver_specific_vol(volume=left_volume, last_full_withdraw=False,
                          withdraw_p="vial", infuse_p="waste",
                          withdraw_spd=transfer_speed, infuse_spd=transfer_speed,
                          transfer_vol=transfer_vol, execute=execute) for i in range(empty_n)]

    logger.info("____ wash system ____")
    [clean_vial(
        rinse_speed=5.0, rinse_vol=3.0, transfer_speed=transfer_speed, transfer_vol=transfer_vol, execute=execute
    ) for i in range(clean_n - 1)]

    # pump M wash
    rinse_vial_time = 1 / 5
    if execute:
        logger.info("____ wash system ____")
        with command_session() as sess:
            # fill the vial
            sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"{5} ml/min"})
            await asyncio.sleep(rinse_vial_time * 60)
            sess.put(pumpM_endpoint + "/pump/stop")

    w, i = transfer("1", "6", transfer_speed, transfer_speed, 1, 1, execute)
    with command_session() as sess:
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": 1})
        await asyncio.sleep(i * 60)
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": 16})

    logger.info("finish purging")


# blocking function
async def blocking_task():
    # report a message
    print(f'task is start running')
    print(f"{time.time()}")
    # block
    time.sleep(4)
    # report a message
    print('task is done')
    print(f"{time.time()}")


# background coroutine task: for transfer.....
def background():
    # loop forever
    while True:
        # report a message
        print(f'>background task running{time.time()}')
        # sleep for a moment
        time.sleep(0.5)


async def main():
    # create a coroutine for the blocking function call
    coro = asyncio.to_thread(background)
    # execute the call in a new thread and await the result

    await asyncio.gather(coro, blocking_task())

    # tranfer_speed = 1.0
    # w, i = await transfer(withdraw_speed=1.0, infuse_speed=0.5,
    #                       withdraw_vol=0.7, infuse_vol=0.7,
    #                       execute=True)

    t_w, t_i, rest_vol, i = deliver_specific_vol(1.0, False, "vial", "waste", execute=True)
    # await clean_vial(execute=True)
    # await purge_system(1.2, execute=False)

    # remain_mx = 2.3 - w * tranfer_speed
    # e = await empty_vial(transfer_speed=1.5, vial_vol=remain_mx, transfer_vol=1.0, execute=False)
    # rinse_t, empty_t = await clean_vial(
    #     rinse_speed=5.0, rinse_vol=2.8, transfer_speed=1.5, transfer_vol=1.0, execute=False)


if __name__ == "__main__":
    asyncio.run(main())
