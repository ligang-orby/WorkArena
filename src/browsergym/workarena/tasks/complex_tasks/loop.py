import json
from typing import List, Tuple, Dict

from faker import Faker

fake = Faker()
from playwright.sync_api._generated import Page

from ..compositional.base import CompositionalTask, HumanEvalTask
from ..compositional.delete_record import DeleteUserTask
from ..form import (
    CreateUserTask,
    CreateChangeRequestTask,
    CreateIncidentTask,
    CreateHardwareAssetTask,
    CreateProblemTask,
    CreateItemRequestTask,
)
from ..form import EditHardwareAssetTask
from ..list import FilterHardwareListTask
from ..navigation import AllMenuTask
from ..base import AbstractServiceNowTask
from ..service_catalog import (
    OrderStandardLaptopTask,
    OrderDeveloperLaptopTask,
    OrderSalesLaptopTask,
    OrderDevelopmentLaptopPCTask,
    OrderIpadMiniTask,
    OrderIpadProTask,
    OrderAppleWatchTask,
    OrderAppleMacBookPro15Task,
    OrderLoanerLaptopTask,
)
from ..knowledge import KnowledgeBaseSearchTask, AddCommentToKnowledgeArticleTask
from ...instance import SNowInstance
from ...api.computer_asset import create_computer_asset
from ...api.user import create_user
from ...api.utils import table_api_call, db_delete_from_table


class OrderMultipleDevicesTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_devices: int = 3,
        device_types: List[str] = None,
    ) -> None:
        """
        Multiple Device Ordering Task

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
        num_devices: int
            Number of devices to order (default: 3)
        device_types: List[str]
            List of device types to order from. If None, will randomly select from all available types.
            Available types: ["standard_laptop", "developer_laptop", "sales_laptop", "development_laptop_pc",
                           "ipad_mini", "ipad_pro", "apple_watch", "apple_macbook_pro15", "loaner_laptop"]
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_devices = num_devices
        self.protocol_name = "Ordering hardware devices"

        # Map device types to their task classes
        self.device_type_to_task = {
            "standard_laptop": OrderStandardLaptopTask,
            "developer_laptop": OrderDeveloperLaptopTask,
            "sales_laptop": OrderSalesLaptopTask,
            "development_laptop_pc": OrderDevelopmentLaptopPCTask,
            "ipad_mini": OrderIpadMiniTask,
            "ipad_pro": OrderIpadProTask,
            "apple_watch": OrderAppleWatchTask,
            "apple_macbook_pro15": OrderAppleMacBookPro15Task,
            "loaner_laptop": OrderLoanerLaptopTask,
        }

        # If device_types is not provided, use all available types
        self.device_types = device_types if device_types else list(self.device_type_to_task.keys())

        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.devices: List[Tuple[str, str]] = []  # List of (device_type, request_item)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random device orders
        for _ in range(self.num_devices):
            device_type = self.random.choice(self.device_types)
            self.devices.append(device_type)

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        device_names = ", ".join([f'"{device[1]}"' for device in self.devices])
        self.short_description = f"Order {self.num_devices} devices"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) order the following devices: {device_names}\n'

        goal, info = super().setup_goal(page=page, config=config)

        merged_goal = [self.subgoals[0], 'Go to the hardware store and order the following devices\n']
        for i in range(1, len(config), 2):
            merged_goal.append('Device: ' + config[i].requested_item)
            merged_goal.append('Quantity: ' + str(config[i].quantity))
            merged_goal.append('Configuration: ' + str(dict((k, v[1]) for k, v in config[i].requested_configuration.items())))

        merged_goal = '\n'.join(merged_goal)
        print(merged_goal)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for ordering multiple devices"""
        config = []

        # Add subtasks for each device
        for device_type in self.devices:
            task_class = self.device_type_to_task[device_type]

            # Order the device
            order_device_subtask = [
                # Navigate to the service catalog
                AllMenuTask(
                    instance=self.instance,
                    fixed_config={
                        "application": "Self-Service",
                        "module": "Service Catalog",
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Create the order
                task_class(
                    instance=self.instance,
                    # fixed_config={
                    #     "field_name": "name",
                    #     "pretty_printed_field_name": "Name",
                    #     "field_value": request_item,
                    #     "other_fields": {},
                    # },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this device
            config.extend(order_device_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as orders are handled by the system
        super().teardown()


class CreateMultipleUserTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_users: int = 3,
    ) -> None:
        """
        Multiple User Creation Task

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
        num_users: int
            Number of users to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_users = num_users
        self.protocol_name = "Creating a new user"
        super().__init__(
            seed=seed,
            instance=self.instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.users: List[Tuple[str, str, str]] = []  # List of (full_name, user_name, user_sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random names and create users
        for _ in range(self.num_users):
            first_name = fake.first_name() + "-" + fake.first_name()
            last_name = fake.last_name() + "-" + fake.last_name()
            user_full_name = first_name + " " + last_name

            # Create user
            user_name, _, user_sys_id = create_user(
                instance=self.instance,
                first_name=first_name,
                last_name=last_name,
                random=self.random,
            )

            assert user_sys_id, f"Failed to create user {first_name} {last_name}"

            self.users.append((user_full_name, user_name, user_sys_id))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        user_names = ", ".join([f'"{user[0]}"' for user in self.users])
        self.short_description = f"Create {self.num_users} users"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following users: {user_names}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple users"""
        config = []

        # Add subtasks for each user
        for user_full_name, user_name, user_sys_id in self.users:
            # Create the user
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
                # Create the user
                CreateUserTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "name",
                        "pretty_printed_field_name": "Name",
                        "field_value": user_full_name,
                        "other_fields": {
                            "first_name": user_full_name.split()[0],
                            "last_name": user_full_name.split()[1],
                            "user_name": user_name,
                            "active": True,
                        },
                    },
                    record_sys_id=user_sys_id,
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this user
            config.extend(create_user_subtask)

        return config

    def teardown(self) -> None:
        # Delete all users
        for _, _, user_sys_id in self.users:
            user_record = table_api_call(
                instance=self.instance,
                table="sys_user",
                params={"sysparm_query": f"sys_id={user_sys_id}"},
            )["result"]
            if user_record:
                db_delete_from_table(
                    instance=self.instance,
                    table="sys_user",
                    sys_id=user_sys_id,
                )
        super().teardown()


class DeleteMultipleUserTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_users: int = 3,
    ) -> None:
        """
        Multiple User Deletion Task

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
        num_users: int
            Number of users to delete (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_users = num_users
        self.protocol_name = "Deleting a user"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.users: List[Tuple[str, str, str]] = []  # List of (full_name, user_name, user_sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random names and create users
        for _ in range(self.num_users):
            first_name = fake.first_name() + "-" + fake.first_name()
            last_name = fake.last_name() + "-" + fake.last_name()
            user_full_name = first_name + " " + last_name

            # Create user
            user_name, _, user_sys_id = create_user(
                instance=self.instance,
                first_name=first_name,
                last_name=last_name,
                random=self.random,
            )

            assert user_sys_id, f"Failed to create user {first_name} {last_name}"

            self.users.append((user_full_name, user_name, user_sys_id))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        user_names = ", ".join([f'"{user[0]}"' for user in self.users])
        self.short_description = f"Delete {self.num_users} users"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) delete the following users: {user_names}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for deleting multiple users"""
        config = []

        # Add subtasks for each user
        for user_full_name, _, user_sys_id in self.users:
            # Delete the user
            delete_user_subtask = [
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
                # Delete the user
                DeleteUserTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "name",
                        "pretty_printed_field_name": "Name",
                        "field_value": user_full_name,
                        "other_fields": {},
                    },
                    record_sys_id=user_sys_id,
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this user
            config.extend(delete_user_subtask)

        return config

    def teardown(self) -> None:
        # Delete all users
        for _, _, user_sys_id in self.users:
            user_record = table_api_call(
                instance=self.instance,
                table="sys_user",
                params={"sysparm_query": f"sys_id={user_sys_id}"},
            )["result"]
            if user_record:
                db_delete_from_table(
                    instance=self.instance,
                    table="sys_user",
                    sys_id=user_sys_id,
                )
        super().teardown()


class OffBoardMultipleUserTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_users: int = 3,
    ) -> None:
        """
        Multiple Employee OffBoarding Task

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
        num_users: int
            Number of users to offboard (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_users = num_users
        self.protocol_name = "Offboarding a user"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.users: List[Tuple[str, str, str]] = []  # List of (full_name, user_name, user_sys_id)
        self.laptop_asset_tags: List[str] = []
        self.laptop_sys_ids: List[str] = []

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random names and create users
        for _ in range(self.num_users):
            first_name = fake.first_name() + "-" + fake.first_name()
            last_name = fake.last_name() + "-" + fake.last_name()
            user_full_name = first_name + " " + last_name
            laptop_asset_tag = "P" + str(id(self) % (10**8)).zfill(8)

            # Create user
            user_name, _, user_sys_id = create_user(
                instance=self.instance,
                first_name=first_name,
                last_name=last_name,
                random=self.random,
            )

            assert user_sys_id, f"Failed to create user {first_name} {last_name}"

            laptop_sys_id, _, _ = create_computer_asset(
                instance=self.instance,
                asset_tag=laptop_asset_tag,
                user_sys_id=user_sys_id,
                random=self.random,
            )

            self.users.append((user_full_name, user_name, user_sys_id))
            self.laptop_asset_tags.append(laptop_asset_tag)
            self.laptop_sys_ids.append(laptop_sys_id)

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        user_names = ", ".join([f'"{user[0]}"' for user in self.users])
        self.short_description = f"Offboard {self.num_users} users"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) offboard the following users: {user_names}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for offboarding multiple users"""
        config = []

        # Add subtasks for each user
        for i, (user_full_name, _, user_sys_id) in enumerate(self.users):
            laptop_sys_id = self.laptop_sys_ids[i]

            # First unassign the hardware asset
            unassign_hardware_subtask = [
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
                FilterHardwareListTask(
                    instance=self.instance,
                    fixed_config={
                        "filter_columns": ["assigned_to"],
                        "filter_kind": "AND",
                        "filter_values": [f"{user_full_name}"],
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Unassign the hardware asset
                EditHardwareAssetTask(
                    instance=self.instance,
                    record_sys_id=laptop_sys_id,
                    new_values={"assigned_to": ""},
                    is_validated=True,
                    used_in_level_2=True,
                    level=self.level,
                ),
            ]

            # Then delete the user
            delete_user_subtask = [
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
                # Delete the user
                DeleteUserTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "name",
                        "pretty_printed_field_name": "Name",
                        "field_value": user_full_name,
                        "other_fields": {},
                    },
                    record_sys_id=user_sys_id,
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add all subtasks for this user
            config.extend(unassign_hardware_subtask + delete_user_subtask)

        return config

    def teardown(self) -> None:
        # Delete all users
        for _, _, user_sys_id in self.users:
            user_record = table_api_call(
                instance=self.instance,
                table="sys_user",
                params={"sysparm_query": f"sys_id={user_sys_id}"},
            )["result"]
            if user_record:
                db_delete_from_table(
                    instance=self.instance,
                    table="sys_user",
                    sys_id=user_sys_id,
                )
        super().teardown()


class CreateMultipleChangeRequestTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_requests: int = 3,
    ) -> None:
        """
        Multiple Change Request Creation Task

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
        num_requests: int
            Number of change requests to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_requests = num_requests
        self.protocol_name = "Creating a change request"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.requests: List[Tuple[str, str]] = []  # List of (short_description, sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random change requests
        for _ in range(self.num_requests):
            short_description = (
                f"Change Request {fake.word().capitalize()} {fake.word().capitalize()}"
            )
            self.requests.append((short_description, None))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        request_descriptions = ", ".join([f'"{req[0]}"' for req in self.requests])
        self.short_description = f"Create {self.num_requests} change requests"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following change requests: {request_descriptions}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple change requests"""
        config = []

        # Add subtasks for each change request
        for short_description, _ in self.requests:
            # Create the change request
            create_request_subtask = [
                # Navigate to the change request list
                AllMenuTask(
                    instance=self.instance,
                    fixed_config={
                        "application": "Change",
                        "module": "All",
                        "url": "/now/nav/ui/classic/params/target/change_request_list.do",
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Create the change request
                CreateChangeRequestTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "short_description",
                        "pretty_printed_field_name": "Short description",
                        "field_value": short_description,
                        "other_fields": {
                            "type": "Normal",
                            "priority": "3 - Moderate",
                            "risk": "3 - Moderate",
                            "impact": "3 - Moderate",
                        },
                    },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this change request
            config.extend(create_request_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as change requests are handled by the system
        super().teardown()


class CreateMultipleIncidentTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_incidents: int = 3,
    ) -> None:
        """
        Multiple Incident Creation Task

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
        num_incidents: int
            Number of incidents to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_incidents = num_incidents
        self.protocol_name = "Creating an incident"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.incidents: List[Tuple[str, str]] = []  # List of (short_description, sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random incidents
        for _ in range(self.num_incidents):
            short_description = f"Incident {fake.word().capitalize()} {fake.word().capitalize()}"
            self.incidents.append((short_description, None))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        incident_descriptions = ", ".join([f'"{inc[0]}"' for inc in self.incidents])
        self.short_description = f"Create {self.num_incidents} incidents"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following incidents: {incident_descriptions}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple incidents"""
        config = []

        # Add subtasks for each incident
        for short_description, _ in self.incidents:
            # Create the incident
            create_incident_subtask = [
                # Navigate to the incident list
                AllMenuTask(
                    instance=self.instance,
                    fixed_config={
                        "application": "Service Desk",
                        "module": "Incidents",
                        "url": "/now/nav/ui/classic/params/target/incident_list.do",
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Create the incident
                CreateIncidentTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "short_description",
                        "pretty_printed_field_name": "Short description",
                        "field_value": short_description,
                        "other_fields": {
                            "priority": "3 - Moderate",
                            "impact": "3 - Moderate",
                            "urgency": "3 - Moderate",
                            "category": "Hardware",
                        },
                    },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this incident
            config.extend(create_incident_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as incidents are handled by the system
        super().teardown()


class CreateMultipleHardwareAssetTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_assets: int = 3,
    ) -> None:
        """
        Multiple Hardware Asset Creation Task

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
        num_assets: int
            Number of hardware assets to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_assets = num_assets
        self.protocol_name = "Creating a hardware asset"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.assets: List[Tuple[str, str]] = []  # List of (name, sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random hardware assets
        for _ in range(self.num_assets):
            name = f"Asset {fake.word().capitalize()} {fake.word().capitalize()}"
            self.assets.append((name, None))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        asset_names = ", ".join([f'"{asset[0]}"' for asset in self.assets])
        self.short_description = f"Create {self.num_assets} hardware assets"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following hardware assets: {asset_names}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple hardware assets"""
        config = []

        # Add subtasks for each hardware asset
        for name, _ in self.assets:
            # Create the hardware asset
            create_asset_subtask = [
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
                # Create the hardware asset
                CreateHardwareAssetTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "name",
                        "pretty_printed_field_name": "Name",
                        "field_value": name,
                        "other_fields": {
                            "model": "Dell Latitude 5420",
                            "model_category": "Laptop",
                            "serial_number": f"SN-{self.random.randint(1000000, 9999999)}",
                            "vendor": "Dell",
                            "install_status": "1 - Ready",
                        },
                    },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this hardware asset
            config.extend(create_asset_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as hardware assets are handled by the system
        super().teardown()


class CreateMultipleProblemTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_problems: int = 3,
    ) -> None:
        """
        Multiple Problem Creation Task

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
        num_problems: int
            Number of problems to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_problems = num_problems
        self.protocol_name = "Creating a problem"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.problems: List[Tuple[str, str]] = []  # List of (short_description, sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random problems
        for _ in range(self.num_problems):
            short_description = f"Problem {fake.word().capitalize()} {fake.word().capitalize()}"
            self.problems.append((short_description, None))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        problem_descriptions = ", ".join([f'"{prob[0]}"' for prob in self.problems])
        self.short_description = f"Create {self.num_problems} problems"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following problems: {problem_descriptions}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple problems"""
        config = []

        # Add subtasks for each problem
        for short_description, _ in self.problems:
            # Create the problem
            create_problem_subtask = [
                # Navigate to the problem list
                AllMenuTask(
                    instance=self.instance,
                    fixed_config={
                        "application": "Problem",
                        "module": "All",
                        "url": "/now/nav/ui/classic/params/target/problem_list.do",
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Create the problem
                CreateProblemTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "short_description",
                        "pretty_printed_field_name": "Short description",
                        "field_value": short_description,
                        "other_fields": {
                            "priority": "3 - Moderate",
                            "impact": "3 - Moderate",
                            "urgency": "3 - Moderate",
                            "category": "Hardware",
                        },
                    },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this problem
            config.extend(create_problem_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as problems are handled by the system
        super().teardown()


class CreateMultipleItemRequestTask(CompositionalTask, HumanEvalTask):
    def __init__(
        self,
        seed: int = None,
        instance: SNowInstance = None,
        fixed_config: list[AbstractServiceNowTask] = None,
        level: int = 2,
        num_requests: int = 3,
    ) -> None:
        """
        Multiple Item Request Creation Task

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
        num_requests: int
            Number of item requests to create (default: 3)
        """
        assert level in [2, 3], "Level must be either 2 or 3"
        self.level = level
        self.num_requests = num_requests
        self.protocol_name = "Creating an item request"
        super().__init__(
            seed=seed,
            instance=instance,
            fixed_config=fixed_config,
            level=level,
            protocol_name=self.protocol_name,
        )
        self.task_description = None
        self.short_description = None
        self.requests: List[Tuple[str, str]] = []  # List of (short_description, sys_id)

    def setup_goal(self, page: Page) -> tuple[str, dict]:
        # Generate random item requests
        for _ in range(self.num_requests):
            short_description = (
                f"Item Request {fake.word().capitalize()} {fake.word().capitalize()}"
            )
            self.requests.append((short_description, None))

        config = self.fixed_config if self.fixed_config else self._get_config()

        # Get the task description
        request_descriptions = ", ".join([f'"{req[0]}"' for req in self.requests])
        self.short_description = f"Create {self.num_requests} item requests"
        self.task_description = f'Referring to company protocol "{self.protocol_name}" (located in the "Company Protocols" knowledge base) create the following item requests: {request_descriptions}\n'

        goal, info = super().setup_goal(page=page, config=config)

        return goal, info

    def _get_config(self) -> list[AbstractServiceNowTask]:
        """Create a list of subtasks for creating multiple item requests"""
        config = []

        # Add subtasks for each item request
        for short_description, _ in self.requests:
            # Create the item request
            create_request_subtask = [
                # Navigate to the service catalog
                AllMenuTask(
                    instance=self.instance,
                    fixed_config={
                        "application": "Self-Service",
                        "module": "Service Catalog",
                        "url": "/now/nav/ui/classic/params/target/sc_req_item_list.do",
                    },
                    is_validated=False,
                    used_in_level_2=True,
                ),
                # Create the item request
                CreateItemRequestTask(
                    instance=self.instance,
                    fixed_config={
                        "field_name": "short_description",
                        "pretty_printed_field_name": "Short description",
                        "field_value": short_description,
                        "other_fields": {
                            "priority": "3 - Moderate",
                            "quantity": "1",
                            "request": "Standard Laptop",
                        },
                    },
                    is_validated=True,
                    used_in_level_2=True,
                ),
            ]

            # Add subtasks for this item request
            config.extend(create_request_subtask)

        return config

    def teardown(self) -> None:
        # No cleanup needed as item requests are handled by the system
        super().teardown()


__TASKS__ = [
    OffBoardMultipleUserTask,
    DeleteMultipleUserTask,
    CreateMultipleUserTask,
    CreateMultipleChangeRequestTask,
    CreateMultipleIncidentTask,
    CreateMultipleHardwareAssetTask,
    CreateMultipleProblemTask,
    CreateMultipleItemRequestTask,
    OrderMultipleDevicesTask,
]
