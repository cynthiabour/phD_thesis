"""
the standalone script to process the hplc result

"""
from pathlib import Path
from loguru import logger

from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import (hplc_txt_to_peaks,
                                                                                 PEAK_RT, PEAK_RT_2, ACCEPTED_SHIFT,
                                                                                 HPLC_ELUENT, HPLC_GRADIENT, HPLC_FLOW_RATE, HPLC_METHOD,
                                                                                 peak_rt_range)


def processing_hplc_file(mongo_id: str,
                         file_existed: Path,
                         condition: dict,
                         cc_is: str = "tol",
                         analysed_samples_folder: str = r"W:\BS-FlowChemistry\data\exported_chromatograms"
                         ) -> dict:
    """

    :param mongo_id: the name of the hplc document
    :param file_existed: from the file_watcher
    :param condition: from the Librarian, only residence time and concentration were used.
    :param analysed_samples_folder: as the name
    :param cc_is: the internal standard used in the hplc
    :return: a dictionary to save back to mongodb
    """
    # parse the txt file at 215 nm
    raw_result_215 = hplc_txt_to_peaks(mongo_id, file_existed, "215", cc_is)
    logger.debug(f"raw result at 215 nm: {raw_result_215}")

    parse_result_215 = parse_raw_exp_result(condition, raw_result_215, "215", cc_is) if raw_result_215 else False
    logger.debug(f"parsed result at 215 nm: {parse_result_215}")

    # parse the txt file at 254 nm
    raw_result_254 = hplc_txt_to_peaks(mongo_id,
                                       Path(analysed_samples_folder) / Path(f"{mongo_id} - DAD 2.1L- Channel 1.txt"),
                                       "254", cc_is)
    logger.debug(f"result at 254 nm: {raw_result_254}")

    parse_result_254 = parse_raw_exp_result(condition, raw_result_254, "254", cc_is) if raw_result_254 else False
    logger.debug(f"parsed result at 254 nm: {parse_result_254}")

    assigned_info = {"PEAK_RT": PEAK_RT, "PEAK_RT_2": PEAK_RT_2, "ACCEPTED_SHIFT": ACCEPTED_SHIFT}
    hplc_method_info = {"eluent": HPLC_ELUENT, "gradient": HPLC_GRADIENT, "flow_rate": HPLC_FLOW_RATE}

    return {"result_254": raw_result_254,
            "result_215": raw_result_215,
            "parsed_result_254": parse_result_254,
            "parsed_result_215": parse_result_215,
            "hplc_method": HPLC_METHOD,
            "method_info": hplc_method_info,
            "assigned_PEAKs": assigned_info,
            }


def check_sampling(hplc_result_dict: dict, check_peak: str = "tol") -> float | bool:
    """check sampling succeed or not by check the peak of internal standard"""
    # check sampling by check tol peak
    if check_peak == "tol":
        for found_peak_rt in hplc_result_dict.keys():
            if peak_rt_range["tol"][0] < float(found_peak_rt) < peak_rt_range["tol"][1]:
                logger.debug("find toluene (IS) peak")
                return found_peak_rt  # return tol rt
        logger.error(f"toluene peak was found nowhere!")
        return False
    elif check_peak == "tmob":
        for found_peak_rt in hplc_result_dict.keys():
            if peak_rt_range["tmob"][0] < float(found_peak_rt) < peak_rt_range["tmob"][1]:
                logger.debug("find tmob (IS) peak")
                return found_peak_rt  # return tol rt
        logger.error(f"tmob peak was found nowhere!")
        return False

