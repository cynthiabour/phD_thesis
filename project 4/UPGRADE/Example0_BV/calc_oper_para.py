from dotenv import load_dotenv
from loguru import logger

setting_oper_para = {
    "FILLING_TIME": "1.1 min",
    "RATE_AFT_PUMPM": "1.0 ml/min"
}

old_setup = {
    "LOOP_VOLUME": [0.38, "0.75 m", "0.8 mm ID"],
    "CROSS": [0.004],
    "TUBE_CROSS_TO_CROSS": [0.005, "0.07 m", "0.3 mm ID"],
    "TUBE_MIXER_TO_LOOP": [0.007, "0.10 m", "0.3 mm ID"],
    "TUBE_LOOP_TO_MIX_GAS": [0.007, "0.10 m", "0.3 mm ID"],
    "TUBE_MIX_GAS_TO_REACTOR": [0.079, "0.10 m", "1.0 mm ID"],
    "REACTOR": [2.886, "3.67 m", "1.0 mm ID", "total 3.075 ml - (0.10+0.14)*785.4 (ul/m)"],
    "TUBE_REACTOR_TO_BPR": [0.110, "0.14 m", "1.0 mm ID"],
    "BPR": [0.0],
    "TUBE_BPR_TO_PUMPM": [0.008, "0.11 m", "0.3 mm ID"],
    "TUBE_PUMPM_TO_SEPARATOR": [0.014, "0.205 m", "0.3 mm ID"],
    "SEPARATOR": [0.5],
    "AF2400X": [0.788, "1.52 m", "0.032 inch ID"],
    "TUBE_AF2400X_TO_DAD": [0.011, "0.16 m", "0.3 mm ID"],
    "DAD": [0.0],
    "TUBE_DAD_TO_PUMPB": [0.007, "0.10 m", "0.3 mm ID"],
    "TUBE_PUMPB_TO_HPLCVAVLE": [0.130, "0.165 m", "1.0 mm ID"],
    "HPLCLOOP": [0.001],
}

current_setup = {
    "LOOP_VOLUME": [0.38, "0.75 m", "0.8 mm ID"],
    "CROSS": [0.004],
    "TUBE_CROSS_TO_CROSS": [0.005, "0.07 m", "0.3 mm ID"],
    "TUBE_MIXER_TO_LOOP": [0.007, "0.10 m", "0.3 mm ID"],
    "TUBE_LOOP_TO_MIX_GAS": [0.007, "0.10 m", "0.3 mm ID"],
    "TUBE_MIX_GAS_TO_REACTOR": [0.079, "0.10 m", "1.0 mm ID"],
    "REACTOR": [2.886, "3.67 m", "1.0 mm ID", "total 3.075 ml - (0.10+0.14)*785.4 (ul/m)"],
    "TUBE_REACTOR_TO_BPR": [0.110, "0.14 m", "1.0 mm ID"],
    "BPR": [0.0],
    "TUBE_BPR_TO_PUMPM": [0.008, "0.11 m", "0.3 mm ID"],
    "TUBE_PUMPM_TO_SEPARATOR": [0.014, "0.205 m", "0.3 mm ID"],
    "SEPARATOR": [0.5],
    "AF2400X": [0.788, "1.52 m", "0.032 inch ID"],
    "TUBE_AF2400X_TO_DAD": [0.007, "0.10 m", "0.3 mm ID"],
    "DAD": [0.0],
    "TUBE_DAD_TO_PUMPB": [0.011, "0.16 m", "0.3 mm ID"],
    "TUBE_PUMPB_TO_HPLCVAVLE": [0.130, "0.165 m", "1.0 mm ID"],
    "HPLCLOOP": [0.001],
}

# todo: change the loop volume
# LOOP_VOLUME = 0.38  # ml = 0.75 (m) * 502.7 (ul/m)
# FILLING_TIME = 1.1  # min  #
# fixme: try 0.50 ml loop first.....
LOOP_VOLUME = 0.50  # ml = 0.88 (m) * 785.4 (ul/m)
FILLING_TIME = 1.5  # min  #
# LOOP_VOLUME = 1.0  # ml = 0.88 (m) * 785.4 (ul/m)
# FILLING_TIME = 2.0  # min  #
total_infusion_rate = LOOP_VOLUME / FILLING_TIME

