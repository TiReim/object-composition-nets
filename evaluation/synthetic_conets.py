"""Object-composition nets used to simulate synthetic object-centric event logs.

The scenarios exercise hierarchical, long-lived, temporary, and deliberately non-rediscoverable
composition lifecycles.
"""

import os
from dataclasses import dataclass

from src.objects.data_types.higher_order_object_types import HigherOrderObjectType
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.object_composition_nets.object_composition_net import (
    ObjectCompositionNet,
    ObjectCompositionWorkflowNet,
)
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.visualization import PetriNetVisualization

OUT_DIR = os.path.join(os.path.dirname(__file__), "nets")


def base_type(object_type: str) -> HigherOrderObjectType:
    """The higher-type ``{T}`` that, semantically, corresponds to the base object type ``T``."""
    return HigherOrderObjectType(frozenset({(object_type, 1)}))


def higher_type(*components: tuple[HigherOrderObjectType | str, int]) -> HigherOrderObjectType:
    """A higher-type from ``(component, capacity)`` pairs, e.g. ``("Vial", 3)`` or ``(inner_ht, 2)``."""
    return HigherOrderObjectType(frozenset(components))


def place(name: str, object_type: HigherOrderObjectType) -> HigherObjectAwarePlace:
    return HigherObjectAwarePlace(name, object_type)


def transition(name: str, label: str, scope: tuple[int, int]) -> Transition:
    return Transition(name, label, payload={"scope": scope})


@dataclass(frozen=True)
class SyntheticOCoN:
    """A named OCoN used for stochastic simulation and rendering."""

    name: str
    net: ObjectCompositionWorkflowNet