def assign_is_peak(hplc_result_dict: dict, check_shift=0.9) -> dict | bool:
    # FIXME: not used; deleted?
    sorted_peaks = sorted(hplc_result_dict.items(), key=lambda x: x[1], reverse=True)
    logger.debug(f"sorted peaks: {sorted_peaks}")

    # find these peaks is in the range of 24 to 29
    potential_is_peaks = {peak[0]: peak[1] for peak in sorted_peaks if 24 < float(peak[0]) < 29}
    logger.debug(f"potential IS peaks: {potential_is_peaks}")

    # assign to tmob peak
    potential_tmob_peaks = {peak[0]: peak[1] for peak in sorted_peaks if
                            (PEAK_RT["tmob"] - check_shift) < float(peak[0]) < (PEAK_RT["tmob"] + check_shift)}
    logger.debug(f"potential tmob peaks: {potential_tmob_peaks}")

    potential_tol_peaks = {peak[0]: peak[1] for peak in sorted_peaks if
                            (PEAK_RT["tol"] - check_shift) < float(peak[0]) < (PEAK_RT["tol"] + check_shift)}
    logger.debug(f"potential tol peaks: {potential_tol_peaks}")
    d_is = PEAK_RT["tol"] - PEAK_RT["tmob"]
    if potential_tmob_peaks == 1 and potential_tol_peaks == 1:
        d_tol = float(list(potential_tol_peaks.keys())[0]) - PEAK_RT["tol"]
        d_tmob = float(list(potential_tmob_peaks.keys())[0]) - PEAK_RT["tmob"]
        logger.debug(f"toluene shifting: {d_tol}, tmob shifting: {d_tmob}. Now, only tmob used.")
    elif potential_tmob_peaks == 1 and potential_tol_peaks != 1:
        logger.error(f"fail to assign toluene peak ({potential_tol_peaks} peaks). use tmob to determine the shifting")
    elif potential_tmob_peaks != 1 and potential_tol_peaks == 1:
        logger.error(f"fail to assign tmob peak ({potential_tmob_peaks} peaks). use tol to determine the shifting")
    else:
        logger.error(f"fail to assign both toluene and trimethoxybenzene")
        assume_tol_rt =float(list(potential_tmob_peaks.keys())[0]) + d_is
        # find the nearest peak to the assumed tol rt
        for potential_tol_peak in potential_tol_peaks.items():
            potential_tol_peak[0]



def shifting_finder(hplc_result_dict: dict,
                    checking_shifting: float = 0.9,
                    output_IS_info: bool = False):
    """
    0.025 is the acceptable shifting range (2.5% of the retention time)
    checking_shifting: float = 0.4 (original)
    :param output_IS_info:
    :param hplc_result_dict:
    :return:
    n_peak_rt:
    used_peak:
    """
    # TODO: the hplc shifting issue cannot be solved now.
    # FIXME: the shifting is not robust
    # find the tol peak (both difference and the number of peaks)
    peak_n_tol = 0

    # calc_acpt_shift_range(PEAK_RT, checking_shifting)
    shifting_accept_range = [PEAK_RT["tol"] - checking_shifting, PEAK_RT["tol"] + checking_shifting]
    for found_peak_rt in hplc_result_dict.keys():
        if shifting_accept_range[0] < float(found_peak_rt) < shifting_accept_range[1]:
            logger.debug("find potential toluene (IS) peak")
            r_tol_rt = float(found_peak_rt)
            peak_n_tol += 1
            d_tol = r_tol_rt - PEAK_RT["tol"]

    # find the tmob peak (both difference and the number of peaks)
    peak_n_tmob = 0
    shifting_accept_range = [PEAK_RT["tmob"] - checking_shifting, PEAK_RT["tmob"] + checking_shifting]
    for found_peak_rt in hplc_result_dict.keys():
        if shifting_accept_range[0] < float(found_peak_rt) < shifting_accept_range[1]:
            logger.debug("find potential tmob (IS) peak")
            r_tmob_rt = float(found_peak_rt)
            peak_n_tmob += 1
            d_tmob = r_tmob_rt - PEAK_RT["tmob"]

    if peak_n_tol != 1 and peak_n_tmob != 1:
        logger.error(f"assign {peak_n_tol} peaks to toluene and {peak_n_tol} peaks to tmob.")
        logger.error(f"fail to assign both toluene and trimethoxybenzene. use the original peak rt")
        n_peak_rt = PEAK_RT
        used_peak = None
    elif peak_n_tol != 1:
        logger.error(f"fail to assign toluene peak ({peak_n_tol} peaks). use tmob to determine the shifting")
        n_peak_rt = {key: (value + d_tmob) for key, value in PEAK_RT.items()}
        used_peak = "tmob"
    elif peak_n_tmob != 1:
        logger.error(f"fail to assign tmob peak ({peak_n_tmob} peaks). use tol to determine the shifting")
        n_peak_rt = {key: (value + d_tol) for key, value in PEAK_RT.items()}
        used_peak = "tol"
    else:
        logger.debug(f"toluene shifting: {d_tol}, tmob shifting: {d_tmob}. Now, only tmob used.")
        n_peak_rt = {key: (value + d_tmob) for key, value in PEAK_RT.items()}
        used_peak = "tmob"

    if output_IS_info:
        return n_peak_rt, used_peak

    return n_peak_rt


