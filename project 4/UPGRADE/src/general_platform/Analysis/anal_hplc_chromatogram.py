"""
Class for all hplc analysis (including signal subtraction)
process hplc data(.txt) -> dict of peak
"""
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
from beanie import PydanticObjectId

from BV_experiments.src.general_platform.Librarian import HplcConfig
# from BV_experiments.src.general_platform.Analysis.anal_Chromatogram import Chromatogram

class DadChromatogram:
    def __init__(self,
                 mongo_id: str | PydanticObjectId,
                 hplc_config: HplcConfig | dict[str, Any],
                 folder_path: str = r"W:\BS-FlowChemistry\data\exported_chromatograms",
                 file_extension: str = ".txt",
                 channel: int | None = None,
                 file_path: Path | None = None,
                 ):
        """
        all function from processing and yield calculation
        """

        # init the class with the hplc config
        self.mongo_id = mongo_id
        if channel is None:
            logger.warning("No channel specified. set to channel 1 by default.")
            channel = 1
        self.channel = channel
        self.folder_path = Path(folder_path)
        self.file_extension = file_extension.strip(".")
        self._hplc_config = hplc_config

        if type(hplc_config) is HplcConfig:
            self.hplc_runtime: int = hplc_config.HPLC_RUNTIME
            self.dad_method: dict = hplc_config.ACQUISITION
            self.file_formate = hplc_config.ASCII_FILE_FORMAT

            self.roi: list = hplc_config.ROI
            self.PEAK_RT: dict = hplc_config.PEAK_RT
            self.PEAK_RT_2: dict = hplc_config.PEAK_RT_2

            self.ACCEPTED_SHIFT: float = hplc_config.ACCEPTED_SHIFT
            self.peak_rt_range: dict = {key: [value - self.ACCEPTED_SHIFT, value + self.ACCEPTED_SHIFT] for key, value
                                        in
                                        self.PEAK_RT.items()}
            # fixme: should be general to all channel :(
            self.bg_file_path: dict = hplc_config.BACKGROUND_FILES[f"channel_{channel}"]

        elif type(hplc_config) is dict:

            self.hplc_runtime: int = hplc_config["HPLC_RUNTIME"]
            self.dad_method: dict = hplc_config["ACQUISITION"]
            self.file_formate = hplc_config["ASCII_FILE_FORMAT"]

            self.roi: list = hplc_config["ROI"]
            self.PEAK_RT: dict = hplc_config["PEAK_RT"]
            self.PEAK_RT_2: dict = hplc_config["PEAK_RT_2"]

            self.ACCEPTED_SHIFT: float = hplc_config["ACCEPTED_SHIFT"]
            self.peak_rt_range: dict = {key: [value - self.ACCEPTED_SHIFT, value + self.ACCEPTED_SHIFT] for key, value
                                        in
                                        self.PEAK_RT.items()}
            # fixme: should be general to all channel :(
            self.bg_file_path: dict = hplc_config["BACKGROUND_FILES"][f"channel_{channel}"]

        self.chromatogram = None
        self._processing = {
            "bg_sub": False,
            "smoothed": False,
            "maximum_y": False,
            "peaks_detected": False,
            "derivative": False,
            "baseline": False,
            "start_end": False,
            "width": False,
        }
        self.header_data = None
        self.header_lines = None
        self.dataset = None
        self.file_path = file_path

    def file_process(self, file_path: Path | None = None) -> pd.DataFrame:
        """
        process the file and return the dataset
        :param file_path:
        :return:
        """
        if file_path is None:
            try:
                self.file_path = self._find_file(self.mongo_id)
            except FileNotFoundError or ValueError as e:
                logger.error(f"{e}")
                self.file_path = self.folder_path / Path(
                    f"{self.mongo_id} - DAD 2.1L- Channel {self.channel}.{self.file_extension}")

        self.header_data, self.header_lines = self.parse_header(self.file_path)
        self.dataset = self.create_dataset(self.file_path)

    def _find_file(self, search_string: str | None = None) -> Path:
        """
        find the file in the folder. If multiple files are found, raise an error.
        :param search_string:
        :return:
        """
        if search_string is None:
            search_string = self.mongo_id

        fitted_files = []
        # Iterate over each file in the directory
        for file_path in self.folder_path.iterdir():
            if file_path.is_file():
                if search_string in file_path.name:
                    if self.channel:
                        if f"Channel {self.channel}" in file_path.name:
                            fitted_files.append(file_path)
                    else:
                        fitted_files.append(file_path)
        if len(fitted_files) == 1:
            return fitted_files[0]
        elif len(fitted_files) > 1:
            logger.error(f"{len(fitted_files)} files found: {fitted_files}")
            raise ValueError(f"Multiple files found for {search_string}.")
        else:
            logger.error(f"No files found for {search_string}.")
            raise FileNotFoundError(f"No files found for {search_string}.")

    # def peak_rt_range(self,
    #                   shift: float = None) -> dict[str, list[float]]:
    #     # the shift is used to define the peak range (it is unavoidable to the current flow rate and hplc pump)
    #     shift = self.ACCEPTED_SHIFT if shift is None else shift
    #     return {key: [value - shift, value + shift] for key, value in self.PEAK_RT.items()}

    def parse_header(self,
                     file_name: Path):
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
                with file_name.open("r") as fh:

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

    def create_dataset(self,
                       file_name: Path) -> pd.DataFrame:
        """read in the hplc txt file"""

        header_data, header_lines = self.parse_header(file_name)

        # X dimension is retention time with units as minute in the source file
        d = pd.read_csv(
            file_name,
            delimiter="\t",
            skiprows=header_lines,
            index_col="time (min.)",
            header=0,
            names=["time (min.)", "Absorbance [mAu]"],
            encoding="cp852")
        # save header_data as metadata
        d._metadata = header_data
        return d

    def process_chromatogram(self, ):
        # self.chromatogram = Chromatogram()
        pass

    def _find_peaks(self,
                    d: pd.DataFrame,
                    max_signal: float = None,
                    limit_height: float = None,
                    limit_prominence: float = None,
                    minimum_width: float = 0.03,
                    maximum_width: int = 1,
                    # TODO this really matters would be nice if it could be inferred
                    detector_frequency: int = 30,
                    ) -> tuple[ndarray, Dict[str, ndarray]]:
        """
        Find peaks in the chromatogram.
        :param d:
        :param max_signal: max signal in the chromatogram
        :param limit_height: minimum height of the peak, default: max_signal/80
        :return:
        """
        if max_signal is None:
            max_signal = max(d)
        if limit_height is None:
            limit_height = max_signal / 80
        if limit_prominence is None:
            limit_prominence = max_signal / 45  # defualt:/80

        # The prominence of a peak measures how much a peak stands out from the surrounding baseline
        peaks, properties = signal.find_peaks(
            d,
            height=limit_height,
            prominence=limit_prominence,
            width=0.05,  # Required width of peaks in samples.
            rel_height=0.5,  # Used for calculation of the peaks width
        )
        logger.debug(f"{len(peaks)} peaks were found.")

        return peaks, properties

    def _find_shift(self,
                    d_bg: pd.DataFrame,
                    d_raw: pd.DataFrame,
                    ROP: list | None = None,
                    ):
        """
        Find the shift between the background and the raw data.
        :param d_bg: data points of the background chromatogram
        :param d_raw: data of the raw chromatogram
        :param ROP: time region of peak to find the shift (IS)  # [start, end] of the peak
        :return:
        """
        if ROP is None:
            ROP = self.peak_rt_range["IS"]

        # find the target peak in both background and raw data
        d_bg_shift = d_bg[ROP[0]:ROP[1]]
        peaks_bg, properties_bg = self._find_peaks(d_bg_shift)
        d_raw_shift = d_raw[ROP[0]:ROP[1]]
        peaks_raw, properties_raw = self._find_peaks(d_raw_shift)

        # find the shift between the background and raw data
        shift = peaks_bg[0] - peaks_raw[0]
        shift_time = d_bg_shift.index[peaks_bg[0]] - d_raw_shift.index[peaks_raw[0]]
        logger.debug(f"Shift between background and raw data: {shift} data points ({shift_time} min).")

        return shift

    def bg_subtraction(self,
                       file_path: Path,
                       bg_file_path: Path,
                       bg_shift: bool = False,
                       plot: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:

        logger.info(f"Processing background subtraction.")
        # parse the background file and raw file to dataframes
        d_bg = self.create_dataset(bg_file_path)
        d_raw = self.create_dataset(file_path)

        if bg_shift:
            logger.debug("Shift the background data to match the raw data.")
            # fixme: shift the background data or raw data?
            # shift the background data
            shift = self._find_shift(d_bg, d_raw)
            d_bg = d_bg.shift(-shift)

        merged_df = pd.merge(d_raw, d_bg, left_index=True, right_index=True, suffixes=("_raw", "_bg"))
        merged_df.fillna(0, inplace=True)

        # merged_df["Absorbance [mAu]"] = merged_df["Absorbance [mAu]_raw"] - merged_df["Absorbance [mAu]_bg"]
        col_names = merged_df.columns.to_list()
        # subtract the background from the raw data
        sub_d = pd.DataFrame(merged_df[col_names[0]] - merged_df[col_names[1]], columns=["Absorbance [mAu]"])

        if plot:
            # Plot raw chromatogram (in gray)
            ax = merged_df.plot(
                label="raw",  # the label for the plot that will be displayed in the legend
                alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
                color="grey",
                # figsize=(10, 4),  # the size of the plot in inches (width, height
                figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
                xlim=(self.hplc_runtime * 0.1, self.hplc_runtime * 0.9),  # x limits of the current axes
            )
            # PLOT subtracted graph
            sub_d.plot(label="subtracted", color="blue", linewidth=1.5, ax=ax)
            plt.show()

        return sub_d, merged_df  # return the subtracted data (1Y) and the merged data (2Y)

    def signal_smooth(self,
                      d: pd.DataFrame):
        # Apply median and FIR filter (set!)
        d = d.apply(signal.medfilt, raw=True, kernel_size=19)

        d = d.apply(self._smooth_by_fir_filter,
                    raw=True,
                    cutoff=1,
                    sample_rate=int(self.dad_method["sampling_frequency"].split()[0]),
                    transition_width=5,
                    attenuation=60)
        return d

    def _smooth_by_fir_filter(self,
                              ndarray,
                              cutoff=1,
                              sample_rate=30,
                              transition_width=5,
                              attenuation=60,
                              ):
        """
        Apply a Finite impulse response filter to a NDArray.

        cutoff: cutoff frequency in Hz
        sample rate: in Hz
        transition_width: width of transition from path to stop in Hz, rel to nyqvist rate
        attenuation: attenuation of stopband in dB
        """
        nyq_rate = sample_rate / 2.0
        width = transition_width / nyq_rate

        # Compute the order and Kaiser parameter for the FIR filter.
        N, beta = kaiserord(attenuation, width)

        # Use firwin with a Kaiser window to create a lowpass FIR filter.
        taps = firwin(N, cutoff / nyq_rate, window=('kaiser', beta))

        # Use lfilter to filter x with the FIR filter.
        return lfilter(taps, 1.0, ndarray)

    def check_quality(self,
                      d: pd.DataFrame,
                      minimum_signal: float = 2.5, ):
        """
        Check the quality of the chromatogram.
        :param d:
        :return:
        """
        # check whole hplc exp time
        # if d.index[-1] < self.hplc_runtime - 5:
        #     logger.error(f"Chromatogram shorter than {self.hplc_runtime - 5} min, skipped.")
        #     return False
        # check type is pd.Series
        if isinstance(d, pd.DataFrame):
            check_d = d.iloc[:, 0]
        elif isinstance(d, pd.Series):
            check_d = d
        else:
            raise ValueError("Input data type is not supported.")
        # check the performance of the experiment
        if max(check_d) < minimum_signal:  # default: 10 mAu
            logger.warning(f"Chromatogram without peaks above {minimum_signal} mAu, skipped.")
            return False
        return True

    def txt_to_peaks(self,
                     file_path: Path | None = None,
                     bg_sub: bool = True,
                     bg_shift: bool = False,
                     use_is_peak: bool = True
                     ) -> bool | dict[float, float]:
        """
        process the hplc data and return the peaks
        :param file_path: the file path of the hplc data
        :param bg_sub: whether to use background subtraction
        :param bg_shift: whether to use background shift
        :param use_is_peak: whether to use IS peak to find the peaks

        :return: the peak dictionary {retention_time: area} for further analysis

        """
        if file_path is None:
            if self.file_path is None:
                self.file_process(file_path=self.file_path)
            file_path = self.file_path  # use the initailize path
        if bg_sub:
            try:
                bg_file_path = self.folder_path / Path(self.bg_file_path)
                d_raw, merged_db = self.bg_subtraction(file_path, bg_file_path, bg_shift)
            except FileNotFoundError as e:
                logger.error(f"{e}")
                bg_file_path = self._find_file(self.bg_file_path[f"channel_{self.channel}"])
                d_raw, merged_db = self.bg_subtraction(file_path, bg_file_path, bg_shift)
        else:
            d_raw: pd.DataFrame = self.create_dataset(file_path)

        # todo: change to Chromatogram class
        # sp = Chromatogram(d_raw, "Absorbance [mAu]",  "time (min.)", region_of_interest=self.roi)

        self.check_quality(d_raw)  # check (whole hplc exp time & performance of the experiment)
        d = self.signal_smooth(d_raw)  # Apply median and FIR filter (set!)

        if not self.check_quality(d):
            raise ValueError("Chromatogram quality check failed.")  # check again

        # Work on the region of interest: Cropping ROI after FIR prevents FIR-related boundary artifacts to affect baseline correction
        trim_d = d[self.roi[0]:self.roi[1]].copy()

        # Plot raw chromatogram (in gray)
        ax = merged_db.plot(
            label="raw",  # the label for the plot that will be displayed in the legend
            alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
            color="grey",
            figsize=(20, 8),  # the size of the plot in inches (width, height
            xlim=(0.1 * self.hplc_runtime, 0.9 * self.hplc_runtime),  # x limits of the current axes
        )
        d_raw.plot(label="subtracted", color="blue", linewidth=1.5, ax=ax)
        # d["Absorbance [mAu]"].plot(label="smoothed", color="green", linewidth=1.5, ax=ax)  # PLOT smoothed graph
        trim_d["Absorbance [mAu]"].plot(label="smoothed", color="green", linewidth=1.5, ax=ax)  # PLOT smoothed graph
        ax.set_ylim(min(trim_d["Absorbance [mAu]"]) - 10,
                    max(trim_d["Absorbance [mAu]"]) + 20)  # set y-axes of the current figure.

        # Find peaks after smoothed(first time....)
        global_max = max(trim_d["Absorbance [mAu]"])
        peaks, properties = self._find_peaks(
            trim_d["Absorbance [mAu]"],
            max_signal=global_max,
            limit_height=global_max / 80,
            limit_prominence=global_max / 45, )

        # baseline correction
        # Create a mask as weight for baseline calculation. 1=no peak, use for baseline 0=peak, ignore for baseline calc.
        weights = np.ones(len(trim_d))
        trim_d["dAbs"] = np.diff(trim_d["Absorbance [mAu]"], prepend=0)  # Calculate derivative
        trim_d.fillna(0, inplace=True)

        for base_left, base_right in zip(properties["left_ips"], properties["right_ips"]):
            # Sets weights for baseline calculation to 0 in the peak range
            weights[round(base_left): round(base_right)] = 0

        trim_d["baseline_0"], _ = pybaselines.polynomial.modpoly(
            trim_d["Absorbance [mAu]"], trim_d.index, poly_order=3, weights=weights
        )
        trim_d["corr_0"] = trim_d["Absorbance [mAu]"] - trim_d["baseline_0"]
        trim_d["corr_0"].plot(
            ax=ax, label="smoothed+baseline corrected_0", alpha=0.5, color="green", )
        trim_d["dCorr"] = np.diff(trim_d["corr_0"], prepend=0)

        # Find peaks after baseline correction (second time....)
        # global_max = max(trim_d["corr_0"])
        # if self.check_quality(trim_d["corr_0"], minimum_signal=3.0):
        #     logger.error(f"After baseline correction, Chromatogram without peaks above 3.0 mAu, skipped.")
        #     # raise ValueError("Chromatogram quality check failed.")
        #     return False

        if use_is_peak == True:
            local_max = max(trim_d["corr_0"][
                            self.peak_rt_range['is'][0]
                            :self.peak_rt_range['is'][1]
                            ])

            if not self.check_quality(
                    trim_d["corr_0"][self.peak_rt_range['is'][0]:self.peak_rt_range["is"][1]],
                    minimum_signal=3.0):
                logger.error(f"After baseline correction, IS peak is below 3.0 mAu, skipped.")
                return False

            peaks, properties = self._find_peaks(
                trim_d["corr_0"],
                max_signal=local_max,
                limit_height=local_max / 50,
                limit_prominence=local_max / 45, )

        hplc_result_dic = {}
        # Define peak boundaries and integrate based on corrected spectrum
        # Also check https://github.com/HaasCP/mocca/blob/90a2143a889b28be96b0502ee107216e73870681/src/mocca/peak/expand.py#L14
        for center, base_left, base_right in zip(
                peaks, properties["left_ips"], properties["right_ips"]
        ):
            # Start from find_peaks positions (i.e. width at half max)
            left_in_min = trim_d.index[int(base_left)]
            right_in_min = trim_d.index[int(base_right)]

            # Failsafe to ensure these are set
            peak_start = trim_d.index[0]
            peak_end = trim_d.index[-1]

            # We rely on the chromatogram to be smoothed at this point!
            # Iterate left side of peak from right to left (i.e. np.flip)
            # for steps, derivative_value in enumerate(np.flip(d["dAbs"][:left_in_min])):
            for steps, derivative_value in enumerate(np.flip(trim_d["dCorr"][:left_in_min])):
                if derivative_value < 1e-2:  # original 1e-3
                    peak_start = trim_d.index[
                        int(base_left) - steps + 1
                        ]  # +1 ensures non-overlapping peaks
                    break

            # Iterate right side from left to right
            # for steps, derivative_value in enumerate(d["dAbs"][right_in_min:]):
            for steps, derivative_value in enumerate(trim_d["dCorr"][right_in_min:]):
                if derivative_value > -1e-2:  # original -1e-3
                    peak_end = trim_d.index[int(base_right) + steps]
                    break

            # Integrate peak based on signal after baseline correction
            peak = trim_d["corr_0"][peak_start:peak_end]
            area = trapezoid(y=peak, x=peak.index)

            # print(f"peak{d.index[int(center)]}: {area}")
            # save the analysis result to a dictionary
            hplc_result_dic[trim_d.index[int(center)]] = area

            # Annotate 註解 peak area
            ax.annotate(
                f"{trim_d.index[int(center)]:0.2f}/{area:0.2f}",
                xy=(trim_d.index[int(center)], d["Absorbance [mAu]"].values[int(center)]),
                xytext=(-5, 0),
                rotation=90,
                textcoords="offset points",
            )

            # Sets weights for baseline calculation to 0 in the peak range
            weights[trim_d.index.get_loc(peak_start): trim_d.index.get_loc(peak_end)] = 0

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
                trim_d.index[int(left)],
                trim_d.index[int(right)],
                color=f"C{num}",
                linewidth=4,
            )
        ax.legend(["raw", "smoothed", "baseline_correction"])

        plot_file_name = f"{datetime.date.today()}_{self.mongo_id}_channel_{self.channel}.svg"
        plot_folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei")
        plot_file_path = plot_folder_path / Path(plot_file_name)
        plt.savefig(plot_file_path)
        # csv_file_name = f"{datetime.date.today()}_{mongo_id}_{wavelength}.csv"
        # csv_file_path = plot_folder_path / Path(csv_file_name)
        # d.to_csv(csv_file_path, index=True)

        return hplc_result_dic

    def plot_chromatogram(self,
                          d_raw: pd.DataFrame,  # raw data
                          d: pd.DataFrame,
                          properties,
                          peaks,
                          hplc_result_dic,
                          plot_file_path: Path = None, ):

        # Plot raw chromatogram (in gray)
        ax = d_raw.plot(
            label="raw",  # the label for the plot that will be displayed in the legend
            alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
            color="grey",
            # figsize=(10, 4),  # the size of the plot in inches (width, height
            figsize=(20, 8),  # TODO: real exp: the size of the plot in inches (width, height
            xlim=(self.hplc_runtime * 0.1, self.hplc_runtime * 0.9),  # x limits of the current axes
        )

        d["Absorbance [mAu]"].plot(label="smoothed", color="green", linewidth=1.5, ax=ax)
        # ax.set_ylim(min(d["Absorbance [mAu]"]) - 10, max(d["Absorbance [mAu]"]) + 20)

        d["corr_0"].plot(
            ax=ax,
            label="smoothed+baseline corrected_0",
            alpha=0.5,
            color="green",
        )

        # Annotate peaks
        for center, area in hplc_result_dic.items():
            ax.annotate(
                f"{center:0.2f}/{area:0.2f}",
                xy=(center, d["Absorbance [mAu]"].values[int(center)]),
                xytext=(-5, 0),
                rotation=90,
                textcoords="offset points",
            )

        # Plot integration limits
        for num, (height, left, right) in enumerate(
                zip(
                    properties["width_heights"], properties["left_ips"], properties["right_ips"]
                )
        ):
            plt.hlines(
                height,
                d.index[int(left)],
                d.index[int(right)],
                color=f"C{num}",
                linewidth=4,
            )
        ax.legend(["raw", "smoothed", "baseline_correction"])
        if plot_file_path is None:
            # change figure.file from png to svg
            plot_file_name = f"{datetime.date.today()}_{self.mongo_id}_channel_{self.channel}.svg"
        plot_folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei")
        plot_file_path = plot_folder_path / Path(plot_file_name)
        plt.savefig(plot_file_path)
        # close the plot
        plt.close("all")


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation

    hplc_info_dict = SecondDebenzylation.hplc_config_info.dict()
    # hplc_info_dict = {attr: getattr(HPLCConfig, attr) for attr in dir(HPLCConfig) if
    #                   not callable(getattr(HPLCConfig, attr)) and not attr.startswith("__")}


    for channel in range(3):
        # fixme: should be general to all channel :(
        chrom = DadChromatogram("yxy001_ctrl_153",
                                SecondDebenzylation.hplc_config_info,
                                channel=channel,
                                file_path=Path(fr"W:\BS-FlowChemistry\data\exported_chromatograms\yxy001_ctrl_153 - DAD 2.1L- Channel {channel}.txt"),)
        print(chrom.txt_to_peaks(use_is_peak=False))  # with saving the plot