def pharmaceutical_cold_chain_conet() -> SyntheticOCoN:
    """A two-level cold chain in which validated boxes remain intact during a hub transfer.

    Up to three vials are packed into ``{ColdBox, Vial^3}``, which is loaded into
    ``{Shipment, {ColdBox, Vial^3}}``. A temperature excursion quarantines the complete nested
    shipment and loops back into transit after release. At a transfer hub only the outer shipment
    layer is removed. The cold-box composite is then inspected without the shipment while
    preserving its vial membership. The shipment record closes at the hub while the cold box
    completes last-mile delivery and is unpacked.

    """
    vial, cold_box, shipment = "Vial", "ColdBox", "Shipment"
    cold_box_with_vials = higher_type((cold_box, 1), (vial, 3))
    loaded_shipment = higher_type((cold_box_with_vials, 1), (shipment, 1))

    vial_src = place("Vial_src", base_type(vial))
    vial_filled = place("Vial_filled", base_type(vial))
    vial_released = place("Vial_released", base_type(vial))
    cold_box_src = place("ColdBox_src", base_type(cold_box))
    packed_cold_box = place("ColdBoxVials_packed", cold_box_with_vials)
    shipment_src = place("Shipment_src", base_type(shipment))
    shipment_staged = place("Shipment_staged", base_type(shipment))
    shipment_loaded = place("ShipmentColdBoxes_loaded", loaded_shipment)
    shipment_in_transit = place("ShipmentColdBoxes_in_transit", loaded_shipment)
    shipment_quarantined = place("ShipmentColdBoxes_quarantined", loaded_shipment)
    cold_box_at_hub = place("ColdBoxVials_at_hub", cold_box_with_vials)
    cold_box_inspected = place("ColdBoxVials_inspected", cold_box_with_vials)
    shipment_at_hub = place("Shipment_at_hub", base_type(shipment))
    shipment_arrived = place("ShipmentColdBoxes_arrived", loaded_shipment)
    vial_sink = place("Vial_sink", base_type(vial))
    cold_box_sink = place("ColdBox_sink", base_type(cold_box))
    shipment_sink = place("Shipment_sink", base_type(shipment))

    fill_vial = transition("fill_vial", "Fill Vial", (0, 0))
    qc_release = transition("qc_release", "Standard QC Release", (0, 0))
    deviation_release = transition("deviation_release", "Release under Deviation", (0, 0))
    pack_cold = transition("pack_cold", "Pack Cold Box", (0, 1))
    stage_shipment = transition("stage_shipment", "Stage Shipment", (0, 0))
    load_shipment = transition("load_shipment", "Load Shipment", (0, 1))
    dispatch = transition("dispatch", "Dispatch Shipment", (0, 0))
    temperature_excursion = transition("temperature_excursion", "Temperature Excursion", (0, 0))
    release_quarantine = transition("release_quarantine", "Release Quarantine", (0, 0))
    arrive_direct = transition("arrive_direct", "Arrive Direct", (0, 0))
    hub_unload = transition("hub_unload", "Hub Unload", (1, 0))
    inspect_cold_box = transition("inspect_cold_box", "Inspect Cold Box", (0, 0))
    close_hub_shipment = transition("close_hub_shipment", "Close Hub Shipment", (0, 0))
    deliver_hub_box = transition("deliver_hub_box", "Deliver Hub Cold Box", (1, 0))
    deliver = transition("deliver", "Deliver Cold Chain", (2, 0))

    places = {
        vial_src,
        vial_filled,
        vial_released,
        cold_box_src,
        packed_cold_box,
        shipment_src,
        shipment_staged,
        shipment_loaded,
        shipment_in_transit,
        shipment_quarantined,
        cold_box_at_hub,
        cold_box_inspected,
        shipment_at_hub,
        shipment_arrived,
        vial_sink,
        cold_box_sink,
        shipment_sink,
    }
    transitions = {
        fill_vial,
        qc_release,
        deviation_release,
        pack_cold,
        stage_shipment,
        load_shipment,
        dispatch,
        temperature_excursion,
        release_quarantine,
        arrive_direct,
        hub_unload,
        inspect_cold_box,
        close_hub_shipment,
        deliver_hub_box,
        deliver,
    }
    arcs = {
        Arc(vial_src, fill_vial),
        Arc(fill_vial, vial_filled),
        Arc(vial_filled, qc_release),
        Arc(qc_release, vial_released),
        Arc(vial_filled, deviation_release),
        Arc(deviation_release, vial_released),
        VariableArc(vial_released, pack_cold),
        Arc(cold_box_src, pack_cold),
        Arc(pack_cold, packed_cold_box),
        Arc(shipment_src, stage_shipment),
        Arc(stage_shipment, shipment_staged),
        VariableArc(packed_cold_box, load_shipment),
        Arc(shipment_staged, load_shipment),
        Arc(load_shipment, shipment_loaded),
        Arc(shipment_loaded, dispatch),
        Arc(dispatch, shipment_in_transit),
        Arc(shipment_in_transit, temperature_excursion),
        Arc(temperature_excursion, shipment_quarantined),
        Arc(shipment_quarantined, release_quarantine),
        Arc(release_quarantine, shipment_in_transit),
        Arc(shipment_in_transit, arrive_direct),
        Arc(arrive_direct, shipment_arrived),
        Arc(shipment_in_transit, hub_unload),
        Arc(hub_unload, cold_box_at_hub),
        Arc(hub_unload, shipment_at_hub),
        Arc(cold_box_at_hub, inspect_cold_box),
        Arc(inspect_cold_box, cold_box_inspected),
        Arc(cold_box_inspected, deliver_hub_box),
        VariableArc(deliver_hub_box, vial_sink),
        Arc(deliver_hub_box, cold_box_sink),
        Arc(shipment_at_hub, close_hub_shipment),
        Arc(close_hub_shipment, shipment_sink),
        Arc(shipment_arrived, deliver),
        VariableArc(deliver, vial_sink),
        VariableArc(deliver, cold_box_sink),
        Arc(deliver, shipment_sink),
    }

    net = ObjectCompositionNet(places, transitions, arcs)
    workflow_net = ObjectCompositionWorkflowNet(
        net,
        source_places={vial_src, cold_box_src, shipment_src},
        sink_places={vial_sink, cold_box_sink, shipment_sink},
    )
    return SyntheticOCoN("pharmaceutical_cold_chain", workflow_net)


