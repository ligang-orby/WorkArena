import random

from browsergym.core.env import BrowserEnv
from browsergym.workarena import ALL_COMPOSITIONAL_TASKS_L2

from time import sleep


for index, task in enumerate(ALL_COMPOSITIONAL_TASKS_L2):
    # Instantiate a new environment
    print(f"Task {index}: {task}")
    env = BrowserEnv(task_entrypoint=task, headless=False)
    env.reset()

    print(env.goal_object)
    print(env.task.task_description)
    print(env.task.short_description)

    # Cheat functions use Playwright to automatically solve the task
    env.chat.add_message(role="assistant", msg="On it. Please wait...")
    input("Press Enter to continue...")

    for i in range(len(env.task)):
        sleep(1)
        env.chat.add_message(role="assistant", msg=f"Executing subtask {i}: {env.task.subtasks[i]}")
        env.task.cheat(page=env.page, chat_messages=env.chat.messages, subtask_idx=i)

    reward, done, message, info = env.task.validate(page=env.page, chat_messages=env.chat.messages)

    if reward == 1:
        env.chat.add_message(role="user", msg="Yes, that works. Thanks!")
    else:
        env.chat.add_message(role="user", msg=f"No, that doesn't work. {info.get('message', '')}")

    env.close()
