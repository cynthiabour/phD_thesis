"""

for now, to export the dad 3d data, the automatic is not possible
PyAutoGUI, to control the mouse and keyboard

https://pyautogui.readthedocs.io/en/latest/
"""
from pathlib import Path


def convert_asc_to_txt(input_file, output_file):
    with open(input_file, 'r') as f_input:
        content = f_input.read()

    # Optionally, you can perform any necessary data processing on 'content' here
    # For example, you might want to manipulate the data before saving it as a .txt file

    with open(output_file, 'w') as f_output:
        f_output.write(content)

def plot_3D():
    folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms")
    input_file = "control_test_026-3D.asc"
    input_file_path = folder_path / Path("control_test_026-3D.asc")
    output_file = "control_test_026-3D.txt"
    output_file_path = folder_path / Path("control_test_026-3D.txt")

    # convert_asc_to_txt(input_file_path, output_file_path)

    # header_data, header_lines = parse_header(input_file_path)
    import pandas as pd
    d_raw = pd.read_csv(
        input_file_path,
        delimiter="\t",
        skiprows=15,
        header=0,
        encoding="cp852",
    ).to_numpy()
    # print(d_raw)

    import matplotlib.pyplot as plt
    import numpy as np

    # # Create 3D coordinates for each point in the 2D array
    x, y = np.meshgrid(range(d_raw.shape[1]), range(d_raw.shape[0]))
    z = d_raw

    # # Sample 2D array (replace this with your own 2D data)
    # data_2d = np.random.rand(5, 6)
    #
    # # Create 3D coordinates for each point in the 2D array
    # x, y = np.meshgrid(range(data_2d.shape[1]), range(data_2d.shape[0]))
    # z = data_2d

    # Create a 3D figure
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot the 3D surface
    ax.plot_surface(x, y, z, cmap='viridis')

    # Set labels for the axes
    ax.set_xlabel('wavelength')
    ax.set_ylabel('time')
    ax.set_zlabel('absorption')

    # Set the title of the plot
    plt.title('3D Plot of a 2D Array')

    # Show the plot
    plt.show()


def decovolution():

    folder_path = Path(r"W:\BS-FlowChemistry\data\exported_chromatograms")
    input_file = "control_test_028 - DAD 2.1L- Channel 2.txt"
    input_file_path = folder_path / Path(input_file)

    # user interaction
    from mocca.user_interaction.campaign import HplcDadCampaign

    camp = HplcDadCampaign()

if __name__ == "__main__":
    decovolution()