CROSS = 0.004
TUBE_CROSS_TO_CROSS = 0.005  # in ml = 0.07 (m)*70.69 (ul/m)
TUBE_MIXER_TO_LOOP = 0.007  # ml = 0.10 (m)*70.69 (ul/m)

TUBE_RX_TO_LOOP = 0.05  # ml  # todo: ?

TUBE_LOOP_TO_MIX_GAS = 0.007  # in ml = 0.10 (m)*70.69 (ul/m)

TUBE_MIX_GAS_TO_REACTOR = 0.079  # in ml = 0.10 (m)*785.4 (ul/m)
REACTOR = 2.886  # ml = 3.075 ml - (0.10+0.14)*785.4 (ul/m)
TUBE_REACTOR_TO_BPR = 0.110  # in ml = 0.14 (m)*785.4 (ul/m)

BPR = 0.0  # ml
TUBE_BPR_TO_PUMPM = 0.008  # in ml = 0.11 (m) * 70.69 (ul/m)   original: 0.028 in ml = 0.40 (m)*70.69 (ul/m)
TUBE_PUMPM_TO_SEPARATOR = 0.014  # in ml = 0.205 (m) * 70.69 (ul/m) original: 0.004 in ml = 0.055 (m)*70.69 (ul/m)
SEPARATOR = 0.5  # ml

AF2400X = 0.788  # in ml = 1.52 (m) * 518.36 (ul/m) -> 0.032"ID

TUBE_AF2400X_TO_DAD = 0.007  # in ml = 0.10 (m)*70.69 (ul/m)

DAD = 0.0  # ml
TUBE_DAD_TO_PUMPB = 0.011  # in ml = 0.16 (m)*70.69 (ul/m)
TUBE_PUMPB_TO_HPLCVAVLE = 0.130  # in ml = 0.165 (m)*785.4 (ul/m)

HPLCLOOP = 0.001  # in ml
TUBE_HPLCLOOP_TO_VALVEC = 0.212  # in ml = 0.27 (m)*785.4 (ul/m)

RATE_AFT_PUMPM = 1.0


def reagent_vol_ratio(condition: dict) -> dict:
    SOLN = {"EY": 0.05, "H3BO3": 1.00}  # in M (mol/L = mmol/ml)

    SUB = {"SM": {"MW": 146.19, "density": 1.087},
           "Tol": {"MW": 92.14, "density": 0.866},
           "TMOB": {"MW": 168.19},
           "DIPEA": {"MW": 129.25, "density": 0.742}}  # {MW in g/mol, density in g/mL}

    SOL = {"MeOH": {"MW": 32.04, "density": 0.792},
           "MeCN": {"MW": 41.05, "density": 0.786}}

    # todo: smart way to calculate the reaction condition....
    def cal_vol_net(mol: float, mw: float, density: float):
        """
        :param mol: in mol
        :param mw:  in g/mol
        :param density: in g/mL
        :return: volume in L
        """
        return mol * mw / (density * 1000)

    def cal_vol_molar(mol: float, mw: float, molar: float):
        """

        :param mol: in mol
        :param mw: in g/mol
        :param molar: in M (mol/L = mmol/ml)
        :return: volume in L
        """
        return mol/molar
    def cal_vol_conc(mol: float, mw: float, conc: float):
        """
        calculate the volume by prepared solution
        :param mol: in mol
        :param mw:  in g/mol
        :param conc: in mg/ml = g/l
        :return: volume in L
        """
        return mol * mw / conc

    def cal_equiv_conc(vol: float, mw: float, conc: float):
        return vol * conc / mw

    # vol_ratio : 1 mmol SM
    # return {"SMIS": 0.001 * (SUB["SM"]["MW"] / SUB["SM"]["density"] + SUB["Tol"]["MW"] / SUB["Tol"]["density"]),
    #         "Dye": condition["dye_equiv"] / SOLN["EY"],
    #         "Activator": condition["activator_equiv"] / SOLN["H3BO3"],
    #         "Quencher": condition["quencher_equiv"] * SUB["DIPEA"]["MW"] * 0.001 / SUB["DIPEA"]["density"],
    #         "Solvent": condition["solvent_equiv"] * SOL["MeOH"]["MW"] * 0.001 / SOL["MeOH"]["density"],
    #         }
    # wrong cal
    # return {"SMIS": 0.001 * (SUB["SM"]["MW"] + SUB["Tol"]["MW"] + SUB["TMOB"]["MW"]) / 1.0912,
    #         "Dye": condition["dye_equiv"] / SOLN["EY"],
    #         "Activator": condition["activator_equiv"] / SOLN["H3BO3"],
    #         "Quencher": condition["quencher_equiv"] * SUB["DIPEA"]["MW"] * 0.001 / SUB["DIPEA"]["density"],
    #         "Solvent": condition["solvent_equiv"] * SOL["MeOH"]["MW"] * 0.001 / SOL["MeOH"]["density"],
    #         }
    return {"SMIS": 0.001 * (SUB["SM"]["MW"] + SUB["Tol"]["MW"] + SUB["TMOB"]["MW"] * 0.5) / 1.0912,
            "Dye": condition["dye_equiv"] / SOLN["EY"],
            "Activator": condition["activator_equiv"] / SOLN["H3BO3"],
            "Quencher": condition["quencher_equiv"] * SUB["DIPEA"]["MW"] * 0.001 / SUB["DIPEA"]["density"],
            "Solvent": condition["solvent_equiv"] * SOL["MeOH"]["MW"] * 0.001 / SOL["MeOH"]["density"],
            }

