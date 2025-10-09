import pint
import networkx as nx
from .platform_error import *

__all__ = [
    "DatabaseError",
    "PlatformError",
    "UnderDefinedError",
    "OverwriteError",
    "NoExperimentFound",
    "InputNotValid",
    "IncompleteAnalysis",
]

ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)

# 1 Millimole/milliliter( mmol/mL ) = 1 Molar( M )
ureg.define("molar = mole/liter")


def convert_graph_to_dict(G: nx.Graph) -> dict:
    """Convert a networkx graph to a dictionary."""
    # Convert to adjacency list (dictionary of dictionaries)
    return nx.to_dict_of_dicts(G)


def convert_dict_to_graph(adj_dict: dict, directed: bool = True) -> nx.Graph:
    """Convert a dictionary to a networkx graph."""
    # Convert the dictionary of dictionaries to a networkx graph
    if directed:
        return nx.from_dict_of_dicts(adj_dict, create_using=nx.DiGraph())
    else:
        return nx.from_dict_of_dicts(adj_dict, create_using=nx.Graph())


def volume_of_tube(length: float, id: float) -> float:
    import math
    return (id / 2) ** 2 * length * math.pi


def vol_of_tube(length: ureg.Quantity, id: ureg.Quantity) -> ureg.Quantity:
    import math
    return (id / 2) ** 2 * length * math.pi
