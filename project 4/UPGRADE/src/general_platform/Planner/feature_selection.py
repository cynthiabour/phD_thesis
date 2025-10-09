"""
This script is used to visualize the data and select the features for the machine learning model.
The script uses PCA, PCA_Whitening, ZCA_Whitening, and DAFE for dimension reduction.
The script also uses Lasso_features_rank, feature_importances_in_RF, and feature_selection_RFE for feature selection.
"""
import numpy
import numpy as np
from pathlib import Path

class DimensionReduction(object):
    def __init__(self): pass

    def PCA(self, data):
        Sigma = DimensionReduction.__get_CovarianceMatrix(data)
        RotMatrix, coe_PC, U = np.linalg.svd(Sigma)
        xRot = np.dot(RotMatrix, np.transpose(data))
        xRot = np.transpose(xRot)
        return coe_PC, xRot

    def PCA_Whitening(self, data):
        Sigma = DimensionReduction.__get_CovarianceMatrix(data)
        RotMatrix, coe_PC, U = np.linalg.svd(Sigma)

        epsilon = 10 ** (-5);
        tmp = np.diag(1 / np.sqrt(coe_PC + epsilon))
        xPCAwhite = np.dot(tmp, np.dot(RotMatrix, np.transpose(data)))
        xPCAwhite = np.transpose(xPCAwhite)
        return coe_PC, xPCAwhite

    def ZCA_Whitening(self, data):
        Sigma = DimensionReduction.__get_CovarianceMatrix(data)
        RotMatrix, coe_PC, U = np.linalg.svd(Sigma)

        epsilon = 10 ** (-5);
        tmp = np.diag(1 / np.sqrt(coe_PC + epsilon))
        xZCAwhite = np.dot(RotMatrix, np.dot(tmp, np.dot(RotMatrix, np.transpose(data))))
        xZCAwhite = np.transpose(xZCAwhite)
        return coe_PC, xZCAwhite

    def DAFE(self, data, label):
        dim = np.size(data, 1)
        TL = (np.unique(label))
        nc = len(TL)
        Sigma_data = np.zeros([dim * nc, dim])
        Mu_data = np.zeros([nc, dim])
        Sw = np.zeros([dim, dim])
        c = 0;
        for i in TL:
            c += 1;
            pos = np.where(label == i)
            pos = pos[0]
            tmp = data[pos, :]
            cindex = range((c - 1) * dim, c * dim)
            Sigma_data[cindex, :] = np.cov(np.transpose(tmp))
            Sw += Sigma_data[cindex, :];
            Mu_data[c - 1, :] = np.average(tmp, axis=0)

        Sw = Sw / nc;
        Sw = 0.5 * Sw + 0.5 * np.diag(np.diag(Sw));  # regualrization for within-class scatter matrix
        Sb = np.cov(np.transpose(Mu_data)) * (nc - 1) / nc;  # between-calss scatter matrix

        C = np.dot(np.linalg.pinv(Sw), Sb)

        DAFE_vect, DAFE_val, U = np.linalg.svd(C)
        xRot = np.dot(DAFE_vect, np.transpose(data))
        xRot = np.transpose(xRot)
        return DAFE_vect, xRot

    def __get_ZeroMean(data):
        N = np.size(data, 0)
        avg = np.average(data)
        data = data - matlib.repmat(avg, N, 1);
        return data

    def __get_CovarianceMatrix(data):
        N = np.size(data, 0)
        x = DimensionReduction.__get_ZeroMean(data)
        Sigma = np.dot(np.transpose(x), x) / N
        return Sigma


def create_3d_figure(f_data, t_data, feature_name, target_names, aX=0, aY=2, aZ=1):
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
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.6, aspect=10, label=target_names)

    # save figure

    # plt.savefig(r'C:\Users\User\Downloads\3D_plot.pdf', dpi=300)  # Change the file format as needed

    # Show the plot
    plt.show()

