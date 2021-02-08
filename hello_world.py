import kopf


@kopf.on.create("workflows.engine", "v1", "todos")
def create_fn(spec, **kwargs):
    print(f"Creating: {spec}")
    return {"message": "done"}
