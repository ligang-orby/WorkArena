from ..conditional import __TASKS__ as CONDITIONAL_TASKS

COMPLEX_CURRICULUM = {
    'conditional': {
        "buckets": [
            CONDITIONAL_TASKS,
        ],
        "num_seeds": 2,
        "weights": [1],

    }
}
