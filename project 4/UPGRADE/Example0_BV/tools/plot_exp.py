from pathlib import Path
from loguru import logger

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# from BV_experiments.anal_Chromatogram import Chromatogram
# from BV_experiments.anal_hplc_chromatogram import fir_filter, parse_header

def find_files_with_text(directory, text):
    matching_files = []
    for path in directory.iterdir():
        if path.is_file() and text in path.name:
            matching_files.append(path)
    return matching_files

def check_find_files(matching_files: list):
    # Display the results
    if len(matching_files) == 1:
        logger.debug(f"Matching file found:{matching_files}")
        return matching_files[0]
    elif len(matching_files) < 1:
        logger.error(f"No Matching file found.")
        raise FileNotFoundError
    else:
        logger.error(f"multiple matching file found:{matching_files}")
        # return matching_files[-1]
        raise FileExistsError

def plot_log(mongo_id):
    logger.debug(f"start plot the exp {mongo_id}")

    # Specify the directory and text to search for
    system_log_folder = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\system_log")
    dad_log_folder = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra")

    # Call the function to find matching files
    s_matching_files = find_files_with_text(system_log_folder, mongo_id)
    d_matching_files = find_files_with_text(dad_log_folder, mongo_id)

    s_log = check_find_files(s_matching_files)
    d_log = check_find_files(d_matching_files)

    # dad_log = pd.read_csv(d_log, index_col=[0])
    # axs = dad_log.plot(figsize=(12, 4))
    # sys_log = pd.read_csv(s_log, index_col=[0])
    # sys_log.plot(figsize=(12, 4), subplots=True)
    # fig, axs = plt.subplots(figsize=(12, 8))
    # sys_log.plot(ax=axs, subplots=True)
    # dad_log.plot(ax=axs)
    # plt.show()

    # change log index start from 0
    sys_np = pd.read_csv(s_log).to_numpy()
    start_time = sys_np[0, 0]
    sys_np[:, 0] = sys_np[:, 0] - start_time


    dad_np = pd.read_csv(d_log).to_numpy()
    # start_time = dad_np[0, 0]
    dad_np[:, 0] = dad_np[:, 0] - start_time

    # Initialise the subplot function using number of rows and columns
    figure, axis = plt.subplots(6, 1,
                                sharex=True,
                                squeeze=True,
                                height_ratios=[0.2, 0.3, 0.3, 1.5, 0.5, 1.5],
                                figsize=(10, 15))
    axis = axis.flat
    figure.suptitle(f'{mongo_id}', fontweight='bold')  # fontsize=12
    # For 1st figure
    axis[0].plot(sys_np[:, 0], sys_np[:, 1], color="C4")
    axis[0].set_title("RunState")
    # axis[0].grid(True)

    # For 2nd figure
    axis[1].plot(sys_np[:, 0], sys_np[:, 2], color="C6")
    axis[1].set_title("allValve")
    axis[1].grid(True)

    # For 3rd figure
    axis[2].plot(sys_np[:, 0], sys_np[:, 11], color="C9")
    axis[2].set_title("hplcValve")
    axis[2].grid(True)

    # For 4rd figure
    pA, = axis[3].plot(sys_np[:, 0], sys_np[:, 3], label="pumpA", alpha=0.6)
    pB, = axis[3].plot(sys_np[:, 0], sys_np[:, 4], label="pumpB", alpha=0.6)
    pR, = axis[3].plot(sys_np[:, 0], sys_np[:, 5], label="system", alpha=0.6)
    pM, = axis[3].plot(sys_np[:, 0], sys_np[:, 10]*100, label="pumpM", alpha=0.6)
    pBPR, = axis[3].plot(sys_np[:, 0], sys_np[:, 8]*1000, label="pumpM", alpha=0.6)
    axis[3].set_title("Pressure")
    axis[3].legend([pA, pB, pR, pM, pBPR], ["pumpA", "pumpB", "system", "pumpM", "pBPR"], bbox_to_anchor=(1.05, 1), ncol=1, )  #bbox_to_anchor=(0, 1, 1, .0)
    axis[3].grid(True)

    # For 5rd figure
    axis[4].plot(sys_np[:, 0], sys_np[:, 6], color="blue", alpha=0.8)
    axis[4].set_title("temp")
    axis[4].grid(True)

    # For 6th figure
    line1, = axis[5].plot(dad_np[:, 0], dad_np[:, 6], color='gray', label="cal", alpha=0.8)
    line2, = axis[5].plot(dad_np[:, 0], dad_np[:, 7], color="C5", label="med", alpha=0.8)
    line3, = axis[5].plot(dad_np[:, 0], dad_np[:, 9], label="400cal", alpha=0.8)
    axis[5].set_title("DAD")
    axis[5].legend([line1, line2, line3], ["cal", "med", "400cal"], bbox_to_anchor=(0, 1, 1, .0), ncol=3, )
    axis[5].grid(True)
    plt.xlabel("time (sec.)")
    # plt.show()

    plot_file_name = f"{mongo_id}_log_figure.svg"  # png
    plot_folder_path = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\system_log\log_plots_wei")
    plot_file_path = plot_folder_path / Path(plot_file_name)
    plt.savefig(plot_file_path)


