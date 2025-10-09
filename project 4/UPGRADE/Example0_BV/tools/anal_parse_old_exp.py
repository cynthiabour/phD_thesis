

from pathlib import Path
from loguru import logger

from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import ACCEPTED_SHIFT

HPLC_ELUENT = {"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN"}
# HPLC_METHOD = r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET"
# HPLC_RUNTIME = 30
# HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 5: 85, 12: 65, 25: 10, 27: 10, 28: 99, 30: 99}
# ROI = [6.0, 23.0]
# PEAK_RT = {"acid": 8.19, "ester": 11.62, "lactone": 12.73, "unk_4": 13.97, "SM": 14.84, "tol": 17.99}
# PEAK_RT_2 = {"EY_deg": 10.16, "EY_1": 18.48, "EY_2": 19.31}

# TODO: ester and unknown have to run reaction to check
# HPLC_METHOD = r"D:\Data2q\BV\BV_General_method_r1met_34min_025mlmin.MET"
# HPLC_RUNTIME = 34
# HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 21: 40, 25: 5, 28: 5, 29: 99, 34: 99}
# ROI = [9.0, 23.0]
# PEAK_RT = {"acid": 9.013, "unk_1": 10.09, "ester": 12.320, "lactone": 13.361, "unk_4": 14.561, "SM": 15.452, "tol": 18.95}
# PEAK_RT_2 = {"EY_deg": 10.917, "EY_1": 19.5, "EY_2": 21.56}



HPLC_METHOD = r"D:\Data2q\BV\BV_General_method_r1met_40min_025mlmin.MET"
HPLC_RUNTIME = 40
HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 31: 40, 34: 5, 36: 5, 37: 99, 40: 99}
ROI = [9.0, 30.0]
PEAK_RT = {"acid": 10.29, "unk_1": 11.37, "ester": 15.18, "lactone": 16.50, "unk_4": 17.51, "SM": 19.54, "tol": 24.38}
PEAK_RT_2 = {"EY_deg": 12.89, "EY_1": 25.826, "EY_2": 28.657}
peak_rt_range = {key: [value - ACCEPTED_SHIFT, value + ACCEPTED_SHIFT] for key, value in PEAK_RT.items()}
def check_hplc_method(mongo_id: str):
    folder_path = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\automatically_export_chromatograms")
    mongo_id = "control_test_018.txt"
    # title = """
    # Primary file : \tcontrol_test_018\tAnalyst  : \tadmin\n

    # Sample ID    : 	06_07_2023_control_018_postrun_40min_3	From     : 	Thu, 06th Jul, 2023	 11:26:16 PM
    # Sample       :
    # Instrument   : 	Instrument 1	Method   : 	BV_General_method_r1met_40min_025mlmin
    # Sample Amount:	0.0	[uL]	ISTD1 Am. :	0.0	[uL]	ISTD2 Am. :	0.0	[uL]	ISTD3 Am. :	0.0	[uL]	ISTD4 Am. :	0.0	[uL]	ISTD5 Am. :	0.0	[uL]	ISTD6 Am. :	0.0	[uL]	ISTD7 Am. :	0.0	[uL]	ISTD8 Am. :	0.0	[uL]	ISTD9 Am. :	0.0	[uL]	ISTD10 Am. :	0.0	[uL]
    # Sample Dilut.:	1.0	Inj. Vol. :	1.0	[µL]
    # Peak width   :	       0.100	[min]	Threshold :	       0.100	[mAU]
    # """
    file_path = folder_path / Path(mongo_id)
    parse_header_BV(file_path)


def parse_header_BV(clarity_file):
    """
    From a clarity exported ASCII chromatogram, extract header and returns info + header length (in lines).
    :param clarity_file: ASCII file to be analyzed
    :return: dict with header fields and length in lines
    """
    header_data = {}

    with clarity_file.open("r") as fh:

        for line_num, content in enumerate(fh):

            # Empty line signifies end of header
            if content == "\n":
                break

            try:

                field_name, field_content = content.split(" : ")
            except ValueError:  # field with no content
                try:
                    field_name, field_content = content.split(": ")
                except ValueError:
                    continue

            header_data[field_name] = field_content.strip()

    return header_data, line_num + 1



