from collections import Counter, defaultdict
from functools import cached_property
from typing import Collection, Dict, Iterable, Tuple

import polars as pl

from src.objects.event_log.object_centric.obj import ObjectCentricEventLog
from src.objects.graphs.abstract_follows_graph.abstract_follows_graph import AbstractFollowsGraph
from src.objects.graphs.abstract_follows_graph.typing import DirectlyFollowsGraphEdgePayload


class MultiObjectDirectlyFollowsGraph(AbstractFollowsGraph):
    def __init__(
        self,
        nbunch_edges: Iterable[Tuple[str, str, Dict[str, DirectlyFollowsGraphEdgePayload]]],
        start_activities: Dict[str, Counter[str]],
        end_activities: Dict[str, Counter[str]],
    ):
        """
        :param nbunch_edges: An iterable of edges in the form of (Activity1, Activity2, Data Dict), where the
        activities are strings and data dict is a dict mapping object type names to direct follows edge payload
        dicts. :param start_activities: A dict mapping object types to sets of activities  representing the start
        activities :param end_activities: A dict mapping object types to sets of activities representing the end
        activities
        """
        super().__init__(nbunch_edges=nbunch_edges)
        self._start_activities = start_activities
        self._end_activities = end_activities

    @property
    def start_activities(self) -> Dict[str, Counter[str]]:
        return self._start_activities

    @property
    def end_activities(self) -> Dict[str, Counter[str]]:
        return self._end_activities

    @cached_property
    def object_types(self):
        otypes = set()

        for *_, data in self.edges(data=True):
            otypes.update(data.keys())

        return otypes

    @classmethod
    def construct_from_object_centric_event_log(cls, oce_log: ObjectCentricEventLog, otypes: Collection[str]):

        otable = oce_log.event_to_object_table.lazy().filter(pl.col(oce_log.object_type_column()).is_in(otypes))
        etable = oce_log.event_table.lazy()

        def _get_directly_follows_pairs(
            query: pl.LazyFrame,
        ) -> Iterable[Tuple[str, str, Dict[str, DirectlyFollowsGraphEdgePayload]]]:

            query_df_pairs = (
                query.with_columns(pl.col("Trace").arr.shift(-1).alias("Trace Shift"))
                .explode(columns=["Trace", "Trace Shift"])
                .drop_nulls()
                .with_columns(pl.struct(["Trace", "Trace Shift"]).alias("DF pairs"))
                .select(["DF pairs", oce_log.object_type_column()])
                .groupby(by=oce_log.object_type_column())
                .agg(pl.col("DF pairs").value_counts())
            ).collect()

            edges: defaultdict[Tuple[str, str], Dict] = defaultdict(dict)

            for otype, df_edge in query_df_pairs.iter_rows():
                for entry in df_edge:
                    uid, vid, count = entry["DF pairs"]["Trace"], entry["DF pairs"]["Trace Shift"], entry["counts"]
                    edges[(uid, vid)][otype] = DirectlyFollowsGraphEdgePayload(count=count)

            return ((uid, vid, data) for (uid, vid), data in edges.items())

        def _get_start_and_end_activities(
            query: pl.LazyFrame,
        ) -> Tuple[Dict[str, Counter[str]], Dict[str, Counter[str]]]:

            query_start_end = (
                query.with_columns(
                    [pl.col("Trace").arr.first().alias("starts"), pl.col("Trace").arr.last().alias("ends")]
                )
                .groupby(by=oce_log.object_type_column())
                .agg([pl.col("starts").value_counts(), pl.col("ends").value_counts()])
            ).collect()

            start_act = {}
            end_act = {}

            for otype, start_counts, end_counts in query_start_end.iter_rows():
                start_counts = {entry["starts"]: entry["counts"] for entry in start_counts}
                end_counts = {entry["ends"]: entry["counts"] for entry in end_counts}

                start_act[otype] = Counter(**start_counts)
                end_act[otype] = Counter(**end_counts)

            return start_act, end_act

        query = (
            etable.join(other=otable, on=oce_log.event_id_column())
            .groupby(by=[oce_log.object_type_column(), oce_log.object_id_column()])
            .agg([pl.col(oce_log.event_name_column()).sort_by(oce_log.event_time_column()).alias("Trace")])
            .select([oce_log.object_type_column(), "Trace"])
        )

        edge_list = _get_directly_follows_pairs(query)
        start_activities, end_activities = _get_start_and_end_activities(query)

        return MultiObjectDirectlyFollowsGraph(edge_list, start_activities, end_activities)
