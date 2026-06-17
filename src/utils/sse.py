import json


def sse_event(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