# def plot_chromatorgram(mongo_id: str):
#     # Initialise the subplot function using number of rows and columns
#     figure, axis = plt.subplots(2, 1,
#                                 sharex=True,
#                                 squeeze=True,
#                                 figsize=(8, 12))
#
#
#     from BV_experiments.anal_hplc_chromatogram import create_dataset
#
# def file_to_chromatogram(mongo_id: str, file_path: Path, wavelength: str = "254"):
#
#     file_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\control_test_011 - DAD 2.1L- Channel 2.txt")
#
#     # parse the header
#     header_data, header_lines = parse_header(file_path)
#
#     if "Detector Unit" in header_data and "Y Axis Title" in header_data:
#         y_ax = header_data["Y Axis Title"] + " [" + header_data["Detector Unit"] + "]"
#     else:
#         y_ax = None
#
#     # X dimension is retention time with units as minute in the source file
#     d_raw = pd.read_csv(
#         file_path,
#         delimiter="\t",
#         skiprows=header_lines,
#         index_col="time (min.)",
#         header=0,
#         names=["time (min.)", y_ax],
#         encoding="cp852",
#     )
#     # save header_data as metadata
#     d_raw._metadata = header_data
#
#     # check whole hplc exp time
#     if d_raw.index[-1] < 30:  # TODO: change method...
#         print(f"Chromatogram shorter than 30 min, skipped.")
#
#     # check the performance of the experiment
#     if max(d_raw["Absorbance [mAu]"]) < 10:
#         print(f"Chromatogram without peaks above 10 mAu, skipped.")
#
#     # Plot raw chromatogram (in gray)
#     ax = d_raw.plot(
#         label="RAW",  # the label for the plot that will be displayed in the legend
#         alpha=0.5,  # the transparency of the plot. 0 is completely transparent; 1 is completely opaque.
#         color="grey",
#         figsize=(10, 4),  # the size of the plot in inches (width, height
#         # figsize=(20, 8),  #TODO: real exp: the size of the plot in inches (width, height
#         xlim=(1.5, 19.5)
#     )
#
#     chrom = Chromatogram(d_raw, y_ax, "time (min.)", region_of_interest=[6, 20])
#     # chrom.process_chromatogram()
#
#     chrom.smooth_chromatogram(chrom.smooth_by_fir)
#
#     # Apply median and FIR filter (set!)
#     d = d_raw.apply(signal.medfilt, kernel_size=19)
#     d = d.apply(fir_filter, raw=True)
#
#     # Cropping ROI after FIR prevents FIR-related boundary artifacts to affect baseline correction
#     d = d[3.0:13.0]  # TODO: hplc method now 16min; change the ROI....
#     # a huge absorption (from solvent) : 14-19 mins (205nm and 215 nm)
#
#     # PLOT smoothed graph
#     d["Absorbance [mAu]"].plot(label="smoothed", linewidth=1.5, ax=ax)
#
#     # set y-axes of the current figure.
#     ax.set_ylim(min(d["Absorbance [mAu]"]) - 10, max(d["Absorbance [mAu]"]) + 20)
#
#     # Find peaks
#     global_max = max(d["Absorbance [mAu]"])
#
#     peaks, properties = signal.find_peaks(
#         d["Absorbance [mAu]"],
#         height=global_max / 80,
#         prominence=global_max / 45,  # defualt:/80.
#         # The prominence of a peak measures how much a peak stands out from the surrounding baseline
#         width=0.05,  # Required width of peaks in samples.
#         rel_height=0.5,  # Used for calculation of the peaks width
#     )
#     print(f"{len(peaks)} peaks was found. Retention time of peaks were ")
#
#     # baseline correction
#     # https://stackoverflow.com/questions/29156532/python-baseline-correction-library
#     # Create a mask as weight for baseline calculation. 1=no peak, use for baseline 0=peak, ignore for baseline calc.
#     weights = np.ones(len(d))
#     # Calculate derivative
#     d["dAbs"] = np.diff(d["Absorbance [mAu]"], prepend=0)
#     # Remove NaN for final value
#     d.fillna(0, inplace=True)
#
#     for base_left, base_right in zip(properties["left_ips"], properties["right_ips"]):
#         # Sets weights for baseline calculation to 0 in the peak range
#         weights[round(base_left): round(base_left)] = 0
#
#     d["baseline_0"], _ = pybaselines.polynomial.modpoly(
#         d["Absorbance [mAu]"], d.index, poly_order=3, weights=weights
#     )
#     d["corr_0"] = d["Absorbance [mAu]"] - d["baseline_0"]
#     d["corr_0"].plot(
#         ax=ax,
#         label="smoothed+baseline corrected_0",
#         alpha=0.5,
#         color="green",
#     )
#     d["dCorr"] = np.diff(d["corr_0"], prepend=0)
#
#     hplc_result_dic = {}
#
#     # Define peak boundaries and integrate based on corrected spectrum
#     # Also check https://github.com/HaasCP/mocca/blob/90a2143a889b28be96b0502ee107216e73870681/src/mocca/peak/expand.py#L14
#     for center, base_left, base_right in zip(
#             peaks, properties["left_ips"], properties["right_ips"]
#     ):
#         # Start from find_peaks positions (i.e. width at half max)
#         left_in_min = d.index[int(base_left)]
#         right_in_min = d.index[int(base_right)]
#
#         # Failsafe to ensure these are set
#         peak_start = d.index[0]
#         peak_end = d.index[-1]
#
#         # We rely on the chromatogram to be smoothed at this point!
#         # Iterate left side of peak from right to left (i.e. np.flip)
#         # for steps, derivative_value in enumerate(np.flip(d["dAbs"][:left_in_min])):
#         for steps, derivative_value in enumerate(np.flip(d["dCorr"][:left_in_min])):
#             if derivative_value < 1e-2:  # original 1e-3
#                 peak_start = d.index[
#                     int(base_left) - steps + 1
#                     ]  # +1 ensures non-overlapping peaks
#                 break
#
#         # Iterate right side from left to right
#         # for steps, derivative_value in enumerate(d["dAbs"][right_in_min:]):
#         for steps, derivative_value in enumerate(d["dCorr"][right_in_min:]):
#             if derivative_value > -1e-2:  # original -1e-3
#                 peak_end = d.index[int(base_right) + steps]
#                 break
#
#         # Integrate peak
#         peak = d["Absorbance [mAu]"][peak_start:peak_end]
#         area = trapezoid(y=peak, x=peak.index)
#
#         # print(f"peak{d.index[int(center)]}: {area}")
#         # save the analysis result to a dictionary
#         hplc_result_dic[d.index[int(center)]] = area
#
#         # Annotate 註解 peak area
#         ax.annotate(
#             f"{d.index[int(center)]:0.2f}/{area:0.2f}",
#             xy=(d.index[int(center)], d["Absorbance [mAu]"].values[int(center)]),
#             xytext=(-5, 0),
#             rotation=90,
#             textcoords="offset points",
#         )
#
#         # Sets weights for baseline calculation to 0 in the peak range
#         weights[d.index.get_loc(peak_start): d.index.get_loc(peak_end)] = 0
#
#         # Plot integration limits
#         ax.axvspan(peak_start, peak_end, facecolor="pink", edgecolor="black", alpha=0.5)
#
#     # Baseline correction
#     d["baseline"], _ = pybaselines.polynomial.modpoly(
#         d["Absorbance [mAu]"], d.index, poly_order=3, weights=weights
#     )
#     corr = d["Absorbance [mAu]"] - d["baseline"]
#     corr.plot(
#         ax=ax,
#         label="smoothed+baseline corrected",
#         alpha=0.5,
#         color="blue",
#     )
#
#     # Plot initial peak width
#     for num, (height, left, right) in enumerate(
#             zip(
#                 properties["width_heights"], properties["left_ips"], properties["right_ips"]
#             )
#     ):
#         plt.hlines(  # 用於在圖表中畫一條水平線
#             height,
#             d.index[int(left)],
#             d.index[int(right)],
#             color=f"C{num}",
#             linewidth=4,
#         )
#     ax.legend(["raw", "smoothed", "baseline_correction"])
#
#     # plt.show()
#     plt.savefig(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei\final.svg")
#
#     # TODO: activate
#     # plot_file_name = f"{datetime.date.today()}_{mongo_id}_{wavelength}.png"
#     # plot_folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms\plots_wei")
#     # plot_file_path = plot_folder_path / Path(plot_file_name)
#     # plt.savefig(plot_file_path)
#
#     # plt.close("all")
#
#     return hplc_result_dic


if __name__ == "__main__":
    # from BV_experiments.tools.plot_exp import plot_log
    x = 74
    while x < 75:

        mongo_id = f"control_test_{x:03}"
        # mongo_id = f"64df5af8cf533ab75bd0ac57"

        try:
            plot_log(f"{mongo_id}")
        except Exception as e:
            logger.warning(f"{e}: {mongo_id} log cannot plot")

        x+=1