def mortgage_origination_conet() -> SyntheticOCoN:
    """A mortgage dossier kept intact through concurrent and iterative underwriting.

    One application, one property and two to four verified documents are filed as the flat
    higher-type ``{Application, Document^4, Property}``. Credit assessment and property appraisal
    then run concurrently on the same dossier. Underwriting may request and review conditions
    repeatedly before choosing approval or decline; both outcomes decompose the dossier only at the
    lifecycle boundary.

    Unlike the other scenarios, membership never changes after filing.
    """
    application, document, property_ = "Application", "Document", "Property"
    loan_dossier = higher_type((application, 1), (document, 4), (property_, 1))

    application_src = place("Application_src", base_type(application))
    application_open = place("Application_open", base_type(application))
    document_src = place("Document_src", base_type(document))
    document_uploaded = place("Document_uploaded", base_type(document))
    document_verified = place("Document_verified", base_type(document))
    property_src = place("Property_src", base_type(property_))
    property_registered = place("Property_registered", base_type(property_))
    dossier_filed = place("LoanDossier_filed", loan_dossier)
    credit_pending = place("LoanDossier_credit_pending", loan_dossier)
    appraisal_pending = place("LoanDossier_appraisal_pending", loan_dossier)
    credit_complete = place("LoanDossier_credit_complete", loan_dossier)
    appraisal_complete = place("LoanDossier_appraisal_complete", loan_dossier)
    underwriting_ready = place("LoanDossier_underwriting_ready", loan_dossier)
    decision_ready = place("LoanDossier_decision_ready", loan_dossier)
    conditions_open = place("LoanDossier_conditions_open", loan_dossier)
    approved = place("LoanDossier_approved", loan_dossier)
    declined = place("LoanDossier_declined", loan_dossier)
    application_sink = place("Application_sink", base_type(application))
    document_sink = place("Document_sink", base_type(document))
    property_sink = place("Property_sink", base_type(property_))

    create_application = transition("create_application", "Create Application", (0, 0))
    upload_document = transition("upload_document", "Upload Document", (0, 0))
    verify_document = transition("verify_document", "Verify Document", (0, 0))
    accept_certified_copy = transition("accept_certified_copy", "Accept Certified Copy", (0, 0))
    register_property = transition("register_property", "Register Property", (0, 0))
    file_dossier = transition("file_dossier", "File Loan Dossier", (0, 1))
    split_underwriting = transition("split_underwriting", "Split Underwriting", (0, 0))
    assess_credit = transition("assess_credit", "Assess Credit", (0, 0))
    appraise_property = transition("appraise_property", "Appraise Property", (0, 0))
    join_underwriting = transition("join_underwriting", "Join Underwriting", (0, 0))
    review_application = transition("review_application", "Review Application", (0, 0))
    request_conditions = transition("request_conditions", "Request Conditions", (0, 0))
    review_conditions = transition("review_conditions", "Review Conditions", (0, 0))
    approve_loan = transition("approve_loan", "Approve Loan", (0, 0))
    decline_loan = transition("decline_loan", "Decline Loan", (0, 0))
    close_loan = transition("close_loan", "Close Loan", (1, 0))
    archive_decline = transition("archive_decline", "Archive Decline", (1, 0))

    places = {
        application_src,
        application_open,
        document_src,
        document_uploaded,
        document_verified,
        property_src,
        property_registered,
        dossier_filed,
        credit_pending,
        appraisal_pending,
        credit_complete,
        appraisal_complete,
        underwriting_ready,
        decision_ready,
        conditions_open,
        approved,
        declined,
        application_sink,
        document_sink,
        property_sink,
    }
    transitions = {
        create_application,
        upload_document,
        verify_document,
        accept_certified_copy,
        register_property,
        file_dossier,
        split_underwriting,
        assess_credit,
        appraise_property,
        join_underwriting,
        review_application,
        request_conditions,
        review_conditions,
        approve_loan,
        decline_loan,
        close_loan,
        archive_decline,
    }
    arcs = {
        Arc(application_src, create_application),
        Arc(create_application, application_open),
        Arc(document_src, upload_document),
        Arc(upload_document, document_uploaded),
        Arc(document_uploaded, verify_document),
        Arc(verify_document, document_verified),
        Arc(document_uploaded, accept_certified_copy),
        Arc(accept_certified_copy, document_verified),
        Arc(property_src, register_property),
        Arc(register_property, property_registered),
        Arc(application_open, file_dossier),
        VariableArc(document_verified, file_dossier),
        Arc(property_registered, file_dossier),
        Arc(file_dossier, dossier_filed),
        Arc(dossier_filed, split_underwriting),
        Arc(split_underwriting, credit_pending),
        Arc(split_underwriting, appraisal_pending),
        Arc(credit_pending, assess_credit),
        Arc(assess_credit, credit_complete),
        Arc(appraisal_pending, appraise_property),
        Arc(appraise_property, appraisal_complete),
        Arc(credit_complete, join_underwriting),
        Arc(appraisal_complete, join_underwriting),
        Arc(join_underwriting, underwriting_ready),
        Arc(underwriting_ready, review_application),
        Arc(review_application, decision_ready),
        Arc(decision_ready, request_conditions),
        Arc(request_conditions, conditions_open),
        Arc(conditions_open, review_conditions),
        Arc(review_conditions, underwriting_ready),
        Arc(decision_ready, approve_loan),
        Arc(approve_loan, approved),
        Arc(decision_ready, decline_loan),
        Arc(decline_loan, declined),
        Arc(approved, close_loan),
        Arc(close_loan, application_sink),
        VariableArc(close_loan, document_sink),
        Arc(close_loan, property_sink),
        Arc(declined, archive_decline),
        Arc(archive_decline, application_sink),
        VariableArc(archive_decline, document_sink),
        Arc(archive_decline, property_sink),
    }

    net = ObjectCompositionNet(places, transitions, arcs)
    workflow_net = ObjectCompositionWorkflowNet(
        net,
        source_places={application_src, document_src, property_src},
        sink_places={application_sink, document_sink, property_sink},
    )
    return SyntheticOCoN("mortgage_origination", workflow_net)


