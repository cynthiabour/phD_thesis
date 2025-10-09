
from loguru import logger
import asyncio
import statistics
import time
from collections import deque

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session

from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import background_collect

async def suppressed_sg(sess, acq_bg, ref_bg, acq_channel, ref_channel):
    acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
    ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
    acq_data = acq_signal.json() - acq_bg
    ref_data = ref_signal.json() - ref_bg
    sup_sg = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data
    return sup_sg


async def standard_dad_collect_bg(acq_channel: int = 1,
                                  ref_channel: int = 2,
                                  ) -> tuple[float, float]:

    """ flush the dad channel and collect the background signal"""
    logger.info(f"____ dad background collection ____")
    with command_session() as sess:
        # collect background
        sess.put(dilute_endpoint + "/infuse", params={"rate": "2.0 ml/min"})
        await asyncio.sleep(20.0)

        # collect the background in 20 sec
        acq_bg, ref_bg = await asyncio.gather(
            background_collect(sess, channel=acq_channel, interval=0.4, period=20, timeout=2),
            background_collect(sess, ref_channel, 0.4, 20, 2)   # previously timeout 5 -> 2; interval 0.8 -> 0.4
        )

        logger.debug(f"channel{acq_channel} background:{acq_bg}; channel{ref_channel} background:{ref_bg}")
        return acq_bg, ref_bg

async def dad_tracing_apex(switching_time: time,
                           flow_rate: dict,
                           time_schedule: dict,
                           acq_channel: int = 1,
                           ref_channel: int = 2,
                           acq_bg: float = 0.0,
                           ref_bg: float = 0.0,
                           ) -> bool:
    logger.info(f"____ dad apex tracing ____")

    if acq_bg == 0.0 and ref_bg == 0.0:
        logger.warning(f"background signal is not provided. start to collect the background signal.")
        acq_bg, ref_bg = await standard_dad_collect_bg(acq_channel, ref_channel)

    with command_session() as sess:
        logger.debug(f"channel{acq_channel} background:{acq_bg}; channel{ref_channel} background:{ref_bg}")
        sess.put(dilute_endpoint + "/infuse", params={"rate": f"{flow_rate['dilute_flow_bf_seperator']} ml/min"})
        logger.info(f"Starting collect DAD data at {time.monotonic()}! Waiting for the reaction mixture came out.....")

    # waiting 1.0 times of the calculated time required....
    waiting_time = (time_schedule["loop_to_sensor"]) * 0.9 * 60  # the fast....
    end_waiting_time = switching_time + waiting_time

    tracking_time = (time_schedule["consumed_all_o2"] + time_schedule["half_peak"]) * 60
    # tracking_time = (time_schedule["consumed_all_o2"] * 1.1 + time_schedule[
    #     "half_peak"] * 2) * 60  # todo, should not need 2 time
    end_tracking_time = switching_time + tracking_time
    detected = 0

    # threshold = dad_threshold(condition["concentration"], flow_rate)
    cal_data_deque = deque([0.0] * 20, maxlen=20)  # 30 sec
    cal_med_deque = deque([0.0] * 20, maxlen=20)  # 30 sec
    cal_diff_deque = deque([0.0] * 10, maxlen=10)  # 15 sec

    while time.monotonic() < end_waiting_time:  # only for record the data...
        acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
        ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        logger.info(f"calibrated signal: {cal_data} (median: {cal_med})")
        await asyncio.sleep(0.8)

    logger.info(f"have been waited {time_schedule['loop_to_sensor']} min")

    # change to analytic method port
    analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4', 'WASTE': '6'}  # todo: analvalve_mapping
    sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['HPLC']})
    # start makeup pump
    sess.put(makeup_endpoint + "/infuse", params={"rate": f"{flow_rate['makeup_flow_for_hplc']} ml/min"})
    # logger.debug(f"start pumping pumpB at {time.monotonic()}")
    logger.debug(f"start pumping makeup_pump at {time.monotonic()}")

    while time.monotonic() < end_tracking_time:  # start to track the data...
        acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
        ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        logger.debug(
            f"signal: {acq_signal.json()}(cal: {acq_data}); "
            f"ref: {ref_signal.json()}(cal: {ref_data}); "
            f"calibrate: {cal_data} (median: {cal_med})")

        # TODO: better threshold
        if cal_med > 10:
            detected += 1
            logger.info("color change!")

        if detected == 25:
            logger.info(f"consecutive 25 data points show color on channel{acq_channel}/{ref_channel} at {time.monotonic()}")
            break
        logger.debug(
            f"Sleeping and waiting for the reaction to arrive for {time.monotonic() - end_waiting_time :.0f} s."
            f"We need another {end_tracking_time - time.monotonic():.0f} s")
        await asyncio.sleep(0.8)

    # once the signal (cal) was greater than 60 for 20 sec...
    # start to check the peak apex...
    while time.monotonic() < end_tracking_time:
        # renew the deque by real intensity of the signal
        acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
        ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        # get difference btw 4 time of interval (5 sec)
        cal_diff = cal_med - cal_med_deque[-4]  # deque[-2] is last measure point
        cal_diff_deque.append(cal_diff)
        logger.info(f"calibrated signal: {cal_data} (median: {cal_med}, signal_diff: {cal_diff})")

        # check the signal is increase (by cal_diff) for a while (15 sec)
        ramp_list = [True if x > 0.001 else False for x in cal_diff_deque]

        # check consecutive signal is decrease and break
        if all(ramp_list):
            logger.info(f"the signal is still increasing!!")
        else:
            # ramp_list_2 = [True if x < 0.001 else False for x in cal_diff_deque]
            # ramp_list contains False
            if not ramp_list[-1]:
                # final number in the deque is False
                logger.info(f"the signal might reach the apex!")
                # ramp_list[:] = [not elem for elem in ramp_list]
                flip_ramp_list = [not elem for elem in ramp_list]
                if all(flip_ramp_list):
                    logger.info(f"the signal reach the apex at {time.monotonic()}")
                    return True
            else:
                # not the final number in the deque is False
                logger.info(f"wrong alarm...")

        await asyncio.sleep(0.8)
    return False