def Lasso_features_rank(X_train: numpy.ndarray , y_train: numpy.ndarray, feature_name: list, alpha:float=0.1):
    print(f"LASSO (alpha={alpha}: model.coef_")
    from sklearn.linear_model import Lasso
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split

    # Assuming X_train and y_train are your feature and target variables
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = Lasso(alpha=alpha)
    model.fit(X_train_scaled, y_train)

    # Make predictions on the testing data
    y_pred = model.predict(X_train)

    # Evaluate the model using different metrics
    mse = mean_squared_error(y_train, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_train, y_pred)
    r2 = r2_score(y_train, y_pred)

    # Display the evaluation metrics
    print("Mean Squared Error (MSE):", mse)
    print("Root Mean Squared Error (RMSE):", rmse)
    print("Mean Absolute Error (MAE):", mae)
    print("R-squared (R^2):", r2)

    # Get feature coefficients
    feature_coefficients = model.coef_

    # Print or visualize feature coefficients
    for feature, coefficient in zip(feature_name, feature_coefficients):
        print(f"{feature}: {coefficient}")

def feature_importances_in_RF(X_train: numpy.ndarray, y_train: numpy.ndarray, feature_name):
    print("Decision Trees and Random Forests: feature_importances_")
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

    # Assuming X_train and y_train are your feature and target variables
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Make predictions on the testing data
    y_pred = model.predict(X_train)

    print("score_val_score: ", model.score(X_train, y_train))
    # Calculate Mean Squared Error (MSE) to evaluate the model
    mse = mean_squared_error(y_train, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_train, y_pred)
    r2 = r2_score(y_train, y_pred)

    print("Mean Squared Error (MSE):", mse)
    print("Root Mean Squared Error (RMSE):", rmse)
    print("Mean Absolute Error (MAE):", mae)
    print("R-squared (R^2):", r2)

    # Get feature importances
    feature_importances = model.feature_importances_

    # Print or visualize feature importances
    for feature, importance in zip(feature_name, feature_importances):
        print(f"{feature}: {importance}")

def feature_selection_RFE(X_train, y_train, feature_name, n_features=5):
    print(f"feature selection for {n_features}: Recursive Feature Elimination (RFE)")
    from sklearn.feature_selection import RFE
    from sklearn.linear_model import Lasso
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Lasso
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.neighbors import KNeighborsRegressor


    # Assuming X_train and y_train are your feature and target variables
    # model = GradientBoostingRegressor(n_estimators=100, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    rfe = RFE(model, n_features_to_select=n_features)
    rfe.fit(X_train, y_train)

    # Get ranking of features
    feature_ranking = rfe.ranking_

    # Print or visualize feature ranking
    for feature, ranking in zip(feature_name, feature_ranking):
        print(f"{feature}: {ranking}")


if __name__ == "__main__":
    # file_path = Path(r'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\data_output\20230426_old_data.csv')
    file_path = Path(r'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\data_output\20240311_crruent_succeed_data.csv')
    # file_path = Path(r'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\data_output\20240312_whole_data_correct.csv')

    feature_name = ["dye_equiv", "activator_equiv", "quencher_equiv", "solvent_equiv", "oxygen_equiv", "time", "light",
                    "pressure", "temperature"]
    f_data = np.genfromtxt(file_path,
                           delimiter=',',
                           skip_header=1,
                           usecols=(0, 1, 2, 3, 4, 5, 6, 7, 8),
                           )
    # target_name = np.array(["Yield_1",	"Conversion_1"	"Productivity_1",	"Yield_2",	"Conversion_2",	"Productivity_2"])
    target_names = "Productivity_2"
    t_data = np.genfromtxt(file_path, delimiter=',', skip_header=1, usecols=(14,))
    # t_data = np.genfromtxt(file_path, delimiter=',', skip_header=1, usecols=(9,))
    create_3d_figure(f_data, t_data, feature_name, target_names, aX=0, aY=2, aZ=5)

    # todo: the cross-validation might help
    X_train = f_data
    y_train = t_data

    feature_selection_RFE(X_train, y_train, feature_name, n_features=2)
    feature_selection_RFE(X_train, y_train, feature_name, n_features=4)
    feature_selection_RFE(X_train, y_train, feature_name, n_features=6)
    feature_selection_RFE(X_train, y_train, feature_name, n_features=8)
    Lasso_features_rank(X_train, y_train, feature_name, alpha=0.1)
    Lasso_features_rank(X_train, y_train, feature_name, alpha=0.01)
    Lasso_features_rank(X_train, y_train, feature_name, alpha=0.005)
    feature_importances_in_RF(X_train, y_train, feature_name)