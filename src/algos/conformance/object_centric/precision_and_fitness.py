"""Object-centric precision and fitness.

Implementation of the fitness and precision notions for object-centric Petri nets defined in

    J. N. Adams and W. M. P. van der Aalst, "Precision and Fitness in Object-Centric Process
    Mining", ICPM 2021, pp. 128-135.

The measures relate an object-centric event log to an accepting object-centric Petri net by
comparing, for the *context* of every event, the activities enabled by the log with the
activities enabled by the model.

The log is provided as an :class:`ObjectCentricEventGraph` (which already is the event-object
graph of Definition 8) and the model as an :class:`ObjectCentricWorkflowNet` (whose per-type
source/sink places are used to build the initial marking of a replay).

The replay is deliberately parameterized by the semantics class. Passing
:class:`GuardedObjectCentricSemantics` replays plain object-centric Petri nets, while passing
:class:`ObjectCompositionSemantics` replays compositional object-centric nets (OCoNs) whose visible
transitions compose/decompose objects into higher-order objects. In both cases the *original*
(non-abstracted) log is used: for OCoNs the base objects of the log are seeded at their base-type
source places and the model composes them on the fly while replaying.
"""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Optional, Type, cast

from src.objects.data_types.higher_order_object_types import HigherOrderObject, HigherOrderObjectType
from src.objects.data_types.object_reference import ObjectID, ObjectReference, ObjectType
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph
from src.objects.petri_net.object_composition_nets.object_composition_tokens import ObjectCompositionIdentityToken
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.object_composition_nets.semantics import ObjectCompositionSemantics
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.oc_nets.oc_workflow_net import ObjectCentricWorkflowNet
from src.objects.petri_net.oc_nets.semantics import GuardedObjectCentricSemantics, ObjectCentricSemantics
from src.objects.petri_net.oc_nets.utils import (
    ObjectCentricPetriNetPropertyCache,
    ObjectCentricPetriNetUtils,
)
from src.objects.petri_net.token import IdentityToken
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import MarkingUtils, PetriNetUtils
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL

# pylint: disable=too-many-locals, too-many-instance-attributes, invalid-name

ActivitySequence = tuple[str, ...]
ObjectsByType = dict[ObjectType, list[ObjectID]]
Binding = tuple[str, ObjectsByType]
IdentityMarking = Marking[IdentityToken[ObjectAwarePlace]]

# A hashable representation of the context of an event (Definition 8): a multiset of activity
# prefixes per object type.
ContextKey = frozenset[tuple[ObjectType, frozenset[tuple[ActivitySequence, int]]]]

# A hashable representation of a replay task (an initial multiset of objects per type plus the
# binding sequence to replay). Two events with the same replay signature yield the same enabled
# model activities, which lets us avoid replaying isomorphic contexts more than once.
ReplaySignature = tuple[tuple[tuple[ObjectType, int], ...], tuple[tuple[str, tuple[tuple[ObjectType, int], ...]], ...]]


@dataclass(frozen=True)
class PrecisionFitnessResult:
    """Result of an object-centric precision/fitness computation."""

    fitness: float
    precision: float
    skipped_events: float
    """Fraction of events without a shared enabled activity (excluded from precision)."""
    num_events: int
    num_replayable_events: int


