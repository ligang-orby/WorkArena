import json
from uuid import uuid4
from faker import Faker

from playwright.sync_api._generated import Page
from ..compositional.base import CompositionalTask, HumanEvalTask
from ..compositional.base import AbstractServiceNowTask
from ...instance import SNowInstance
from ..list import FilterHardwareListTask, FilterChangeRequestListTask, FilterListTask
from ..navigation import AllMenuTask
from ..form import (
    CreateHardwareAssetTask,
    CreateChangeRequestTask,
    CreateProblemTask,
    CreateIncidentTask,
)
from ...api.utils import table_api_call
from ...api.expense_line import create_expense_line
from ...config import (
    EXPECTED_PROBLEM_COLUMNS_PATH,
    EXPECTED_INCIDENT_COLUMNS_PATH,
    EXPECTED_EXPENSE_LINE_COLUMNS_PATH,
)

fake = Faker()


class FilterProblemListTask(FilterListTask):
    """Task for filtering problem list."""

    def __init__(
        self,
        seed: int = None,
        instance=None,
        fixed_config: dict = None,
        **kwargs,
    ) -> None:
        super().__init__(
            seed=seed,
            instance=instance,
            list_url="/now/nav/ui/classic/params/target/problem_list.do",
            fixed_config=fixed_config,
            expected_fields_path=EXPECTED_PROBLEM_COLUMNS_PATH,
            **kwargs,
        )


class FilterIncidentListTask(FilterListTask):
    """Task for filtering incident list."""

    def __init__(
        self,
        seed: int = None,
        instance=None,
        fixed_config: dict = None,
        **kwargs,
    ) -> None:
        super().__init__(
            seed=seed,
            instance=instance,
            list_url="/now/nav/ui/classic/params/target/incident_list.do",
            fixed_config=fixed_config,
            expected_fields_path=EXPECTED_INCIDENT_COLUMNS_PATH,
            **kwargs,
        )


class FilterExpenseLineListTask(FilterListTask):
    """Task for filtering expense line list."""

    def __init__(
        self,
        seed: int = None,
        instance=None,
        fixed_config: dict = None,
        **kwargs,
    ) -> None:
        super().__init__(
            seed=seed,
            instance=instance,
            list_url="/now/nav/ui/classic/params/target/fm_expense_line_list.do",
            fixed_config=fixed_config,
            expected_fields_path=EXPECTED_EXPENSE_LINE_COLUMNS_PATH,
            **kwargs,
        )