def shifting_finder_tPeak(hplc_result_dict: dict, n: int = 5, output_IS_info: bool = False):
    """
    find the shifting by the top 5 maximum peaks, and create a new retention time dictionary

    :param n: the number of peaks to find the shifting
    :param hplc_result_dict:  the raw peak list from the hplc chromatogram parse
    :return: a new retention time dictionary, and peak used to find the shifting
    """
    # find the top six peaks
    top_n_peaks = sorted(hplc_result_dict.items(), key=lambda x: x[1], reverse=True)[:(n-1)]
    logger.debug(f"top {n} peaks: {top_n_peaks}")

    # find these peaks is in the range of 24 to 29
    potential_is_peaks = {peak[0]: peak[1] for peak in top_n_peaks if 24 < float(peak[0]) < 29}
    logger.debug(f"potential IS peaks: {potential_is_peaks}")

    # use shifting finder to find the shifting
    return shifting_finder(potential_is_peaks, output_IS_info=output_IS_info)

def calc_acpt_shift_range(hplc_rt_dict: dict, acceptable_shift: float = None) -> dict:
    """
    1-2% of the retention time is acceptable shifting range in the hplc. maximum 0.025.
    ACCEPTED_SHIFT = 0.22 (min)
    :return:
    """

    acpt_shift = acceptable_shift if acceptable_shift else ACCEPTED_SHIFT

    # use set value to adjust the shifting
    peak_rt_range = {key: [value - acpt_shift, value + acpt_shift] for key, value in
                       hplc_rt_dict.items()}
    logger.debug(f"new retention time range w/ acceptable_shift: {peak_rt_range}")

    # use set percentage of rt to adjust the shifting
    # shift = 0.015
    # a_n_peak_rt_range = {key: [value * (1 - shift), value * (1 + shift)] for key, value in hplc_rt_dict.items()}
    # logger.debug(f"new retention time range w/ {shift * 100}% rt: {a_n_peak_rt_range}")

    return peak_rt_range