async def dad_tracing_half_height(switching_time: float,
                                  flow_rate: dict,
                                  time_schedule: dict,
                                  loop_volume: float,
                                  acq_channel: int = 1,
                                  ref_channel: int = 2,
                                  acq_bg: float = 0.0,
                                  ref_bg: float = 0.0,
                                  ) -> bool:
    logger.info(f"____ dad half_height tracing ____")

    if acq_bg == 0.0 and ref_bg == 0.0:
        logger.warning(f"background signal is not provided. start to collect the background signal.")
        acq_bg, ref_bg = await standard_dad_collect_bg(acq_channel, ref_channel)

    with command_session() as sess:
        logger.debug(f"channel{acq_channel} background:{acq_bg}; channel{ref_channel} background:{ref_bg}")
        sess.put(dilute_endpoint + "/infuse", params={"rate": f"{flow_rate['dilute_flow_bf_seperator']} ml/min"})
        logger.info(f"Starting collect DAD data at {time.monotonic()}! Waiting for the reaction mixture came out.....")

    # waiting 1.0 times of the calculated time required....
    waiting_time = (time_schedule["loop_to_sensor"]) * 0.9 * 60  # the fast....
    end_waiting_time = switching_time + waiting_time

    tracking_time = (time_schedule["consumed_all_o2"] + time_schedule["half_peak"]) * 60
    # todo: before 1.0 time. more time need after adding the bpr after pumpM),
    # tracking_time = (time_schedule["consumed_all_o2"] * 1.1 + time_schedule[
    #     "half_peak"] * 2) * 60  # todo,shouldn't need 2 time
    end_tracking_time = switching_time + tracking_time
    detected = 0

    # threshold = dad_threshold(condition["concentration"], flow_rate)
    cal_data_deque = deque([0.0] * 20, maxlen=20)  # 24 sec (real signal)
    cal_med_deque = deque([0.0] * 40, maxlen=40)  # 32 sec (signal by median filter (30 points)

    diff_data_deque = deque([0.0] * 30, maxlen=30)  # 24 sec (differential one time)
    # diff_med_deque = deque([0.0] * 20, maxlen=20)  # 16 sec (differential value filtering by median)

    ddiff_data_deque = deque([0.0] * 20, maxlen=20)  # 16 sec (differential twice)

    # only for record the data...
    logger.debug(f"___start record dad data___")
    while time.monotonic() < end_waiting_time:
        acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
        ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        # differential twice
        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)  # median of 30 data point
        cal_med_deque.append(cal_med)
        # diff = cal_med - cal_med_deque[0]  # deque[-4], previously. deque[-2] is last measurement
        diff = cal_med - cal_med_deque[-11]  # deque[-4], previously. deque[-2] is last measurement
        diff_data_deque.append(diff)
        # diff_med = statistics.median(diff_data_deque)
        # diff_med_deque.append(diff_med)
        # ddiff = diff_med - diff_med_deque[0]
        ddiff = diff - diff_data_deque[-11]
        ddiff_data_deque.append(ddiff)

        logger.info(f"calibrated signal: {cal_data} (median: {cal_med}, signal_diff: {diff})")
        await asyncio.sleep(0.4)  # previous 1.3 s

    logger.debug(f"have been waited {time_schedule['loop_to_sensor']} min since inject the reaction slug")

    # change to analytic method port
    analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4', 'WASTE': '6'}  # todo: analvalve_mapping
    sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['HPLC']})
    # start makeup pump
    sess.put(makeup_endpoint + "/infuse", params={"rate": f"{flow_rate['makeup_flow_for_hplc']} ml/min"})
    logger.info(f"start pumping the makeup pump at {time.monotonic()}.")

    # start to track the data...
    logger.debug(f"___start track reaction slug____")
    while time.monotonic() < end_tracking_time:
        acq_signal = sess.get(dad_endpoint + f"/channel{acq_channel}/acquire-signal")
        ref_signal = sess.get(dad_endpoint + f"/channel{ref_channel}/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        # differential twice
        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)  # median of 30 data point
        cal_med_deque.append(cal_med)
        # diff = cal_med - cal_med_deque[0]  # deque[-4], previously. deque[-2] is last measurement
        diff = cal_med - cal_med_deque[-11]  # deque[-4], previously. deque[-2] is last measurement
        diff_data_deque.append(diff)
        # diff_med = statistics.median(diff_data_deque)
        # diff_med_deque.append(diff_med)
        # ddiff = diff_med - diff_med_deque[0]
        ddiff = diff - diff_data_deque[-11]
        ddiff_data_deque.append(ddiff)

        logger.debug(
            f"signal: {acq_signal.json()}(cal: {acq_data}); "
            f"ref: {ref_signal.json()}(cal: {ref_data}); "
            f"calibrate: {cal_data} (median: {cal_med})")  # todo: for debugging
        logger.debug(
            f"new diff: {diff} (deque:{diff_data_deque})"
            f"new ddiff: {ddiff} (deque: {diff_data_deque})")

        # TODO: better threshold
        if cal_med > 10:
            detected += 1
            logger.info("color change!")

        if detected == 25:
            # todo: collect reaction mixture
            logger.info(f"consecutive 25 data points show color at {time.monotonic()}")
            detected_time = time.monotonic()
            break
        logger.debug(
            f"Sleeping and waiting for the reaction to arrive for {time.monotonic() - end_waiting_time :.0f} s."
            f"We need another {end_tracking_time - time.monotonic():.0f} s")
        await asyncio.sleep(0.4)  # todo: 1.3

    logger.info("____color change____")
    # once the signal (cal) was greater than 10 for 20 sec, start to check the peak half_height...
    while time.monotonic() < end_tracking_time:
        # renew the deque by real intensity of the signal
        acq_signal = sess.get(dad_endpoint + "/channel1/acquire-signal")
        ref_signal = sess.get(dad_endpoint + "/channel2/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        # differential twice
        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)  # median of 30 data point
        cal_med_deque.append(cal_med)
        # diff = cal_med - cal_med_deque[0]  # deque[-4], previously. deque[-2] is last measurement
        diff = cal_med - cal_med_deque[-11]
        diff_data_deque.append(diff)
        # diff_med = statistics.median(diff_data_deque)
        # diff_med_deque.append(diff_med)
        # ddiff = diff_med - diff_med_deque[0]
        ddiff = diff - diff_data_deque[-11]
        ddiff_data_deque.append(ddiff)
        logger.info(f"calibrated signal: {cal_data} (median: {cal_med}, signal_diff: {diff}, ddiff: {ddiff})")

        # check the signal is increase (by cal_diff) for a while (15 sec)
        ramp_list = [True if x > 0.001 else False for x in diff_data_deque]

        # check consecutive signal is still increasing
        if all(ramp_list):
            logger.debug(f"lovely, the signal is still increasing!!")

            # check ddiff
            dd_ramp_list = [True if x > 0.001 else False for x in ddiff_data_deque]

            # check consecutive slope is still increasing
            if all(dd_ramp_list):  # all True
                logger.debug(f"the slope of the signal peak is still increasing.")
            else:
                if not dd_ramp_list[-1]:
                    # final number in the deque is False
                    logger.info(f"the slope might reach the apex!")

                    # todo: if thresholds checking is longer than 2nd diff, 16sec delay will happened.
                    flip_dd_ramp_list = [not elem for elem in dd_ramp_list]
                    if all(flip_dd_ramp_list):
                        logger.info(f"the signal have reached the half height at {time.monotonic()}.")
                        half_h_time = time.monotonic()

                        # 0.35 mL to reach half height. fixme: 0.35 mL is from???
                        sleeping_time = 0.35 * 60 / flow_rate["bf_sep_rate"] - (half_h_time - detected_time)

                        total_vol_aft_sep = loop_volume * flow_rate["bf_sep_rate"] / flow_rate['liquid_flow']
                        logger.debug(f"theoretical total volume after seperator: {total_vol_aft_sep} mL")

                        if total_vol_aft_sep <= 1.4:
                            end_delay_time = half_h_time + sleeping_time

                        else:
                            stable_vol = total_vol_aft_sep - 1.4
                            # end_delay_time = half_h_time + sleeping_time + stable_vol / 4 / rate_after_pumpM * 60
                            # divide by 1.5 means 2/3 position of loop to hplc analysis
                            end_delay_time = half_h_time + sleeping_time + stable_vol / 1.5 / flow_rate["bf_sep_rate"] * 60
                        while time.monotonic() < end_delay_time:
                            logger.debug(
                                f"Sleeping and waiting for another {end_delay_time - time.monotonic():.0f} s.")
                            await asyncio.sleep(0.4)
                        return True

                else:
                    # not the final number in the deque is False
                    logger.info(f"wrong alarm for the half height...")

        # ramp_list contains False
        else:
            logger.debug(f"the signal might decrease!!")

            if not ramp_list[-1]:
                # final number in the deque is False
                logger.info(f"the signal might reach the apex!")
                flip_ramp_list = [not elem for elem in ramp_list]
                if all(flip_ramp_list):
                    logger.info(f"sadly, the signal is already reach the apex at {time.monotonic()}.")
                    return True

            else:
                # not the final number in the deque is False
                logger.info(f"wrong alarm for the slope...")

        await asyncio.sleep(0.4)

    return False
