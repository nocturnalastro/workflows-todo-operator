from logging import Logger, log
from os import set_inheritable
import kopf
import kubernetes
from kubernetes.client.rest import ApiException
from io import StringIO
import yaml
from dateutil.parser import parse as dtparse
from pathlib import Path

ROOT = Path(__file__).parent


def load_str(content):
    with StringIO() as f:
        f.write(content)
        f.seek(0)  # Reset position
        return yaml.load(f, Loader=yaml.FullLoader)


def _process_template(object_name, template_path, template_values, logger):
    logger.info("fetching {object_name} template".format(object_name=object_name))

    with (ROOT / template_path).open() as template_file:
        stream_template = template_file.read()
        stream = stream_template.format(**template_values)
        return load_str(stream)


def _create_CRD_from_template(object_name, template_path, template_values, crd_values, logger):
    api = kubernetes.client.CustomObjectsApi()
    body = _process_template(object_name, template_path, template_values, logger)
    return api.create_namespaced_custom_object(body=body, **crd_values)


def _get_CRD(name, crd_values):
    api = kubernetes.client.CustomObjectsApi()
    return api.get_namespaced_custom_object(name=name, **crd_values)


def _check_for_CRD(object_name, name, crd_values, logger):
    logger.info("looking to see if {object_name} aready exists".format(object_name=object_name))
    try:
        _get_CRD(name, crd_values)
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

    return _get_CRD(
        name=template_values["NAME"],
        crd_values=crd_values,
    )


def _get_image_ref(image_stream, tag_name):
    tags = image_stream["status"]["tags"]
    matching_tags = [t for t in image_stream["status"]["tags"] if t["tag"] == tag_name]
    if not matching_tags:
        raise ValueError("Tag not found")

    tag = matching_tags[0]

    if not tag["items"]:
        raise ValueError("No items in tag dicription perhaps no buids")

    latest_build = sorted(tag["items"], key=lambda i: dtparse(i["created"]))[0]
    return latest_build["dockerImageReference"]


def create_deployment(spec, name, namespace, image_stream, logger):
    template_values = dict(
        GIT_BRANCH="master",
        GIT_REPO="https://github.com/unipartdigital/workflows_engine",
        NAME="workflows-engine",
        NAMESPACE="todo",
        APP_NAME="workflows-engine",
        IMAGE=_get_image_ref(image_stream, "latest"),
        SERVICE_ACCOUNT_NAME="kopfexample-account",
        SERVICE_ACCOUNT="kopfexample-account",
        empty="{}",
    )

    body = _process_template(
        object_name="deployment", template_path="templates/deployment.yaml", template_values=template_values
    )
    api = kubernetes.client.AppsV1Api()
    return api.create_namespaced_deployment(body=body, namespace=template_values["NAMESPACE"])


@kopf.on.create("workflows.engine", "v1", "todos")
def create_fn(spec, name, namespace, logger, **kwargs):
    logger.info("Todo CRD created")
    create_build_congfig(spec, name, namespace, logger)
    image_stream = create_image_stream(spec, name, namespace, logger)
    create_deployment(spec, name, namespace, image_stream, logger)