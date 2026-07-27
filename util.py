import json

def read_json_file(filename: str):
    with open(filename, 'r') as f:
        return json.load(f)

