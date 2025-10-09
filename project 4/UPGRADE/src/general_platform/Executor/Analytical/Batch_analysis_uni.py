"""
The universal code here is used to control the transfer syringe.

"""
import asyncio
import os
from pathlib import Path
from loguru import logger

from dotenv import load_dotenv
from math import floor

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.src.general_platform.platform_error import PlatformError

dotenv_path = Path(r"/BV_experiments/Example2_methionie/.env")

async def transfer(
        withdraw_p: str = "1",
        infuse_p: str = "6",
        withdraw_speed: float = 1.0,
        infuse_speed: float = 1.0,
        withdraw_vol: float = 0.25,
        infuse_vol: float = 0.25,
        execute: bool = False,
        wait_to_finish_infuse: bool = True):
    """
    transfer single unit (per syringe) without change flow rate

    :param withdraw_p: withdraw position
    :param infuse_p: infuse position
    :param withdraw_speed: flow rate to transfer solution (default 1.0 ml/min)
    :param infuse_speed: flow rate to transfer solution (default 1.0 ml/min)
    :param withdraw_vol: should the maximum transfer volume
    :param infuse_vol:
    :param execute:
    :param wait_to_finish_infuse: wait the infusing to finish to start next step
    :return:
        withdraw_time: calculate time during the withdrawing (in min)
        infuse_time: calculate time during the infusing (in min)
    """
    # check the volume is doable
    load_dotenv(dotenv_path=dotenv_path)
    TRANSFER_SYRINGE = 1.0
    viscosity = True #todo: to test

    if withdraw_vol > TRANSFER_SYRINGE or infuse_vol > TRANSFER_SYRINGE:
        raise PlatformError(f"the max transfer vol only {TRANSFER_SYRINGE} ml. Check required transfer vol")

    # todo: current available position
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
        sess.put(sixportvalve_endpoint + "/distribution-valve/position", params={"position": withdraw_p})
        sess.put(syr3_endpoint + "/pump/withdraw",
                 params={"rate": f"{withdraw_speed} ml/min",
                         "volume": f"{withdraw_vol} ml"})
        await asyncio.sleep(withdraw_time * 60)
        if viscosity:
            await asyncio.sleep(2)

        # infuse to
        sess.put(sixportvalve_endpoint + "/distribution-valve/position", params={"position": infuse_p})
        sess.put(syr3_endpoint + "/pump/infuse",
                 params={"rate": f"{infuse_speed} ml/min",
                         "volume": f"{infuse_vol} ml"})

        await asyncio.sleep(infuse_time * 60) if wait_to_finish_infuse else None

    # logger.debug(f"finish one transfer.")
    return withdraw_time, infuse_time


async def empty_syringe(left_volume: float,
                        infuse_speed: float = 1.0,
                        infuse_p: str = "2",
                        wait_to_finish_infuse: bool = True):
    """
    empty the residual solution in the syringe.....

    :param left_volume: left volume in the syringe
    :param infuse_speed: flow rate of infuse
    :param infuse_p: the position of infuse
    :param wait_to_finish_infuse: wait the infusing finish or not
    :return:
    """
    logger.info("____ empty syringe ____")
    infuse_time = left_volume/infuse_speed

    with command_session() as sess:
        sess.put(sixportvalve_endpoint + "/distribution-valve/position", params={"position": infuse_p})
        sess.put(syr3_endpoint + "/pump/infuse",
                 params={"rate": f"{infuse_speed} ml/min",
                         "volume": f"{left_volume} ml"})

        await asyncio.sleep(infuse_time * 60) if wait_to_finish_infuse else None

async def empty_vial(transfer_speed: float = 1.0,
                     vial_vol: float = 4.9,
                     max_transfer_vol: float = 1.0,
                     execute: bool = True):
    """
    empty the vial (less than maximum volume of vial)

    transfer speed, the flow rate to transfer solution (1.0 ml/min)
    vial, the size for the vial (5 ml)
    """
    await deliver_specific_vol(volume=vial_vol, last_full_withdraw=False,
                               withdraw_p="1", infuse_p="waste", withdraw_spd=transfer_speed, infuse_spd=transfer_speed,
                               max_transfer_vol=max_transfer_vol, execute=execute)

async def deliver_specific_vol(
        volume: float,
        last_full_withdraw: bool,
        withdraw_p: str = "1",
        infuse_p: str = "6",
        withdraw_spd: float = 1.0,
        infuse_spd: float = 1.0,
        max_transfer_vol: float = 1.0,
        execute: bool = False,
        wait_to_finish_infuse: bool = False):
    """
    the function is used to deliver set volume
    :param volume: deliver total volume in ml
    :param last_full_withdraw: control the last withdraw is full syringe or rest volume
    :param withdraw_p: control valve position (input)
    :param infuse_p: deliver valve position (output)
    :param withdraw_spd: withdraw speed (ml/min)
    :param infuse_spd: infuse speed (ml/min)
    :param max_transfer_vol: define the maximum transfer each time
    :param execute: execute real transfer or only for calculate
    :param wait_to_finish_infuse:

    :return:
    withdraw_t: total time of withdraw
    infuse_t: total time of infuse
    last_w_vol-volume: provide info of rest volume in syringe
    """
    full_transfer_n = floor(volume / max_transfer_vol)  # 無條件捨去
    last_transfer_vol = volume % max_transfer_vol
    tol_withdraw_t = 0
    tol_infuse_t = 0

    for i in range(full_transfer_n):
        logger.debug(f"The {i + 1} time of transfer. Still {full_transfer_n - i - 1} times of full transfer.")
        w, i = await transfer(withdraw_p, infuse_p, withdraw_spd, infuse_spd, max_transfer_vol, max_transfer_vol, execute, True)
        volume -= max_transfer_vol
        tol_withdraw_t += w
        tol_infuse_t += i

    if last_transfer_vol == 0:
        return tol_withdraw_t, tol_infuse_t, 0, 0

    # last deliver
    logger.debug(f"The last time of transfer.")
    last_w_vol = max_transfer_vol if last_full_withdraw else volume
    w, i = await transfer(withdraw_p=withdraw_p, infuse_p=infuse_p,
                          withdraw_speed=withdraw_spd, infuse_speed=infuse_spd,
                          withdraw_vol=last_w_vol, infuse_vol=volume, execute=execute,
                          wait_to_finish_infuse=wait_to_finish_infuse)
    tol_withdraw_t += w
    tol_infuse_t = tol_infuse_t + i if wait_to_finish_infuse else tol_infuse_t
    # logger.info(f"finish delivering {transfer_vol * full_transfer_n + volume} ml.")
    logger.info(f"still {last_w_vol - volume} ml left in syringe.")
    return tol_withdraw_t, tol_infuse_t, last_w_vol - volume, i

