from abc import ABC

from synchro.graph.graph_node import GraphNode, ReceivingNodeMixin


class AbstractOutputNode(GraphNode, ReceivingNodeMixin, ABC):
    pass
