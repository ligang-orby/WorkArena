import json

import playwright.sync_api
from playwright.sync_api._generated import Page

from browsergym.workarena.tasks.navigation import AllMenuTask

from ..compositional.base import CompositionalTask
from ..compositional.base import AbstractServiceNowTask
from ...instance import SNowInstance
from ..form import CreateUserTask
from ..service_catalog import (
    OrderAppleMacBookPro15Task,
    OrderDevelopmentLaptopPCTask,
    OrderStandardLaptopTask,
    OrderSalesLaptopTask,
)


class ConditionalTask(object):
    """Conditional task consisting of a true/false branch."""

    def __init__(
        self,
        true_branch_task,
        true_branch_prefix,
        false_branch_task,
        false_branch_prefix,
    ) -> None:
        self.used_in_level_2 = True
        self.true_branch_task = true_branch_task
        self.true_branch_prefix = true_branch_prefix
        self.false_branch_task = false_branch_task
        self.false_branch_prefix = false_branch_prefix

    def setup(self, page: playwright.sync_api.Page, do_start=True) -> tuple[str, dict]:
        # Setup the true branch task
        true_branch_goal, true_branch_info = self.true_branch_task.setup(
            page=page, do_start=do_start
        )
        # Setup the false branch task
        false_branch_goal, false_branch_info = self.false_branch_task.setup(
            page=page, do_start=do_start
        )
        # Concatenate the prefix and the goal
        true_branch_goal = self.true_branch_prefix + true_branch_goal
        false_branch_goal = self.false_branch_prefix + false_branch_goal
        # Return the goal with both branches
        goal = [true_branch_goal, false_branch_goal]
        goal = " ".join(goal)
        return goal, {}

    def teardown(self) -> None:
        self.true_branch_task.teardown()
        self.false_branch_task.teardown()

    def validate(
        self, page: playwright.sync_api.Page, chat_messages: list[str]
    ) -> tuple[float, bool, str, dict]:
        # Validate the true branch task only.
        return self.true_branch_task.validate(page, chat_messages)

    def cheat(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> None:
        # Cheat the true branch task only.
        return self.true_branch_task.cheat(page, chat_messages)


class OnBoardUserConditionalTask(CompositionalTask):
    """Conditional task consisting of a true/false branch."""

    _DEPARTMENT_TO_LAPTOP_TASK = {
        "Sales": OrderSalesLaptopTask,
        "IT": OrderDevelopmentLaptopPCTask,
        "Finance": OrderAppleMacBookPro15Task,
    }

    _DEFAULT_LAPTOP_TASK = OrderStandardLaptopTask

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a compositional task with specific subtasks

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task and the related company protocol
            to complete it.
        Attributes:
        -----------
        task_description: str
            The start of the task description to be completed. e.g. "Referring to company protocol 'Onboarding a new user', onboard user with the following information: \n"
        short_description: str
            A short description of the task to be completed. e.g. "Onboard user John Doe"
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Onboarding a new user"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.all_user_configs = CreateUserTask.all_configs()
        self.task_description = None
        self.short_description = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()
        user_name = (
            config[1].fixed_config["template_record"]["first_name"]
            + " "
            + config[1].fixed_config["template_record"]["last_name"]
        )
        # Get the task description
        self.short_description = f"Onboard user {user_name}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) onboard user with the following information: \n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_target_and_candidate_tasks(self, department):
        # Get the target task and the candidate tasks
        target_task = self._DEPARTMENT_TO_LAPTOP_TASK.get(department, self._DEFAULT_LAPTOP_TASK)
        candidate_tasks = list(self._DEPARTMENT_TO_LAPTOP_TASK.items()) + [
            ("default", self._DEFAULT_LAPTOP_TASK)
        ]
        candidate_tasks = [t for t in candidate_tasks if t[0] != department]
        candidate_index = self.random.choice(len(candidate_tasks))
        candidate_department, candidate_task = candidate_tasks[candidate_index]

        # Sample the target task configuration with quantity 1.
        with open(target_task.config_path, "r") as f:
            target_task_config = json.load(f)
            target_task_config = [c for c in target_task_config if c["quantity"] == 1]
            target_task_config = self.random.choice(target_task_config)

        # Sample the candidate task configuration with quantity 1.
        with open(candidate_task.config_path, "r") as f:
            candidate_task_config = json.load(f)
            candidate_task_config = [c for c in candidate_task_config if c["quantity"] == 1]
            candidate_task_config = self.random.choice(candidate_task_config)

        return (
            target_task,
            target_task_config,
            candidate_department,
            candidate_task,
            candidate_task_config,
        )

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample base configurations.
        user_config = self.random.choice(self.all_user_configs)
        department = user_config["template_record"]["department"]

        # Create the create user subtask
        create_user_subtask = [
            # Navigate to the user list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "System Security",
                    "module": "Users and Groups > Users",
                    "url": "/now/nav/ui/classic/params/target/sys_user_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Create a new user
            CreateUserTask(
                instance=self.instance,
                fixed_config=user_config,
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Get the target task and the candidate tasks
        (
            target_task,
            target_task_config,
            candidate_department,
            candidate_task,
            candidate_task_config,
        ) = self._get_target_and_candidate_tasks(department)

        # Create the target task instance
        target_task_instance = target_task(
            instance=self.instance,
            fixed_config=target_task_config,
            is_validated=True,
            used_in_level_2=True,
        )
        # Create the candidate task instance
        candidate_task_instance = candidate_task(
            instance=self.instance,
            fixed_config=candidate_task_config,
            is_validated=True,
            used_in_level_2=True,
        )

        order_hardware_subtask = [
            # Navigate to the hardware asset list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Self-Service",
                    "module": "Service Catalog",
                    "url": "/now/nav/ui/classic/params/target/catalog_home.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task_instance,
                true_branch_prefix=f"If the user department is {department}, ",
                false_branch_task=candidate_task_instance,
                false_branch_prefix=f"If the user department is {candidate_department}, ",
            ),
        ]

        config = create_user_subtask + order_hardware_subtask

        return config


local_vars = locals().copy()

__TASKS__ = [OnBoardUserConditionalTask]
