"""
the standalone script to process the hplc result

"""
from pathlib import Path
from loguru import logger

from typing import Any, List
import math
from BV_experiments.src.general_platform import IncompleteAnalysis
from BV_experiments.src.general_platform.Librarian import HplcConfig


class AnalysisProcessor:
    """
    process the alignment data to the performance data of the experiment
    e.g. yield, conversion, productivity
    """

    def __init__(self,
                 channel: int,
                 align_peak_dict: dict,
                 raw_peak_dict: dict,
                 hplc_config: HplcConfig | dict[str, Any],
                 ):
        self.channel = channel
        self.align_peak_dict: dict = align_peak_dict
        self.raw_peak_dict: dict = raw_peak_dict

        if type(hplc_config) is HplcConfig:
            self.dad_method: dict = hplc_config.ACQUISITION
            self.cc_initial: float = hplc_config.CALIBRATION[f"channel_{channel}_initial_conc"]
            self.cc: dict = hplc_config.CALIBRATION[f"channel_{channel}"]
            # self.PEAK_RT: dict = hplc_config.PEAK_RT
            # self.PEAK_RT_2: dict = hplc_config.PEAK_RT_2

        elif type(hplc_config) is dict:
            self.dad_method: dict = hplc_config["ACQUISITION"]
            self.cc_initial: float = hplc_config["CALIBRATION"][f"channel_{channel}_initial_conc"]
            self.cc: dict = hplc_config["CALIBRATION"][f"channel_{channel}"]

            # self.PEAK_RT: dict = hplc_config["PEAK_RT"]
            # self.PEAK_RT_2: dict = hplc_config["PEAK_RT_2"]

    def yield_conv_by_cc(self,
                         cc_is: str = "is",
                         y2: list = ["product"],
                         conv2: list = ["sm"],
                         ) -> tuple[float, float]:
        """
        Calculate yield and conversion using per-compound calibration curves.

        Args:
            initial_ratio (float): Initial ratio of SM to cc_is.
            cc_is (str): Internal standard name.
            y2 (list): Peaks to calculate yield (e.g., products).
            conv2 (list): Peaks to calculate conversion (e.g., SMs).

        Return:
            tuple: (yield_total, conversion_total)
        """
        if cc_is not in self.align_peak_dict or self.align_peak_dict[cc_is] == 0:
            raise IncompleteAnalysis(f"The internal standard peak '{cc_is}' is missing or zero.")

        # Ratio of species to IS
        # r_conv = sum(self.align_dict[name] for name in conv2) / self.align_dict[cc_is]
        # r_yield = sum(self.align_dict[name] for name in y2) / self.align_dict[cc_is]

        # Apply calibration
        is_val = self.align_peak_dict[cc_is]

        # Conversion: calculate 1 - percentage of remaining SM
        conc_conv_total = 0.0
        for name in conv2:
            if name not in self.align_peak_dict or name not in self.cc:
                continue
            r = self.align_peak_dict[name] / is_val
            a, b = self.cc[name]
            conc = (r - b) / a
            conc_conv_total += conc

        # Yield: calculate pct of product
        conc_yield_total = 0.0
        for name in y2:
            if name not in self.align_peak_dict or name not in self.cc:
                continue
            r = self.align_peak_dict[name] / is_val
            a, b = self.cc[name]
            conc = (r - b) / a
            conc_yield_total += conc

        # Calculate yield and conversion
        conversion = (self.cc_initial - conc_conv_total) / self.cc_initial
        yield_val = conc_yield_total / self.cc_initial

        return yield_val, conversion

    def yield_conc_rough(self,
                         rel_range: list = [5, 10],
                         y1: list = ["product"],
                         ) -> tuple[float, float]:
        """this func is used to calculate the yield and conversion by the inclded all peaks"""
        # total = sum(self.align_dict.values()) - self.align_dict["is"]
        total_peaks = sum(value for key, value in self.raw_peak_dict.items() if rel_range[0] <= key <= rel_range[1])

        r_yield = sum(self.align_peak_dict[name] for name in y1) / total_peaks
        r_conv = 1 - self.align_peak_dict["sm"] / total_peaks

        return r_yield, r_conv

    def space_time_yield(self,  yield_val: float, condition: dict) -> float:
        """
        Calculate space-time yield (STY) using yield, residence time and reaction concentration.

        Args:
            yield_val (float): Yield value.
            condition (dict): Experimental conditions including residence time.

        Returns:
            float: Space-time yield.
        """
        if "concentration" not in condition:
            raise ValueError("Concentration not found in condition.")

        sty = yield_val * condition["concentation"]/ condition["time"]
        return sty


