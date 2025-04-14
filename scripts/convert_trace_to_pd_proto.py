import io
import json
import glob
import pickle

from google.protobuf import text_format
from PIL import Image

from pb.process_discovery.dataset_pb2 import DatasetFile


files = glob.glob('order_device_tasks/*.pickle')

dataset_file = DatasetFile()
dataset_file.name = 'WorkArena traces'
dataset_file.description = 'WorkArena traces'
dataset = dataset_file.dataset


def to_string(strings, idx):
    if idx == -1:
        return None
    else:
        return strings[idx]


def find_object_by_bid(step):
    bid = step['bid']
    strings = step['obs']['dom_object']['strings']

    for doc in step['obs']['dom_object']['documents']:
        nodes = doc['nodes']
        for node_idx in range(len(nodes["nodeName"])):
            node_type = nodes["nodeType"][node_idx]
            node_name = to_string(strings, nodes["nodeName"][node_idx])
            node_value = to_string(strings, nodes["nodeValue"][node_idx])
            node_attr_idxs = nodes["attributes"][node_idx]

            found = False
            attributes = {'node_type': node_type, 'node_name': node_name, 'node_value': node_value}
            for i in range(0, len(node_attr_idxs), 2):
                attr_name = to_string(strings, node_attr_idxs[i])
                attr_value = to_string(strings, node_attr_idxs[i + 1])
                attributes[attr_name] = attr_value

                if attr_name == 'bid' and attr_value == bid:
                    found = True

            if found:
                return attributes


for file in files:
    print('Converting', file)
    with open(file, 'rb') as f:
        name = file.split('/')[-1].split('.')[0]
        trace_count = 0
        while True:
            try:
                trace = pickle.load(f)
            except EOFError:
                break

            # if trace_count >= 3:
            #     break
            trace_count += 1

            trace_proto = dataset.traces.add()
            trace_proto.id = name + '_' + str(len(dataset.traces))

            for index, step in enumerate(trace):
                # Get WebState.
                obs = trace_proto.observations.add()

                # Get screenshot.
                pil_image = Image.fromarray(step['obs']['screenshot'])
                width, height = pil_image.size
                image_bytes = io.BytesIO()
                pil_image.save(image_bytes, format='PNG')
                image_bytes = image_bytes.getvalue()
                obs.auxiliary_observation_info.before_state_screenshot_data = image_bytes

                # Get timestamp.
                obs.user_event.timestamp.seconds = int(step['time'])

                # Get URL.
                obs.user_event.url = step['obs']['url']

                # Get action.
                action = obs.user_event.action
                action.description = step['action']
                if step['args']:
                    args = ' '.join(step["args"])
                    action.description += f' {args}'

                action.before_state.viewport_screenshot.id = f'{trace_proto.id}_{index}'
                action.before_state.viewport_width = width
                action.before_state.viewport_height = height

                bid = step['bid']
                target = find_object_by_bid(step)

                if step['action'] == 'click':
                    action.click.locator.json_value = json.dumps(target)
                    element = step['obs']['extra_element_properties'].get(bid)
                    bbox = element['bbox']
                    x, y, width, height = bbox
                    center = (x + width / 2, y + height / 2)
                    raw_event = action.raw_events.add()
                    raw_event.mouse.viewport_x = int(center[0])
                    raw_event.mouse.viewport_y = int(center[1])
                    raw_event.mouse.button = raw_event.mouse.MouseButton.LEFT
                    raw_event.mouse.event_type = raw_event.mouse.MouseEventType.CLICK
                elif step['action'] == 'select_option':
                    action.set_value.field_locator.json_value = json.dumps(target)
                    action.set_value.field_value.json_value = json.dumps(args)
                elif step['action'] == 'fill':
                    action.set_value.field_locator.json_value = json.dumps(target)
                    action.set_value.field_value.json_value = json.dumps(args)


with open(f'trace_profiling/workarena_traces.textproto', 'w') as f:
    text_format.PrintMessage(dataset_file, f)
