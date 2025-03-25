import json

import playwright.sync_api
from playwright.sync_api._generated import Page

from browsergym.workarena.tasks.navigation import AllMenuTask

from ..compositional.base import CompositionalTask, HumanEvalTask
from ..compositional.base import AbstractServiceNowTask
from ...instance import SNowInstance
from ..form import CreateUserTask, EditHardwareAssetTask
from ..list import FilterHardwareListTask
from ..service_catalog import (
    OrderAppleMacBookPro15Task,
    OrderDevelopmentLaptopPCTask,
    OrderStandardLaptopTask,
    OrderSalesLaptopTask,
)
from faker import Faker
from ...api.utils import table_api_call

fake = Faker()


class ConditionalTask(object):
    """Conditional task consisting of a true/false branch."""

    def __init__(
        self,
        true_branch_task,
        true_branch_prefix,
        false_branch_task,
        false_branch_prefix,
    ) -> None:
        self.true_branch_task = true_branch_task
        self.true_branch_prefix = true_branch_prefix
        self.false_branch_task = false_branch_task
        self.false_branch_prefix = false_branch_prefix
        self.is_validated = False
        self.used_in_level_2 = True

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


class EditHardwareConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing hardware assets based on their model category."""

    _MODEL_CATEGORY_TO_CONFIG = {
        "Laptop": {"assigned_to": "", "asset_function": "Primary"},
        "Desktop": {"assigned_to": "", "asset_function": "Secondary"},
        "Mobile Phone": {"assigned_to": "", "asset_function": "Shared"},
    }

    _DEFAULT_CONFIG = {"assigned_to": "", "asset_function": "Primary"}

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits hardware assets differently based on their model category.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Editing hardware assets"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.all_hardware_configs = EditHardwareAssetTask.all_configs()
        self.task_description = None
        self.short_description = None
        self.hardware_config = None
        self.model_category = None
        self.hardware_sys_id = None
        self.assigned_to = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()
        
        # Get the task description
        self.short_description = f"Edit hardware asset {self.hardware_config['template_record']['asset_tag']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the hardware asset based on its model category: \n'
        
        if self.level == 2:
            self.task_description += (
                f"\nFor {self.model_category} assets:\n"
                f"- Set asset function to {self._MODEL_CATEGORY_TO_CONFIG.get(self.model_category, self._DEFAULT_CONFIG)['asset_function']}\n"
                f"- Remove assigned user\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_target_and_candidate_configs(self, model_category):
        # Get the target config and a random candidate config
        target_config = self._MODEL_CATEGORY_TO_CONFIG.get(model_category, self._DEFAULT_CONFIG)
        
        # Get all possible configs except the target one
        candidate_configs = [(cat, conf) for cat, conf in self._MODEL_CATEGORY_TO_CONFIG.items() 
                           if cat != model_category]
        if model_category not in self._MODEL_CATEGORY_TO_CONFIG:
            candidate_configs.append(("default", self._DEFAULT_CONFIG))
        
        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_category, candidate_config = candidate_configs[random_index]
        
        return target_config, candidate_category, candidate_config

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample a hardware configuration if not specified
        if self.hardware_config is None:
            random_index = self.random.randint(0, len(self.all_hardware_configs) - 1)
            self.hardware_config = self.all_hardware_configs[random_index]
        self.model_category = self.hardware_config["template_record"]["model_category"]
        self.hardware_sys_id = self.hardware_config["template_record"]["sys_id"]
        self.assigned_to = self.hardware_config["template_record"]["assigned_to"]

        # Get the target and candidate configurations
        target_config, candidate_category, candidate_config = self._get_target_and_candidate_configs(self.model_category)

        # Create the target task instance
        target_task = EditHardwareAssetTask(
            instance=self.instance,
            record_sys_id=self.hardware_sys_id,
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditHardwareAssetTask(
            instance=self.instance,
            record_sys_id=self.hardware_sys_id,
            new_values=candidate_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        edit_hardware_subtask = [
            # Navigate to the hardware asset list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Asset",
                    "module": "Portfolios > Hardware Assets",
                    "url": "/now/nav/ui/classic/params/target/alm_hardware_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Filter hardware list by assigned user
            FilterHardwareListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["assigned_to"],
                    "filter_kind": "AND",
                    "filter_values": [f"{self.assigned_to}"],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the hardware model category is {self.model_category}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the hardware model category is {candidate_category}, ",
            ),
        ]

        return edit_hardware_subtask

    def teardown(self) -> None:
        # No cleanup needed as hardware assets are managed by the system
        super().teardown()


class EditProblemConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing problems based on their impact."""

    _IMPACT_TO_CONFIG = {
        "1 - High": {"assigned_to": "", "priority": "1 - Critical"},
        "2 - Medium": {"assigned_to": "", "priority": "2 - High"},
        "3 - Low": {"assigned_to": "", "priority": "3 - Medium"},
    }

    _DEFAULT_CONFIG = {"assigned_to": "", "priority": "4 - Low"}

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits problems differently based on their impact.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Editing problems"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.all_problem_configs = EditProblemTask.all_configs()
        self.task_description = None
        self.short_description = None
        self.problem_config = None
        self.impact = None
        self.problem_sys_id = None
        self.assigned_to = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()
        
        # Get the task description
        self.short_description = f"Edit problem {self.problem_config['template_record']['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the problem based on its impact: \n'
        
        if self.level == 2:
            self.task_description += (
                f"\nFor {self.impact} impact problems:\n"
                f"- Set priority to {self._IMPACT_TO_CONFIG.get(self.impact, self._DEFAULT_CONFIG)['priority']}\n"
                f"- Remove assigned user\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_target_and_candidate_configs(self, impact):
        # Get the target config and a random candidate config
        target_config = self._IMPACT_TO_CONFIG.get(impact, self._DEFAULT_CONFIG)
        
        # Get all possible configs except the target one
        candidate_configs = [(imp, conf) for imp, conf in self._IMPACT_TO_CONFIG.items() 
                           if imp != impact]
        if impact not in self._IMPACT_TO_CONFIG:
            candidate_configs.append(("default", self._DEFAULT_CONFIG))
        
        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_impact, candidate_config = candidate_configs[random_index]
        
        return target_config, candidate_impact, candidate_config

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample a problem configuration if not specified
        if self.problem_config is None:
            random_index = self.random.randint(0, len(self.all_problem_configs) - 1)
            self.problem_config = self.all_problem_configs[random_index]
        self.impact = self.problem_config["template_record"]["impact"]
        self.problem_sys_id = self.problem_config["template_record"]["sys_id"]
        self.assigned_to = self.problem_config["template_record"]["assigned_to"]

        # Get the target and candidate configurations
        target_config, candidate_impact, candidate_config = self._get_target_and_candidate_configs(self.impact)

        # Create the target task instance
        target_task = EditProblemTask(
            instance=self.instance,
            record_sys_id=self.problem_sys_id,
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditProblemTask(
            instance=self.instance,
            record_sys_id=self.problem_sys_id,
            new_values=candidate_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        edit_problem_subtask = [
            # Navigate to the problem list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Problem",
                    "module": "Open",
                    "url": "/now/nav/ui/classic/params/target/problem_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Filter problem list by assigned user
            FilterProblemListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["assigned_to"],
                    "filter_kind": "AND",
                    "filter_values": [f"{self.assigned_to}"],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the problem impact is {self.impact}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the problem impact is {candidate_impact}, ",
            ),
        ]

        return edit_problem_subtask

    def teardown(self) -> None:
        # No cleanup needed as problems are managed by the system
        super().teardown()


class EditIncidentConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing incidents based on their priority."""

    _PRIORITY_TO_CONFIG = {
        "1 - Critical": {"assigned_to": "", "state": "2 - In Progress"},
        "2 - High": {"assigned_to": "", "state": "1 - New"},
        "3 - Medium": {"assigned_to": "", "state": "1 - New"},
        "4 - Low": {"assigned_to": "", "state": "1 - New"},
    }

    _DEFAULT_CONFIG = {"assigned_to": "", "state": "1 - New"}

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits incidents differently based on their priority.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Editing incidents"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.all_incident_configs = EditIncidentTask.all_configs()
        self.task_description = None
        self.short_description = None
        self.incident_config = None
        self.priority = None
        self.incident_sys_id = None
        self.assigned_to = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()
        
        # Get the task description
        self.short_description = f"Edit incident {self.incident_config['template_record']['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the incident based on its priority: \n'
        
        if self.level == 2:
            self.task_description += (
                f"\nFor {self.priority} priority incidents:\n"
                f"- Set state to {self._PRIORITY_TO_CONFIG.get(self.priority, self._DEFAULT_CONFIG)['state']}\n"
                f"- Remove assigned user\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_target_and_candidate_configs(self, priority):
        # Get the target config and a random candidate config
        target_config = self._PRIORITY_TO_CONFIG.get(priority, self._DEFAULT_CONFIG)
        
        # Get all possible configs except the target one
        candidate_configs = [(pri, conf) for pri, conf in self._PRIORITY_TO_CONFIG.items() 
                           if pri != priority]
        if priority not in self._PRIORITY_TO_CONFIG:
            candidate_configs.append(("default", self._DEFAULT_CONFIG))
        
        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_priority, candidate_config = candidate_configs[random_index]
        
        return target_config, candidate_priority, candidate_config

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample an incident configuration if not specified
        if self.incident_config is None:
            random_index = self.random.randint(0, len(self.all_incident_configs) - 1)
            self.incident_config = self.all_incident_configs[random_index]
        self.priority = self.incident_config["template_record"]["priority"]
        self.incident_sys_id = self.incident_config["template_record"]["sys_id"]
        self.assigned_to = self.incident_config["template_record"]["assigned_to"]

        # Get the target and candidate configurations
        target_config, candidate_priority, candidate_config = self._get_target_and_candidate_configs(self.priority)

        # Create the target task instance
        target_task = EditIncidentTask(
            instance=self.instance,
            record_sys_id=self.incident_sys_id,
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditIncidentTask(
            instance=self.instance,
            record_sys_id=self.incident_sys_id,
            new_values=candidate_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        edit_incident_subtask = [
            # Navigate to the incident list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Incident",
                    "module": "Open",
                    "url": "/now/nav/ui/classic/params/target/incident_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Filter incident list by assigned user
            FilterIncidentListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["assigned_to"],
                    "filter_kind": "AND",
                    "filter_values": [f"{self.assigned_to}"],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the incident priority is {self.priority}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the incident priority is {candidate_priority}, ",
            ),
        ]

        return edit_incident_subtask

    def teardown(self) -> None:
        # No cleanup needed as incidents are managed by the system
        super().teardown()


class EditChangeRequestScheduleConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing change request schedules based on their risk level."""

    _RISK_TO_CONFIG = {
        "1 - High": {"start_date": "2024-03-20", "end_date": "2024-03-23"},  # 3 days
        "2 - Medium": {"start_date": "2024-03-20", "end_date": "2024-03-22"},  # 2 days
        "3 - Low": {"start_date": "2024-03-20", "end_date": "2024-03-21"},  # 1 day
    }

    _DEFAULT_CONFIG = {"start_date": "2024-03-20", "end_date": "2024-03-21"}  # 1 day default

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits change request schedules differently based on their risk level.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Editing change request schedules"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.all_change_configs = EditChangeRequestScheduleTask.all_configs()
        self.task_description = None
        self.short_description = None
        self.change_config = None
        self.risk = None
        self.change_sys_id = None
        self.assigned_to = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()
        
        # Get the task description
        self.short_description = f"Edit change request {self.change_config['template_record']['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the change request schedule based on its risk level: \n'
        
        if self.level == 2:
            self.task_description += (
                f"\nFor {self.risk} risk change requests:\n"
                f"- Set start date to {self._RISK_TO_CONFIG.get(self.risk, self._DEFAULT_CONFIG)['start_date']}\n"
                f"- Set end date to {self._RISK_TO_CONFIG.get(self.risk, self._DEFAULT_CONFIG)['end_date']}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_target_and_candidate_configs(self, risk):
        # Get the target config and a random candidate config
        target_config = self._RISK_TO_CONFIG.get(risk, self._DEFAULT_CONFIG)
        
        # Get all possible configs except the target one
        candidate_configs = [(r, conf) for r, conf in self._RISK_TO_CONFIG.items() 
                           if r != risk]
        if risk not in self._RISK_TO_CONFIG:
            candidate_configs.append(("default", self._DEFAULT_CONFIG))
        
        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_risk, candidate_config = candidate_configs[random_index]
        
        return target_config, candidate_risk, candidate_config

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample a change request configuration if not specified
        if self.change_config is None:
            random_index = self.random.randint(0, len(self.all_change_configs) - 1)
            self.change_config = self.all_change_configs[random_index]
        self.risk = self.change_config["template_record"]["risk"]
        self.change_sys_id = self.change_config["template_record"]["sys_id"]
        self.assigned_to = self.change_config["template_record"]["assigned_to"]

        # Get the target and candidate configurations
        target_config, candidate_risk, candidate_config = self._get_target_and_candidate_configs(self.risk)

        # Create the target task instance
        target_task = EditChangeRequestScheduleTask(
            instance=self.instance,
            record_sys_id=self.change_sys_id,
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditChangeRequestScheduleTask(
            instance=self.instance,
            record_sys_id=self.change_sys_id,
            new_values=candidate_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        edit_change_subtask = [
            # Navigate to the change request list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Change",
                    "module": "Open",
                    "url": "/now/nav/ui/classic/params/target/change_request_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Filter change request list by assigned user
            FilterChangeRequestListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["assigned_to"],
                    "filter_kind": "AND",
                    "filter_values": [f"{self.assigned_to}"],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the change request risk is {self.risk}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the change request risk is {candidate_risk}, ",
            ),
        ]

        return edit_change_subtask

    def teardown(self) -> None:
        # No cleanup needed as change requests are managed by the system
        super().teardown()


local_vars = locals().copy()

__TASKS__ = [OnBoardUserConditionalTask, EditHardwareConditionalTask, EditProblemConditionalTask, EditIncidentConditionalTask, EditChangeRequestScheduleConditionalTask]