class PeakAlignment:
    def __init__(self,
                 raw_peak_dict: dict[float: float],
                 hplc_config: HplcConfig | dict[str, Any],
                 ):

        self.raw_peak_dict: dict = raw_peak_dict

        # if cc_is is not None and channel is None:
        #     raise ValueError("No channel specified.")
        # self.cc_is = cc_is
        # self.channel = channel

        if type(hplc_config) is HplcConfig:
            self.hplc_runtime: int = hplc_config.HPLC_RUNTIME
            self.dad_method: dict = hplc_config.ACQUISITION

            self.PEAK_RT: dict = hplc_config.PEAK_RT
            self.PEAK_RT_2: dict = hplc_config.PEAK_RT_2

            self.ACCEPTED_SHIFT: float = hplc_config.ACCEPTED_SHIFT
            self.peak_rt_range: dict = {key: [value - self.ACCEPTED_SHIFT, value + self.ACCEPTED_SHIFT] for key, value
                                        in
                                        self.PEAK_RT.items()}

        elif type(hplc_config) is dict:

            self.hplc_runtime: int = hplc_config["HPLC_RUNTIME"]
            self.dad_method: dict = hplc_config["ACQUISITION"]

            self.PEAK_RT: dict = hplc_config["PEAK_RT"]
            self.PEAK_RT_2: dict = hplc_config["PEAK_RT_2"]

            self.ACCEPTED_SHIFT: float = hplc_config["ACCEPTED_SHIFT"]
            self.peak_rt_range: dict = {key: [value - self.ACCEPTED_SHIFT, value + self.ACCEPTED_SHIFT] for key, value
                                        in
                                        self.PEAK_RT.items()}
        # process data storage
        self.new_rt: dict = {}
        self.found_shift = None

    def _calc_max_acpt_shift(self,
                             percentage: float = 0.02) -> float:
        """
        In general,
        1-2% of the retention time is acceptable shifting range in the hplc. maximum 0.025.
        ACCEPTED_SHIFT = 0.22 (min)
        :return:
        """
        max_acpt_shift = self.hplc_runtime * percentage
        logger.debug(f"acceptable shift for current hplc run time: {max_acpt_shift}. "
                     f"current used acceptable shift: {self.ACCEPTED_SHIFT}")
        return max_acpt_shift

    def check_spec_peak(self,
                        check_dict: dict,
                        check_peak_rt: float,
                        shift: float | None = None
                        ) -> list[list[float | Any]]:

        """General use for checking a specific peak
        Returns: list of [found_peak_rt, shift]
        """
        if shift is None:
            logger.warning(f"accepted_shift is None, use default value {self.ACCEPTED_SHIFT}")
            shift = self.ACCEPTED_SHIFT

        # check sampling by check tol peak
        check_rt_range = [check_peak_rt - shift, check_peak_rt + shift]
        possible_peak = []

        for found_peak_rt in check_dict.keys():
            # found_peak_rt = float(list_peak_rt)  # str --> float
            if check_rt_range[0] < found_peak_rt < check_rt_range[1]:
                d_check = found_peak_rt - check_peak_rt
                logger.debug(f"find a potential peak ({found_peak_rt} min), shifting of the peak is {d_check:.4f} min")
                possible_peak.append([found_peak_rt, d_check])

        nos_peak = len(possible_peak)
        if nos_peak > 1:
            logger.error(f"more than one peak was found in the range of {check_rt_range[0]} to {check_rt_range[1]}. "
                         f"The nearest accepted_shift was required.")
        elif nos_peak == 0:
            logger.error(f"peak was found nowhere!")

        return possible_peak

    def peak_finder(self,
                    check_dict: dict,
                    check_peak_rt: float,
                    int_shift: float | None = None,
                    max_shift: float = 0.9,
                    step: float = 0.05
                    ) -> tuple[float, float] | bool:
        """
        Iteratively find the right accepted_shift value that results in only one matched peak.
        Returns: matched peak or False if not found.
        """
        shift = int_shift if int_shift is not None else step

        while shift <= max_shift:
            possible_peak = self.check_spec_peak(check_dict, check_peak_rt, shift)
            if len(possible_peak) == 1:
                logger.info(f"Found a unique peak with accepted_shift = {shift:.2f}")
                return possible_peak[0][0]  # reture found_peak_rt, shift
            shift += step

        logger.error(f"Could not find a unique peak within {max_shift} min shift range.")
        return False

    def _peak_name_processor(self,
                             check_peak: str | float = "is",
                             ) -> float:
        """
        check_peak: str | float = "is"
        return the peak rt used for the shift finder and peak finder
        """
        # find the tol peak (both difference and the number of peaks)
        if isinstance(check_peak, str):
            try:
                # find is peak form
                used_peak_rt = self.PEAK_RT[check_peak]  # in min

            except KeyError:
                used_peak_rt = self.PEAK_RT_2[check_peak]  # in min
        else:
            used_peak_rt = check_peak
        logger.debug(f"used peak rt: {used_peak_rt}")

    def one_peak_range_gen(self,
                           check_dict: dict,
                           check_peak: str | float = "is",
                           int_shift: float | None = None,
                           max_shift: float = 0.9,  # in min
                           ) -> None:
        """

        """
        # TODO: the hplc shifting issue cannot be solved now. the shift is not stable.

        # find the main peak use for shift finding
        used_peak_rt = self._peak_name_processor(check_peak)

        # check the peak
        check_peak_info = self.peak_finder(check_dict, used_peak_rt, int_shift=int_shift, max_shift=max_shift)

        if not check_peak_info:
            logger.error(f"fail to find the peak. check.")

        new_peak_rt, shift = check_peak_info if check_peak_info else used_peak_rt, 0
        logger.debug(f"original peak ({check_peak})  {check_peak_info}")

        # generate new retention time dictionary
        self.found_shift = shift
        self.new_rt = {key: (value + shift) for key, value in self.PEAK_RT.items()}

    def mul_peak_range_gen(self,
                           peak_1_rt: float,
                           peak_2_rt: float,
                           ):

        # fixme: input should be both str or both float

        # check the peak
        check_peak1_info = self.peak_finder(self.raw_peak_dict, peak_1_rt, int_shift=0.25)
        check_peak2_info = self.peak_finder(self.raw_peak_dict, peak_2_rt, int_shift=0.25)
        n_peak1_rt, shift1 = check_peak1_info if check_peak1_info else peak_1_rt, math.inf
        n_peak2_rt, shift2 = check_peak2_info if check_peak2_info else peak_2_rt, math.inf

        if abs(shift1) > abs(shift2):
            logger.debug(f"peak ({peak_2_rt}) was used")
            shift = shift2

        elif abs(shift1) < abs(shift2):
            logger.debug(f"peak ({peak_1_rt}) was used")
            shift = shift1

        elif shift1 == shift2 and shift1 == 0:
            logger.debug(f"shift1 is equal to shift2")
            shift = shift1
        else:
            logger.error("both peaks are not found. check.")
            shift = 0

        self.found_shift = shift
        self.new_rt = {key: (value + shift) for key, value in self.PEAK_RT.items()}

    def _sort_top_peaks(self,
                        rt_range: list | None = None,
                        ) -> list[tuple[float, float]] | bool:
        """
        sort the peaks by the peak height in a retention time range
        :return: a sorted list of peaks
        """
        if rt_range is None:
            peak_dict = self.raw_peak_dict
        else:
            # find the peaks in the range
            peak_dict = {key: value for key, value in self.raw_peak_dict.items() if
                         rt_range[0] < float(key) < rt_range[1]}

        # sort the peaks by the peak height
        sorted_peaks = sorted(peak_dict.items(), key=lambda x: x[1], reverse=True)
        logger.debug(f"sorted peaks: {sorted_peaks}")

        return sorted_peaks

    def top_peak_range_gen(self,
                           n: int = 5,
                           checked_peak: str | float = "is",
                           checking_shifting: float = 1.5,
                           ):

        """
        idea of this is to find the shifting by the top 5 maximum peaks (which should be the IS peaks)
        find the shifting by the top 5 maximum peaks, and create a new retention time dictionary

        :param n: the number of peaks to find the shifting
        :param hplc_result_dict:  the raw peak list from the hplc chromatogram parse
        :return: a new retention time dictionary, and peak used to find the shifting
        """
        # process the peak name
        used_peak_rt = self._peak_name_processor(checked_peak)

        # find possible peaks in a specific range

        sorted_peaks = self._sort_top_peaks()  # already trim the range of the peak?

        # find the top n highest peaks in the full spectrum
        top_n_peaks: list = sorted_peaks[:(n - 1)]  # list[tuple(float: float)]

        # trim the range of the peak
        checking_range = [used_peak_rt-checking_shifting, used_peak_rt+checking_shifting]
        potential_find_peaks = {peak[0]: peak[1] for peak in top_n_peaks if
                                checking_range[0] < peak[0] < checking_range[1]}

        logger.debug(f"potential checked_peak: {potential_find_peaks}")

        # use peak finder to find the shifting of one peak, and generate new retention time dictionary
        return self.one_peak_range_gen(potential_find_peaks, used_peak_rt, int_shift=0.25)

    def align(self,
              shift_levels: list = [0.35, 0.22, 0.15, 0.1, 0.05, 0.0],
              checked_shift_peak: str | float | None = "is",
              int_shift: float | None = None,
              max_shift: float | None = None,
              step: float = 0.05,
              ):
        """
        original alignment method start from
        1. find the shifting by the top 5 maximum peaks and return the new retention time dictionary
        2. assign the peak by the new retention time dictionary (acceptable range 0.35, 0.22, 0.15)
        3. if 0.15 acceptable range failed. just used the highest peak in range of 0.22

        :return:
        peaks: peaks used to calculate the result
        used_shift_peak: to check the is used for shift finding and result calculation is same
        """
        # new shifting finder by the top 5 peaks, and create a new retention time dictionary
        if checked_shift_peak is None:
            self.found_shift = 0
            self.new_rt = self.PEAK_RT
        else:
            self.top_peak_range_gen(checked_peak=checked_shift_peak)  # update self.new_rt & self.shift

        # Store for final result
        ali_peaks = {key: 0 for key, value in self.PEAK_RT.items()}

        # initial the first shift
        shift = int_shift if int_shift is not None else step

        if max_shift is None:
            # find rest_acpted_shift
            max_shift = self._calc_max_acpt_shift()  # todo: acceptable shift calculation by percentage

        # find the peaks in the range
        for peak_name, expected_rt in self.new_rt.items():
            assigned = False
            final_candidates = []

            for shift in shift_levels:
                rt_min = expected_rt - shift
                rt_max = expected_rt + shift

                # Find peaks within range
                candidates = [
                    (float(rt), intensity)
                    for rt, intensity in self.raw_peak_dict.items()
                    if rt_min <= float(rt) <= rt_max
                ]

                if len(candidates) == 1:
                    ali_peaks[peak_name] = candidates[0][1]
                    assigned = True
                    break

                elif len(candidates) > 1:
                    logger.warning(
                        f"{len(candidates)} peaks found for '{peak_name}' in ±{shift} min. "
                        f"Trying tighter range..."
                    )
                    final_candidates = candidates  # keep for fallback

            if not assigned:
                if final_candidates:
                    logger.error(
                        f"Multiple peaks remain for '{peak_name}' after all shifts. "
                        f"Using highest intensity."
                    )
                    ali_peaks[peak_name] = max(final_candidates, key=lambda x: x[1])[1]
                else:
                    logger.error(f"No peaks found for '{peak_name}' in any range.")

        return ali_peaks


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