def aircraft_maintenance_conet() -> SyntheticOCoN:
    """Aircraft line maintenance with a stable work package and temporary execution resources.

    A work order and up to two line-replaceable units (LRUs) first form
    ``{WorkOrder, LRU^2}``. A technician and up to two tools are then attached in a second
    composition step, yielding ``{Technician, Tool^2, {WorkOrder, LRU^2}}``. Functional testing may
    fail and loop through rework while this execution team remains intact.

    ``Release Maintenance Resources`` removes only the outer layer: the work package survives while
    tools and technician follow independent return/sign-off lifecycles.
    """
    work_order, lru, tool, technician = "WorkOrder", "LRU", "Tool", "Technician"
    work_package = higher_type((work_order, 1), (lru, 2))
    maintenance_execution = higher_type((work_package, 1), (tool, 2), (technician, 1))

    work_order_src = place("WorkOrder_src", base_type(work_order))
    work_order_open = place("WorkOrder_open", base_type(work_order))
    lru_src = place("LRU_src", base_type(lru))
    lru_removed = place("LRU_removed", base_type(lru))
    lru_ready = place("LRU_ready", base_type(lru))
    tool_src = place("Tool_src", base_type(tool))
    tool_checked_out = place("Tool_checked_out", base_type(tool))
    technician_src = place("Technician_src", base_type(technician))
    technician_assigned = place("Technician_assigned", base_type(technician))
    package_defined = place("WorkOrderLRUs_defined", work_package)
    maintenance_active = place("MaintenanceExecution_active", maintenance_execution)
    test_ready = place("MaintenanceExecution_test_ready", maintenance_execution)
    test_result = place("MaintenanceExecution_test_result", maintenance_execution)
    rework_required = place("MaintenanceExecution_rework_required", maintenance_execution)
    maintenance_complete = place("MaintenanceExecution_complete", maintenance_execution)
    package_post_maintenance = place("WorkOrderLRUs_post_maintenance", work_package)
    tools_to_return = place("Tool_to_return", base_type(tool))
    technician_to_release = place("Technician_to_release", base_type(technician))
    package_inspected = place("WorkOrderLRUs_inspected", work_package)
    work_order_sink = place("WorkOrder_sink", base_type(work_order))
    lru_sink = place("LRU_sink", base_type(lru))
    tool_sink = place("Tool_sink", base_type(tool))
    technician_sink = place("Technician_sink", base_type(technician))

    open_work_order = transition("open_work_order", "Open Work Order", (0, 0))
    remove_lru = transition("remove_lru", "Remove LRU", (0, 0))
    bench_test_lru = transition("bench_test_lru", "Bench Test LRU", (0, 0))
    accept_exchange_unit = transition("accept_exchange_unit", "Accept Exchange Unit", (0, 0))
    check_out_tool = transition("check_out_tool", "Check Out Tool", (0, 0))
    assign_technician = transition("assign_technician", "Assign Technician", (0, 0))
    define_work_package = transition("define_work_package", "Define Work Package", (0, 1))
    start_maintenance = transition("start_maintenance", "Start Maintenance", (0, 1))
    perform_replacement = transition("perform_replacement", "Perform Replacement", (0, 0))
    functional_test = transition("functional_test", "Functional Test", (0, 0))
    test_failed = transition("test_failed", "Test Failed", (0, 0))
    rework = transition("rework", "Rework Maintenance", (0, 0))
    test_passed = transition("test_passed", "Test Passed", (0, 0))
    release_resources = transition("release_resources", "Release Maintenance Resources", (1, 0))
    independent_inspection = transition("independent_inspection", "Independent Inspection", (0, 0))
    close_work_order = transition("close_work_order", "Close Work Order", (1, 0))
    return_tools = transition("return_tools", "Return Tools", (0, 0))
    end_assignment = transition("end_assignment", "End Technician Assignment", (0, 0))

    places = {
        work_order_src,
        work_order_open,
        lru_src,
        lru_removed,
        lru_ready,
        tool_src,
        tool_checked_out,
        technician_src,
        technician_assigned,
        package_defined,
        maintenance_active,
        test_ready,
        test_result,
        rework_required,
        maintenance_complete,
        package_post_maintenance,
        tools_to_return,
        technician_to_release,
        package_inspected,
        work_order_sink,
        lru_sink,
        tool_sink,
        technician_sink,
    }
    transitions = {
        open_work_order,
        remove_lru,
        bench_test_lru,
        accept_exchange_unit,
        check_out_tool,
        assign_technician,
        define_work_package,
        start_maintenance,
        perform_replacement,
        functional_test,
        test_failed,
        rework,
        test_passed,
        release_resources,
        independent_inspection,
        close_work_order,
        return_tools,
        end_assignment,
    }
    arcs = {
        Arc(work_order_src, open_work_order),
        Arc(open_work_order, work_order_open),
        Arc(lru_src, remove_lru),
        Arc(remove_lru, lru_removed),
        Arc(lru_removed, bench_test_lru),
        Arc(bench_test_lru, lru_ready),
        Arc(lru_removed, accept_exchange_unit),
        Arc(accept_exchange_unit, lru_ready),
        Arc(tool_src, check_out_tool),
        Arc(check_out_tool, tool_checked_out),
        Arc(technician_src, assign_technician),
        Arc(assign_technician, technician_assigned),
        Arc(work_order_open, define_work_package),
        VariableArc(lru_ready, define_work_package),
        Arc(define_work_package, package_defined),
        Arc(package_defined, start_maintenance),
        VariableArc(tool_checked_out, start_maintenance),
        Arc(technician_assigned, start_maintenance),
        Arc(start_maintenance, maintenance_active),
        Arc(maintenance_active, perform_replacement),
        Arc(perform_replacement, test_ready),
        Arc(test_ready, functional_test),
        Arc(functional_test, test_result),
        Arc(test_result, test_failed),
        Arc(test_failed, rework_required),
        Arc(rework_required, rework),
        Arc(rework, test_ready),
        Arc(test_result, test_passed),
        Arc(test_passed, maintenance_complete),
        Arc(maintenance_complete, release_resources),
        Arc(release_resources, package_post_maintenance),
        VariableArc(release_resources, tools_to_return),
        Arc(release_resources, technician_to_release),
        Arc(package_post_maintenance, independent_inspection),
        Arc(independent_inspection, package_inspected),
        Arc(package_inspected, close_work_order),
        Arc(close_work_order, work_order_sink),
        VariableArc(close_work_order, lru_sink),
        Arc(tools_to_return, return_tools),
        Arc(return_tools, tool_sink),
        Arc(technician_to_release, end_assignment),
        Arc(end_assignment, technician_sink),
    }

    net = ObjectCompositionNet(places, transitions, arcs)
    workflow_net = ObjectCompositionWorkflowNet(
        net,
        source_places={work_order_src, lru_src, tool_src, technician_src},
        sink_places={work_order_sink, lru_sink, tool_sink, technician_sink},
    )
    return SyntheticOCoN("aircraft_maintenance", workflow_net)