class CompareHardwareDate(CompositionalTask, HumanEvalTask):
    """Task for comparing purchase dates of two hardware assets."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        earlier: bool = True,
    ) -> None:
        """
        Create a task that compares purchase dates of two hardware assets.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        earlier: bool
            If True, find the hardware purchased earlier. If False, find the hardware purchased later.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Comparing hardware purchase dates"
        self.earlier = earlier
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.hardware1 = None
        self.hardware2 = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Find {'earlier' if self.earlier else 'later'} purchased hardware between {self.hardware1['serial_number']} and {self.hardware2['serial_number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", find the hardware asset that was purchased {"earlier" if self.earlier else "later"} between the following two assets:\n'

        if self.level == 2:
            self.task_description += (
                f"\nHardware 1:\n"
                f"- Serial Number: {self.hardware1['serial_number']}\n"
                f"- Model: {self.hardware1['model']}\n"
                f"- Purchase Date: {self.hardware1['purchase_date']}\n"
                f"\nHardware 2:\n"
                f"- Serial Number: {self.hardware2['serial_number']}\n"
                f"- Model: {self.hardware2['model']}\n"
                f"- Purchase Date: {self.hardware2['purchase_date']}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Get hardware configurations
        hardware_configs = CreateHardwareAssetTask.all_configs()
        # Filter out configs without purchase dates
        hardware_configs = [
            config for config in hardware_configs if config["template_record"]["purchase_date"]
        ]

        # Sample two different hardware configurations
        index = self.random.choice(len(hardware_configs))
        hardware1_config = hardware_configs[index]
        remaining_configs = [c for c in hardware_configs if c != hardware1_config]
        index = self.random.choice(len(remaining_configs))
        hardware2_config = remaining_configs[index]

        # Create hardware records using table_api_call
        unique_id = uuid4()
        serial_number = f"SN-{unique_id}"
        hardware1_config = {
            "assigned_to": hardware1_config["template_record"]["assigned_to"],
            "asset_tag": hardware1_config["template_record"]["asset_tag"],
            "display_name": hardware1_config["template_record"]["display_name"],
            "model": hardware1_config["template_record"]["model"],
            "model_category": hardware1_config["template_record"]["model_category"],
            "warranty_expiration": hardware1_config["template_record"]["warranty_expiration"],
            "purchase_date": hardware1_config["template_record"]["purchase_date"],
            "serial_number": serial_number,
        }

        unique_id = uuid4()
        serial_number = f"SN-{unique_id}"
        hardware2_config = {
            "assigned_to": hardware2_config["template_record"]["assigned_to"],
            "asset_tag": hardware2_config["template_record"]["asset_tag"],
            "display_name": hardware2_config["template_record"]["display_name"],
            "model": hardware2_config["template_record"]["model"],
            "model_category": hardware2_config["template_record"]["model_category"],
            "purchase_date": hardware2_config["template_record"]["purchase_date"],
            "serial_number": serial_number,
        }
        hardware1_record = table_api_call(
            instance=self.instance,
            table="alm_hardware",
            method="POST",
            data=json.dumps(hardware1_config),
        )
        hardware2_record = table_api_call(
            instance=self.instance,
            table="alm_hardware",
            method="POST",
            data=json.dumps(hardware2_config),
        )

        # Create tasks for comparing hardware assets
        tasks = [
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
            # Filter for first hardware
            FilterHardwareListTask(
                instance=self.instance,
                list_name="alm_hardware",
                fixed_config={
                    "filter_columns": ["serial_number"],
                    "filter_kind": "",
                    "filter_values": [hardware1_record["result"]["serial_number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
            # Filter for second hardware
            FilterHardwareListTask(
                instance=self.instance,
                list_name="alm_hardware",
                fixed_config={
                    "filter_columns": ["serial_number"],
                    "filter_kind": "",
                    "filter_values": [hardware2_record["result"]["serial_number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Store hardware info for task description
        self.hardware1 = hardware1_record["result"]
        self.hardware2 = hardware2_record["result"]

        return tasks

    def teardown(self) -> None:
        # No cleanup needed as we're just comparing data
        super().teardown()

    def _get_selected_hardware(self) -> dict:
        """Helper method to get the selected hardware based on purchase dates.

        Returns:
        --------
        dict
            The hardware record that was purchased earlier/later based on self.earlier
        """
        date1 = self.hardware1["purchase_date"]
        date2 = self.hardware2["purchase_date"]

        if self.earlier:
            return self.hardware1 if date1 < date2 else self.hardware2
        else:
            return self.hardware1 if date1 > date2 else self.hardware2

    def cheat(self, page: Page, chat_messages: list[str], subtask_idx: int = None) -> None:
        # Perform default cheat actions from parent class
        super().cheat(page, chat_messages, subtask_idx)

        # Only send the chat message if we're at the last subtask
        if subtask_idx is None or subtask_idx == len(self.subtasks) - 1:
            # Get the selected hardware based on purchase dates
            selected_hardware = self._get_selected_hardware()

            # Send a chat message with the selected hardware's serial number
            message = f"The hardware with serial number {selected_hardware['serial_number']} was purchased {'earlier' if self.earlier else 'later'} on {selected_hardware['purchase_date']}."
            chat_messages.append({"role": "assistant", "message": message})

    def validate(self, page: Page, chat_messages: list[str]) -> tuple[float, bool, str, dict]:
        # Get the correct hardware based on purchase dates
        correct_hardware = self._get_selected_hardware()

        # Check if any chat message contains both the correct serial number and date
        correct_serial = correct_hardware["serial_number"]
        correct_date = correct_hardware["purchase_date"]
        found_serial = False
        found_date = False

        for message in chat_messages:
            if isinstance(message, dict):
                message_text = message.get("message", "")
            else:
                message_text = message

            if correct_serial in message_text:
                found_serial = True
            if correct_date in message_text:
                found_date = True

        # Return validation results
        if found_serial and found_date:
            return 1.0, True, "Correct hardware serial number and date identified.", {}
        elif found_serial:
            return 0.5, False, "Hardware serial number found but date not mentioned.", {}
        elif found_date:
            return 0.5, False, "Purchase date found but hardware serial number not mentioned.", {}
        else:
            return 0.0, False, "Neither hardware serial number nor date were mentioned.", {}


class CompareChangeRequestPriority(CompositionalTask, HumanEvalTask):
    """Task for comparing priorities of two change requests."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        higher: bool = True,
    ) -> None:
        """
        Create a task that compares priorities of two change requests.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        higher: bool
            If True, find the change request with higher priority. If False, find the one with lower priority.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Comparing change request priorities"
        self.higher = higher
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.change1 = None
        self.change2 = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Find {'higher' if self.higher else 'lower'} priority change request between {self.change1['number']} and {self.change2['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", find the change request that has {"higher" if self.higher else "lower"} priority between the following two requests:\n'

        if self.level == 2:
            self.task_description += (
                f"\nChange Request 1:\n"
                f"- Number: {self.change1['number']}\n"
                f"- Short Description: {self.change1['short_description']}\n"
                f"- Priority: {self.change1['priority']}\n"
                f"\nChange Request 2:\n"
                f"- Number: {self.change2['number']}\n"
                f"- Short Description: {self.change2['short_description']}\n"
                f"- Priority: {self.change2['priority']}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Get change request configurations
        change_configs = CreateChangeRequestTask.all_configs()
        # Filter out configs without priority
        change_configs = [
            config for config in change_configs if config["template_record"]["priority"]
        ]

        # Sample two different change request configurations
        index = self.random.choice(len(change_configs))
        change1_config = change_configs[index]
        remaining_configs = [c for c in change_configs if c != change1_config]
        index = self.random.choice(len(remaining_configs))
        change2_config = remaining_configs[index]

        # Create change request records using table_api_call
        unique_id = uuid4()
        number = f"CHG{unique_id}"
        change1_config = {
            "short_description": change1_config["template_record"]["short_description"],
            "description": change1_config["template_record"]["description"],
            "priority": change1_config["template_record"]["priority"],
            "risk": change1_config["template_record"]["risk"],
            "type": change1_config["template_record"]["type"],
            "number": number,
        }

        unique_id = uuid4()
        number = f"CHG{unique_id}"
        change2_config = {
            "short_description": change2_config["template_record"]["short_description"],
            "description": change2_config["template_record"]["description"],
            "priority": change2_config["template_record"]["priority"],
            "risk": change2_config["template_record"]["risk"],
            "type": change2_config["template_record"]["type"],
            "number": number,
        }

        change1_record = table_api_call(
            instance=self.instance,
            table="change_request",
            method="POST",
            data=json.dumps(change1_config),
        )
        change2_record = table_api_call(
            instance=self.instance,
            table="change_request",
            method="POST",
            data=json.dumps(change2_config),
        )

        # Create tasks for comparing change requests
        tasks = [
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
            # Filter for first change request
            FilterChangeRequestListTask(
                instance=self.instance,
                list_name="change_request",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [change1_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
            # Filter for second change request
            FilterChangeRequestListTask(
                instance=self.instance,
                list_name="change_request",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [change2_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Store change request info for task description
        self.change1 = change1_record["result"]
        self.change2 = change2_record["result"]

        return tasks

    def _get_selected_change(self) -> dict:
        """Helper method to get the selected change request based on priorities.

        Returns:
        --------
        dict
            The change request record that has higher/lower priority based on self.higher
        """
        # In ServiceNow, lower priority number means higher priority (1 is highest, 5 is lowest)
        priority1 = int(self.change1["priority"])
        priority2 = int(self.change2["priority"])

        if self.higher:
            return self.change1 if priority1 < priority2 else self.change2
        else:
            return self.change1 if priority1 > priority2 else self.change2

    def cheat(self, page: Page, chat_messages: list[str], subtask_idx: int = None) -> None:
        # Perform default cheat actions from parent class
        super().cheat(page, chat_messages, subtask_idx)

        # Only send the chat message if we're at the last subtask
        if subtask_idx is None or subtask_idx == len(self.subtasks) - 1:
            # Get the selected change request based on priorities
            selected_change = self._get_selected_change()

            # Send a chat message with the selected change request's number
            message = f"The change request {selected_change['number']} has {'higher' if self.higher else 'lower'} priority with priority level {selected_change['priority']}."
            chat_messages.append({"role": "assistant", "message": message})

    def validate(self, page: Page, chat_messages: list[str]) -> tuple[float, bool, str, dict]:
        # Get the correct change request based on priorities
        correct_change = self._get_selected_change()

        # Check if any chat message contains both the correct number and priority
        correct_number = correct_change["number"]
        correct_priority = correct_change["priority"]
        found_number = False
        found_priority = False

        for message in chat_messages:
            if isinstance(message, dict):
                message_text = message.get("message", "")
            else:
                message_text = message

            if correct_number in message_text:
                found_number = True
            if str(correct_priority) in message_text:
                found_priority = True

        # Return validation results
        if found_number and found_priority:
            return 1.0, True, "Correct change request number and priority identified.", {}
        elif found_number:
            return 0.5, False, "Change request number found but priority not mentioned.", {}
        elif found_priority:
            return 0.5, False, "Priority found but change request number not mentioned.", {}
        else:
            return 0.0, False, "Neither change request number nor priority were mentioned.", {}


class CompareProblemPriority(CompositionalTask, HumanEvalTask):
    """Task for comparing priorities of two problems."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        higher: bool = True,
    ) -> None:
        """
        Create a task that compares priorities of two problems.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        higher: bool
            If True, find the problem with higher priority. If False, find the one with lower priority.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Comparing problem priorities"
        self.higher = higher
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.problem1 = None
        self.problem2 = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Find {'higher' if self.higher else 'lower'} priority problem between {self.problem1['number']} and {self.problem2['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", find the problem that has {"higher" if self.higher else "lower"} priority between the following two problems:\n'

        if self.level == 2:
            self.task_description += (
                f"\nProblem 1:\n"
                f"- Number: {self.problem1['number']}\n"
                f"- Short Description: {self.problem1['short_description']}\n"
                f"- Priority: {self.problem1['priority']}\n"
                f"\nProblem 2:\n"
                f"- Number: {self.problem2['number']}\n"
                f"- Short Description: {self.problem2['short_description']}\n"
                f"- Priority: {self.problem2['priority']}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Get problem configurations
        problem_configs = CreateProblemTask.all_configs()
        # Filter out configs without priority
        problem_configs = [
            config for config in problem_configs if config["template_record"]["priority"]
        ]

        # Sample two different problem configurations
        index = self.random.choice(len(problem_configs))
        problem1_config = problem_configs[index]
        remaining_configs = [c for c in problem_configs if c != problem1_config]
        index = self.random.choice(len(remaining_configs))
        problem2_config = remaining_configs[index]

        # Create problem records using table_api_call
        unique_id = uuid4()
        number = f"PRB{unique_id}"
        problem1_config = {
            "short_description": problem1_config["template_record"]["short_description"],
            "description": problem1_config["template_record"]["description"],
            "priority": problem1_config["template_record"]["priority"],
            "impact": problem1_config["template_record"]["impact"],
            "urgency": problem1_config["template_record"]["urgency"],
            "number": number,
        }

        unique_id = uuid4()
        number = f"PRB{unique_id}"
        problem2_config = {
            "short_description": problem2_config["template_record"]["short_description"],
            "description": problem2_config["template_record"]["description"],
            "priority": problem2_config["template_record"]["priority"],
            "impact": problem2_config["template_record"]["impact"],
            "urgency": problem2_config["template_record"]["urgency"],
            "number": number,
        }

        problem1_record = table_api_call(
            instance=self.instance,
            table="problem",
            method="POST",
            data=json.dumps(problem1_config),
        )
        problem2_record = table_api_call(
            instance=self.instance,
            table="problem",
            method="POST",
            data=json.dumps(problem2_config),
        )

        # Create tasks for comparing problems
        tasks = [
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
            # Filter for first problem
            FilterProblemListTask(
                instance=self.instance,
                list_name="problem",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [problem1_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
            # Filter for second problem
            FilterProblemListTask(
                instance=self.instance,
                list_name="problem",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [problem2_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Store problem info for task description
        self.problem1 = problem1_record["result"]
        self.problem2 = problem2_record["result"]

        return tasks

    def _get_selected_problem(self) -> dict:
        """Helper method to get the selected problem based on priorities.

        Returns:
        --------
        dict
            The problem record that has higher/lower priority based on self.higher
        """
        # In ServiceNow, lower priority number means higher priority (1 is highest, 5 is lowest)
        priority1 = int(self.problem1["priority"])
        priority2 = int(self.problem2["priority"])

        if self.higher:
            return self.problem1 if priority1 < priority2 else self.problem2
        else:
            return self.problem1 if priority1 > priority2 else self.problem2

    def cheat(self, page: Page, chat_messages: list[str], subtask_idx: int = None) -> None:
        # Perform default cheat actions from parent class
        super().cheat(page, chat_messages, subtask_idx)

        # Only send the chat message if we're at the last subtask
        if subtask_idx is None or subtask_idx == len(self.subtasks) - 1:
            # Get the selected problem based on priorities
            selected_problem = self._get_selected_problem()

            # Send a chat message with the selected problem's number
            message = f"The problem {selected_problem['number']} has {'higher' if self.higher else 'lower'} priority with priority level {selected_problem['priority']}."
            chat_messages.append({"role": "assistant", "message": message})

    def validate(self, page: Page, chat_messages: list[str]) -> tuple[float, bool, str, dict]:
        # Get the correct problem based on priorities
        correct_problem = self._get_selected_problem()

        # Check if any chat message contains both the correct number and priority
        correct_number = correct_problem["number"]
        correct_priority = correct_problem["priority"]
        found_number = False
        found_priority = False

        for message in chat_messages:
            if isinstance(message, dict):
                message_text = message.get("message", "")
            else:
                message_text = message

            if correct_number in message_text:
                found_number = True
            if str(correct_priority) in message_text:
                found_priority = True

        # Return validation results
        if found_number and found_priority:
            return 1.0, True, "Correct problem number and priority identified.", {}
        elif found_number:
            return 0.5, False, "Problem number found but priority not mentioned.", {}
        elif found_priority:
            return 0.5, False, "Priority found but problem number not mentioned.", {}
        else:
            return 0.0, False, "Neither problem number nor priority were mentioned.", {}


class CompareIncidentBusinessDuration(CompositionalTask, HumanEvalTask):
    """Task for comparing business durations of two incidents."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        longer: bool = True,
    ) -> None:
        """
        Create a task that compares business durations of two incidents.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        longer: bool
            If True, find the incident with longer business duration. If False, find the one with shorter duration.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Comparing incident business durations"
        self.longer = longer
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.incident1 = None
        self.incident2 = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Find {'longer' if self.longer else 'shorter'} business duration incident between {self.incident1['number']} and {self.incident2['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", find the incident that has {"longer" if self.longer else "shorter"} business duration between the following two incidents:\n'

        if self.level == 2:
            self.task_description += (
                f"\nIncident 1:\n"
                f"- Number: {self.incident1['number']}\n"
                f"- Short Description: {self.incident1['short_description']}\n"
                f"- Business Duration: {self.incident1['business_duration']} seconds\n"
                f"\nIncident 2:\n"
                f"- Number: {self.incident2['number']}\n"
                f"- Short Description: {self.incident2['short_description']}\n"
                f"- Business Duration: {self.incident2['business_duration']} seconds\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Get incident configurations
        incident_configs = CreateIncidentTask.all_configs()
        # Filter out configs without business duration
        incident_configs = [
            config for config in incident_configs if config["template_record"]["business_duration"]
        ]

        # Sample two different incident configurations
        index = self.random.choice(len(incident_configs))
        incident1_config = incident_configs[index]
        remaining_configs = [c for c in incident_configs if c != incident1_config]
        index = self.random.choice(len(remaining_configs))
        incident2_config = remaining_configs[index]

        # Create incident records using table_api_call
        unique_id = uuid4()
        number = f"INC{unique_id}"
        incident1_config = {
            "short_description": incident1_config["template_record"]["short_description"],
            "description": incident1_config["template_record"]["description"],
            "priority": incident1_config["template_record"]["priority"],
            "impact": incident1_config["template_record"]["impact"],
            "urgency": incident1_config["template_record"]["urgency"],
            "business_duration": incident1_config["template_record"]["business_duration"],
            "number": number,
        }

        unique_id = uuid4()
        number = f"INC{unique_id}"
        incident2_config = {
            "short_description": incident2_config["template_record"]["short_description"],
            "description": incident2_config["template_record"]["description"],
            "priority": incident2_config["template_record"]["priority"],
            "impact": incident2_config["template_record"]["impact"],
            "urgency": incident2_config["template_record"]["urgency"],
            "business_duration": incident2_config["template_record"]["business_duration"],
            "number": number,
        }

        incident1_record = table_api_call(
            instance=self.instance,
            table="incident",
            method="POST",
            data=json.dumps(incident1_config),
        )
        incident2_record = table_api_call(
            instance=self.instance,
            table="incident",
            method="POST",
            data=json.dumps(incident2_config),
        )

        # Create tasks for comparing incidents
        tasks = [
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
            # Filter for first incident
            FilterIncidentListTask(
                instance=self.instance,
                list_name="incident",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [incident1_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
            # Filter for second incident
            FilterIncidentListTask(
                instance=self.instance,
                list_name="incident",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [incident2_record["result"]["number"]],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Store incident info for task description
        self.incident1 = incident1_record["result"]
        self.incident2 = incident2_record["result"]

        return tasks

    def _get_selected_incident(self) -> dict:
        """Helper method to get the selected incident based on business durations.

        Returns:
        --------
        dict
            The incident record that has longer/shorter business duration based on self.longer
        """
        duration1 = self.incident1["business_duration"]
        duration2 = self.incident2["business_duration"]

        if self.longer:
            return self.incident1 if duration1 > duration2 else self.incident2
        else:
            return self.incident1 if duration1 < duration2 else self.incident2

    def cheat(self, page: Page, chat_messages: list[str], subtask_idx: int = None) -> None:
        # Perform default cheat actions from parent class
        super().cheat(page, chat_messages, subtask_idx)

        # Only send the chat message if we're at the last subtask
        if subtask_idx is None or subtask_idx == len(self.subtasks) - 1:
            # Get the selected incident based on business durations
            selected_incident = self._get_selected_incident()

            # Send a chat message with the selected incident's number
            message = f"The incident {selected_incident['number']} has {'longer' if self.longer else 'shorter'} business duration with {selected_incident['business_duration']} seconds."
            chat_messages.append({"role": "assistant", "message": message})

    def validate(self, page: Page, chat_messages: list[str]) -> tuple[float, bool, str, dict]:
        # Get the correct incident based on business durations
        correct_incident = self._get_selected_incident()

        # Check if any chat message contains both the correct number and duration
        correct_number = correct_incident["number"]
        correct_duration = correct_incident["business_duration"]
        found_number = False
        found_duration = False

        for message in chat_messages:
            if isinstance(message, dict):
                message_text = message.get("message", "")
            else:
                message_text = message

            if correct_number in message_text:
                found_number = True
            if str(correct_duration) in message_text:
                found_duration = True

        # Return validation results
        if found_number and found_duration:
            return 1.0, True, "Correct incident number and business duration identified.", {}
        elif found_number:
            return 0.5, False, "Incident number found but business duration not mentioned.", {}
        elif found_duration:
            return 0.5, False, "Business duration found but incident number not mentioned.", {}
        else:
            return 0.0, False, "Neither incident number nor business duration were mentioned.", {}


class CompareExpenseLineAmountTask(CompositionalTask, HumanEvalTask):
    """Task for comparing amounts of two expense lines."""

    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        higher: bool = True,
    ) -> None:
        """
        Create a task that compares amounts of two expense lines.

        Parameters:
        -----------
        instance: SNowInstance
            The ServiceNow instance to run the task on.
        fixed_config: list[AbstractServiceNowTask]
            A list of subtasks.
        level: int
            The level of the task; choice between 2 and 3. L2 will have all the info in the goal and start in the SNOW home page.
            L3 will start in a private task page describing the information needed to complete the task.
        higher: bool
            If True, find the expense line with higher amount. If False, find the one with lower amount.
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.protocol_name = "Comparing expense line amounts"
        self.higher = higher
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.expense1 = None
        self.expense2 = None

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Sample a configuration
        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        self.short_description = f"Find {'higher' if self.higher else 'lower'} amount expense line between {self.expense1['number']} and {self.expense2['number']}"
        self.task_description = f'Referring to company protocol "{self.protocol_name}", find the expense line that has {"higher" if self.higher else "lower"} amount between the following two expense lines:\n'

        if self.level == 2:
            self.task_description += (
                f"\nExpense Line 1:\n"
                f"- Number: {self.expense1['number']}\n"
                f"- Description: {self.expense1['short_description']}\n"
                f"- Amount: ${self.expense1['amount']}\n"
                f"\nExpense Line 2:\n"
                f"- Number: {self.expense2['number']}\n"
                f"- Description: {self.expense2['short_description']}\n"
                f"- Amount: ${self.expense2['amount']}\n"
            )

        goal, info = super().setup_goal(page=page, config=config)
        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        # Generate random amounts for two expense lines
        amount1 = self.random.randint(1000, 10000)
        amount2 = self.random.randint(1000, 10000)
        while amount2 == amount1:  # Ensure different amounts
            amount2 = self.random.randint(1000, 10000)

        # Create expense line records using create_expense_line
        unique_id = uuid4()
        number = f"EXP{unique_id}"
        expense1_sys_id, expense1_number = create_expense_line(
            instance=self.instance,
            amount=amount1,
            number=number,
            date=str(fake.date_this_year(before_today=True, after_today=False)),
            short_description=fake.sentence(4),
        )

        unique_id = uuid4()
        number = f"EXP{unique_id}"
        expense2_sys_id, expense2_number = create_expense_line(
            instance=self.instance,
            amount=amount2,
            number=number,
            date=str(fake.date_this_year(before_today=True, after_today=False)),
            short_description=fake.sentence(4),
        )

        # Get the full expense line records
        expense1_record = table_api_call(
            instance=self.instance,
            table="fm_expense_line",
            params={"sysparm_query": f"sys_id={expense1_sys_id}"},
        )["result"][0]

        expense2_record = table_api_call(
            instance=self.instance,
            table="fm_expense_line",
            params={"sysparm_query": f"sys_id={expense2_sys_id}"},
        )["result"][0]

        # Create tasks for comparing expense lines
        tasks = [
            # Navigate to the expense line list
            AllMenuTask(
                instance=self.instance,
                fixed_config={
                    "application": "Cost",
                    "module": "Expense Lines",
                    "url": "/now/nav/ui/classic/params/target/fm_expense_line_list.do",
                },
                is_validated=False,
                used_in_level_2=True,
            ),
            # Filter for first expense line
            FilterExpenseLineListTask(
                instance=self.instance,
                start_rel_url="/now/nav/ui/classic/params/target/fm_expense_line_list.do",
                list_name="Expense Lines",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [expense1_number],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
            # Filter for second expense line
            FilterExpenseLineListTask(
                instance=self.instance,
                start_rel_url="/now/nav/ui/classic/params/target/fm_expense_line_list.do",
                list_name="Expense Lines",
                fixed_config={
                    "filter_columns": ["number"],
                    "filter_kind": "",
                    "filter_values": [expense2_number],
                },
                is_validated=True,
                used_in_level_2=True,
            ),
        ]

        # Store expense line info for task description
        self.expense1 = expense1_record
        self.expense2 = expense2_record

        return tasks

    def _get_selected_expense(self) -> dict:
        """Helper method to get the selected expense line based on amounts.

        Returns:
        --------
        dict
            The expense line record that has higher/lower amount based on self.higher
        """
        amount1 = float(self.expense1["amount"])
        amount2 = float(self.expense2["amount"])

        if self.higher:
            return self.expense1 if amount1 > amount2 else self.expense2
        else:
            return self.expense1 if amount1 < amount2 else self.expense2

    def cheat(self, page: Page, chat_messages: list[str], subtask_idx: int = None) -> None:
        # Perform default cheat actions from parent class
        super().cheat(page, chat_messages, subtask_idx)

        # Only send the chat message if we're at the last subtask
        if subtask_idx is None or subtask_idx == len(self.subtasks) - 1:
            # Get the selected expense line based on amounts
            selected_expense = self._get_selected_expense()

            # Send a chat message with the selected expense line's number
            message = f"The expense line {selected_expense['number']} has {'higher' if self.higher else 'lower'} amount with ${selected_expense['amount']}."
            chat_messages.append({"role": "assistant", "message": message})

    def validate(self, page: Page, chat_messages: list[str]) -> tuple[float, bool, str, dict]:
        # Get the correct expense line based on amounts
        correct_expense = self._get_selected_expense()

        # Check if any chat message contains both the correct number and amount
        correct_number = correct_expense["number"]
        correct_amount = correct_expense["amount"]
        found_number = False
        found_amount = False

        for message in chat_messages:
            if isinstance(message, dict):
                message_text = message.get("message", "")
            else:
                message_text = message

            if correct_number in message_text:
                found_number = True
            if str(correct_amount) in message_text:
                found_amount = True

        # Return validation results
        if found_number and found_amount:
            return 1.0, True, "Correct expense line number and amount identified.", {}
        elif found_number:
            return 0.5, False, "Expense line number found but amount not mentioned.", {}
        elif found_amount:
            return 0.5, False, "Amount found but expense line number not mentioned.", {}
        else:
            return 0.0, False, "Neither expense line number nor amount were mentioned.", {}


local_vars = locals().copy()

__TASKS__ = [
    CompareHardwareDate,
    CompareChangeRequestPriority,
    CompareProblemPriority,
    CompareIncidentBusinessDuration,
    CompareExpenseLineAmountTask,
]
