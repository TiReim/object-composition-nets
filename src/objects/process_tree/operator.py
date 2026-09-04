from enum import Enum


class Operator(Enum):
    SEQUENCE = "->"
    XOR = "X"
    PARALLEL = "+"
    LOOP = "*"
    REVERSE_SEQUENCE = "<-"
