from collections import Counter


class CounterUtils:
    @staticmethod
    def all_empty(counters: list[Counter]) -> bool:
        return all(CounterUtils.is_empty(counter) for counter in counters)

    @staticmethod
    def is_empty(counter: Counter) -> bool:
        return not bool(counter - Counter())  # -Counter() removes zero elements
