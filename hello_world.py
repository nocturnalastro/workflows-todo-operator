from logging import Logger, log
from os import set_inheritable
import kopf
import kubernetes
from kubernetes.client.rest import ApiException
from io import StringIO
import yaml
import json
from pathlib import Path

ROOT = Path(__file__).parent


def load_str(content):
    with StringIO() as f:
        f.write(content)
        f.seek(0)  # Reset position
        return yaml.load(f, Loader=yaml.FullLoader)


def _create_CRD_from_template(object_name, template_path, template_values, crd_values, logger):
    api = kubernetes.client.CustomObjectsApi()

    logger.info("fetching {object_name} template".format(object_name=object_name))

    with (ROOT / template_path).open() as template_file:
        stream_template = template_file.read()
        stream = stream_template.format(**template_values)
        body = load_str(stream)

    logger.info(f"creating object: {json.dumps(stream)}")

    res = api.create_namespaced_custom_object(body=body, **crd_values)

    logger.info(f"result: {res}")


def _check_for_CRD(object_name, name, crd_values, logger):
    api = kubernetes.client.CustomObjectsApi()
    logger.info("looking to see if {object_name} aready exists".format(object_name=object_name))
    try:
        res = api.get_namespaced_custom_object(name=name, **crd_values)
        return True
    except ApiException:
        return False


def create_build_congfig(sepc, name, namespace, logger):
    template_values = dict(
        GIT_BRANCH="master",
        GIT_REPO="https://github.com/unipartdigital/workflows_engine",
        NAME="workflows-engine",
        NAMESPACE="todo",
        APP_NAME="workflows-engine",
        STREAM_NAME="workflows-engine:latest",
        empty="{}",
    )

    crd_values = dict(
        group="build.openshift.io",
        version="v1",
        namespace=namespace,
        plural="buildconfigs",
    )

    if not _check_for_CRD(
        object_name="build config",
        name=template_values["NAME"],
        crd_values=crd_values,
        logger=logger,
    ):

        _create_CRD_from_template(
            object_name="build config",
            template_path="templates/build_config.yaml",
            template_values=template_values,
            crd_values=crd_values,
            logger=logger,
        )


def create_image_stream(spec, name, namespace, logger):
    template_values = dict(
        GIT_BRANCH="master",
        GIT_REPO="https://github.com/unipartdigital/workflows_engine",
        NAME="workflows-engine",
        NAMESPACE="todo",
        APP_NAME="workflows-engine",
        STREAM_NAME="workflows-engine",
        empty="{}",
    )

    crd_values = dict(
        group="image.openshift.io",
        version="v1",
        namespace=namespace,
        plural="imagestreams",
    )

    if not _check_for_CRD(
        object_name="image steam",
        name=template_values["NAME"],
        crd_values=crd_values,
        logger=logger,
    ):
        _create_CRD_from_template(
            object_name="image steam",
            template_path="templates/image_stream.yaml",
            template_values=template_values,
            crd_values=crd_values,
            logger=logger,
        )


@kopf.on.create("workflows.engine", "v1", "todos")
def create_fn(spec, name, namespace, logger, **kwargs):
    logger.info("Todo CRD created")
    create_build_congfig(spec, name, namespace, logger)
    create_image_stream(spec, name, namespace, logger)
