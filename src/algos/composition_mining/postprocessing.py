from src.algos.composition_mining.compute_object_compositions import ObjectComposition

def postprocess_compositions_remove(compositions: set[ObjectComposition]) -> list[ObjectComposition]:
    sorted_compositions = sorted(compositions, key=lambda c: c.start_time.timestamp())
    result = []
    for i, composition in enumerate(sorted_compositions):
        overlapping_compositions = set()
        j = i - 1
        while j >= 0 and composition.start_time <= sorted_compositions[j].end_time:
            overlapping_compositions.add(sorted_compositions[j])
            j -= 1
        j = i + 1
        while j < len(sorted_compositions) and composition.end_time >= sorted_compositions[j].start_time:
            overlapping_compositions.add(sorted_compositions[j])
            j += 1
        overlapping = False
        for overlapping_comp in overlapping_compositions:
            object_intersection = composition.objects & overlapping_comp.objects
            if object_intersection and object_intersection not in {composition.objects, overlapping_comp.objects}:
                overlapping = True
        if not overlapping:
            result.append(composition)
    return result
