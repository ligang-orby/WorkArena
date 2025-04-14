from ..conditional import __TASKS__ as CONDITIONAL_TASKS
from ..loop import __TASKS__ as LOOP_TASKS
from ..comparison import __TASKS__ as COMPARISON_TASKS
COMPLEX_CURRICULUM = {
    'conditional': {
        "buckets": [
            CONDITIONAL_TASKS,
        ],
        "num_seeds": 2,
        "weights": [1],

    },
    'loop': {
        "buckets": [
            LOOP_TASKS,
        ],
        "num_seeds": 2,
        "weights": [1],
    },
    'comparison': {
        "buckets": [
            COMPARISON_TASKS,
        ],
        "num_seeds": 2,
        "weights": [1],
    }
}