def calc_inj_loop(condition: dict):
    """Prepare the reaction solution by syringes
    :param condition: the condition from Gryffin + concentration
    :return: flow rate of syringes
    """
    vol_ratio = reagent_vol_ratio(condition)

    # Calculate the required volume to fill the loop [0.1 mL]
    vol_of_all = {key: value * LOOP_VOLUME / sum(vol_ratio.values()) for key, value in vol_ratio.items()}
    rate_of_all = {key: value / FILLING_TIME for key, value in vol_of_all.items()}
    return vol_of_all, rate_of_all

    # original (calc by concentration)
    # mmol_of_SM = LOOP_VOLUME * condition["concentration"]  # concentration in M (mmol/mL)
    # # the volume of each substrate/syringe needed for the loop
    # ml_of_all = {key: value * mmol_of_SM for key, value in vol_ratio.items()}
    # # the volume of make up solvent to reach the concentration.....
    # total_vol = sum(ml_of_all.values())
    # ml_of_all["Solvent"] = LOOP_VOLUME - total_vol
    # rate_of_all = {key: value / FILLING_TIME for key, value in ml_of_all.items()}
    # return Infuse flow rate in ml/min



def calc_dilute_flow_rate(condition: dict) -> dict:
    gl_flow = calc_gas_liquid_flow_rate(condition)

    # todo: change
    conc = condition["concentration"]
    set_liquid_flow = gl_flow["liquid_flow"]

    # DILUTE_VOL = 3  # ml
    # dilute pumpM to increase the flow rate to 1 ml/min
    time_of_dilution = 13.64  #DILUTE_VOL / LOOP_VOLUME  # still 13.64 time

    if RATE_AFT_PUMPM > set_liquid_flow:
        dilute_flow = RATE_AFT_PUMPM - set_liquid_flow
        if dilute_flow > set_liquid_flow * time_of_dilution:  #DILUTE_VOL ~ 5 # ml
            logger.warning(f"the rate of pumpM is {dilute_flow/set_liquid_flow} times of rate of liquid. Change to {time_of_dilution:.2f} times")
            dilute_flow = set_liquid_flow * time_of_dilution
            rate_after_pumpM = set_liquid_flow * (1+time_of_dilution)
        else:
            rate_after_pumpM = RATE_AFT_PUMPM
    else:
        dilute_flow = 0
        rate_after_pumpM = set_liquid_flow

    dilute_factor_pumpM = set_liquid_flow / rate_after_pumpM
    logger.debug(f"concentration after diluted by pumpM: {conc * dilute_factor_pumpM} M")

    # makeup_solvent flow rate (in ml/min)
    ANAL_CONC = 0.010  # HPLC sample in M: 10 mM

    # if the overall volume flow into the camber is larger than the seperator dilute factor will be 1
    dilute_factor_seperator = 1  # 0.3
    logger.debug(f"current dilute_factor_seperator set {dilute_factor_seperator}")
    # dilute_factor_seperator = cal_dilute_factor_sep(rate_after_pumpM)
    conc_aft_sep = conc * dilute_factor_pumpM * dilute_factor_seperator
    logger.debug(f"concentration after seperator: {conc_aft_sep} M")
    if conc_aft_sep > ANAL_CONC:
        makeup_flow = conc_aft_sep * rate_after_pumpM / ANAL_CONC - rate_after_pumpM
    else:
        logger.warning(f"concentration after diluted by pumpM ({conc_aft_sep}) is already too diluted.")
        makeup_flow = 0

    return {"total_flow": gl_flow["total_flow"],
            "liquid_flow": set_liquid_flow,
            "gas_flow": gl_flow["gas_flow"],
            "dilute_flow": dilute_flow,  # for pumpM
            "makeup_flow": makeup_flow,  # for pumpB
            }

