"""This modules provides functions to implement a deployment pipeline for ECS.
The first part of this module is dedicated to loading and transforming task
definitions. Whereas the second part is a group of wrappers around boto3 SDK.
"""

import boto3
import datetime
import json
import kitipy
import mypy_boto3_ecs
import time
from container_transform.converter import Converter  # type: ignore
from typing import Dict, Generator, List, Optional, Tuple


def convert_compose_to_ecs_config(compose_file: str) -> dict:
    """Convert a compose file into an ECS task definition.

    Args:
        compose_file (str): Path to the compose file to convert.

    Returns:
        dict: Contains the converted task definition.
    """
    converter = Converter(filename=compose_file,
                          input_type="compose",
                          output_type="ecs")
    return json.loads(converter.convert())


def set_image_tag(containers: List[dict],
                  tag: str,
                  placeholder: str = "${IMAGE_TAG}") -> List[dict]:
    """Iterate over a list of containers and replace the given placeholder by
    a tag, in the containers' image parameter.

    Args:
        containers (List[dict]):
            A list of containers.
        tag (str):
            The image tag that should be set.
        placeholder (str):
            The placeholder to replace in containers' image parameter.
    
    Returns:
        List[dict]: The mutated list of containers.
    """
    return [
        dict(c, image=c["image"].replace(placeholder, tag)) for c in containers
    ]


def set_readonly_fs(containers: List[dict]) -> List[dict]:
    """Iterate over a list of containers and add the readonly parameter to all.

    Args:
        containers (List[dict]): A list of containers to transform.
    
    Returns:
        List[dict]: The list of transformed containers.
    """
    return [dict(c, readonlyRootFilesystem=True) for c in containers]


def add_secrets(containers):
    kctx = kitipy.get_current_context()
    by_name = {c["name"]: c for c in containers}
    stack = kctx.config["stacks"][kctx.stack.name]
    secrets = stack["secrets"] if "secrets" in stack else {}

    for cname, secrets_fn in secrets.items():
        secrets = secrets_fn(kctx.stage["name"])
        by_name[cname].update({"secrets": secrets})

    return list(by_name.values())


def remove_containers(containers, excluding: Dict[str, str] = {}):
    return list(filter(lambda c: c["name"] in excluding, containers))


class ServiceNotFoundError(Exception):
    """ServiceNotFoundError is raised when trying to access an ECS service or
    one of its property (e.g. events or deployments) but the given service is
    not found."""
    pass


class DeploymentNotFoundError(Exception):
    """DeploymentNotFoundError is raised when looking for a deployment in a 
    service description but that deployment is not found."""
    pass


class ServiceDefinitionChangedError(Exception):
    """ServiceDefinitionChangedError is raised when trying to upsert a service
    but either its `loadBalancers` or `serviceRegistries` parameters don't
    match the parameters of the service currently deployed."""
    pass


def new_client() -> mypy_boto3_ecs.ECSClient:
    """Create a new boto3 ECS client.

    Returns:
        mypy_boto3_ecs.ECSClient: The API client.
    """
    return boto3.client("ecs")


def register_task_definition(client: mypy_boto3_ecs.ECSClient,
                             task_def: dict) -> str:
    """Register a task definition and returns its id.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        task_def (dict):
            A task definition as expected by ECS API. See https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html.

    Returns:
        str: The definition ID in format "family:revision".
    """
    resp = client.register_task_definition(**task_def)
    task_def_id = "{0}:{1}".format(resp["taskDefinition"]["family"],
                                   resp["taskDefinition"]["revision"])

    # @TODO: use a proper logger
    kctx = kitipy.get_current_context()
    kctx.info(("A new task definition {task_def_id} " +
               "has been registered").format(task_def_id=task_def_id))

    return task_def_id