def total_run(mongo_id: str,
              condition: dict,
              cc_is: str = "tol",
              ) -> dict:
    """

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

    hplc_results = {"channel_1": {"raw": raw_result_254, "parsed": parse_result_254, "result": None},
                    "channel_2": {"raw": raw_result_215, "parsed": parse_result_215, "result": None},
                    "channel_3": {"raw": raw_result_280, "parsed": parse_result_280, "result": None}}
    return hplc_results

def processing_serial(find_word: str, date="20240408"):
    # to save the serial results
    import pandas as pd
    log = pd.DataFrame({'acid': 0, 'unk_1': 0, 'ester': 0, 'lactone': 0, 'unk_4': 0, 'SM': 0, 'tmob': 0, 'tol': 0,
                        'Yield_1': 0, 'Conversion_1': 0, 'Productivity_1': 0, 'Yield_2': 0, 'Conversion_2': 0,
                        'Productivity_2': 0},
                       index=["empty"])

    # find all file with the specific suffix
    for file in Path(r"W:\BS-FlowChemistry\data\exported_chromatograms").rglob(
            f"*{find_word}* - DAD 2.1L- Channel 2.txt"):
        print(file.stem)
        mongo_id = file.stem.split(" - ")[0]

        result = processing_hplc_file(mongo_id, file, control_condition, cc_is="tmob")
        print(result['parsed_result_254'])
        try:
            log = pd.concat([log, pd.DataFrame(result['parsed_result_254'], index=[mongo_id])])
        except:
            print(f"fail to concat {mongo_id}")

    log.to_csv(f'W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei\{date}_log_{find_word}.csv', header=True)

def bv_hplc_processing_test():
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
               '28.081666666666667': 25.075083482217956, '28.05': 9.00, '28.25': 10.00, '28.45': 10.00986879654934,
               '28.74': 2.245996450970103,
               '29.478333333333328': 4.144811595904272, '29.80333333333333': 1.8632402919431317}


if __name__ == "__main__":

    # processing_serial("ctrl_073", date="20240412")

    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation
    dict_yxy001_ctrl_153 = {5.838333333333333: 3.6220652632031527,
                            5.988333333333332: 3.0394149316652004,
                            6.453333333333333: 2.353852122087556,
                            6.755: 3.2370835920136822,
                            6.905: 56.18779994289814,  #product
                            7.366666666666665: 2.5593433599352498,
                            8.01833333333333: 2.5444237297136514,
                            8.171666666666667: 3.3902014862796404,
                            8.286666666666667: 5.9407407820430915,
                            8.644999999999998: 28.936329324624374}  # sm

    peak_alignment = PeakAlignment(dict_yxy001_ctrl_153,
                                   SecondDebenzylation.hplc_config_info)
    align_peak_dict = peak_alignment.align(checked_shift_peak=None)
    print(align_peak_dict)

    processor = AnalysisProcessor(3,
                                  align_peak_dict,
                                  dict_yxy001_ctrl_153,
                                  SecondDebenzylation.hplc_config_info)

    yield_val, conversion = processor.yield_conc_rough(rel_range=[5, 10], y1=["product"])
    print(f"yield: {yield_val}, conversion: {conversion}")

    # condition
    condition = {'time': 10, "concentration": 0.2}
    sty = processor.space_time_yield(yield_val, condition)