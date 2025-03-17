import random

from browsergym.core.env import BrowserEnv
from browsergym.workarena import (
    DASHBOARD_TASKS,
    FORM_TASKS,
    KB_TASKS,
    LIST_TASKS,
    NAVIGATION_TASKS,
    SERVICE_CATALOG_TASKS,
    UPDATE_TASKS,
)
from time import sleep

# Combine all L1 tasks.
ALL_L1_TASKS = (
    DASHBOARD_TASKS
    + FORM_TASKS
    + KB_TASKS
    + LIST_TASKS
    + NAVIGATION_TASKS
    + SERVICE_CATALOG_TASKS
    + UPDATE_TASKS
)

for task in ALL_L1_TASKS:
    task_name = str(task).split(".")[-1][:-2]
    print(task_name)

for index, task in enumerate(ALL_L1_TASKS):
    print(f"Task {index}: {task}")

    # Instantiate a new environment
    env = BrowserEnv(task_entrypoint=task, headless=False)
    env.reset()

    print(env.goal_object[0]["text"])
    print()

    # Cheat functions use Playwright to automatically solve the task
    env.chat.add_message(role="assistant", msg="On it. Please wait...")
    cheat_messages = []
    env.task.cheat(env.page, cheat_messages)

    # Send cheat messages to chat
    for cheat_msg in cheat_messages:
        env.chat.add_message(role=cheat_msg["role"], msg=cheat_msg["message"])

    # Post solution to chat
    env.chat.add_message(role="assistant", msg="I'm done!")

    # Validate the solution
    reward, stop, message, info = env.task.validate(env.page, cheat_messages)
    if reward == 1:
        env.chat.add_message(role="user", msg="Yes, that works. Thanks!")
    else:
        env.chat.add_message(role="user", msg=f"No, that doesn't work. {info.get('message', '')}")

    env.close()
