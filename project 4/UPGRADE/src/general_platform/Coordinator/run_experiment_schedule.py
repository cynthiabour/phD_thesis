from loguru import logger

from calc_oper_para import (calc_time, calc_gas_liquid_flow_rate, calc_concentration, check_param_doable,
                            calibrate_flow_rate, calibrate_syringe_rate, calc_inj_loop, calc_stable_system)
from anal_hplc_chromatogram import HPLC_RUNTIME


def inj_hplc_to_next_exp(exp_schedule: dict, hplc_runtime: float | None = None) -> float :
    """ """
    exp_schedule = {'adj_press': 15, 'pre_run_time': 2.2, 'fill_loop': 1.5, 'pushing_mixture': 0.034999999999999996,
                     'loop_to_sensor': 9.695131426371773, 'half_peak': 4.847565713185887, 'consumed_all_o2': 9.787679996446533,
                     'start_hplc': 0.36887779781906954, 'purge_system': 9.08, 'total_operation_time': 27.819123507451494}

    exp_schedule["shortest_before_lc"] = (exp_schedule["pre_run_time"]
                                          + exp_schedule["fill_loop"] + exp_schedule["pushing_mixture"]
                                          + exp_schedule["loop_to_sensor"] + exp_schedule["start_hplc"]
                                          )

    if hplc_runtime == None:
        hplc_runtime = HPLC_RUNTIME

    return hplc_runtime - exp_schedule["shortest_before_lc"]


if __name__ == "__main__":
    # logger.add("myapp.log", rotation="10 MB")
    whh_136 = {'dye_equiv': 0.10, 'activator_equiv': 0.20, 'quencher_equiv': 2.0, 'oxygen_equiv': 2.0,
                'solvent_equiv': 900.0, 'time': 6, 'light': 13, 'pressure': 4.0, 'temperature': 34,
               }
    logger.info(f"condition: {whh_136}")
    whh_136["concentration"] = calc_concentration(whh_136)
    logger.info(f"theoretically concentration: {whh_136['concentration']}")

    # calculate the setting parameters
    volume, set_syringe_rate = calc_inj_loop(whh_136)
    logger.info(f"syringe rate:{set_syringe_rate}")
    logger.info(f"consumed syringe volume:{volume} ")

    set_gas_liquid_flow = calc_gas_liquid_flow_rate(whh_136)
    logger.info(f"pump:{set_gas_liquid_flow}")

    time_period = calc_time(whh_136, set_gas_liquid_flow)
    logger.info(f"time periods:{time_period}")
    logger.debug(f"Predicted total operation time: {time_period['total_operation_time']}")

    # calibrate the real operating parameters
    setting_syringe_rate = calibrate_syringe_rate(set_syringe_rate)
    setting_gas_liquid_flow = calibrate_flow_rate(set_gas_liquid_flow)

    # check the platform setting is doable or not
    check_param_doable(setting_syringe_rate, setting_gas_liquid_flow)

    # calc the system filling
    prepared_system = calc_stable_system(whh_136, set_gas_liquid_flow)
    logger.info(f"for prepared system {prepared_system}")

    #
    logger.info(check_param_doable(setting_syringe_rate, setting_gas_liquid_flow))