def upsert_service(client: mypy_boto3_ecs.ECSClient, cluster_name: str,
                   service_name: str, task_def: dict, service_def: dict) -> str:
    """Upsert an ECS service with its task definition.
    
    The desiredCount of the current service deployment is automatically reused.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service should be looked for.
        service_name (str):
            The name of the service to look for.
        task_def (dict):
            The task definition to register and deploy. See https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html.
        service_def (dict):
            The definition of the service to upsert. See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.create_service.
    
    Returns:
        string: The ID of the service deployment.

    Raises:
        ServiceDefinitionChangedError:
            Both loadBalancers and serviceRegistries parameters from the
            service definitions can't be changed after creation. If you need to
            update these parameters, you should change the service name.
    """
    # @TODO: use a proper logger
    kctx = kitipy.get_current_context()

    task_def_id = register_task_definition(client, task_def)

    service_def["cluster"] = cluster_name
    service_def["service"] = service_name

    if find_service_arn(client, cluster_name, service_name) is None:
        kctx.info(("Creating service {service} " +
                   "in {cluster} cluster.").format(service=service_name,
                                                   cluster=cluster_name))
        resp = client.create_service(**service_def)
        return resp["service"]["deployments"][0]["id"]

    existing = describe_service(client, cluster_name, service_name)

    if existing["loadBalancers"] != service_def["loadBalancers"]:
        raise ServiceDefinitionChangedError(
            "The parameter loadBalancers has changed.")

    if existing["serviceRegistries"] != service_def["serviceRegistries"]:
        raise ServiceDefinitionChangedError(
            "The parameter serviceRegistries has changed.")

    kctx.info(("Updating service {service} " + "in {cluster} cluster.").format(
        service=service_name, cluster=cluster_name))

    service_def["desiredCount"] = existing["desiredCount"]

    resp = client.update_service(**service_def)
    return resp["service"]["deployments"][0]["id"]


def describe_service(
    client: mypy_boto3_ecs.ECSClient, cluster_name: str, service_name: str
) -> mypy_boto3_ecs.type_defs.ClientDescribeServicesResponseservicesTypeDef:
    """Find the given service in the given cluster.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service should be looked for.
        service_name (str):
            The name of the service to look for.
    
    Returns:
        mypy_boto3_ecs.type_defs.ClientDescribeServicesResponseservicesTypeDef:
            The selected service.

    Raises:
        ServiceNotFoundError: When no matching service was found.
        RuntimeError: When more than 1 service have been returned by ECS API.
    """
    resp = client.describe_services(cluster=cluster_name,
                                    services=[service_name])
    services = resp["services"]

    if len(services) == 0:
        raise ServiceNotFoundError(
            "Service {0} not found.".format(service_name))
    elif len(services) != 1:
        raise RuntimeError("Expected 1 service in the list but got %d." %
                           (len(services)))

    return services[0]


def list_service_events(
    client: mypy_boto3_ecs.ECSClient, cluster_name: str, service_name: str
) -> List[mypy_boto3_ecs.type_defs.
          ClientDescribeServicesResponseserviceseventsTypeDef]:
    """List the ECS events for a given service.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service should be looked for.
        service_name (str):
            The name of the service to look for.

    Returns:
        List[mypy_boto3_ecs.type_defs.
             ClientDescribeServicesResponseserviceseventsTypeDef]:
            List of ECS events for the selected service.

    Raises:
        ServiceNotFoundError: When no matching service was found.
        RuntimeError: When more than 1 service have been returned by ECS API.
    """
    resp = describe_service(client, cluster_name, service_name)
    return resp["events"]


def find_service_deployments(
    client: mypy_boto3_ecs.ECSClient,
    cluster_name: str,
    service_name: str,
) -> List[mypy_boto3_ecs.type_defs.
          ClientDescribeServicesResponseservicesdeploymentsTypeDef]:
    """List the deployments for a given service.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service should be looked for.
        service_name (str):
            The name of the service to look for.

    Returns:
        List[mypy_boto3_ecs.type_defs.
             ClientDescribeServiceResponseservicedeploymentsTypeDef]:
            List of deployments for the selected service.

    Raises:
        ServiceNotFoundError: When no matching service was found.
        RuntimeError: When more than 1 service have been returned by ECS API.
    """
    resp = describe_service(client, cluster_name, service_name)
    return resp["deployments"]