def concurrent_composition_conet() -> SyntheticOCoN:
    """A composition whose member participates in a concurrent branch.

    ``Form Composition`` duplicates the case object: one token is composed with the item while the
    other enters an independent review branch. The review must finish before the branches join and
    the composition is decomposed. Consequently, each case/item pair has the event sequence
    ``Form Composition`` (both), ``Review Case`` (case only), ``Close Composition`` (both). The
    composition miner therefore never observes two consecutive events over the complete pair.
    """
    case, item = "Case", "Item"
    composition = higher_type((case, 1), (item, 1))

    case_src = place("Case_src", base_type(case))
    case_ready = place("Case_ready", base_type(case))
    item_src = place("Item_src", base_type(item))
    item_ready = place("Item_ready", base_type(item))
    composition_active = place("Composition_active", composition)
    case_review_pending = place("Case_review_pending", base_type(case))
    case_reviewed = place("Case_reviewed", base_type(case))
    case_sink = place("Case_sink", base_type(case))
    item_sink = place("Item_sink", base_type(item))

    create_case = transition("create_case", "Create Case", (0, 0))
    register_item = transition("register_item", "Register Item", (0, 0))
    form_composition = transition("form_composition", "Form Composition", (0, 1))
    review_case = transition("review_case", "Review Case", (0, 0))
    close_composition = transition("close_composition", "Close Composition", (1, 0))

    places = {
        case_src,
        case_ready,
        item_src,
        item_ready,
        composition_active,
        case_review_pending,
        case_reviewed,
        case_sink,
        item_sink,
    }
    transitions = {
        create_case,
        register_item,
        form_composition,
        review_case,
        close_composition,
    }
    arcs = {
        Arc(case_src, create_case),
        Arc(create_case, case_ready),
        Arc(item_src, register_item),
        Arc(register_item, item_ready),
        Arc(case_ready, form_composition),
        Arc(item_ready, form_composition),
        Arc(form_composition, composition_active),
        Arc(form_composition, case_review_pending),
        Arc(case_review_pending, review_case),
        Arc(review_case, case_reviewed),
        Arc(composition_active, close_composition),
        Arc(case_reviewed, close_composition),
        Arc(close_composition, case_sink),
        Arc(close_composition, item_sink),
    }

    net = ObjectCompositionNet(places, transitions, arcs)
    workflow_net = ObjectCompositionWorkflowNet(
        net,
        source_places={case_src, item_src},
        sink_places={case_sink, item_sink},
    )
    return SyntheticOCoN("concurrent_composition", workflow_net)


