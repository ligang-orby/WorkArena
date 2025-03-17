from .utils.curriculum import COMPLEX_CURRICULUM

ALL_COMPLEX_TASKS = []
for category, items in COMPLEX_CURRICULUM.items():
    category_tasks = []
    for task in items["buckets"]:
        category_tasks += task
    ALL_COMPLEX_TASKS += category_tasks