def n_alignment(raw_peaks: dict):
    """
    new alignment method start from
    1. find the shifting by the top 5 maximum peaks and return the new retention time dictionary
    2. assign the peak by the new retention time dictionary (acceptable range 0.35, 0.22, 0.15)
    3. if 0.15 acceptable range failed. just used the highest peak in range of 0.22
    :param raw_peaks: raw peaks after automatic peak picking
    :return:
    peaks: peaks used to calculate the result
    used_shift_peak: to check the is used for shift finding and result calculation is same
    """
    # new shifting finder by the top 5 peaks, and create a new retention time dictionary
    n_rt, used_shift_peak = shifting_finder_tPeak(raw_peaks, output_IS_info=True)
    logger.debug(f"new retention time: {n_rt}, used peak: {used_shift_peak}")

    # first try to assign the peak
    # create new range of retention time
    n_peak_rt_range = calc_acpt_shift_range(n_rt, 0.35)  # todo: acceptable shifting range calculation by specific range or percentage
    logger.debug(f"new retention time range: {n_peak_rt_range}, with 0.35 shifting allowed.")

    peaks = {key: 0 for key, value in PEAK_RT.items()}

    for target_peak, target_range in n_peak_rt_range.items():
        # find how many peaks are in the range
        temp_peaks = [found_peak for found_peak in raw_peaks.items() if target_range[0] <= float(found_peak[0]) <= target_range[1]]
        n = len(temp_peaks)

        if n == 1:
            peaks[target_peak] = temp_peaks[0][1]

        elif n > 1:
            m = 0
            # if more than one peak was found in the range, small peaks reassign to the nearest peak
            logger.warning(f"more than one peak was found in the range of {target_peak} at "
                           f"{target_range[0]} to {target_range[1]}. "
                           f"The nearest peak will be used.")
            s_peak_rt_range = calc_acpt_shift_range(n_rt, 0.22)
            temp_peaks_2 = [temp_peak for temp_peak in temp_peaks if s_peak_rt_range[target_peak][0] <= float(temp_peak[0]) <= s_peak_rt_range[target_peak][1]]
            m = len(temp_peaks_2)
            if m == 1:
                peaks[target_peak] = temp_peaks_2[0][1]
            elif m > 1:
                logger.warning(f"more than one peak was found in the range of {target_peak} at "
                               f"{s_peak_rt_range[target_peak][0]} to {s_peak_rt_range[target_peak][1]}. "
                               f"The nearest peak will be used.")
                s_peak_rt_range = calc_acpt_shift_range(n_rt, 0.15)
                temp_peaks_3 = [temp_peak for temp_peak in temp_peaks_2 if s_peak_rt_range[target_peak][0] <= float(temp_peak[0]) <= s_peak_rt_range[target_peak][1]]
                m = len(temp_peaks_3)
                if m == 1:
                    peaks[target_peak] = temp_peaks_3[0][1]
                else:
                    logger.error(f"{m} peaks were found in the range of {target_peak} at "
                                 f"{s_peak_rt_range[target_peak][0]} to {s_peak_rt_range[target_peak][1]}. "
                                 f"The maximum peak will be used.")
                    peaks[target_peak] = max(temp_peaks_2, key=lambda x: x[1])[1]

    return peaks, used_shift_peak


def assign_peak(hplc_result_dict: dict) -> dict | bool:
    """ FIXME: deleted
        "acid": 0.0,
        "ester": 0.06,
        "lactone": 0.09,
        "unk_4": 0.26,
        "SM": 0.58,
    :param hplc_result_dic: the raw peak list from the hplc chromatogram parse
    :return:
    """
    # check sampling okay or not by check tol/tmob peak
    # check_sampling(hplc_result_dict, "tmob")

    # new_peak_dict = {"acid": 0, "ester": 0, "lactone": 0, "unk_4": 0, "SM": 0, "tmob": 0, "tol": 0}
    new_peak_dict = {key: 0 for key, value in PEAK_RT.items()}

    # always find the new retention time by the shifting finder
    n_peak_rt = shifting_finder(hplc_result_dict)
    n_peak_rt = shifting_finder_tPeak(hplc_result_dict) if not n_peak_rt else None
    if n_peak_rt:
        # todo: check the shifting range
        n_peak_rt_range = {key: [value - ACCEPTED_SHIFT, value + ACCEPTED_SHIFT] for key, value in
                           n_peak_rt.items()}
        logger.debug(f"new retention time range: {n_peak_rt_range}")
        # shift = 0.01
        # n_peak_rt_range = {key: [value * (1 - shift), value * (1 + shift)] for key, value in PEAK_RT.items()}
    else:
        logger.error(f"fail to find the shifting. Check the hplc result manually.")
        return False

    # to assign the peak
    new_peak_dict.update(hplc_result_dict)

    for found_peak in hplc_result_dict.items():
        # TODO: check the parameter above.....
        if found_peak[1] <= 0.005:
            # get rid of the small peak
            new_peak_dict.pop(found_peak[0])
            continue
        else:
            for target_peak in n_peak_rt_range.items():
                if target_peak[1][0] <= float(found_peak[0]) <= target_peak[1][1]:
                    new_peak_dict[target_peak[0]] = found_peak[1]
                    del new_peak_dict[found_peak[0]]

    logger.debug(f"final:{new_peak_dict}")

    return new_peak_dict