def cal_dilute_factor_sep(flow: float = RATE_AFT_PUMPM) -> float:
    """
    In theory, dilute_factor_sep = LOOP_VOLUME / SEPARATOR  # 0.1/0.7 = 0.14 (7 times)

    dilute_factor_seperator = 0.14  #  0.03 ml/min
    dilute_factor_seperator = 0.3  # 0.5 ml/min

    :param flow: liquid flow rate into the seperator
    :return:
    """
    return flow * 0.1 + 0.14

# def dad_threshold(concentration: float, flow_rate: dict) -> float:
#     """
#     dilute factor from 0.14 to 0.33
#     max intensity (by testing)
#     at 2 ml/min : 15 mM * 0.33 = 5 mM: 30 mAu
#     at 0.5 ml/min: 60 mM * ~0.18 = ~10 mM: 90 mAu
#     at 0.03 ml/min: 3000 mM * 0.14 =420 mM;
#
#     :param concentration:
#     :return: mAu
#     """
#     rate_after_pumpM = flow_rate["liquid_flow"] + flow_rate["dilute_flow"]
#
#     dilute_factor_seperator = cal_dilute_factor_sep(rate_after_pumpM)
#     logger.debug(f"dilute factor of the seperator:{dilute_factor_seperator}")
#     conc_aft_sep = concentration * flow_rate["liquid_flow"] / rate_after_pumpM * dilute_factor_seperator
#     return conc_aft_sep * 6000

def calibrate_syringe_rate(calc_inj_rate: dict) -> dict:
    """correction_factor for each pump to give accurate operation parameters"""
    SPUMP_SM_CALIBR = 1
    SPUMP_DYE_CALIBR = 1
    SPUMP_ACTV_CALIBR = 1
    SPUMP_QUNCH_CALIBR = 1
    SPUMP_SOLV_CALIBR = 1

    return {'SMIS': calc_inj_rate['SMIS'] / SPUMP_SM_CALIBR,
            'Dye': calc_inj_rate['Dye'] / SPUMP_DYE_CALIBR,
            'Activator': calc_inj_rate['Activator'] / SPUMP_ACTV_CALIBR,
            'Quencher': calc_inj_rate['Quencher'] / SPUMP_QUNCH_CALIBR,
            'Solvent': calc_inj_rate['Solvent'] / SPUMP_SOLV_CALIBR,
            }

def calibrate_flow_rate(flow_rate: dict) -> dict:
    PUMPA_CALIBR: float = 0.9905  # ml while setting 1.0 ml/min
    PUMPB_CALIBR = 0.9618
    PUMPM_CALIBR = 0.947
    return {'total_flow': flow_rate['total_flow'],
            'liquid_flow': flow_rate['liquid_flow'] / PUMPA_CALIBR,
            'gas_flow': flow_rate['gas_flow'],
            'dilute_flow': flow_rate['dilute_flow'] / PUMPM_CALIBR,
            'makeup_flow': flow_rate['makeup_flow'] / PUMPB_CALIBR,
            }