def find_service_deployment(
    client: mypy_boto3_ecs.ECSClient,
    cluster_name: str,
    service_name: str,
    deployment_id: str,
) -> Optional[mypy_boto3_ecs.type_defs.
              ClientDescribeServicesResponseservicesdeploymentsTypeDef]:
    """Find a specific deployment for a given service.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service run.
        service_name (str):
            The name of the deployed service.
        deployment_id (str):
            The ID of the deployment to look for.

    Returns:
        Optional[mypy_boto3_ecs.type_defs.
                 ClientDescribeServiceResponseservicedeploymentsTypeDef]]:
            The service deployment if found, None otherwise.

    Raises:
        ServiceNotFoundError: When no matching service was found.
        RuntimeError: When more than 1 service have been returned by ECS API.
    """
    deployments = find_service_deployments(client, cluster_name, service_name)
    deployment = next((d for d in deployments if d["id"] == deployment_id),
                      None)

    return deployment


def find_service_arn(client: mypy_boto3_ecs.ECSClient, cluster_name: str,
                     service_name: str) -> Optional[str]:
    """Find the ARN of a service.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service run.
        service_name (str):
            The name of the service to look for.

    Returns:
        Optional[str]:
            The service ARN if found, None otherwise.
    """
    list_resp = client.list_services(cluster=cluster_name)

    for arn in list_resp["serviceArns"]:
        if arn.endswith("service/" + service_name):
            return arn

    return None


def watch_deployment(
    client: mypy_boto3_ecs.ECSClient,
    cluster_name: str,
    service_name: str,
    deployment_id: str,
    max_attempts: int = 120,
) -> Generator[mypy_boto3_ecs.type_defs.
               ClientDescribeServicesResponseserviceseventsTypeDef, None, None]:
    """Wait until a service deployment is complete and stream ECS events.

    This function polls the ECS API every 5s until the given deployment has
    completed. A deployment is completed once it has PRIMARY status and its
    number of desired replicas matches the running count.

    Args:
        client (mypy_boto3_ecs.ECSClient):
            An ECS API client.
        cluster_name (str):
            The name of the cluster where the service run.
        service_name (str):
            The name of the service to look for.
        deployment_id (str):
            The ID of the deployment to watch.
        max_attempts (number):
            The maximum number of attempts to be made. Default: 120 (~10 minutes).

    Raises:
        ServiceNotFoundError: When no matching service was found.
        RuntimeError: When more than 1 service have been returned by ECS API.
        DeploymentNotFoundError: When no deployment with the given ID is found.
        RuntimeError: When max_attempts is reached.
    """
    kctx = kitipy.get_current_context()
    status = None
    last_date = None
    attempts = 0.

    while attempts < max_attempts:
        deployment = find_service_deployment(client, cluster_name, service_name,
                                             deployment_id)

        if deployment is None:
            raise DeploymentNotFoundError(
                "Deployment {0} not found.".format(deployment_id))

        if last_date is None:
            last_date = deployment["createdAt"]

        status = deployment["status"]
        events = list_service_events(client, cluster_name, service_name)
        new_events = list(e for e in events if e["createdAt"] > last_date)

        if len(new_events) > 0:
            last_date = new_events[0]["createdAt"]

        for event in reversed(new_events):
            yield event

        running_count = deployment["runningCount"]
        desired_count = deployment["desiredCount"]
        if status == "PRIMARY" and running_count == desired_count:
            return

        time.sleep(5)
        attempts += 1

    raise RuntimeError(
        "watch_deployment timed out before the deployment was completed. It is probably broken."
    )