def hplc_result_by_cc(hplc_result: dict, cc_is="tol", cc=None, initial_conc: float = 10):
    if cc is None:
        cc = [1, 0, 1, 0]

    if cc_is == "tol":
        r_sm = hplc_result["SM"] / hplc_result["tol"]
        r_p = (hplc_result["ester"] + hplc_result["lactone"]) / hplc_result["tol"]
    elif cc_is == "tmob":
        r_sm = hplc_result["SM"] / hplc_result["tmob"]
        r_p = (hplc_result["ester"] + hplc_result["lactone"]) / hplc_result["tmob"]

    conc_sm = (r_sm - cc[1]) / cc[0]
    conc_p = (r_p - cc[3]) / cc[2]
    conversion_sm = (initial_conc - conc_sm) / initial_conc
    yield_p = conc_p / initial_conc
    return yield_p, conversion_sm


def parse_raw_exp_result(condition: dict,
                         r_hplc_result: dict,
                         wavelength: str = "254",
                         cc_is: str = "tol") -> dict | bool:
    """
    calculate the yield, conversion, and productivity by the hplc result
    :param condition: the condition of the experiment
    :param r_hplc_result: the raw peak list from the hplc chromatogram parse
    :param wavelength: the wavelength of the hplc
        "Yield_1": 0.15,
        "Conversion_1": 0.42,
        "Producivity_1": 0.381944952,
        "Yield_2": null,
        "Conv_2": null,
        "Producivity_2": null
    """
    hplc_result, used_is = n_alignment(r_hplc_result)
    # logger.debug(f"alignment: {hplc_result}")
    if used_is != cc_is:
        logger.warning(f"the shifting was found by {used_is} peak but the result was planed to calculate by {cc_is}. "
                       f"Use {used_is} to calculate the result.")
        cc_is = used_is

    sum_target_peak = hplc_result["acid"] + hplc_result["ester"] + hplc_result["lactone"] + hplc_result["unk_4"] + \
                      hplc_result["SM"]

    if sum_target_peak == 0:
        # check the alignment succeed or not
        logger.error(f"fail to assign peak.")
        return False

    if wavelength == "254":
        hplc_result["Yield_1"] = (hplc_result["ester"] + hplc_result["lactone"]) / sum_target_peak
        hplc_result["Conversion_1"] = 1 - hplc_result["SM"] / sum_target_peak

        # productivity = concentration * yield / time * 1000 to (umol/ml/min)
        hplc_result["Productivity_1"] = condition["concentration"] * hplc_result["Yield_1"] / condition["time"] * 1000

        if cc_is == "tol":
            hplc_result["Yield_2"], hplc_result["Conversion_2"] = hplc_result_by_cc(hplc_result,
                                                                                    cc_is=cc_is,
                                                                                    cc=tol_cc["254_cc"],
                                                                                    initial_conc=tol_cc[
                                                                                        "254_initial_conc"]
                                                                                    )
        elif cc_is == "tmob":
            hplc_result["Yield_2"], hplc_result["Conversion_2"] = hplc_result_by_cc(hplc_result,
                                                                                    cc_is=cc_is,
                                                                                    cc=tmob_cc["254_cc"],
                                                                                    initial_conc=tmob_cc[
                                                                                        "254_initial_conc"]
                                                                                    )

        hplc_result["Productivity_2"] = condition["concentration"] * hplc_result["Yield_2"] / condition["time"] * 1000

        return hplc_result
    elif wavelength == "215":
        if cc_is == "tol":
            hplc_result["Yield_3"], hplc_result["Conversion_3"] = hplc_result_by_cc(hplc_result,
                                                                                    cc_is=cc_is,
                                                                                    cc=tol_cc["215_cc"],
                                                                                    initial_conc=tol_cc[
                                                                                        "215_initial_conc"]
                                                                                    )
        elif cc_is == "tmob":
            hplc_result["Yield_3"], hplc_result["Conversion_3"] = hplc_result_by_cc(hplc_result,
                                                                                    cc_is=cc_is,
                                                                                    cc=tmob_cc["215_cc"],
                                                                                    initial_conc=tmob_cc[
                                                                                        "215_initial_conc"]
                                                                                    )
        hplc_result["Productivity_3"] = condition["concentration"] * hplc_result["Yield_3"] / condition["time"] * 1000

        return hplc_result
    else:
        logger.error(f"check wavelength....")
        return False

