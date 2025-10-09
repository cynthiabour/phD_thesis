"""
class for  processing chromatograms
"""
import types

from scipy.signal import (
    find_peaks,
    peak_widths,
    firwin,
    kaiserord,
    lfilter,
    butter,
    savgol_filter,
    medfilt,
)
from scipy.integrate import trapezoid
from pandas import DataFrame
from numpy import diff, append
# import pybeads
import pybaselines


class Chromatogram:
    # ideally should inherit from spectrum or sth -> spectrochempy

    def __init__(
        self,
        chromatogram: DataFrame,
        y_ax: str or int,
        x_ax: str or int,
        region_of_interest: list = None,
    ):
        self.chromatogram = chromatogram  # d.raw
        self.y_ax = y_ax
        self.x_ax = x_ax

        self.peaks = None
        self._peaks = None
        self._peak_properties = None
        self.mod_chrom = chromatogram.copy()

        # if given, chromatogram is trimmed to this region
        self.roi = region_of_interest
        self._processing = {
            "smoothed": False,
            "maximum_y": False,
            "peaks_detected": False,
            "derivative": False,
            "baseline": False,
            "start_end": False,
            "width": False,
        }

    def process_chromatogram(self, detector_frequency=30):
        self.smooth_chromatogram(self.smooth_by_fir)
        self.global_maximum()
        self.find_peaks(
            fraction_of_largest_peak=80,
            detector_frequency=detector_frequency
        )
        self.get_derivative()
        self.get_peakwidth()
        self.mod_find_peak_start_end()
        self.baseline_correction(order=3)
        self.peak_area()
        return self.peaks

    def _trim_chromatogram(self, chrom):
        try:
            start = chrom.loc[chrom[self.x_ax] == self.roi[0]].index.values[0]
            end = chrom.loc[chrom[self.x_ax] == self.roi[1]].index.values[0]
            chrom = chrom.loc[start:end]
            return chrom
        except IndexError:
            raise ValueError("Experiment did not contain Chromatogram of valid size")

    def _butterworth_lowpass_coeffs(self, cutoff=0.5, sample_rate=30, order=6):
        nyq = 0.5 * sample_rate
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype="low", analog=False)
        return b, a

    def smooth_by_butter_lowpass(self, data, cutoff=0.5, sample_rate=30, order=6):
        b, a = self._butterworth_lowpass_coeffs(cutoff, sample_rate, order=order)
        y = lfilter(b, a, data)
        return y

    def smooth_by_savgol(self, data, window: int, polyorder: int):
        # with sedere (30 Hz) savgol window size 3 and polyorder 1 produces good results, but for integration 17 is better
        y = savgol_filter(data, window, polyorder)
        return y

    # def smooth_by_beads(self, data):
    #     # Chromatogram baseline estimation and denoising using
    #     # sparsity (BEADS)☆
    #     # Xiaoran Ning, Ivan W. Selesnick, Laurent Duval
    #     # params determined to kind of work
    #     fc = 0.006
    #     d = 1
    #     r = 6
    #     amp = 0.08
    #     lam0 = 0.5 * amp
    #     lam1 = 5 * amp
    #     lam2 = 4 * amp
    #     Nit = 15
    #     pen = "L1_v2"
    #
    #     signal_est, bg_est, cost = pybeads.beads(
    #         data, d, fc, r, Nit, lam0, lam1, lam2, pen, conv=None
    #     )
    #     return signal_est

    def smooth_by_fir(
        self,
        data_to_smooth,
        cutoff=1,
        sample_rate=30,
        transition_width=5,
        attenuation=60,
    ):
        """
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
        taps = firwin(N, cutoff / nyq_rate, window=("kaiser", beta))

        # Use lfilter to filter x with the FIR filter.
        return lfilter(taps, 1.0, data_to_smooth)

    def median_filter(self, data_to_smooth, window_size=19):
        # perform median filtering, this removes artefacts

        return medfilt(data_to_smooth, window_size)

    def smooth_chromatogram(
        self,
        smoothing_function: types.MethodType,
        *smoothing_args: list,
        **smoothing_kwargs,
    ):
        """
        Different smoothing functions can be plugged in to smooth the chromatogram
        Performs median filtering before other filter to remove artefacts
        """
        assert isinstance(smoothing_function, types.MethodType)
        assert not self._processing[
            "smoothed"
        ], "you are smoothing your chromatogram multiple times - while that doesn't necessarily do harm, its better to select better parameters."
        self.mod_chrom[self.y_ax] = self.median_filter(self.mod_chrom[self.y_ax].values, window_size=19)
        self.mod_chrom[self.y_ax] = smoothing_function(
            self.mod_chrom[self.y_ax].values, *smoothing_args, **smoothing_kwargs
        )
        self._processing["smoothed"] = True
        return self.mod_chrom

    def global_maximum(self):
        # no need
        # TODO check for min height or only allow max number of peaks
        # only trim if specified
        signal = (
            self.mod_chrom[self.y_ax]
            if not self.roi
            else self._trim_chromatogram(self.mod_chrom)[self.y_ax]
        )
        signal = list(signal)
        signal.sort(reverse=True)
        maximum_y = signal[0]
        self._processing["maximum_y"] = maximum_y
        return maximum_y

    def find_peaks(
        self,
        fraction_of_largest_peak: float = 80,

        minimum_width: float = 0.03,
        maximum_width: int = 1,
        # TODO this really matters would be nice if it could be inferred
        detector_frequency: int = 30,  # Hz
    ):
        """
        detector frequency in Hz
        minimum width in minutes
        """

        assert self._processing[
            "maximum_y"
        ], "Be sure to run Chromatogram.global_maximum() before, otherwise not reference peak height is given."
        # multiply by 60 to get seconds
        self._peaks, self._peak_properties = find_peaks(
            self.mod_chrom[self.y_ax],
            height=self._processing["maximum_y"] / fraction_of_largest_peak,
            prominence=self._processing["maximum_y"] / fraction_of_largest_peak,
            width=[round(minimum_width * detector_frequency * 60), round(maximum_width * detector_frequency * 60)],
            rel_height=0.8,
        )
        self.peaks = self.mod_chrom.iloc[self._peaks].copy()
        self._processing["peaks_detected"] = True

    def get_peakwidth(self):
        """
        """
        assert self._processing[
            "peaks_detected"
        ], "Be sure to run Chromatogram.find_peaks before."
        widths = peak_widths(
            self.mod_chrom[self.y_ax], self.peaks.index, rel_height=0.5
        )
        self.peaks.insert(2, "width", widths[0])
        self._processing["width"] = True

    def get_derivative(self, degree: int = 1):
        """

        :param degree:
        :return:
        """
        deriv = diff(self.mod_chrom[self.y_ax], degree)
        self.mod_chrom[f"{degree}_deriv"] = append(
            deriv, degree * [0]
        )  # fill missing values with trailing zeros
        self._processing["derivative"] = True

    def mod_find_peak_start_end(self):
        # tested, works as replacement
        from numpy import flip

        for center, base_left, base_right in zip(
            self._peaks,
            self._peak_properties["left_ips"],
            self._peak_properties["right_ips"],
        ):
            # Start from find_peaks positions (i.e. width at 80% max)
            left_in_min = self.mod_chrom["1_deriv"].index[int(base_left)]
            right_in_min = self.mod_chrom["1_deriv"].index[int(base_right)]

            # Failsafe to ensure these are set
            peak_start = self.mod_chrom["1_deriv"].index[0]
            peak_end = self.mod_chrom["1_deriv"].index[-1]

            # We rely on the chromatogram to be smoothed at this point!
            # Iterate left side of peak from right to left (i.e. np.flip)
            for steps, derivative_value in enumerate(
                flip(self.mod_chrom["1_deriv"][:left_in_min])
            ):
                if derivative_value < 1e-3:
                    peak_start = self.mod_chrom["1_deriv"].index[
                        int(base_left) - steps + 1
                    ]  # +1 ensures non-overlapping peaks
                    break

            # Iterate right side from left to right
            for steps, derivative_value in enumerate(
                self.mod_chrom["1_deriv"][right_in_min:]
            ):
                if derivative_value > -1e-3:
                    peak_end = self.mod_chrom["1_deriv"].index[int(base_right) + steps]
                    break
            self.peaks.loc[center, "lower"] = peak_start
            self.peaks.loc[center, "upper"] = peak_end
            self.peaks.loc[center, "lower_t"] = self.mod_chrom.loc[peak_start][
                self.x_ax
            ]
            self.peaks.loc[center, "upper_t"] = self.mod_chrom.loc[peak_end][self.x_ax]

        # clean up: in chromatogram "64675c3048c97f8ffdcc4d4d" a split peak occurs, for which the peak end is
        # determined far to far away, after another peak starts even
        # also a problem: 646b918fae2b3954ff6ccd5d
        for index, index_next in zip(self.peaks.index, self.peaks.index[1:]):
            if self.peaks.loc[index, "lower"] >= self.peaks.loc[index_next, "lower"]:
                self.peaks.loc[index_next, "lower"] = self.peaks.loc[index, "upper"] + 1
                self.peaks.loc[index, "lower_t"] = self.mod_chrom.loc[self.peaks.loc[index_next, "lower"]][
                    self.x_ax
                ]
            if self.peaks.loc[index, "upper"] >= self.peaks.loc[index_next, "lower"]:
                self.peaks.loc[index, "upper"] = self.peaks.loc[index_next, "lower"] - 1
                self.peaks.loc[index, "upper_t"] = self.mod_chrom.loc[self.peaks.loc[index, "upper"]][self.x_ax]

        self._processing["start_end"] = True

    def find_peak_start_end(self, peak_index, max_slope=0.001):
        """Supplying the peak index will inspect the derivative in that region, adding half the fwhm to the the index
        and subtracting. Outside of this range, peak start and end are defined as anything w a slope of less than 0.05
         in smoothed chromatogram"""
        assert self._processing[
            "peaks_detected"
        ], "Be sure to run Chromatogram.get_derivative() before. Peak start and end detection works on derivative."
        assert self._processing[
            "width"
        ], "Be sure to run Chromatogram.get_peakwidth before. Peak start and end detection takes peakwidth into account."

        # 3 is ambiguasly added for peaks with a flat base
        smaller = self.mod_chrom["1_deriv"][: peak_index - 3]
        larger = self.mod_chrom["1_deriv"][peak_index + 3:]
        # initialize w lowest value
        lower_bound = smaller.argsort()[0]
        for index in smaller[::-1].index:
            if (
                abs(smaller[index]) < max_slope
                or smaller[index] <= 0 <= smaller[index + 1]
            ):
                lower_bound = index
                # check if peak end is at least lower in intensity than 50 % of full peak height, also check if it is within half of peak width away from center at least
                if (
                    index < (peak_index - self.peaks.loc[peak_index, "width"] / 2)
                    or self.mod_chrom.loc[lower_bound, self.y_ax]
                    < 0.5 * self.peaks.loc[peak_index, self.y_ax]
                ):
                    break
        # initialize w lowest value
        for index in larger.index:
            # the slope is positive at the beginning of peak, but negative after maximum, therefore the abs
            if (
                abs(larger[index]) < max_slope
                or larger[index] >= 0 >= larger[index - 1]
            ):
                upper_bound = index
                # check if peak end is at least lower in intensity than 50 % of full peak height, also check if it is within half of peak width away from center at least
                if (
                    index > (peak_index + self.peaks.loc[peak_index, "width"] / 2)
                    or self.mod_chrom.loc[upper_bound, self.y_ax]
                    < 0.5 * self.peaks.loc[peak_index, self.y_ax]
                ):
                    break
        return lower_bound, upper_bound

    def peaks_find_start_end(self, unite_split=True):
        assert self._processing[
            "derivative"
        ], "Be sure to run Chromatogram.get_derivative() before. Peak start and end detection works on derivative."
        # iterate through the peaks found so far and append the peak starta nd end
        for peak_index in self.peaks.index:
            lower, upper = self.find_peak_start_end(peak_index)
            self.peaks.loc[peak_index, "lower"] = lower
            self.peaks.loc[peak_index, "upper"] = upper
            self.peaks.loc[peak_index, "lower_t"] = self.mod_chrom.loc[lower][self.x_ax]
            self.peaks.loc[peak_index, "upper_t"] = self.mod_chrom.loc[upper][self.x_ax]
            self._processing["start_end"] = True

        # check for split_peaks
        if len(self.peaks["lower"]) != len(set(self.peaks["lower"])) or len(
            self.peaks["upper"]
        ) != len(set(self.peaks["upper"])):
            print("Split peak detected. Pls inspect visually")
            if unite_split:
                # find which one is a duplicate
                print("Split peak detected. Will try to assume as one peak")
                if not self.peaks.loc[self.peaks.duplicated(subset="lower")].empty:
                    duplicate_value = self.peaks.loc[
                        self.peaks.duplicated(subset="lower")
                    ]["lower"].values[0]
                    duplicate_rows = self.peaks[
                        self.peaks["lower"] == duplicate_value
                    ].sort_values(by="width")
                    self.peaks.drop(
                        duplicate_rows.index[:-1], axis="index", inplace=True
                    )
                    print("drop from lower")
                elif not self.peaks.loc[self.peaks.duplicated(subset="upper")].empty:
                    duplicate_value = self.peaks.loc[
                        self.peaks.duplicated(subset="upper")
                    ]["upper"].values[0]
                    duplicate_rows = self.peaks[
                        self.peaks["upper"] == duplicate_value
                    ].sort_values(by="width")
                    self.peaks.drop(
                        duplicate_rows.index[:-1], axis="index", inplace=True
                    )
                    print("drop from upper")
                else:
                    print(
                        "No split peak found with same start or same end. Probably start-end between peaks same. check!"
                    )

    def plot_results(self):
        # simple for now -> only to quickly check reuslts
        testplot = self.chromatogram.plot(y=self.y_ax, x=self.x_ax)
        self.mod_chrom.plot(y=self.y_ax, ax=testplot, x=self.x_ax)
        self.peaks.plot(y=self.y_ax, style="o", ax=testplot, x=self.x_ax)
        self.mod_chrom.plot(y="1_deriv", ax=testplot, x=self.x_ax)
        for i in self.peaks.index:
            testplot.vlines(
                self.mod_chrom.loc[self.peaks.loc[i, "lower"], self.x_ax], 0, 100
            )
            testplot.vlines(
                self.mod_chrom.loc[self.peaks.loc[i, "upper"], self.x_ax], 0, 100
            )
            testplot.text(
                self.peaks.loc[i, self.x_ax],
                self.peaks.loc[i, self.y_ax],
                round(self.peaks.loc[i, "area"], 2),
            )

    def _baseline_peak_start_end(self, peak_start, peak_end):
        """
        Only useful on small peaks sitting on a big peak, otherwise if not baseline-separated, wrong results are obtained
        """
        # take start and end and simply do trapezoidal rule on these 2 point
        # put y values and x values
        chrom = self.mod_chrom
        baseline_area = trapezoid(
            [chrom.loc[peak_start, self.y_ax], chrom.loc[peak_end, self.y_ax]],
            x=[chrom.loc[peak_start, self.x_ax], chrom.loc[peak_end, self.x_ax]],
        )
        return baseline_area

    def peak_area(self, on_smoothed=True, _peak_start_end_baseline=False):
        # apply trapezoidal rule on smoothed chromatogram from peak start to peak end
        # if baseline_corrected, use baseline_correction function
        assert (
            False not in self._processing.values()
        ), "Be sure to run peakdetection, smothing and so on before"
        chrom = self.mod_chrom if on_smoothed else self.chromatogram
        # hand a slice of chromatogram to trapezoid function
        for peak in self.peaks.index:
            current_peak = chrom.loc[
                self.peaks.loc[peak, "lower"] : self.peaks.loc[peak, "upper"]
            ]
            area = trapezoid(current_peak[self.y_ax], x=current_peak[self.x_ax])
            if _peak_start_end_baseline:
                print(
                    "You are using a baseline subtraction that only gives reasonable results if peaks are baseline "
                    "separated. The only really good usecase are small peaks sitting on a big lump"
                )
                area -= self._baseline_peak_start_end(
                    self.peaks.loc[peak, "lower"], self.peaks.loc[peak, "upper"]
                )

            self.peaks.loc[peak, "area"] = area

    def baseline_correction(self, order=1):
        from numpy import ones

        assert self._processing["start_end"], (
            "Make sure to determine peak start and end before baseline calculation. "
            "The peak regions are weighted for the baseline caluculation to get a better baseline"
        )
        # works decently
        # get peak weights - create a mask for the peaks
        weights = ones(len(self.chromatogram.index))
        for i in self.peaks.index:
            weights[
                int(self.peaks.loc[i, "lower"]) : int(self.peaks.loc[i, "upper"])
            ] = 0
        # perform baseline determination on modified chromatogram
        baseline = pybaselines.polynomial.modpoly(
            self.mod_chrom[self.y_ax],
            self.mod_chrom[self.x_ax],
            poly_order=order,
            weights=weights,
        )
        self.mod_chrom[self.y_ax] = self.mod_chrom[self.y_ax] - baseline[0]
        self._processing["baseline"] = True

    def return_peak_table(self):
        return self.peaks[[self.x_ax, self.y_ax, "area"]]

if __name__ == "__main__":
    from pathlib import Path
    file_path = Path(
        # r"W:\BS-FlowChemistry\data\exported_chromatograms\6492c295a7f28250ff34bb24 - DAD 2.1L- Channel 1.txt")
        r"W:\BS-FlowChemistry\data\exported_chromatograms\06_10_2024_std_case_3_sugarStock_1mM_10_6_2024 11_53_45 AM_349 - DAD 2.1L- Channel 1.txt")

    from .anal_hplc_chromatogram import parse_header, create_dataset

    header_data, header_lines = parse_header(file_path)

    chromatogram = create_dataset(file_path, header_lines)
    sp = Chromatogram(
        chromatogram,
        "Absorbance [mAu]",
        "time (min.)",
        region_of_interest=[10, 31]
    )
    sp.process_chromatogram()