def check_param_doable(syringe_rate: dict, flow_rate: dict) -> bool:
    """check the operating parameters is in the operating range"""
    # TODO: check pump limitation
    # PumpA: R2
    PUMP_LIMIT_MAX = 9.9  # ml/min
    PUMP_LIMIT_MIN = 0.01  # 0.03 ml/min

    # PumpM: AzuraCompact/00:80:a3:ba:ef:3b
    PUMPM_LIMIT_MAX = 9.9
    PUMPM_LIMIT_MIN = 0.1

    O2FLOW_MAX = 10  # ml/min
    O2FLOW_MIN = 0.1  # 0.2 ml/min; 0.1 ml/min unstable todo: to reach 0.1 ml/min, 0.5 ml/min -> 0.1 ml/min
    PRESSFLOW_MAX = 10
    PRESSFLOW_MIN = 0.2  # ml/min (without backpressure)
    PRESSP_MAX = 10.0  # bar
    PRESSP_MIN = 0.2

    if flow_rate["liquid_flow"] <= PUMP_LIMIT_MIN:
        logger.error(f"liquid_flow: {flow_rate['liquid_flow']} is less than minimum pump limit")
        return False
    elif flow_rate["dilute_flow"] >= PUMPM_LIMIT_MAX:
        logger.error(f"dilute_flow: {flow_rate['dilute_flow']} is lgreater than maximum pump limit")
        return False
    elif flow_rate["makeup_flow"] >= PUMP_LIMIT_MAX:
        logger.error(f"makeup_flow: {flow_rate['makeup_flow']} is greater than maximum pump limit")
        return False
    elif flow_rate["gas_flow"] >= O2FLOW_MAX:
        logger.error(f"gas_flow: {flow_rate['gas_flow']} is greater than maximum MFC limit")
        return False
    elif flow_rate["gas_flow"] <= O2FLOW_MIN:
        logger.error(f"gas_flow: {flow_rate['gas_flow']} is less than minimum MFC limit")
        return False
    elif all(i < 0 for i in syringe_rate.values()):
        logger.error(f"at least one of syringe_rate less than 0")
        return False
    else:
        return True

    # return False if flow_rate["makeup_flow"] >= PUMP_LIMIT_MAX or flow_rate["liquid_flow"] <= PUMP_LIMIT_MIN \
    #                 or flow_rate["gas_flow"] >= O2FLOW_MAX or flow_rate["gas_flow"] <= O2FLOW_MIN \
    #                 or all(i < 0 for i in syringe_rate.values()) else True

def calc_stable_system(condition: dict, flow_rate: dict) -> dict:
    """
    Fill the reactor with the correct gas/liquid ratio after set to the new pressure
    in order the system stablilty influence the overall slug.
    :param condition:
    :param flow_rate:
    :return:
    """
    ratio_gas_to_liquid = flow_rate["gas_flow"] / flow_rate["liquid_flow"]

    max_pumpA = 2
    max_O2MFC = 5
    # the limit 4.5 ml/min pumpA; 10 ml/min O2, but separation poor
    time_g = max_O2MFC / flow_rate["gas_flow"]
    time_l = max_pumpA / flow_rate["liquid_flow"]

    # to check if run flow rate are larger than max gas/liquid limit...

    if time_g <= 1 or time_l <= 1:  # each of them is less than means setting flow rate is faster than max_pre_run
        # time required to fill the reactor (residence time) + the area before light
        fill_system = TUBE_MIX_GAS_TO_REACTOR / flow_rate["total_flow"] + condition["time"]

        prep_sys = {"pre_liquid_flow": flow_rate["liquid_flow"],
                    "pre_gas_flow": flow_rate["gas_flow"],
                    "pre_run_time": fill_system * 1.1}
    else:
        if time_g <= time_l: #time_g is smaller: gas_flow reach the maximum limitation....
            pre_liquid_flow = max_O2MFC / ratio_gas_to_liquid
            req_time = (TUBE_MIX_GAS_TO_REACTOR + REACTOR) / (max_O2MFC/condition["pressure"]
                                                              + pre_liquid_flow)

            prep_sys = {"pre_liquid_flow": pre_liquid_flow,
                        "pre_gas_flow": max_O2MFC,
                        "pre_run_time": req_time * 1.1}
        else:
            pre_gas_flow = max_pumpA * ratio_gas_to_liquid
            req_time = (TUBE_MIX_GAS_TO_REACTOR + REACTOR) / (pre_gas_flow / condition["pressure"]
                                                              + max_pumpA)
            prep_sys = {"pre_liquid_flow": max_pumpA,
                        "pre_gas_flow": pre_gas_flow,
                        "pre_run_time": req_time * 1.1}  #min

    if prep_sys["pre_run_time"] < 5.0:
        logger.debug(f"original pre_run_time {prep_sys['pre_run_time']}")
        prep_sys["pre_run_time"] = 5.0
    return prep_sys