def current_hplc_processing_test():
    # 65ca740929422c53d33945a8
    raw_215 = {'15.84': 117.31382717419669, '19.863333333333333': 52.0240109874139, '20.9': 102.54347112147155,
               '23.35': 24.876914208845406, '24.02': 274.7989412104782, '25.65333333333333': 457.6853470279815,
               '26.331666666666667': 19.198340103676127, '26.696666666666665': 42.92107401929108,
               '27.496666666666663': 22.153884827229902, '28.08333333333333': 216.19013204766784,
               '28.446666666666665': 39.4749468021706,
               '29.476666666666667': 15.046993165225482, '29.805': 7.577272709785077}
    # two fake peak was add ('28.05': 9.00, '28.25': 10.00)
    raw_254 = {'13.585': 11.380394280645442, '19.101666666666667': 2.697800182962489, '19.865': 2.33726512241778,
               '20.90333333333333': 3.95418226017107, '22.33833333333333': 5.537034739960214,
               '22.935': 1.6679042862812175, '23.335': 2.4036957364246065, '23.728333333333328': 1.4110094965183944,
               '24.02166666666667': 15.46224245975398, '24.968333333333334': 1.1627352800413604,
               '25.65333333333333': 28.22400979920022, '26.33833333333333': 4.950409094386355,
               '26.818333333333328': 2.8182700166621446, '27.568333333333328': 7.648337687379029,
               '28.081666666666667': 25.075083482217956, '28.05': 9.00, '28.25': 10.00, '28.45': 10.00986879654934, '28.74': 2.245996450970103,
               '29.478333333333328': 4.144811595904272, '29.80333333333333': 1.8632402919431317}
    assign_is_peak(raw_254)
    # assigned_peaks = n_alignment(raw_254)
    # print(assigned_peaks)
    # assigned_peaks = n_alignment(raw_215)
    # print(assigned_peaks)


if __name__ == "__main__":
    # current_hplc_processing()
    # condition
    control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                         'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34, }

    from BV_experiments.calc_oper_para import calc_concentration
    control_condition["concentration"] = calc_concentration(control_condition)

    # to save the serial results
    def processing_serial(find_word: str, date="20240408"):
        import pandas as pd
        log = pd.DataFrame({'acid': 0, 'unk_1': 0, 'ester': 0, 'lactone': 0, 'unk_4': 0, 'SM': 0, 'tmob': 0, 'tol': 0,
                           'Yield_1': 0, 'Conversion_1': 0, 'Productivity_1': 0, 'Yield_2': 0, 'Conversion_2': 0, 'Productivity_2': 0},
                           index=["empty"])

        # find all file with the specific suffix
        for file in Path(r"W:\BS-FlowChemistry\data\exported_chromatograms").rglob(f"*{find_word}* - DAD 2.1L- Channel 2.txt"):
            print(file.stem)
            mongo_id = file.stem.split(" - ")[0]
            result = processing_hplc_file(mongo_id, file, control_condition,  cc_is="tmob")
            print(result['parsed_result_254'])
            try:
                log = pd.concat([log, pd.DataFrame(result['parsed_result_254'], index=[mongo_id])])
            except:
                print(f"fail to concat {mongo_id}")

        log.to_csv(f'W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei\{date}_log_{find_word}.csv', header=True)


    processing_serial("ctrl_073", date="20240412")