class ObjectCentricPrecisionFitness:
    """Computes the object-centric fitness and precision of a model with respect to a log."""

    @classmethod
    def apply(
        cls,
        log: ObjectCentricEventGraph,
        model: ObjectCentricWorkflowNet,
        semantics: Type[ObjectCentricSemantics] = GuardedObjectCentricSemantics,
        max_states_per_context: int = 100_000,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PrecisionFitnessResult:
        """Computes fitness and precision of ``model`` with respect to ``log``.

        :param log: the object-centric event log as an event-object graph.
        :param model: the accepting object-centric workflow net (source/sink places per object type).
        :param semantics: the semantics used to replay bindings on the model.
        :param max_states_per_context: safety bound on the number of states explored while replaying
            a single context (guards against silent-transition loops in unbounded nets).
        :param progress_callback: optional callback invoked as ``(processed_events, total_events)``
            after each event; useful for monitoring long-running computations.
        """
        compositional = issubclass(semantics, ObjectCompositionSemantics)
        events = sorted(log.event_nodes, key=lambda node: (node.timestamp, node.event_id))
        if not events:
            return PrecisionFitnessResult(1.0, 1.0, 0.0, 0, 0)

        ordered_event_ids = [event.event_id for event in events]
        # Rank of each event in the log's total order (timestamp, then event id). Preset events must be
        # ordered by this rank (not by raw event-id string) when building prefixes and binding sequences.
        order = {event_id: rank for rank, event_id in enumerate(ordered_event_ids)}
        event_objects = cls._collect_event_objects(log, ordered_event_ids)
        activities = {event.event_id: event.activity for event in events}
        presets = cls._compute_event_presets(ordered_event_ids, event_objects)

        net = ObjectCentricPetriNetPropertyCache(net=model.net, nested=True)
        subnets = ObjectCentricPetriNetUtils.get_subnets(net)
        silent_transitions = {
            transition
            for transition in net.transitions
            if transition.label is None or transition.label == SILENT_TRANSITION_LABEL
        }

        enabled_log: dict[ContextKey, set] = defaultdict(set)
        enabled_model: dict[ContextKey, set] = defaultdict(set)
        event_context: dict[str, ContextKey] = {}
        replay_cache: dict[ReplaySignature, set] = {}

        total = len(events)
        for processed, event in enumerate(events, start=1):
            event_id = event.event_id
            binding_sequence, scope, canonical = cls._build_binding_sequence(
                event_id, presets[event_id], event_objects, activities, order
            )
            context_key = cls._context_key(presets[event_id], event_id, event_objects, activities, order)
            event_context[event_id] = context_key
            enabled_log[context_key].add(cls._log_token(event_id, activities, event_objects, canonical))

            signature = cls._replay_signature(scope, binding_sequence)
            if signature not in replay_cache:
                replay_cache[signature] = cls._enabled_model_activities(
                    net,
                    model,
                    semantics,
                    subnets,
                    silent_transitions,
                    scope,
                    binding_sequence,
                    max_states_per_context,
                    compositional,
                )
            enabled_model[context_key] |= replay_cache[signature]
            if progress_callback is not None:
                progress_callback(processed, total)

        return cls._aggregate(events, event_context, enabled_log, enabled_model)

    @classmethod
    def _log_token(
        cls,
        event_id: str,
        activities: dict[str, str],
        event_objects: dict[str, list[tuple[ObjectType, ObjectID]]],
        canonical: dict[ObjectID, ObjectID],
    ):
        """The comparable token an event contributes to its context on the log side.

        The base measure (Adams & van der Aalst) compares enabled *activities*, so an event
        contributes its activity label. Subclasses can override this to compare at a finer
        granularity (e.g. bindings) as long as the model side (:meth:`_enabled_visible_activities`)
        produces tokens in the same space.
        """
        return activities[event_id]

    @staticmethod
    def _aggregate(
        events,
        event_context: dict[str, ContextKey],
        enabled_log: dict[ContextKey, set[str]],
        enabled_model: dict[ContextKey, set[str]],
    ) -> PrecisionFitnessResult:
        fitness_sum = 0.0
        precision_sum = 0.0
        replayable = 0
        for event in events:
            context_key = event_context[event.event_id]
            log_activities = enabled_log[context_key]
            model_activities = enabled_model[context_key]
            shared = len(log_activities & model_activities)
            fitness_sum += shared / len(log_activities)
            # Adams and van der Aalst exclude contexts from precision when replay either yields no
            # enabled model activity or no enabled model activity matches the log.
            if model_activities and shared:
                precision_sum += shared / len(model_activities)
                replayable += 1

        num_events = len(events)
        fitness = fitness_sum / num_events
        precision = precision_sum / replayable if replayable else 0.0
        skipped = (num_events - replayable) / num_events
        return PrecisionFitnessResult(fitness, precision, skipped, num_events, replayable)

    @staticmethod
    def _collect_event_objects(
        log: ObjectCentricEventGraph, event_ids: list[str]
    ) -> dict[str, list[tuple[ObjectType, ObjectID]]]:
        event_objects: dict[str, list[tuple[ObjectType, ObjectID]]] = {}
        for event_id in event_ids:
            objects: list[tuple[ObjectType, ObjectID]] = []
            for object_id in log.get_neighbors(event_id):
                object_node = log.get_object_node(object_id)
                if object_node is not None:
                    objects.append((object_node.object_type, object_id))
            event_objects[event_id] = objects
        return event_objects

    @staticmethod
    def _compute_event_presets(
        ordered_event_ids: list[str], event_objects: dict[str, list[tuple[ObjectType, ObjectID]]]
    ) -> dict[str, set[str]]:
        """Computes the event preset (transitive ancestors in the event-object graph) of each event.

        Processing events in temporal order, the direct predecessors of an event are, per shared
        object, the most recent earlier event on that object. All earlier events on the same object
        form a chain and are therefore contained in that predecessor's ancestor set, so taking the
        latest earlier event per object plus its ancestors yields the full preset.
        """
        presets: dict[str, set[str]] = {}
        last_event_per_object: dict[ObjectID, str] = {}
        for event_id in ordered_event_ids:
            predecessors = {
                last_event_per_object[object_id]
                for _, object_id in event_objects[event_id]
                if object_id in last_event_per_object
            }
            preset = set(predecessors)
            for predecessor in predecessors:
                preset |= presets[predecessor]
            presets[event_id] = preset
            for _, object_id in event_objects[event_id]:
                last_event_per_object[object_id] = event_id
        return presets

    @classmethod
    def _build_binding_sequence(
        cls,
        event_id: str,
        preset: set[str],
        event_objects: dict[str, list[tuple[ObjectType, ObjectID]]],
        activities: dict[str, str],
        order: dict[str, int],
    ) -> tuple[list[Binding], ObjectsByType, dict[ObjectID, ObjectID]]:
        """Builds the visible binding sequence of the preset plus the initial object scope.

        Object identities are canonicalized (per type, by first appearance) so that structurally
        equal contexts share a replay signature. The returned ``scope`` maps every object type to
        the canonical ids of all objects in the preset and the event itself; these are placed at
        their type's source place to form the initial marking.
        """
        ordered_preset = sorted(preset, key=lambda preset_event: order[preset_event])
        canonical: dict[ObjectID, ObjectID] = {}
        type_counters: Counter[ObjectType] = Counter()

        def canonicalize(object_type: ObjectType, object_id: ObjectID) -> ObjectID:
            if object_id not in canonical:
                canonical[object_id] = f"{object_type}#{type_counters[object_type]}"
                type_counters[object_type] += 1
            return canonical[object_id]

        binding_sequence: list[Binding] = []
        for preset_event in ordered_preset:
            objects_by_type: ObjectsByType = defaultdict(list)
            for object_type, object_id in event_objects[preset_event]:
                objects_by_type[object_type].append(canonicalize(object_type, object_id))
            binding_sequence.append(
                (activities[preset_event], {object_type: sorted(ids) for object_type, ids in objects_by_type.items()})
            )

        scope: dict[ObjectType, list[ObjectID]] = defaultdict(list)
        for preset_event in ordered_preset:
            for object_type, object_id in event_objects[preset_event]:
                scope[object_type].append(canonicalize(object_type, object_id))
        for object_type, object_id in event_objects[event_id]:
            scope[object_type].append(canonicalize(object_type, object_id))
        deduplicated_scope = {object_type: sorted(set(ids)) for object_type, ids in scope.items()}
        return binding_sequence, deduplicated_scope, canonical

    @staticmethod
    def _context_key(
        preset: set[str],
        event_id: str,
        event_objects: dict[str, list[tuple[ObjectType, ObjectID]]],
        activities: dict[str, str],
        order: dict[str, int],
    ) -> ContextKey:
        """Builds the hashable context of an event (Definition 8).

        For every object appearing in the preset or the event itself, the prefix is the sequence of
        activities of the preset events involving that object (in temporal order). Prefixes are
        grouped per object type into a multiset.
        """
        ordered_preset = sorted(preset, key=lambda preset_event: order[preset_event])
        prefixes: dict[ObjectID, list[str]] = defaultdict(list)
        object_type_of: dict[ObjectID, ObjectType] = {}
        for preset_event in ordered_preset:
            for object_type, object_id in event_objects[preset_event]:
                prefixes[object_id].append(activities[preset_event])
                object_type_of[object_id] = object_type
        for object_type, object_id in event_objects[event_id]:
            object_type_of.setdefault(object_id, object_type)

        context: dict[ObjectType, Counter[ActivitySequence]] = defaultdict(Counter)
        for object_id, object_type in object_type_of.items():
            context[object_type][tuple(prefixes.get(object_id, []))] += 1
        return frozenset(
            (object_type, frozenset(counter.items())) for object_type, counter in context.items()
        )

    @staticmethod
    def _replay_signature(scope: ObjectsByType, binding_sequence: list[Binding]) -> ReplaySignature:
        initial = tuple(sorted((object_type, len(ids)) for object_type, ids in scope.items()))
        sequence = tuple(
            (
                activity,
                tuple(sorted((object_type, len(ids)) for object_type, ids in objects_by_type.items())),
            )
            for activity, objects_by_type in binding_sequence
        )
        return initial, sequence

    @classmethod
    def _enabled_model_activities(
        cls,
        net: ObjectCentricPetriNet,
        model: ObjectCentricWorkflowNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        silent_transitions: set[Transition],
        scope: ObjectsByType,
        binding_sequence: list[Binding],
        max_states: int,
        compositional: bool = False,
    ) -> set[str]:
        """Replays the binding sequence on the model and returns the enabled activities (Algorithm 1).

        A breadth-first search advances a (marking, position) state. When the next binding is
        enabled it is executed; otherwise all enabled silent transitions are fired to search for a
        state in which the next binding (or, once fully replayed, further behavior) becomes enabled.
        Whenever the binding sequence is fully replayed, the visible activities enabled in the
        reached marking are collected.
        """
        initial_marking = cls._build_initial_marking(model, scope, compositional)
        if initial_marking is None:
            return set()

        fire_binding = cls._fire_binding_compositional if compositional else cls._fire_binding
        length = len(binding_sequence)
        start = (initial_marking, 0)
        queue: deque[tuple[IdentityMarking, int]] = deque([start])
        visited: set[tuple[IdentityMarking, int]] = {start}
        enabled_activities: set[str] = set()

        while queue:
            if len(visited) > max_states:
                return set()
            marking, position = queue.popleft()

            if position == length:
                enabled_activities |= cls._enabled_visible_activities(net, semantics, subnets, silent_transitions, marking)

            advanced = False
            if position < length:
                for next_marking in fire_binding(net, semantics, subnets, marking, binding_sequence[position]):
                    state = (next_marking, position + 1)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)
                        advanced = True
            if not advanced:
                for next_marking in cls._fire_silent_transitions(
                    net, semantics, subnets, silent_transitions, marking
                ):
                    state = (next_marking, position)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)

        return enabled_activities

    @staticmethod
    def _build_initial_marking(
        model: ObjectCentricWorkflowNet, scope: ObjectsByType, compositional: bool = False
    ) -> Optional[IdentityMarking]:
        marking: IdentityMarking = Marking()
        for object_type, object_ids in scope.items():
            if compositional:
                # A compositional net types its base places by the single-component higher-order type
                # ``{<object_type>1}``; base objects are seeded there as single-reference higher-order
                # tokens and the model composes them while replaying.
                base_type = HigherOrderObjectType(frozenset({(object_type, 1)}))
                source = model.get_source_of_object_type(base_type.object_type)
                if source is None:
                    continue
                for object_id in object_ids:
                    identity = HigherOrderObject(frozenset({ObjectReference(object_type, object_id)}))
                    marking[ObjectCompositionIdentityToken(source, identity)] += 1
            else:
                source = model.get_source_of_object_type(object_type)
                if source is None:
                    continue
                for object_id in object_ids:
                    marking[IdentityToken(source, object_id)] += 1
        return marking

    @staticmethod
    def _fire_binding(
        net: ObjectCentricPetriNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        marking: IdentityMarking,
        binding: Binding,
    ) -> list[IdentityMarking]:
        activity, objects_by_type = binding
        results: list[IdentityMarking] = []
        for transition in PetriNetUtils.get_transitions_by_label(net, activity):
            pre_set = cast(set[ObjectAwarePlace], PetriNetUtils.get_pre_set(net, transition))
            if not {place.object_type for place in pre_set}.issubset(objects_by_type.keys()):
                continue
            consumption: IdentityMarking = Marking()
            for place in pre_set:
                for object_id in objects_by_type.get(place.object_type, []):
                    consumption[IdentityToken(place, object_id)] += 1
            if not consumption or Marking(consumption - marking):
                continue
            productions = semantics.get_productions(net, transition, marking, consumption, subnets)
            if not productions:
                continue
            results.append(semantics.fire(net, transition, marking, consumption, productions[0], sanity_check=False))
        return results

    @classmethod
    def _fire_binding_compositional(
        cls,
        net: ObjectCentricPetriNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        marking: IdentityMarking,
        binding: Binding,
    ) -> list[IdentityMarking]:
        """Fires a binding on a compositional net, driven by the (fixed) compositional semantics.

        Unlike the plain object-centric case, a visible transition of a compositional net may
        compose or decompose objects, so the consumed/produced tokens are higher-order objects that
        cannot be constructed object-by-object. The event fixes the binding: the semantics enumerates
        all consumptions and productions, and only the ones whose contained base objects are exactly
        the event's objects (restricted to the transition's input resp. output object types) are
        executed. This keeps the replay faithful to the observed binding -- e.g. composing a purchase
        requisition with *all* of its materials rather than with an arbitrary subset.
        """
        activity, objects_by_type = binding
        target_refs = frozenset(
            ObjectReference(object_type, object_id)
            for object_type, object_ids in objects_by_type.items()
            for object_id in object_ids
        )
        results: list[IdentityMarking] = []
        for transition in PetriNetUtils.get_transitions_by_label(net, activity):
            pre_set = cast(set[HigherObjectAwarePlace], PetriNetUtils.get_pre_set(net, transition))
            post_set = cast(set[HigherObjectAwarePlace], PetriNetUtils.get_post_set(net, transition))
            required_in = cls._event_references_of_types(target_refs, pre_set)
            required_out = cls._event_references_of_types(target_refs, post_set)
            if not required_in:
                continue
            for consumption in semantics.get_consumptions(net, transition, marking, subnets):
                if cls._flatten_references(consumption) != required_in:
                    continue
                for production in semantics.get_productions(net, transition, marking, consumption, subnets):
                    results.append(
                        semantics.fire(net, transition, marking, consumption, production, sanity_check=False)
                    )
        return results

    @staticmethod
    def _event_references_of_types(
        references: frozenset[ObjectReference], places: set[HigherObjectAwarePlace]
    ) -> frozenset[ObjectReference]:
        base_types: set[ObjectType] = set()
        for place in places:
            base_types |= place.higher_order_object_type.base_object_types()
        return frozenset(reference for reference in references if reference.otype in base_types)

    @staticmethod
    def _flatten_references(tokens: Counter) -> frozenset[ObjectReference]:
        references: set[ObjectReference] = set()
        for token in tokens:
            references |= token.higher_order_object.flatten()
        return frozenset(references)

    @staticmethod
    def _fire_silent_transitions(
        net: ObjectCentricPetriNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        silent_transitions: set[Transition],
        marking: IdentityMarking,
    ) -> list[IdentityMarking]:
        results: list[IdentityMarking] = []
        eligible = MarkingUtils.get_eligible_transitions(net, marking) & silent_transitions
        for transition in eligible:
            for consumption in semantics.get_consumptions(net, transition, marking, subnets):
                for production in semantics.get_productions(net, transition, marking, consumption, subnets):
                    results.append(
                        semantics.fire(net, transition, marking, consumption, production, sanity_check=False)
                    )
        return results

    @staticmethod
    def _enabled_visible_activities(
        net: ObjectCentricPetriNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        silent_transitions: set[Transition],
        marking: IdentityMarking,
    ) -> set[str]:
        activities: set[str] = set()
        for transition in MarkingUtils.get_eligible_transitions(net, marking):
            if transition in silent_transitions:
                continue
            if semantics.get_consumptions(net, transition, marking, subnets):
                activities.add(transition.label)
        return activities


