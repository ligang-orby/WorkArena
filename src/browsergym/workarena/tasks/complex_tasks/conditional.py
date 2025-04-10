import json

import playwright.sync_api
from playwright.sync_api._generated import Page

from browsergym.workarena.tasks.navigation import AllMenuTask

from ..compositional.base import CompositionalTask, HumanEvalTask
from ..compositional.base import AbstractServiceNowTask
from ...instance import SNowInstance
from ..form import (
    CreateUserTask,
    EditHardwareAssetTask,
    EditRecordTask,
    EditIncidentTask,
)
from ..list import FilterHardwareListTask, FilterIncidentListTask, FilterChangeRequestListTask
from ..service_catalog import (
    OrderAppleMacBookPro15Task,
    OrderDevelopmentLaptopPCTask,
    OrderStandardLaptopTask,
    OrderSalesLaptopTask,
)
from faker import Faker
from ...api.utils import table_api_call
from .comparison import FilterProblemListTask
from ...config import (
    EXPECTED_PROBLEM_FORM_FIELDS_PATH,
    EXPECTED_CHANGE_REQUEST_FORM_FIELDS_PATH,
)

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
        self.short_description = (
            f"Edit hardware asset {self.hardware_config['template_record']['asset_tag']}"
        )
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
        candidate_configs = [
            (cat, conf)
            for cat, conf in self._MODEL_CATEGORY_TO_CONFIG.items()
            if cat != model_category
        ]
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
        target_config, candidate_category, candidate_config = (
            self._get_target_and_candidate_configs(self.model_category)
        )

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


class EditProblemTask(EditRecordTask):
    """
    Task to edit a problem in the system.
    We re-define this class for correct task description.
    TODO: merged with the original EditProblemTask.
    """

    expected_fields_path = EXPECTED_PROBLEM_FORM_FIELDS_PATH

    def __init__(
        self,
        seed: int = None,
        instance=None,
        fixed_config: dict = None,
        new_values: dict = None,
        record_sys_id: str = None,
        record_number: str = None,
        **kwargs,
    ) -> None:
        super().__init__(
            seed=seed,
            instance=instance,
            form_url="/now/nav/ui/classic/params/target/problem.do",
            table_label="problem",
            prohibited_fields=["state", "first_reported_by_task"],
            new_values=new_values,
            fixed_config=fixed_config,
            record_sys_id=record_sys_id,
            record_number=record_number,
        )
        if self.new_values is None:
            self.new_values = {"assigned_to": ""}
        self.__dict__.update(kwargs)

    def get_pretty_printed_description(self) -> str:
        """
        Get the task info for this task when used in a private task; Used in L3 compositional tasks.
        """
        if self.level == 2:
            description = "Edit the problem record with the following values:\n"
            for key, value in self.new_values.items():
                description += f"- Set {key} to {value}\n"
            return description
        else:
            return ""


class EditProblemConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing problems based on their urgency."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits problems differently based on their urgency.

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
        # Need self.random to be initialized before calling _create_random_urgency_to_impact.
        self._URGENCY_TO_IMPACT = self._create_random_urgency_to_impact()
        self.task_description = fake.sentence()
        self.short_description = fake.sentence()
        self.cause = fake.sentence()
        self.problem_config = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Edit problem {self.problem_config['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the problem based on its urgency: \n'

        if self.level == 2:
            self.task_description += "Set task impact based on urgency"

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _create_random_urgency_to_impact(self):
        # Create a random urgency to impact mapping
        urgency_to_impact = {}
        for urgency in range(1, 4):
            impact = self.random.randint(1, 3)
            urgency_to_impact[urgency] = impact
        return urgency_to_impact

    def _get_target_and_candidate_configs(self):
        # Sample a random urgency level
        urgency = self.random.choice(list(self._URGENCY_TO_IMPACT.keys()))

        # Get the target config based on urgency
        target_impact = self._URGENCY_TO_IMPACT[urgency]
        # Work notes is a required field, so we need to add a placeholder value.
        target_config = {"impact": target_impact, "work_notes": "Update impact"}

        # Get all possible configs except the target one
        candidate_configs = [
            (urg, imp) for urg, imp in self._URGENCY_TO_IMPACT.items() if urg != urgency
        ]
        if not candidate_configs:
            candidate_configs.append((3, 3))

        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_urgency, candidate_impact = candidate_configs[random_index]
        # Work notes is a required field, so we need to add a placeholder value.
        candidate_config = {"impact": candidate_impact, "work_notes": "Update impact"}

        return target_config, urgency, candidate_config, candidate_urgency

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Get the target and candidate configurations
        target_config, target_urgency, candidate_config, candidate_urgency = (
            self._get_target_and_candidate_configs()
        )

        problem_record = {
            "made_sla": True,
            "upon_reject": "cancel",
            "cause_notes": f" <p>{self.cause}</p> ",
            "fix_notes": " placeholder ",  # placeholder value - will not work without a fix note
            "knowledge": False,
            "major_problem": False,
            "sys_domain_path": "/",
            "short_description": self.short_description,
            "known_error": False,
            "description": self.task_description,
            "closed_at": "",
            "resolution_code": "fix_applied",
            "active": True,
            "impact": 3,  # random impact as we want to change it later.
            "urgency": int(target_urgency),
        }

        result = table_api_call(
            instance=self.instance,
            table="problem",
            json=problem_record,
            method="POST",
        )["result"]
        self.problem_config = result

        # Create the target task instance
        target_task = EditProblemTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditProblemTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
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
            # Filter problem list by problem number
            FilterProblemListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "AND",
                    "filter_values": [result["number"]],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the problem urgency is {target_urgency}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the problem urgency is {candidate_urgency}, ",
            ),
        ]

        return edit_problem_subtask

    def teardown(self) -> None:
        # No cleanup needed as problems are managed by the system
        super().teardown()


class EditIncidentConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing incidents based on their urgency."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits incidents differently based on their urgency.

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
        # Need self.random to be initialized.
        self._URGENCY_TO_STATE = self._create_random_urgency_to_state()
        self.task_description = fake.sentence()
        self.short_description = fake.sentence()
        self.incident_config = None
        self.urgency = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Edit incident {self.incident_config['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the incident based on its urgency: \n'

        if self.level == 2:
            self.task_description += (
                f"\nFor urgency {self.urgency} incidents:\n"
                f"- Set state to {self._URGENCY_TO_STATE[self.urgency]}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _create_random_urgency_to_state(self):
        # Create a random urgency to state mapping
        urgency_to_state = {}
        states = ["New", "In Progress", "On Hold", "Resolved", "Closed", "Canceled"]
        for urgency in range(1, 4):
            state = self.random.choice(states)
            urgency_to_state[urgency] = state
        return urgency_to_state

    def _get_target_and_candidate_configs(self, urgency):
        # Get the target config based on urgency
        target_state = self._URGENCY_TO_STATE[urgency]
        target_config = {"state": target_state}

        # Get all possible configs except the target one
        candidate_configs = [
            (urg, state) for urg, state in self._URGENCY_TO_STATE.items() if urg != urgency
        ]
        if not candidate_configs:
            candidate_configs.append((3, "New"))

        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_urgency, candidate_state = candidate_configs[random_index]
        candidate_config = {"state": candidate_state}

        return target_config, candidate_config, candidate_urgency

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample a random urgency level
        self.urgency = self.random.choice(list(self._URGENCY_TO_STATE.keys()))

        # Get the target and candidate configurations
        target_config, candidate_config, candidate_urgency = self._get_target_and_candidate_configs(
            self.urgency
        )

        # Generate a unique incident number
        incident_number = "INC" + str(self.random.randint(1000000, 9999999))

        incident_record = {
            "task_effective_number": incident_number,
            "number": incident_number,
            "state": 2,
            "knowledge": False,
            "impact": 3,
            "active": True,
            "priority": 3,
            "caller_id": self._base_user_sysid,
            "short_description": " ".join(fake.words(5)),
            "description": " ".join(fake.words(10)),
            "incident_state": int(self.random.choice(range(1, 7))),
            "urgency": int(self.urgency),
            "severity": 3,
            "category": "software",
        }

        result = table_api_call(
            instance=self.instance,
            table="incident",
            json=incident_record,
            method="POST",
        )["result"]
        self.incident_config = result

        # Create the target task instance
        target_task = EditIncidentTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditIncidentTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
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
            # Filter incident list by incident number
            FilterIncidentListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "AND",
                    "filter_values": [result["number"]],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the incident urgency is {self.urgency}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the incident urgency is {candidate_urgency}, ",
            ),
        ]

        return edit_incident_subtask

    def teardown(self) -> None:
        # No cleanup needed as incidents are managed by the system
        super().teardown()


class EditChangeRequestScheduleTask(EditRecordTask):
    """
    Task to edit a change request in the system.
    We re-define this class for correct task description.
    TODO: merged with the original EditChangeRequestTask.
    """

    expected_fields_path = EXPECTED_CHANGE_REQUEST_FORM_FIELDS_PATH

    def __init__(
        self,
        seed: int = None,
        instance=None,
        fixed_config: dict = None,
        new_values: dict = None,
        record_sys_id: str = None,
        record_number: str = None,
        **kwargs,
    ) -> None:
        super().__init__(
            seed=seed,
            instance=instance,
            form_url="/now/nav/ui/classic/params/target/change_request.do",
            table_label="change_request",
            prohibited_fields=["state", "first_reported_by_task"],
            new_values=new_values,
            fixed_config=fixed_config,
            record_sys_id=record_sys_id,
            record_number=record_number,
        )
        if self.new_values is None:
            self.new_values = {"impact": 3}
        self.__dict__.update(kwargs)

    def get_pretty_printed_description(self) -> str:
        """
        Get the task info for this task when used in a private task; Used in L3 compositional tasks.
        """
        if self.level == 2:
            description = "Edit the change request record with the following values:\n"
            for key, value in self.new_values.items():
                description += f"- Set {key} to {value}\n"
            return description
        else:
            return ""


class EditChangeRequestScheduleConditionalTask(CompositionalTask, HumanEvalTask):
    """Conditional task for editing change requests based on their category."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
    ) -> None:
        """
        Create a task that edits change requests differently based on their category.

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
        self.protocol_name = "Editing change requests"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        # Need self.random to be initialized.
        self._CATEGORY_TO_IMPACT = self._create_random_category_to_impact()
        self.task_description = fake.sentence()
        self.short_description = fake.sentence()
        self.change_config = None
        self.category = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Edit change request {self.change_config['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", edit the change request based on its category: \n'

        if self.level == 2:
            self.task_description += (
                f"\nFor {self.category} change requests:\n"
                f"- Set impact to {self._CATEGORY_TO_IMPACT[self.category]}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _create_random_category_to_impact(self):
        # Create a random category to impact mapping
        category_to_impact = {}
        categories = [
            "Hardware",
            "Software",
            "Service",
            "System Software",
            "Applications Software",
            "Network",
            "Telecom",
            "Documentation",
            "Other",
            "Server Reboot",
        ]
        for category in categories:
            impact = self.random.randint(1, 3)
            category_to_impact[category] = impact
        return category_to_impact

    def _get_target_and_candidate_configs(self, category):
        # Get the target config based on category
        target_impact = self._CATEGORY_TO_IMPACT[category]
        target_config = {"impact": target_impact}

        # Get all possible configs except the target one
        candidate_configs = [
            (cat, imp) for cat, imp in self._CATEGORY_TO_IMPACT.items() if cat != category
        ]
        if not candidate_configs:
            candidate_configs.append(("Other", 3))

        # Choose a random candidate
        random_index = self.random.randint(0, len(candidate_configs) - 1)
        candidate_category, candidate_impact = candidate_configs[random_index]
        candidate_config = {"impact": candidate_impact}

        return target_config, candidate_config, candidate_category

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Sample a random category
        self.category = self.random.choice(list(self._CATEGORY_TO_IMPACT.keys()))

        # Get the target and candidate configurations
        target_config, candidate_config, candidate_category = (
            self._get_target_and_candidate_configs(self.category)
        )

        # Generate a unique change request number
        change_number = "CHG" + str(self.random.randint(1000000, 9999999))
        change_record = {
            "number": change_number,
            "short_description": " ".join(fake.words(5)),
            "description": " ".join(fake.words(10)),
            "category": self.category,
            "impact": self.random.randint(
                1, 3
            ),  # Default impact, will be changed based on category
            "type": "normal",
            "state": "new",
            "start_date": "2024-03-20",
            "end_date": "2024-03-21",
            "risk": "low",
            "active": True,
        }

        result = table_api_call(
            instance=self.instance,
            table="change_request",
            json=change_record,
            method="POST",
        )["result"]
        self.change_config = result

        # Create the target task instance
        target_task = EditChangeRequestScheduleTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
            new_values=target_config,
            is_validated=True,
            used_in_level_2=True,
            level=self.level,
        )

        # Create the candidate task instance
        candidate_task = EditChangeRequestScheduleTask(
            instance=self.instance,
            record_sys_id=result["sys_id"],
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
            # Filter change request list by change number
            FilterChangeRequestListTask(
                instance=self.instance,
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "AND",
                    "filter_values": [result["number"]],
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Conditional task with the target task as the true branch and the candidate task as the false branch
            ConditionalTask(
                true_branch_task=target_task,
                true_branch_prefix=f"If the change request category is {self.category}, ",
                false_branch_task=candidate_task,
                false_branch_prefix=f"If the change request category is {candidate_category}, ",
            ),
        ]

        return edit_change_subtask

    def teardown(self) -> None:
        # No cleanup needed as change requests are managed by the system
        super().teardown()


local_vars = locals().copy()

__TASKS__ = [
    OnBoardUserConditionalTask,
    EditHardwareConditionalTask,
    EditProblemConditionalTask,
    EditIncidentConditionalTask,
    EditChangeRequestScheduleConditionalTask,
]
