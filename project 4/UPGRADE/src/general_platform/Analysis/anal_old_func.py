from typing import Dict, Any

import time
import numpy as np
import pandas as pd
import datetime
from pathlib import Path
from loguru import logger

import pybaselines
from matplotlib import pyplot as plt
from numpy import ndarray
from scipy import signal
from scipy.integrate import trapezoid
from scipy.signal import firwin, kaiserord, lfilter


def create_dataset(file_name: Path, header_lines: int) -> pd.DataFrame:
    """read in the hplc txt file"""
    return pd.read_csv(
        file_name,
        delimiter="\t",
        skiprows=header_lines,
        index_col="time (min.)",
        header=0,
        names=["time (min.)", "Absorbance [mAu]"],
        encoding="cp852")


def parse_header(clarity_file):
    """
    From a clarity exported ASCII chromatogram, extract header and returns info + header length (in lines).
    :param clarity_file: ASCII file to be analyzed
    :return: dict with header fields and length in lines
    """
    header_data = {}

    attempts = 0
    # PermissionError [Errno 13] Permission denied will happened. try 3 time
    # @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(10), reraise=True)
    while attempts < 6:
        try:
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

        except PermissionError as e:
            attempts += 1
            logger.error(f"{e}")
            time.sleep(5)

    raise PermissionError("cannot read the clarity txt file.")


def fir_filter(ndarray, cutoff=1, sample_rate=30, transition_width=5, attenuation=60):
    """Apply a Finite impulse response filter to a NDArray."""
    nyq_rate = sample_rate / 2.0
    width = transition_width / nyq_rate

    # Compute the order and Kaiser parameter for the FIR filter.
    N, beta = kaiserord(attenuation, width)

    # Use firwin with a Kaiser window to create a lowpass FIR filter.
    taps = firwin(N, cutoff / nyq_rate, window=('kaiser', beta))

    # Use lfilter to filter x with the FIR filter.
    return lfilter(taps, 1.0, ndarray)