def check_sampling(hplc_result_dict: dict) -> float | bool:
    # check sampling by check tol peak
    for found_peak_rt in hplc_result_dict.keys():
        if peak_rt_range["tol"][0] < float(found_peak_rt) < peak_rt_range["tol"][1]:
            logger.debug("find toluene (IS) peak")
            return found_peak_rt  # return tol rt
    logger.error(f"toluene peak was found nowhere!")
    return False

def assign_peak(hplc_result_dict: dict) -> dict:
    """
        "acid": 0.0,
        "ester": 0.06,
        "lactone": 0.09,
        "unk_4": 0.26,
        "SM": 0.58,
    :param hplc_result_dic:
    :return:
    """
    new_peak_dict = {"acid": 0, "ester": 0, "lactone": 0, "unk_4": 0, "SM": 0, "tol": 0}
    # check sampling okay or not by check tol
    if check_sampling(hplc_result_dict):
        # trim the EY peak

        # to assign the peak
        new_peak_dict.update(hplc_result_dict)
        # logger.debug(new_peak_dict)
        for found_peak in hplc_result_dict.items():
            # TODO: check the parameter above.....
            if found_peak[1] <= 0.005:
                new_peak_dict.pop(found_peak[0])
                continue
            else:
                for target_peak in peak_rt_range.items():
                    if target_peak[1][0] <= float(found_peak[0]) <= target_peak[1][1]:
                        new_peak_dict[target_peak[0]] = found_peak[1]
                        del new_peak_dict[found_peak[0]]

        logger.debug(f"final:{new_peak_dict}")

    return new_peak_dict


def hplc_result_by_cc(hplc_result: dict, cc=None, initial_conc: float = 10):
    if cc is None:
        cc = [1, 0, 1, 0]

    r_sm = hplc_result["SM"] / hplc_result["tol"]
    r_p = (hplc_result["ester"] + hplc_result["lactone"]) / hplc_result["tol"]

    conc_sm = (r_sm - cc[1]) / cc[0]
    conc_p = (r_p - cc[3]) / cc[2]
    conversion_sm = (initial_conc - conc_sm) / initial_conc
    yield_p = conc_p / initial_conc
    return yield_p, conversion_sm


def parse_raw_exp_result(condition: dict, r_hplc_result: dict, wavelength: str = "254") -> dict | bool:
    """ "Yield_1": 0.15,
        "Conversion_1": 0.42,
        "Producivity_1": 0.381944952,
        "Yield_2": null,
        "Conv_2": null,
        "Producivity_2": null
    """
    hplc_result = assign_peak(r_hplc_result)
    sum_target_peak = hplc_result["acid"] + hplc_result["ester"] + hplc_result["lactone"] + hplc_result["unk_4"] + \
                      hplc_result["SM"]

    if sum_target_peak != 0:
        if wavelength == "254":

            hplc_result["Yield_1"] = (hplc_result["ester"] + hplc_result["lactone"]) / sum_target_peak
            hplc_result["Conversion_1"] = 1 - hplc_result["SM"] / sum_target_peak
            hplc_result["Productivity_1"] = condition["concentration"] * hplc_result["Yield_1"] / condition["time"]

            hplc_result["Yield_2"], hplc_result["Conversion_2"] = hplc_result_by_cc(hplc_result,
                                                                                    cc=[0.08539, 0, 0.084, 0],
                                                                                    # cc=[0.095185, -0.00217,
                                                                                    #     0.070554, -0.02759],
                                                                                    initial_conc=17.219
                                                                                    )
            hplc_result["Productivity_2"] = condition["concentration"] * hplc_result["Yield_2"] / condition["time"]

            return hplc_result
        elif wavelength == "215":

            hplc_result["Yield_3"], hplc_result["Conversion_3"] = hplc_result_by_cc(hplc_result,
                                                                                    cc=[.1343, 0, .1027, 0],
                                                                                    # cc=[0.118741, 0.174774,
                                                                                    #     0.096041, 0.117872],
                                                                                    initial_conc=12.243
                                                                                    )
            hplc_result["Productivity_3"] = condition["concentration"] * hplc_result["Yield_3"] / condition["time"]

            return hplc_result
        else:
            logger.error(f"check wavelength....")
            return False

    logger.error(f"fail to assign peak.")
    return False


if __name__ == "__main__":
    check_hplc_method("control_test_018.txt")