"""
A demonstration of how observation/action traces can be extracted
for WorkArena tasks without modifying the task code.

Author: Alexandre Drouin (alexandre.drouin@servicenow.com)

Notes:
- This approach relies on monkey patching the playwright actions to log the actions and observations.
  It has not been tested for parallel execution. It might work with multiprocessing, but it will for
  sure not work with multithreading.

"""

import logging
import os
import pickle
import playwright

from browsergym.core import env
from browsergym.workarena import ALL_WORKARENA_TASKS
from collections import defaultdict
from tenacity import retry, stop_after_attempt, wait_fixed
from time import time

logging.basicConfig(level=logging.INFO)

from browsergym.workarena import (
    DASHBOARD_TASKS,
    FORM_TASKS,
    KB_TASKS,
    LIST_TASKS,
    NAVIGATION_TASKS,
    SERVICE_CATALOG_TASKS,
    UPDATE_TASKS,
)

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


def monkey_patch_playwright(observation_callback, trace_storage):
    """
    A function that overrides the default playwright actions to log the actions and observations.

    Parameters:
    ------------
    observation_callback: callable
        A function that returns the observation of the environment.
    trace_storage: list
        A list to store the trace of the actions and observations.
        These will be appended in-place.

    """

    def wrapper(func, interface):
        def wrapped(*args, **kwargs):
            # Get the observation
            obs = observation_callback()
            logging.info(args)
            # Get the BID of the element on which we are acting.
            if interface.__name__ == "Locator":
                # Get the locator
                locator = args[0]
                # Get the BID
                bid = locator.element_handle().evaluate('(el) => el.getAttribute("bid")')
            elif interface.__name__ == "Keyboard":
                # Get the BID of the element
                bid = "keyboard"
            else:
                # Get the BID of the element
                bid = args[0].evaluate('(el) => el.getAttribute("bid")')

            logging.info(f"Action: {func.__name__} BID: {bid}  --   Args: {args[1:]} {kwargs}")
            trace_storage.append(
                {
                    "obs": obs,
                    "action": func.__name__,
                    "args": args[1:],
                    "kwargs": kwargs,
                    "bid": bid,
                    "time": time(),
                }
            )

            # Resume action
            return func(*args, **kwargs)

        return wrapped

    # TODO: Make sure the list of interfaces and actions is exhaustive
    #       It covers all that is used in WorkArena cheats as of April 11, 2024
    interfaces = [
        playwright.sync_api.Page,
        playwright.sync_api.Frame,
        playwright.sync_api.Locator,
        playwright.sync_api.Keyboard,
        playwright.sync_api.ElementHandle,
    ]
    actions = ["click", "select_option", "set_checked", "fill", "press", "type", "down", "up"]

    original_actions = {}
    for interface in interfaces:
        for action in actions:
            if hasattr(interface, action):
                original_actions[interface, action] = getattr(interface, action)
                setattr(interface, action, wrapper(getattr(interface, action), interface))

    return original_actions


def monkey_depatch_playwright(original_actions):
    for interface, action in original_actions:
        setattr(interface, action, original_actions[interface, action])


# @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def extract_trace(task_cls, headless=True):
    """
    Extracts the trace of actions and observations for a given task.

    Parameters:
    ------------
    task_cls: class
        The class of the task to extract the trace from.

    """
    # Instantiate a new environment
    browser_env = env.BrowserEnv(task_entrypoint=task_cls, headless=headless, slow_mo=1000)

    # Setup customized tracing
    trace = []
    original_actions = monkey_patch_playwright(
        observation_callback=browser_env._get_obs, trace_storage=trace
    )

    browser_env.reset()

    # L1
    browser_env.task.cheat(browser_env.page, browser_env.chat.messages)

    # L2
    # for i in range(len(env.task)):
    #     sleep(1)
    #     env.chat.add_message(role="assistant", msg=f'Executing subtask {i}: {env.task.subtasks[i]}')
    #     env.task.cheat(page=env.page, chat_messages=env.chat.messages, subtask_idx=i)

    # For gold traces, we don't have to validate the task
    # reward, done, message, info = env.task.validate(page=env.page, chat_messages=env.chat.messages)
    # if reward == 1:
    #     env.chat.add_message(role="user", msg="Yes, that works. Thanks!")
    # else:
    #     env.chat.add_message(role="user", msg=f"No, that doesn't work. {info.get('message', '')}")
    browser_env.close()

    # Restore the original actions. The original code based onimportlib.reload doesn't work here.
    monkey_depatch_playwright(original_actions)

    return trace


if __name__ == "__main__":
    os.makedirs("trace_profiling", exist_ok=True)

    NUM_TRACES_PER_TASK = 10

    tasks = [t for t in ALL_L1_TASKS if "Order" in str(t)]
    print("In total, there are", len(tasks), "tasks")
    for task in tasks:
        print(task)

    task_traces = defaultdict(list)
    for task in tasks:
        name = str(task).split(".")[-1][:-2]
        print("Task:", name)

        with open(f"trace_profiling/{name}.pickle", "wb") as f:
            for i in range(NUM_TRACES_PER_TASK):
                print(f"Extracting trace {i+1}/{NUM_TRACES_PER_TASK}")
                try:
                    trace = extract_trace(task, headless=True)
                    pickle.dump(trace, f)
                except Exception as e:
                    print(f"Error extracting trace {i+1}/{NUM_TRACES_PER_TASK}: {e}")
                    input("Press Enter to continue...")
