from uuid import uuid4


def new_id() -> str:
    return str(uuid4())