def calc_time(condition: dict, inj_rate: dict, flow_rate: dict) -> dict:
    """
    calculate the time period
    """
    rate_after_pumpM = flow_rate["liquid_flow"] + flow_rate["dilute_flow"]
    rate_after_makeup = rate_after_pumpM + flow_rate["makeup_flow"]

    # trial and error for the purging time required..........
    before_sensor_time: float = (
            TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
            TUBE_MIX_GAS_TO_REACTOR / flow_rate["total_flow"] +
            condition["time"] +
            TUBE_BPR_TO_PUMPM / (flow_rate["liquid_flow"] + flow_rate["gas_flow"]) +  # some gas will be consumed...expand the time
            TUBE_PUMPM_TO_SEPARATOR / (rate_after_pumpM + flow_rate["gas_flow"]) +
            (SEPARATOR + AF2400X + TUBE_AF2400X_TO_DAD) / rate_after_pumpM
            )

    consumed_all_o2: float = (
            TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
            TUBE_MIX_GAS_TO_REACTOR / flow_rate["total_flow"] +
            REACTOR / flow_rate["liquid_flow"] +
            TUBE_BPR_TO_PUMPM / flow_rate["liquid_flow"] +  # all gas
            TUBE_PUMPM_TO_SEPARATOR / rate_after_pumpM +
            (SEPARATOR + AF2400X + TUBE_AF2400X_TO_DAD) / rate_after_pumpM
            )

    dilute_vol = LOOP_VOLUME * rate_after_pumpM / flow_rate["liquid_flow"]  # in a range of
    logger.debug(f"theoretical total volume after seperator: {dilute_vol}")

    # sampling by 1 ul HPLC loop : dilute 2.00 ml of HPLC sampling...once the reaction mixture stable

    total_available_time = LOOP_VOLUME / flow_rate["liquid_flow"]
    logger.debug(f"theoretical available sampling time: {total_available_time}")
    logger.debug(f"total volume of HPLC sample solution will be {total_available_time * rate_after_makeup}")

    """
    # adj_press: adjust
    fill_loop / pushing_mixture: for tubing
    loop_to_sensor: the theoretical maximum time to reach DAD....
    delay_to_valveC: after the front of the peak detected by DAD, the time to reach the collection valve
    
    wait_til_dilute: the leading reaction mixture go to the waste
    dilution: DILUTE_VOL (5 ml) for hplc sampling -> using for pumpB 
    
    start_hplc: collect the middle of the diluted soln (~2.5 mL) 
    purge_tube_to_hplc: switch valveC to waste, wash both side and pumpB purge the tube......
    purge whole system: 5 time volume of the system volume (~4 ml) w/ consistent flow rate...
    """
    prep_sys_para = calc_stable_system(condition, flow_rate)

    time_schedule = {"adj_press": 15,
                     "pre_run_time": prep_sys_para["pre_run_time"],
                     "3_mix":  (CROSS + TUBE_CROSS_TO_CROSS) / (
                             inj_rate['Solvent'] + inj_rate['Activator'] + inj_rate['Quencher']) * 1.2,
                     "5_mix": (CROSS + TUBE_MIXER_TO_LOOP) / total_infusion_rate,
                     "delay_filling": 0.025 / total_infusion_rate,
                     "fill_loop": FILLING_TIME * 1.0,
                     # "pushing_mixture": TUBE_MIXER_TO_LOOP / total_infusion_rate * 0.5,
                     "loop_to_sensor": before_sensor_time,
                     "half_peak": dilute_vol / 2 / rate_after_pumpM,  # before_sensor_time / 2
                     "consumed_all_o2": consumed_all_o2,
                     "start_hplc": (TUBE_DAD_TO_PUMPB / rate_after_pumpM +
                                    (TUBE_PUMPB_TO_HPLCVAVLE + HPLCLOOP) / rate_after_makeup),
                     "purge_system": 5 * (
                             LOOP_VOLUME + TUBE_LOOP_TO_MIX_GAS + TUBE_MIX_GAS_TO_REACTOR + REACTOR +
                             BPR + TUBE_BPR_TO_PUMPM + TUBE_PUMPM_TO_SEPARATOR + SEPARATOR +
                             AF2400X + TUBE_AF2400X_TO_DAD + DAD + TUBE_DAD_TO_PUMPB + TUBE_PUMPB_TO_HPLCVAVLE) / 2.5,
                     }

    # record total operation time: the maximum time.....
    time_schedule["total_operation_time"] = (time_schedule["pre_run_time"]
                                             + time_schedule["3_mix"] + time_schedule["5_mix"] + time_schedule["delay_filling"]
                                             + time_schedule["fill_loop"]
                                             + time_schedule["consumed_all_o2"]
                                             + time_schedule["half_peak"] * 2
                                             + time_schedule["start_hplc"]
                                             + time_schedule["purge_system"]
                                             )
    time_schedule["shortest_before_lc"] = (time_schedule["pre_run_time"]
                                           + time_schedule["3_mix"] + time_schedule["5_mix"] + time_schedule["delay_filling"]
                                           + time_schedule["fill_loop"]
                                           + time_schedule["loop_to_sensor"]
                                           + time_schedule["start_hplc"]
                                           )
    return time_schedule