# A binding is an activity together with the (canonicalized) objects it binds.
ObjectSignature = frozenset[tuple[ObjectType, ObjectID]]
BindingToken = tuple[str, ObjectSignature]


class ObjectCentricBindingPrecisionFitness(ObjectCentricPrecisionFitness):
    """Binding-level variant of :class:`ObjectCentricPrecisionFitness`.

    The base measure compares the *activities* enabled by the log and the model in each context.
    That measure is insensitive to how objects are related, because identities are abstracted into
    the context and only activity labels are scored. This variant instead compares *bindings* -- an
    activity together with the concrete objects it binds -- so that restrictions on identity
    relationships become visible. This is exactly what higher-order compositions add: e.g. a plain
    object-centric net may enable "Approve" for any subset of materials (many bindings), whereas a
    compositional net only enables it for the material bundle belonging to the purchase requisition
    (one binding), which lowers the plain net's binding precision while keeping the compositional
    net's at 1.

    Objects are canonicalized per context (by type and first appearance) so that a log binding and a
    model binding refer to the same abstract objects. The result is therefore identity-aware but
    still independent of the raw object ids.

    This variant is more expensive than the activity-level measure, as it enumerates all consumptions
    (object bindings) of every enabled transition rather than only checking enablement.
    """

    @classmethod
    def _log_token(
        cls,
        event_id: str,
        activities: dict[str, str],
        event_objects: dict[str, list[tuple[ObjectType, ObjectID]]],
        canonical: dict[ObjectID, ObjectID],
    ) -> BindingToken:
        references: ObjectSignature = frozenset(
            (object_type, canonical[object_id]) for object_type, object_id in event_objects[event_id]
        )
        return activities[event_id], references

    @staticmethod
    def _enabled_visible_activities(
        net: ObjectCentricPetriNet,
        semantics: Type[ObjectCentricSemantics],
        subnets: dict,
        silent_transitions: set[Transition],
        marking: IdentityMarking,
    ) -> set[BindingToken]:
        bindings: set[BindingToken] = set()
        for transition in MarkingUtils.get_eligible_transitions(net, marking):
            if transition in silent_transitions:
                continue
            for consumption in semantics.get_consumptions(net, transition, marking, subnets):
                bindings.add(
                    (transition.label, ObjectCentricBindingPrecisionFitness._consumed_references(consumption))
                )
        return bindings

    @staticmethod
    def _consumed_references(consumption: Counter) -> ObjectSignature:
        """The set of (object type, canonical id) pairs bound by a consumption.

        Handles both plain identity tokens and compositional tokens (whose contained base objects are
        flattened), so a binding is always expressed in terms of the base objects it involves.
        """
        references: set[tuple[ObjectType, ObjectID]] = set()
        for token in consumption:
            if isinstance(token, ObjectCompositionIdentityToken):
                for reference in token.higher_order_object.flatten():
                    references.add((reference.otype, reference.oid))
            else:
                references.add((token.place.object_type, token.identity))
        return frozenset(references)
