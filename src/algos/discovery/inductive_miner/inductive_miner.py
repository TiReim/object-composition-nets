from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from src.algos.discovery.inductive_miner.activity_mapper import ActivityMapper
from src.algos.discovery.inductive_miner.cuts.abstract import Cut
from src.algos.discovery.inductive_miner.cuts.concurrent import ConcurrentCut
from src.algos.discovery.inductive_miner.cuts.loop import LoopCut
from src.algos.discovery.inductive_miner.cuts.sequence import SequenceCut
from src.algos.discovery.inductive_miner.cuts.xor import XorCut
from src.algos.discovery.inductive_miner.fall_throughs.abstract import FallThrough
from src.algos.discovery.inductive_miner.fall_throughs.activity_concurrent import ActivityConcurrent
from src.algos.discovery.inductive_miner.fall_throughs.activity_once_per_trace import (
    ActivityOncePerTrace,
)
from src.algos.discovery.inductive_miner.fall_throughs.flower_model import FlowerModel
from src.algos.discovery.inductive_miner.fall_throughs.strict_tau_loop import StrictTauLoop
from src.algos.discovery.inductive_miner.fall_throughs.tau_loop import TauLoop
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.graphs.directly_follows_graph.directly_follows_graph_factory import (
    DirectlyFollowsGraphFactory,
)
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class InductiveMiner(Generic[T]):
    @classmethod
    def _base_case(cls, event_log: T) -> Optional[ProcessTree]:
        variants = list(event_log.keys())
        # Base case 1
        if len(variants) == 1 and len(variants[0]) == 1:
            return ProcessTree(label=variants[0][0])
        # Base case 2
        if not variants or (len(variants) == 1 and len(variants[0]) == 0):
            return ProcessTree(label=SILENT_TRANSITION_LABEL)
        return None

    @classmethod
    def _find_cut(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        cuts: Tuple[Cut] = (XorCut(), SequenceCut(), ConcurrentCut(), LoopCut())  # type: ignore
        for cut in cuts:
            result = cut.apply(event_log, dfg)
            if result is not None:
                return result
        return None

    @classmethod
    def _fall_through(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        fall_throughs: Tuple[FallThrough] = (
            ActivityOncePerTrace(),
            ActivityConcurrent(),
            StrictTauLoop(),
            TauLoop(),
            FlowerModel(),
        )  # type: ignore
        for fall_through in fall_throughs:
            result = fall_through.apply(event_log, dfg)
            if result is not None:
                return result
        return None

    @classmethod
    def apply_without_mapping(cls, event_log: T) -> ProcessTree:
        tree: ProcessTree = cls._base_case(event_log)
        if tree is None:
            dfg = DirectlyFollowsGraphFactory.create_from_event_log(event_log)
            result = cls._find_cut(event_log, dfg)
            if result is None:
                result = cls._fall_through(event_log, dfg)
            tree, projections = result
            for projection in projections:
                tree.children.append(cls.apply_without_mapping(projection))
        return tree

    @classmethod
    def apply(cls, event_log: T) -> ProcessTree:
        if (
            not isinstance(event_log, Counter)
            or not all((isinstance(sequence, tuple) for sequence in event_log.keys()))
            or not all((isinstance(activity, str) for sequence in event_log.keys() for activity in sequence))
        ):
            raise TypeError(
                str(type(event_log))
                + " is an incorrect argument type. Function only supports a Counter[tuple[str, ...]] as argument"
            )
        mapped_log, mapping = ActivityMapper.create_mapped_event_log(event_log)  # type: ignore
        tree = cls.apply_without_mapping(mapped_log)  # type: ignore
        return ActivityMapper.map_process_tree_back(tree, mapping)
