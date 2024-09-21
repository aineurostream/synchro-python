from abc import ABC

from synchro.graph.graph_node import GraphNode, EmittingNodeMixin


class AbstractInputNode(GraphNode, EmittingNodeMixin, ABC):
    pass
