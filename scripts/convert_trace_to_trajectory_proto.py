import io
import glob
import pickle
import json
import os


from orby.trajectory_collector.utils import record_utils
from fm.trajectory_data_pb2 import TrajectoryData
from orby.digitalagent.utils import file_utils


files = glob.glob("trace_profiling/*.pickle")
debug_output_base_dir = "debug_output/"

for file in files:
    print("Converting", file)
    with open(file, "rb") as f:
        name = file.split("/")[-1].split(".")[0]

        count = 0
        while True:
            try:
                trace = pickle.load(f)
            except Exception as e:
                # Usually EOFError at the end of the file.
                print("Error loading trace", e)
                break

            debug_output_dir = os.path.join(debug_output_base_dir, name, str(count))
            os.makedirs(debug_output_dir, exist_ok=True)
            count += 1

            trajectory_data = TrajectoryData()
            trajectory_data.base_url = ""
            trajectory_data.goal = trace[0]["obs"]["goal"]
            before_state = None
            for index, step in enumerate(trace):
                state = record_utils.record_web_state_from_browser_gym_observation(step["obs"])
                after_state = record_utils.record_web_state_from_browser_gym_observation(
                    observation=step["obs"],
                    reward=0,
                    terminated=False,
                    truncated=False,
                )

                action_string = step.get("action")
                if step.get('args'):
                    action_string += ' args: ' + str(step.get("args"))
                if step.get('kwargs'):
                    action_string += ' kwargs: ' + str(step.get("kwargs"))

                action_data = record_utils.record_action_data_from_browser_gym_interaction(
                    domain="",
                    action_string=action_string,
                    after_state=after_state,
                    before_state=before_state,
                )

                trajectory_data.actions.extend([action_data])

                # Make after the new before state for the next action
                before_state = after_state

            # Save the reward. TODO: improve this and make it more informative
            trajectory_data.success.CopyFrom(TrajectoryData.ResultSuccess(answer=f"Got reward 1.0"))

            # Save the object to a file
            with file_utils.open(os.path.join(debug_output_dir, "trajectory.pb"), "wb") as tf:
                tf.write(trajectory_data.SerializeToString())

            debugging_data_row = {
                "example": "WorkArena",
                "goal": trajectory_data.goal,
                "reward": 1.0,
                "success": True,
                "model_configs": "",
                "agent_name": "Gold trace",
                "steps": len(trace),
                "debug_output_dir": debug_output_dir,
            }
            # save json file
            with file_utils.open(os.path.join(debug_output_dir, "results.json"), "w") as rf:
                json.dump(debugging_data_row, rf)