def hplc_txt_to_peaks(mongo_id: str,
                      file_path: Path,
                      wavelength: str = "254",
                      cc_is: str = "tol") -> bool | dict[Any, float | ndarray]:
    # parse the header
    header_data, header_lines = parse_header(file_path)

    # X dimension is retention time with units as minute in the source file
    d_raw = pd.read_csv(
        file_path,
        delimiter="\t",
        skiprows=header_lines,
        index_col="time (min.)",
        header=0,
        names=["time (min.)", "Absorbance [mAu]"],
        encoding="cp852",
    )

    # save header_data as metadata
    d_raw._metadata = header_data

    # check whole hplc exp time
    if d_raw.index[-1] < HPLC_RUNTIME - 5:
        logger.error(f"Chromatogram shorter than {HPLC_RUNTIME - 5} min, skipped.")
        return False

    # check the performance of the experiment
    if max(d_raw["Absorbance [mAu]"]) < 2.5:  # default: 10 mAu
        logger.warning(f"Chromatogram without peaks above 2.5 mAu, skipped.")
        # continue

    # Plot raw chromatogram (in gray)
    ax = d_raw.plot(
        label="raw",  # the label for the plot that will be displayed in the legend
        alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
        color="grey",
        # figsize=(10, 4),  # the size of the plot in inches (width, height
        figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
        xlim=(5, HPLC_RUNTIME - 5),  # x limits of the current axes
    )

    # Apply median and FIR filter (set!)
    d = d_raw.apply(signal.medfilt, raw=True, kernel_size=19)
    d = d.apply(fir_filter, raw=True)

    # Cropping ROI after FIR prevents FIR-related boundary artifacts to affect baseline correction
    d = d[ROI[0]:ROI[1]]  # TODO: hplc method now 30 min; change the ROI....
    # a huge absorption (from solvent) : 14-19 mins (205nm and 215 nm)

    # PLOT smoothed graph
    d["Absorbance [mAu]"].plot(label="smoothed", linewidth=1.5, ax=ax)

    # set y-axes of the current figure.
    # ax.set_ylim(min(d["Absorbance [mAu]"]) - 10, max(d["Absorbance [mAu]"]) + 20)

    # Find peaks after smoothed(first time....)
    global_max = max(d["Absorbance [mAu]"])

    peaks, properties = signal.find_peaks(
        d["Absorbance [mAu]"],
        height=global_max / 80,  # defualt: /80
        prominence=global_max / 45,  # defualt:/80.
        # The prominence of a peak measures how much a peak stands out from the surrounding baseline
        width=0.05,  # Required width of peaks in samples.
        rel_height=0.5,  # Used for calculation of the peaks width
    )
    logger.debug(f"{len(peaks)} peaks were found after smoothed.")

    # baseline correction
    # Create a mask as weight for baseline calculation. 1=no peak, use for baseline 0=peak, ignore for baseline calc.
    weights = np.ones(len(d))
    # Calculate derivative
    d["dAbs"] = np.diff(d["Absorbance [mAu]"], prepend=0)
    # Remove NaN for final value
    d.fillna(0, inplace=True)

    for base_left, base_right in zip(properties["left_ips"], properties["right_ips"]):
        # Sets weights for baseline calculation to 0 in the peak range
        weights[round(base_left): round(base_right)] = 0

    d["baseline_0"], _ = pybaselines.polynomial.modpoly(
        d["Absorbance [mAu]"], d.index, poly_order=3, weights=weights
    )
    d["corr_0"] = d["Absorbance [mAu]"] - d["baseline_0"]
    d["corr_0"].plot(
        ax=ax,
        label="smoothed+baseline corrected_0",
        alpha=0.5,
        color="green",
    )
    d["dCorr"] = np.diff(d["corr_0"], prepend=0)

    # Find peaks after baseline correction (second time....)
    global_max = max(d["corr_0"])
    if global_max < 3.0:
        logger.error(f"After baseline correction, Chromatogram without peaks above 3.0 mAu, skipped.")
        return False

    # todo: change this part to sth
    # Use toluene peak
    if cc_is == "tol":
        local_max = max(d["corr_0"][peak_rt_range['tol'][0]:peak_rt_range["tol"][1]])
        if local_max < 3.0:
            logger.error(f"After baseline correction, toluene peak is below 3.0 mAu, skipped.")
            return False

    # Use tmob peak
    elif cc_is == "tmob":
        local_max = max(d["corr_0"][peak_rt_range['tmob'][0]:peak_rt_range["tmob"][1]])
        if local_max < 3.0:
            logger.error(f"After baseline correction, tmob peak is below 3.0 mAu, skipped.")
            return False

    # TODO: use IS to determine height?
    # peaks, properties = signal.find_peaks(
    #     d["corr_0"],
    #     height=global_max / 80,  # defualt: / 80
    #     prominence=global_max / 45,  # defualt: / 80
    #     # The prominence of a peak measures how much a peak stands out from the surrounding baseline
    #     width=0.05,  # Required width of peaks in samples.
    #     rel_height=0.5,  # Used for calculation of the peaks width
    # )
    peaks, properties = signal.find_peaks(
        d["corr_0"],
        height=local_max / 50,  # defualt: / 80
        prominence=local_max / 45,  # defualt: / 80
        # The prominence of a peak measures how much a peak stands out from the surrounding baseline
        width=0.05,  # Required width of peaks in samples.
        rel_height=0.5,  # Used for calculation of the peaks width
    )
    logger.debug(f"{len(peaks)} peaks were found after baseline correction.")

    hplc_result_dic = {}

    # Define peak boundaries and integrate based on corrected spectrum
    # Also check https://github.com/HaasCP/mocca/blob/90a2143a889b28be96b0502ee107216e73870681/src/mocca/peak/expand.py#L14
    for center, base_left, base_right in zip(
            peaks, properties["left_ips"], properties["right_ips"]
    ):
        # Start from find_peaks positions (i.e. width at half max)
        left_in_min = d.index[int(base_left)]
        right_in_min = d.index[int(base_right)]

        # Failsafe to ensure these are set
        peak_start = d.index[0]
        peak_end = d.index[-1]

        # We rely on the chromatogram to be smoothed at this point!
        # Iterate left side of peak from right to left (i.e. np.flip)
        # for steps, derivative_value in enumerate(np.flip(d["dAbs"][:left_in_min])):
        for steps, derivative_value in enumerate(np.flip(d["dCorr"][:left_in_min])):
            if derivative_value < 1e-2:  # original 1e-3
                peak_start = d.index[
                    int(base_left) - steps + 1
                    ]  # +1 ensures non-overlapping peaks
                break

        # Iterate right side from left to right
        # for steps, derivative_value in enumerate(d["dAbs"][right_in_min:]):
        for steps, derivative_value in enumerate(d["dCorr"][right_in_min:]):
            if derivative_value > -1e-2:  # original -1e-3
                peak_end = d.index[int(base_right) + steps]
                break

        # Integrate peak based on signal after baseline correction
        peak = d["corr_0"][peak_start:peak_end]
        area = trapezoid(y=peak, x=peak.index)

        # print(f"peak{d.index[int(center)]}: {area}")
        # save the analysis result to a dictionary
        hplc_result_dic[d.index[int(center)]] = area

        # Annotate 註解 peak area
        ax.annotate(
            f"{d.index[int(center)]:0.2f}/{area:0.2f}",
            xy=(d.index[int(center)], d["Absorbance [mAu]"].values[int(center)]),
            xytext=(-5, 0),
            rotation=90,
            textcoords="offset points",
        )

        # Sets weights for baseline calculation to 0 in the peak range
        weights[d.index.get_loc(peak_start): d.index.get_loc(peak_end)] = 0

        # Plot integration limits
        ax.axvspan(peak_start, peak_end, facecolor="pink", edgecolor="black", alpha=0.5)

    # Baseline correction
    # d["baseline"], _ = pybaselines.polynomial.modpoly(
    #     d["Absorbance [mAu]"], d.index, poly_order=3, weights=weights
    # )
    # corr = d["Absorbance [mAu]"] - d["baseline"]
    # corr.plot(
    #     ax=ax,
    #     label="smoothed+baseline corrected",
    #     alpha=0.5,
    #     color="blue",
    # )

    # Plot initial peak width
    for num, (height, left, right) in enumerate(
            zip(
                properties["width_heights"], properties["left_ips"], properties["right_ips"]
            )
    ):
        plt.hlines(  # 用於在圖表中畫一條水平線
            height,
            d.index[int(left)],
            d.index[int(right)],
            color=f"C{num}",
            linewidth=4,
        )
    ax.legend(["raw", "smoothed", "baseline_correction"])

    # plt.show()
    plot_file_name = f"{datetime.date.today()}_{mongo_id}_{wavelength}.svg"  # change figure.file from png to svg
    plot_folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei")
    plot_file_path = plot_folder_path / Path(plot_file_name)
    plt.savefig(plot_file_path)
    # close the plot
    plt.close("all")

    # csv_file_name = f"{datetime.date.today()}_{mongo_id}_{wavelength}.csv"
    # csv_file_path = plot_folder_path / Path(csv_file_name)
    # d.to_csv(csv_file_path, index=True)

    return hplc_result_dic


