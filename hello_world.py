from os import set_inheritable
import kopf
import kubernetes
from io import StringIO
import yaml
import json


def load_str(content):
    with StringIO() as f:
        f.write(f)
        f.seek(0)  # Reset position
        return yaml.load(f)


def create_image_stream(spec, name, namespace, logger):
    api = kubernetes.client.CustomObjectsApi()

    logger.info("fetching image stream template")

    with open("templates/image_stream.yaml") as template_file:
        stream_template = template_file.read()
        stream = stream_template.format(
            GIT_BRANCH="master",
            GIT_REPO="https://github.com/unipartdigital/workflows_engine",
            NAME="workflows-engine-3",
            NAMESPACE="todo",
            APP_NAME="workflows-engine",
            STREAM_NAME="workflows-engine-3:latest",
            empty="{}",
        )
        body = load_str(stream)

    logger.info(f"creating object: {json.dumps(stream)}")

    res = api.create_namespaced_custom_object(
        group="image.openshift.io",
        version="v1",
        namespace=namespace,
        plural="imagestreams",
        body=body,
    )

    logger.info(f"result: {res}")


@kopf.on.create("workflows.engine", "v1", "todos")
def create_fn(spec, name, namespace, logger, **kwargs):
    logger.info("Todo CRD created")
    create_image_stream(spec, name, namespace, logger)