async def air_remove(vol_waste_each: float = 1.0,
                     transfer_vol: float = 1.5,
                     number: int = 4
                     ):
    logger.info("____ air removing : remove the air in the tube....____")
    logger.debug(f"total {vol_waste_each*number} ml was used to remove the air")
    [await transfer(withdraw_p="1", infuse_p="2", withdraw_speed=transfer_vol, infuse_speed=transfer_vol,
                    withdraw_vol=vol_waste_each, infuse_vol=vol_waste_each, execute=True,
                    wait_to_finish_infuse=True) for i in range(number)]

async def clean_vial(rinse_speed: float = 4.0,
                     rinse_vol: float = 4.0,
                     transfer_speed: float = 1.0,
                     infuse_p: str = "waste",
                     transfer_vol: float = 1.0,
                     execute: bool = False):
    """
    deliver solvent to clean the vial.

    :param rinse_speed: flow rate of delivering washing solvent (by hplc pump)
    :param rinse_vol: volume of washing solvent
    :param transfer_speed: rate of deliver the washing solvent (by transfer syringe)
    :param infuse_p: position of deliver the washing solvent
    :param transfer_vol: maximum transfer volume
    :param execute:
    :return:
        rinse_vial_time: time to deliver washing solvent
        t_w + t_i: total time of withdraw and infuse
    """
    # pump M wash
    rinse_vial_time = rinse_vol / rinse_speed
    if execute:
        logger.info("____ start pumping cleaning solvent ____")
        with command_session() as sess:
            sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})
            # fill the vial
            sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"{rinse_speed} ml/min"})
            await asyncio.sleep(rinse_vial_time * 60)
            sess.put(pumpM_endpoint + "/pump/stop")
            sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})

    # empty the vial
    t_w, t_i, rest_vol, i = await deliver_specific_vol(volume=rinse_vol, last_full_withdraw=False,
                                                       withdraw_p="vial", infuse_p=infuse_p,
                                                       withdraw_spd=transfer_speed, infuse_spd=transfer_speed,
                                                       max_transfer_vol=transfer_vol, execute=execute)

    logger.debug(f"time of rinse: {rinse_vial_time} min; time of empty: {t_w + t_i} min.")
    return rinse_vial_time, t_w + t_i


async def wash_system(
        left_volume: float,
        empty_n: int = 1,
        clean_n: int = 3,
        transfer_speed: float = 1.0,
        transfer_vol: float = 1.0,
        execute: bool = True):
    """
    purge the vial (after submitting all analysis): empty the vial and wash the vial....

    :param left_volume: left volume in the vial
    :param empty_n:
    :param clean_n: times of washing the vial
    :param transfer_speed: (rate of syringe)
    :param transfer_vol: (max volume of the syringe)
    :param execute:

    :return:
    """
    # check the volume is doable
    load_dotenv(dotenv_path=dotenv_path)
    max_vial = float(os.environ.get("COLLECTED_VIAL"))

    if left_volume > max_vial:
        raise PlatformError(f"the max transfer vol only {max_vial} ml. Check required transfer vol.")

    logger.info(f"____ empty vial ____")
    await deliver_specific_vol(volume=left_volume, last_full_withdraw=False,
                               withdraw_p="vial", infuse_p="waste",
                               withdraw_spd=transfer_speed, infuse_spd=transfer_speed,
                               max_transfer_vol=transfer_vol, execute=execute)

    logger.info(f"____ clean vial {clean_n} times____")
    [await clean_vial(
        rinse_speed=5.0, rinse_vol=3.0, transfer_speed=transfer_speed, transfer_vol=transfer_vol, execute=execute
    ) for i in range(clean_n-1)]

    # pump M wash
    rinse_vial_time = 1 / 5
    if execute:
        logger.info("____ wash system ____")
        with command_session() as sess:
            # fill the vial
            sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"{5} ml/min"})
            await asyncio.sleep(rinse_vial_time * 60)
            sess.put(pumpM_endpoint + "/pump/stop")

    w, i = await transfer("1", "6", transfer_speed, transfer_speed, 1, 1, execute, False)
    with command_session() as sess:
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": 1})
        await asyncio.sleep(i * 60)
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": 16})

    logger.info("finish purging")

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


async def main():

    with command_session() as sess:
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})
        # fill the vial
        sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"2 ml/min"})
        await asyncio.sleep(1 * 60)
        sess.put(pumpM_endpoint + "/pump/stop")
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})

    await air_remove(0.1, number=4)
    await empty_vial(vial_vol=2.0, transfer_speed=1.5)


if __name__ == "__main__":
    asyncio.run(main())