def exp_code_generator(exp_start_n: int = 0, exp_max_n: int = 500) -> int:
    for exp in range(exp_start_n, exp_max_n + 1):
        yield exp + 1


def calc_concentration(condition: dict) -> float:
    # vol_ratio : 1 mmol SM
    vol_ratio = reagent_vol_ratio(condition)
    return 1 / sum(vol_ratio.values())

def calc_loop_filling(condition: dict) -> dict:
    """
    Calculate the loop filling time
    :param condition:
    :return:
    """
    logger.debug(total_infusion_rate)
    # Calculate the volume ratio of the reagents
    vol_ratio = reagent_vol_ratio(condition)

    # calculate the volume of each reagent and the rate of each reagent
    vol_of_all = {key: value * LOOP_VOLUME / sum(vol_ratio.values()) for key, value in vol_ratio.items()}
    rate_of_all = {key: value / FILLING_TIME for key, value in vol_of_all.items()}

    # push all solution with the same rate
    t_0_1 = (CROSS + TUBE_CROSS_TO_CROSS) / 3 / (total_infusion_rate / 5)
    t_0_2 = CROSS / 2 / (total_infusion_rate / 5)

    # prepare the mixture in first cross and tube to the 2nd cross
    t_1 = (CROSS + TUBE_CROSS_TO_CROSS) / (
            rate_of_all['Solvent'] + rate_of_all['Activator'] + rate_of_all['Quencher']) * 1.2

    # prepare the mixture in the 2nd cross and tube to the loop
    t_2 = (CROSS + TUBE_MIXER_TO_LOOP) / total_infusion_rate

    t_3 = 0.025 / total_infusion_rate  # default waste, 0.025 ml (25 ul)

    # filling time calculation
    t_4 = FILLING_TIME * 1.0  # 1.0 :0.1 ml

    return {"3_prep": t_0_1, "5_prep": t_0_2,
            "3_mix": t_1, "5_mix": t_2,
            "delay_filling": t_3,
            "fill_loop": t_4
            }

if __name__ == "__main__":
    # logger.add("myapp.log", rotation="10 MB")
    # 20240404 control_condition
    control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 2, 'oxygen_equiv': 2.2,
                         'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34,
                         }
    loop_prep_schedule = calc_loop_filling(control_condition)
    logger.info(f"{loop_prep_schedule}")

    logger.info(f"condition: {control_condition}")
    control_condition["concentration"] = calc_concentration(control_condition)
    logger.info(f"theoretically concentration: {control_condition['concentration']}")

    # calculate the setting parameters
    volume, set_syringe_rate = calc_inj_loop(control_condition)
    logger.info(f"syringe rate:{set_syringe_rate}")
    logger.info(f"consumed syringe volume:{volume} ")

    set_gas_liquid_flow = calc_gas_liquid_flow_rate(control_condition)
    logger.info(f"pump:{set_gas_liquid_flow}")

    time_period = calc_time(control_condition, set_syringe_rate, set_gas_liquid_flow)
    logger.info(f"time periods:{time_period}")
    logger.debug(f"Predicted total operation time: {time_period['total_operation_time']}")

    # calibrate the real operating parameters
    setting_syringe_rate = calibrate_syringe_rate(set_syringe_rate)
    setting_gas_liquid_flow = calibrate_flow_rate(set_gas_liquid_flow)

    # calc the system filling
    prepared_system = calc_stable_system(control_condition, set_gas_liquid_flow)
    logger.info(f"for prepared system {prepared_system}")

    # check the platform setting is doable or not
    logger.info(check_param_doable(setting_syringe_rate, setting_gas_liquid_flow))