def find_shift(d_bg, d_raw, ROP: list=[34, 36]):
    """
    Find the shift between the background and the raw data.
    :param d_bg:
    :param d_raw:
    :param ROP:
    :return:
    """
    # find the peak
    d_bg_shift = d_bg[ROP[0]:ROP[1]]
    peaks_bg, properties_bg = find_peaks(d_bg_shift)
    d_raw_shift = d_raw[ROP[0]:ROP[1]]
    peaks_raw, properties_raw = find_peaks(d_raw_shift)

    # find the shift between the background and the raw data
    shift = peaks_bg[0] - peaks_raw[0]
    shift_time = d_bg_shift.index[peaks_bg[0]] - d_raw_shift.index[peaks_raw[0]]
    logger.debug(f"Shift between background and raw data: {shift} data points ({shift_time} min).")

    return shift

def bg_subtraction(mongo_id: str,
                   file_path: Path,
                   wavelength: str = "254",
                   bg_shift: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:

    logger.info(f"Processing {mongo_id} for background subtraction.")

    #  parse the background file
    if wavelength == "254":
        bg_file_path = Path(
            # r"W:\BS-FlowChemistry\data\exported_chromatograms\blank_20240416 - DAD 2.1L- Channel 1.txt"
            r"W:\BS-FlowChemistry\data\exported_chromatograms\16_04_2024_blank_16-Apr-24 3_32_55 AM_149 - DAD 2.1L- Channel 1.txt"
        )
    elif wavelength == "215":
        bg_file_path = Path(
            r"W:\BS-FlowChemistry\data\exported_chromatograms\16_04_2024_blank_16-Apr-24 3_32_55 AM_149 - DAD 2.1L- Channel 2.txt"
        )

    # parse the background file
    header_data, header_lines = parse_header(bg_file_path)
    d_bg = create_dataset(bg_file_path, header_lines)
    # parse the raw file
    header_data, header_lines = parse_header(file_path)
    d_raw = create_dataset(file_path, header_lines)

    if bg_shift:
        logger.debug("Shift the background data to match the raw data.")
        # fixme: shift the background data or raw data?
        # shift the background data
        shift = find_shift(d_bg, d_raw)
        d_bg = d_bg.shift(-shift)

    merged_df = pd.merge(d_raw, d_bg, left_index=True, right_index=True, suffixes=("_raw", "_bg"))
    merged_df.fillna(0, inplace=True)

    # merged_df["Absorbance [mAu]"] = merged_df["Absorbance [mAu]_raw"] - merged_df["Absorbance [mAu]_bg"]
    col_names = merged_df.columns.to_list()
    sub_d = pd.DataFrame(merged_df[col_names[0]] - merged_df[col_names[1]], columns=["Absorbance [mAu]"])

    plot = False
    if plot:
        # Plot raw chromatogram (in gray)
        ax = merged_df.plot(
            label="raw",  # the label for the plot that will be displayed in the legend
            alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
            color="grey",
            # figsize=(10, 4),  # the size of the plot in inches (width, height
            figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
            xlim=(5, HPLC_RUNTIME - 5),  # x limits of the current axes
        )
        # PLOT subtracted graph
        sub_d.plot(label="subtracted", color="blue", linewidth=1.5, ax=ax)
        plt.show()

    return sub_d, merged_df


def signal_smooth(d: pd.DataFrame):
    # Apply median and FIR filter (set!)
    d = d.apply(signal.medfilt, raw=True, kernel_size=19)
    d = d.apply(fir_filter, raw=True)
    return d

def find_peaks(d: pd.DataFrame,
               max_signal: float = None,
               limit_height: float = None
               ) -> tuple[ndarray, Dict[str, ndarray]]:
    """
    Find peaks in the chromatogram.
    :param d:
    :param max_signal: max signal in the chromatogram
    :param limit_height: minimum height of the peak, default: max_signal/80
    :return:
    """
    if max_signal is None:
        max_signal = max(d["Absorbance [mAu]"])
    if limit_height is None:
        limit_height = max_signal / 80

    peaks, properties = signal.find_peaks(
        d["Absorbance [mAu]"],
        height=limit_height,  # defualt: /80
        prominence=max_signal / 45,  # defualt:/80.
        # The prominence of a peak measures how much a peak stands out from the surrounding baseline
        width=0.05,  # Required width of peaks in samples.
        rel_height=0.5,  # Used for calculation of the peaks width
    )
    logger.debug(f"{len(peaks)} peaks were found.")

    return peaks, properties


def txt_to_peak_bg(mongo_id: str,
                   file_path: Path,
                   wavelength: str = "254",
                   bg_sub: bool = True,
                   bg_shift: bool = False):
    """

    :param mongo_id:
    :param file_path:
    :param wavelength:
    :param bg_sub: use background subtraction or not
    :return:
    """
    if bg_sub:
        # bf_df is the subtracted data, merged_df is the raw data and background data
        bf_df, merged_df = bg_subtraction(mongo_id, file_path, wavelength, bg_shift)

        # Plot raw chromatogram (in gray)
        ax = merged_df.plot(
            label="raw",  # the label for the plot that will be displayed in the legend
            alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
            color="grey",
            # figsize=(10, 4),  # the size of the plot in inches (width, height
            figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
            xlim=(5, HPLC_RUNTIME - 5),  # x limits of the current axes
        )
        # PLOT subtracted/smoothed graph
        bf_df.plot(label="subtracted", color="blue", linewidth=1.5, ax=ax)

    else:
        # parse the hplc file
        header_data, header_lines = parse_header(file_path)
        bf_df = create_dataset(file_path, header_lines)
        # Plot raw chromatogram (in gray)
        ax = bf_df.plot(
            label="raw",  # the label for the plot that will be displayed in the legend
            alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
            color="grey",
            # figsize=(10, 4),  # the size of the plot in inches (width, height
            figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
            xlim=(5, HPLC_RUNTIME - 5),  # x limits of the current axes
        )

    # Apply median and FIR filter (set!)
    d = signal_smooth(bf_df)
    d["Absorbance [mAu]"].plot(label="smoothed", color="green", linewidth=1.5, ax=ax)

    # check whole hplc exp time
    if d.index[-1] < HPLC_RUNTIME - 5:
        logger.error(f"Chromatogram shorter than {HPLC_RUNTIME - 5} min, skipped.")
        return False

    # check the performance of the experiment
    if max(d["Absorbance [mAu]"]) < 2.5:  # default: 10 mAu
        logger.warning(f"Chromatogram without peaks above 2.5 mAu, skipped.")

    d = d[ROI[0]:ROI[1]]

    # Find peaks
    global_max = max(d["Absorbance [mAu]"])
    peaks, properties = find_peaks(d, global_max)

    # Create a mask as weight for baseline calculation.
    # 1=no peak, use for baseline 0=peak, ignore for baseline calc.
    weights = np.ones(len(d))
    # Calculate derivative
    d["dAbs"] = np.diff(d["Absorbance [mAu]"], prepend=0)
    # Remove NaN for final value
    d.fillna(0, inplace=True)

    hplc_result_dic = {}

    # Define peak boundaries and integrate based on corrected spectrum
    # Also check https://github.com/HaasCP/mocca/blob/90a2143a889b28be96b0502ee107216e73870681/src/mocca/peak/expand.py#L14
    for center, base_left, base_right in zip(
            peaks, properties["left_ips"], properties["right_ips"]
    ):
        # Start from find_peaks positions (i.e. width at half max)
        left_in_min = d.index[int(base_left)]
        right_in_min = d.index[int(base_right)]

        # Failsafe to ensure these are set
        peak_start = d.index[0]
        peak_end = d.index[-1]

        # We rely on the chromatogram to be smoothed at this point!
        # Iterate left side of peak from right to left (i.e. np.flip)
        for steps, derivative_value in enumerate(np.flip(d["dAbs"][:left_in_min])):
            if derivative_value < 1e-2:  # original 1e-3
                peak_start = d.index[
                    int(base_left) - steps + 1
                    ]  # +1 ensures non-overlapping peaks
                break

        # Iterate right side from left to right
        for steps, derivative_value in enumerate(d["dAbs"][right_in_min:]):
            if derivative_value > -1e-2:  # original -1e-3
                peak_end = d.index[int(base_right) + steps]
                break

        # Integrate peak based on signal after baseline correction
        peak = d["Absorbance [mAu]"][peak_start:peak_end]
        area = trapezoid(y=peak, x=peak.index)

        # print(f"peak{d.index[int(center)]}: {area}")
        # save the analysis result to a dictionary
        hplc_result_dic[d.index[int(center)]] = area

        # Annotate 註解 peak area
        ax.annotate(
            f"{d.index[int(center)]:0.2f}/{area:0.2f}",
            xy=(d.index[int(center)], d["Absorbance [mAu]"].values[int(center)]),
            xytext=(-5, 0),
            rotation=90,
            textcoords="offset points",
        )

        # Sets weights for baseline calculation to 0 in the peak range
        weights[d.index.get_loc(peak_start): d.index.get_loc(peak_end)] = 0

        # Plot integration limits
        ax.axvspan(peak_start, peak_end, facecolor="pink", edgecolor="black", alpha=0.5)

    # Plot initial peak width
    for num, (height, left, right) in enumerate(
            zip(
                properties["width_heights"], properties["left_ips"], properties["right_ips"]
            )
    ):
        plt.hlines(  # 用於在圖表中畫一條水平線
            height,
            d.index[int(left)],
            d.index[int(right)],
            color=f"C{num}",
            linewidth=4,
        )
    ax.legend(["Absorbance [mAu]_raw", "Absorbance [mAu]_bg", "subtracted", "smoothed"])
    # show the plot
    # plt.show()

    plot_file_name = f"{datetime.date.today()}_{mongo_id}_{wavelength}_bg.svg"  # change figure.file from png to svg
    plot_folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei")
    plot_file_path = plot_folder_path / Path(plot_file_name)
    plt.savefig(plot_file_path)
    # close the plot
    plt.close("all")

    return hplc_result_dic




if __name__ == "__main__":

    def compare():
        """the method used to compare the results from different methods"""
        file = Path(
            r"W:\BS-FlowChemistry\data\exported_chromatograms\12_04_2024_ctrl_073_2ul_005_12-Apr-24 10_52_22 AM_123 - DAD 2.1L- Channel 1.txt")
        raw_result_254 = txt_to_peak_bg("test", file, "254")
        print(raw_result_254)

        from anal_hplc_chromatogram import hplc_txt_to_peaks
        raw_result_254 = hplc_txt_to_peaks("test", file, "254")
        print(raw_result_254)

        file = Path(
            r"W:\BS-FlowChemistry\data\exported_chromatograms\12_04_2024_ctrl_073_2ul_005_12-Apr-24 10_52_22 AM_123 - DAD 2.1L- Channel 2.txt")
        raw_result_215 = txt_to_peak_bg("test", file, "215")
        print(raw_result_215)

        raw_result_215 = hplc_txt_to_peaks(f"test", file, "215")
        print(f"{raw_result_215}")


    def create_cali_curve(file_list: list | None = None, **kwargs):
        """cali_curve process"""
        cc_215 = [
            r"W:\BS-FlowChemistry\data\exported_chromatograms\15_08_2023_cc_0mM_tol_Htmob_15-Aug-23 10_03_23 AM_202 - DAD 2.1L- Channel 2.txt",
            r"W:\BS-FlowChemistry\data\exported_chromatograms\15_08_2023_cc_2mM_tol_Htmob_15-Aug-23 10_46_21 AM_203 - DAD 2.1L- Channel 2.txt",
            r"W:\BS-FlowChemistry\data\exported_chromatograms\15_08_2023_cc_6mM_tol_Htmob_15-Aug-23 11_29_19 AM_204 - DAD 2.1L- Channel 2.txt",
            r"W:\BS-FlowChemistry\data\exported_chromatograms\15_08_2023_cc_10mM_tol_Htmob_15-Aug-23 12_12_17 PM_205 - DAD 2.1L- Channel 2.txt",
            r"W:\BS-FlowChemistry\data\exported_chromatograms\15_08_2023_cc_12mM_tol_Htmob_15-Aug-23 12_55_14 PM_206 - DAD 2.1L- Channel 2.txt",
        ]

        # for testing
        if not file_list:
            file_list = cc_215

        channel = file_list[1].split("\\")[-1].split("-")[-1].strip().split(".")[0].split("Channel")[-1].strip()
        import numpy as np
        # current method
        channel_wavelength = {"1": "254nm", "2": "215nm"}

        for file in file_list:
            find_cc = file.split("\\")[-1].split("-")[0].find("cc")
            conc_name = file.split("\\")[-1].split("-")[0][find_cc:].strip()
            file_path = Path(file)

            std_name = conc_name + "_" + channel_wavelength[channel]
            result = hplc_txt_to_peaks(std_name, file_path)
            print(conc_name)
            print(result)


    def current_hplc_spactrum_process():
        # test the current process/ messy experiment mixture
        file = Path(
            r"W:\BS-FlowChemistry\data\exported_chromatograms\6492c295a7f28250ff34bb24 - DAD 2.1L- Channel 1.txt")
        raw_result_254 = hplc_txt_to_peaks(f"6492c295a7f28250ff34bb24-1", file, "254")
        logger.debug(f"raw result at 254 nm: {raw_result_254}")

        file = Path(
            r"W:\BS-FlowChemistry\data\exported_chromatograms\control_test_023 - DAD 2.1L- Channel 2.txt")
        raw_result_215 = hplc_txt_to_peaks(f"control_test_023", file, "215")
        logger.debug(f"raw result at 215 nm: {raw_result_215}")


