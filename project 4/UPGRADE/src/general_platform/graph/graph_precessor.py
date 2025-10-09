
import networkx as nx
import json
import copy
from pydantic import BaseModel

from BV_experiments.src.general_platform.Librarian import TubeInfo, SyringeInfo


def graph_to_dict(graph) -> dict:
    """
    Converts a NetworkX graph to a dictionary format,
    including all node and edge attributes w/o basemodel info.
    """

    def convert_model_fields(data):
        return {
            k: v.dict() if isinstance(v, BaseModel) else v
            for k, v in data.items()
        }
    def serialize_value(value):
        # Check for Pydantic models
        if hasattr(value, 'dict'):
            return value.dict()
        # Add other custom serialization rules here if needed
        return value

    # Convert Pydantic model to dict before serialization
    G_serializable = copy.deepcopy(graph)

    # Convert node attributes
    for node, data in G_serializable.nodes(data=True):
        for key, value in data.items():
            data[key] = serialize_value(value)

        # new_data = convert_model_fields(data)
        # G_serializable.nodes[node].update(new_data)

    # Convert edge attributes
    for u, v, data in G_serializable.edges(data=True):
        for key, value in data.items():
            data[key] = serialize_value(value)

    # Prepare final dict
    full_serialized = {
        "nodes": dict(G_serializable.nodes(data=True)),
        "edges": nx.to_dict_of_dicts(G_serializable)
    }
    return full_serialized


def graph_to_dict_basemodel(graph) -> dict:
    """
    Converts a NetworkX graph to a dictionary format,
     including all node and edge attributes type information for Pydantic models.
    This is useful for serialization and deserialization of graphs with complex node and edge attributes.
    Args:
        graph (networkx.Graph): The input graph to be converted.
    """

    def serialize_attrs(data):
        result = {}
        for k, v in data.items():
            if isinstance(v, BaseModel):
                result[k] = v.dict()
                result[k + "_type"] = v.__class__.__name__
            else:
                result[k] = v
        return result

    # Copy graph structure
    G_serializable = graph.copy()

    # Serialize node attributes (keep everything!)
    for n, attrs in G_serializable.nodes(data=True):
        G_serializable.nodes[n].update(serialize_attrs(attrs))

    # Serialize edge attributes (keep everything!)
    for u, v, attrs in G_serializable.edges(data=True):
        G_serializable.edges[u, v].update(serialize_attrs(attrs))

    # Return JSON-safe dict
    graph_dict = {
        "nodes": dict(G_serializable.nodes(data=True)),
        "edges": nx.to_dict_of_dicts(G_serializable),
    }
    return graph_dict

def serialize_graph(graph):
    """
    Serializes a NetworkX graph to a JSON-compatible format.
    """
    # data = nx.readwrite.json_graph.node_link_data(graph)
    # return json.dumps(data)
    # Convert graph to dict w/ Pydantic model info
    graph_dict = graph_to_dict_basemodel(graph)

    return json.dumps(graph_dict, indent=2)


def deserialize_graph(json_data):
    """
    Deserializes a JSON-compatible format back to a NetworkX graph.
    """
    # data = json.loads(data)
    # return nx.readwrite.json_graph.node_link_graph(data)
    data = json.loads(json_data)
    # fixme: check if the data is including the type information

    # Create a new graph
    G = nx.from_dict_of_dicts(data["edges"])

    model_classes = {
        "SyringeInfo": SyringeInfo,
        "TubeInfo": TubeInfo,
    }

    for node, attrs in data["nodes"].items():
        new_attrs = {}
        for k, v in attrs.items():
            if k.endswith("_type"):
                continue  # skip type tag
            type_key = k + "_type"
            if type_key in attrs:
                model_name = attrs[type_key]
                model_cls = model_classes.get(model_name)
                if model_cls:
                    new_attrs[k] = model_cls(**v)
                else:
                    new_attrs[k] = v  # unknown type
            else:
                new_attrs[k] = v
        nx.set_node_attributes(G, {node: new_attrs})

    return G


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import FlowSetupDad


    graph_dict = graph_to_dict(FlowSetupDad.G)
    print("Graph dict:", graph_dict)
    serial_2 = json.dumps(graph_dict, indent=2)
    deserialized_graph = deserialize_graph(serial_2)
    print("Deserialized graph:", deserialized_graph.nodes(data=True))
    print("Deserialized graph edges:", deserialized_graph.edges(data=True))
    print("Deserialized graph:", deserialized_graph)

    # serialize and deserialize the graph with Pydantic model info
    serialized = serialize_graph(FlowSetupDad.G)
    print("Serialized graph:", serialized)

    deserialized_graph = deserialize_graph(serialized)
    print("Deserialized graph:", deserialized_graph.nodes(data=True))
    print("Deserialized graph edges:", deserialized_graph.edges(data=True))
    print("Deserialized graph:", deserialized_graph)


