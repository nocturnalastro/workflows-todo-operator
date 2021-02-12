from logging import Logger, log
from os import set_inheritable
import kopf
import kubernetes
from kubernetes.client.rest import ApiException
from io import StringIO
import yaml
from dateutil.parser import parse as dtparse
from pathlib import Path
import json
import time

ROOT = Path(__file__).parent


def _load_str(content):
    with StringIO() as f:
        f.write(content)
        f.seek(0)  # Reset position
        return yaml.load(f, Loader=yaml.FullLoader)


def _process_template(object_name, template_path, template_values, logger):
    logger.info("fetching {object_name} template".format(object_name=object_name))

    with (ROOT / template_path).open() as template_file:
        stream_template = template_file.read()
        stream = stream_template.format(**template_values)
        return _load_str(stream)


def _create_custom_resource_from_template(object_name, template_path, template_values, crd_values, logger):
    api = kubernetes.client.CustomObjectsApi()
    body = _process_template(object_name, template_path, template_values, logger)
    return api.create_namespaced_custom_object(body=body, **crd_values)


def _get_custom_resource(name, crd_values):
    api = kubernetes.client.CustomObjectsApi()
    return api.get_namespaced_custom_object(name=name, **crd_values)


def _check_for_custom_resource(object_name, name, crd_values, logger):
    logger.info("looking to see if {object_name} aready exists".format(object_name=object_name))
    try:
        _get_custom_resource(name, crd_values)
        return True
    except ApiException:
        return False


def create_build_congfig(spec, name, namespace, logger):
    template_values = dict(
        GIT_BRANCH=spec.get("gitBranch", "master"),
        GIT_REPO=spec.get("gitRepo"),
        NAME=spec.get("appName", name),
        NAMESPACE=namespace,
        APP_NAME=spec.get("appName", name),
        STREAM_NAME="{name}:{tag}".format(name=spec.get("appName", name), tag=spec.get("tag", "latest")),
        empty="{}",
    )

    crd_values = dict(
        group="build.openshift.io",
        version="v1",
        namespace=namespace,
        plural="buildconfigs",
    )

    if not _check_for_custom_resource(
        object_name="build config",
        name=template_values["NAME"],
        crd_values=crd_values,
        logger=logger,
    ):

        _create_custom_resource_from_template(
            object_name="build config",
            template_path="templates/build_config.yaml",
            template_values=template_values,
            crd_values=crd_values,
            logger=logger,
        )


def create_image_stream(spec, name, namespace, logger):
    template_values = dict(
        GIT_BRANCH=spec.get("gitBranch", "master"),
        GIT_REPO=spec.get("gitRepo"),
        NAME=spec.get("appName", name),
        NAMESPACE=namespace,
        APP_NAME=spec.get("appName", name),
        STREAM_NAME=spec.get("appName", name),
        empty="{}",
    )

    crd_values = dict(
        group="image.openshift.io",
        version="v1",
        namespace=namespace,
        plural="imagestreams",
    )

    if not _check_for_custom_resource(
        object_name="image steam",
        name=template_values["NAME"],
        crd_values=crd_values,
        logger=logger,
    ):
        _create_custom_resource_from_template(
            object_name="image steam",
            template_path="templates/image_stream.yaml",
            template_values=template_values,
            crd_values=crd_values,
            logger=logger,
        )

    return lambda: _get_custom_resource(
        name=template_values["NAME"],
        crd_values=crd_values,
    )


def _get_image_ref(image_stream, tag_name):
    tags = image_stream["status"]["tags"]
    matching_tags = [t for t in image_stream["status"]["tags"] if t["tag"] == tag_name]
    if not matching_tags:
        raise ValueError("Tag not found")

    tag = matching_tags[0]

    if "items" not in tag or not tag["items"]:
        raise ValueError("No items in tag dicription perhaps no buids")

    latest_build = sorted(tag["items"], key=lambda i: dtparse(i["created"]))[0]
    return latest_build["dockerImageReference"]


def _wait_for_build(get_image_stream, spec, retrys=5):
    atempts = 0
    while atempts < retrys:
        try:
            image_stream = get_image_stream()
            _get_image_ref(image_stream, spec.get("tagName", "latest"))
            return image_stream
        except KeyError:
            time.sleep(1)
        atempts += 1

    raise TimeoutError("No build found")


def _get_deployment(name, namespace):
    api = kubernetes.client.CustomObjectsApi()
    return api.read_namespaced_deployment(name=name, namespace=namespace)


def _check_for_deployment(name, namespace, logger):
    logger.info("looking to see if deployment aready exists")
    try:
        _get_deployment(name, namespace)
        return True
    except ApiException:
        return False


def create_deployment(spec, name, namespace, get_image_stream, logger):

    if not _check_for_deployment(name, namespace, logger):

        _wait_for_build(get_image_stream, spec, logger)
        image_stream = get_image_stream()

        template_values = dict(
            GIT_BRANCH=spec.get("gitBranch", "master"),
            GIT_REPO=spec.get("gitRepo"),
            NAME=spec.get("appName", name),
            NAMESPACE=namespace,
            APP_NAME=spec.get("appName", name),
            IMAGE=_get_image_ref(image_stream, spec.get("tagName", "latest")),
            empty="{}",
        )

        body = _process_template(
            object_name="deployment",
            template_path="templates/deployment.yaml",
            template_values=template_values,
            logger=logger,
        )
        api = kubernetes.client.AppsV1Api()
        api.create_namespaced_deployment(body=body, namespace=template_values["NAMESPACE"])


@kopf.on.create("workflows.engine", "v1", "todos")
def create_fn(spec, name, namespace, logger, **kwargs):
    logger.info("Todo CRD created")
    create_build_congfig(spec, name, namespace, logger)
    get_image_stream = create_image_stream(spec, name, namespace, logger)
    create_deployment(spec, name, namespace, get_image_stream, logger)