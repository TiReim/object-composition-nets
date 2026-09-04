from typing import Counter, Dict, Generic, Tuple, TypeVar

import polars as pl

from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class ActivityMapper(Generic[T]):
    @classmethod
    def create_mapped_event_log(cls, event_log: T) -> Tuple[T, pl.DataFrame]:
        mapping_dict: Dict[str, str] = {}
        i = 0
        mapped_event_log: T = Counter()  # type: ignore
        for sequence, cnt in event_log.items():
            mapped_sequence = []
            for event in sequence:
                if event not in mapping_dict:
                    mapping_dict[event] = str(i)
                    i += 1
                mapped_sequence.append(mapping_dict[event])
            mapped_event_log.update({tuple(mapped_sequence): cnt})
        mapping_df = pl.DataFrame(
            {"activity_name": list(mapping_dict.keys()), "id": list(mapping_dict.values())},
            schema={"activity_name": str, "id": str},
        )
        return mapped_event_log, mapping_df

    @classmethod
    def map_process_tree_back(cls, tree: ProcessTree, mapping_df: pl.DataFrame) -> ProcessTree:
        if tree.label is not None:
            if tree.label is not SILENT_TRANSITION_LABEL:
                return ProcessTree(label=mapping_df.filter(pl.col("id") == tree.label).select("activity_name").item())
            return ProcessTree(label=SILENT_TRANSITION_LABEL)
        original_tree: ProcessTree = ProcessTree(operator=tree.operator)
        for child in tree.children:
            original_tree.children.append(cls.map_process_tree_back(child, mapping_df))
        return original_tree
