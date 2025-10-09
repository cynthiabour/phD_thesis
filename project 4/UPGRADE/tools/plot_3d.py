"""
the function create_3d_figure is used to create a 3D scatter plot with color mapping.
form feature_selection import create_3d_figure
"""
from pathlib import Path

import numpy as np


def create_3d_figure(f_data, t_data, feature_name, target_name, aX=0, aY=2, aZ=1):
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    from matplotlib.animation import FuncAnimation

    # Generate sample data
    x = f_data[:, aX]
    y = f_data[:, aY]
    z = f_data[:, aZ]
    additional_info = t_data  # Continuous information for color

    # Create a 3D scatter plot with color mapping
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    scatter = ax.scatter(x, y, z, c=additional_info, cmap='viridis')

    # Set labels
    ax.set_xlabel(feature_name[aX])
    # ax.set_xlim(0, 0.2)
    ax.set_ylabel(feature_name[aY])
    ax.set_zlabel(feature_name[aZ])

    # Add a colorbar to show the correspondence between colors and additional_info values
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.6, aspect=10, label=target_name)

    # save figure

    # plt.savefig(r'C:\Users\User\Downloads\3D_plot.pdf', dpi=300)  # Change the file format as needed

    # Show the plot
    plt.show()


if __name__ == "__main__":

    # todo: change to more general code
    # file_path = Path(r'W:\BS-Automated\wei-hsin\Juliana\3d_figure\UCOJuliana_r.csv')
    file_path = Path(r'W:\BS-Automated\wei-hsin\Juliana\3d_figure\20241213_Productivity_wei.csv')

    feature_name = ["Temperature, °C", "Flow ratio H2O2/oil", "Flow ratio acids/oil", "Residence time, min",
                    "Ratio Faq/Foil"]
    f_data = np.genfromtxt(file_path,
                           delimiter=',',
                           skip_header=1,
                           usecols=(0, 1, 2, 3, 4),
                           )
    # target_names = np.array(["Yield_1",	"Conversion_1"	"Productivity_1",	"Yield_2",	"Conversion_2",	"Productivity_2"])
    # target_name = "Conversion"
    target_name = "Productivity, kg OO/m3*min"
    t_data = np.genfromtxt(file_path, delimiter=',', skip_header=1, usecols=(5,))
    create_3d_figure(f_data, t_data, feature_name, target_name, aX=4, aY=0, aZ=3)