BUILDERS = (
    pharmaceutical_cold_chain_conet,
    mortgage_origination_conet,
    aircraft_maintenance_conet,
    concurrent_composition_conet,
)


def validate(synthetic: SyntheticOCoN) -> list[str]:
    """Structural well-formedness checks. Returns a list of problems (empty means valid)."""
    problems: list[str] = []
    wf = synthetic.net
    net = wf.net
    for arc in net.arcs:
        endpoints = (arc.source, arc.target)
        for endpoint in endpoints:
            if endpoint not in net.places and endpoint not in net.transitions:
                problems.append(f"arc endpoint {endpoint!r} is not part of the net")
    for t in net.transitions:
        pre = [arc for arc in net.arcs if arc.target == t]
        post = [arc for arc in net.arcs if arc.source == t]
        if not pre:
            problems.append(f"transition {t.name} has no input arc")
        if not post:
            problems.append(f"transition {t.name} has no output arc")
        if "scope" not in t.payload:
            problems.append(f"transition {t.name} has no scope")
    for boundary, kind in ((wf.source_places, "source"), (wf.sink_places, "sink")):
        for p in boundary:
            if p not in net.places:
                problems.append(f"{kind} place {p.name} is not part of the net")
    return problems


def render(synthetic: SyntheticOCoN, out_dir: str = OUT_DIR) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"synthetic_{synthetic.name}_conet.png")
    vis = PetriNetVisualization.visualize_petri_net(synthetic.net.net, show_place_names=True, show_guards=True)
    vis.graph.write_png(path, prog="dot")
    return path


def main() -> None:
    for builder in BUILDERS:
        synthetic = builder()
        net = synthetic.net.net
        problems = validate(synthetic)
        status = "OK" if not problems else "INVALID"
        print(f"=== {synthetic.name} [{status}] ===")
        print(f"  places={len(net.places)} transitions={len(net.transitions)} arcs={len(net.arcs)}")
        print(f"  source={sorted(p.name for p in synthetic.net.source_places)}")
        print(f"  sink={sorted(p.name for p in synthetic.net.sink_places)}")
        for t in sorted(net.transitions, key=lambda tr: str(tr.label)):
            print(f"    {t.label}: scope={t.payload['scope']}")
        for p in sorted(net.places, key=lambda pl: str(pl.name)):
            print(f"    place {p.name}: {p.higher_order_object_type}")
        for problem in problems:
            print(f"  PROBLEM: {problem}")
        path = render(synthetic)
        print(f"  rendered -> {path}")


if __name__ == "__main__":
    main()
