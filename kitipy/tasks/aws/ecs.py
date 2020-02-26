"""This package provides tasks for deploying to ECS.

It expects `ecs_cluster_name` parameter to be defined in the stage
configuration.

Also, it expects following stack parameters:

* `ecs_service_version` (number):
    The current version of the ECS service. This can be used to recreate a
    service whenever changes have to be made on `loadBalancers` and
    `serviceRegistries` parameters as these parameters can't be changed ;

* `ecs_task_defnition` (Callable[[kitipy.Context], dict]):
    A function returning the ECS task definition for that service. See https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html ;

* `ecs_container_transformer` (Callable[[kitipy.Context, str], dict]):
    A function returning the containers to put in the task definition. Check
    helper functions in kitipy.libs.aws.ecs module (e.g. convert_compose_to_ecs_config).
    The second argument passed to the callable is the image tag set through the
    CLI argument or via the IMAGE_TAG env var ;

* `ecs_oneoff_container_transformer` (Callable[[kitipy.Context, dict, string], dict]):
    A function returning the containers to put in the task definition when
    running oneoff tasks. It takes the current kitipy Context, the list of
    containers as returned by `ecs_container_transformer` and the target
    container where the command will run (as specified via CLI arg).

* `ecs_service_definition` (Callable[[kitipy.Context], dict]):
    A function returning the ECS service definition. See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.create_service ;

Example:

config = {
    'stages': {
        'prod': {
            'type': 'local',
            'default': True,
            'ecs_cluster_name': 'knpinternals-prod',
        },
    },
    'stacks': {
        'taiga-app': {
            'ecs_container_transformer': (lambda kctx, image_tag: kitipy.functools.pipe(
                    partial(convert_compose_to_ecs_config, compose_file='services/taiga/app.yml'),
                    partial(set_image_tag, image_tag=image_tag),
                    partial(set_readonly_fs),
                    partial(add_secrets, secrets={
                        'app': taiga_app_secrets(),
                        'events': taiga_app_secrets(),
                    }),
                )
            ),
            'ecs_task_defnition': (lambda kctx: {
                'family': 'taiga-app',
                'cpu': 256,
                'memory': 512,
                'networkMode': 'awsvpc',
                'taskRoleArn': taiga_app_task_role_arn(kctx),
                'executionRoleArn': taiga_app_execution_role_arn(kctx),
                'requiresCompatibilities': [],
            }),
            'ecs_service_version': 1,
            'ecs_service_definition': (lambda kctx: {
                'launchType': 'EC2',
                'networkConfiguration': {
                    'awsvpcConfiguration': {
                        "subnets": vpc_subnet_ids(kctx),
                        "securityGroups": [taiga_app_security_group_id(kctx)],
                        "assignPublicIp": "DISABLED",
                    },
                },
            }),
        },
    },
}
"""

import click
import kitipy
from typing import List, Optional


@kitipy.group(name="ecs")
def task_group():
    """Manage API stack on AWS infra."""
    pass


@task_group.task()
@click.argument("version", nargs=1, type=str, envvar="IMAGE_TAG")
def deploy(kctx: kitipy.Context, version: str):
    """Deploy a given version to ECS."""
    client = kitipy.libs.aws.ecs.new_client()
    stack = kctx.config["stacks"][kctx.stack.name]
    cluster_name = kctx.stage["ecs_cluster_name"]
    service_name = "%s-%d" % (kctx.stack.name, stack["ecs_service_version"])

    service_def = stack["ecs_service_definition"](kctx)
    task_def = stack["ecs_task_definition"](kctx)
    task_def["containerDefinitions"] = stack["ecs_container_transformer"](
        kctx, version)

    task_def_tags = task_def["tags"] if task_def["tags"] in task_def else []
    task_def_tags.append({'key': 'kitipy.image_tag', 'value': version})

    try:
        deployment_id = kitipy.libs.aws.ecs.upsert_service(
            client, cluster_name, service_name, task_def, service_def)
    except kitipy.libs.aws.ecs.ServiceDefinitionChangedError:
        kctx.fail("Could not deploy the API: ECS service definition has " +
                  "changed. You have to increment the version number in the " +
                  "./tasks.py file before re-running this command.")

    for event in kitipy.libs.aws.ecs.watch_deployment(client, cluster_name,
                                                      service_name,
                                                      deployment_id):
        createdAt = event["createdAt"].isoformat()
        message = event["message"]
        kctx.info("[{createdAt}] {message}".format(createdAt=createdAt,
                                                   message=message))


@task_group.task()
@click.option(
    "--version",
    nargs=1,
    type=str,
    envvar="IMAGE_TAG",
    help="The version of the current ECS deployment is reused when not specfied."
)
@click.argument("container", nargs=1, type=str)
@click.argument("command", nargs=-1, type=str)
def run(kctx: kitipy.Context, container: str, command: List[str],
        version: Optional[str]):
    """Run a given command in a oneoff task."""
    client = kitipy.libs.aws.ecs.new_client()
    stack = kctx.config["stacks"][kctx.stack.name]
    cluster_name = kctx.stage["ecs_cluster_name"]
    service_name = "%s-%d" % (kctx.stack.name, stack["ecs_service_version"])
    task_def = stack["ecs_task_definition"](kctx)

    if version is None:
        regular_task_def = kitipy.libs.aws.ecs.get_task_definition(
            client, task_def["family"])
        version = next((tag["value"]
                        for tag in regular_task_def["tags"]
                        if tag["key"] == "kitipy.image_tag"), None)

    if version is None:
        kctx.fail(
            "No --version flag was provided and no deployments have been found."
        )

    task_name = "-".join(command)

    containers = stack["ecs_container_transformer"](kctx, version)
    containers = stack["ecs_oneoff_container_transformer"](kctx, containers,
                                                           container)

    run_args = stack["ecs_service_definition"](kctx)
    task_def["containerDefinitions"] = containers

    task_arn = kitipy.libs.aws.ecs.run_oneoff_task(client, cluster_name, task_name,
                                               task_def, container, command,
                                               run_args)
    kitipy.libs.aws.ecs.wait_until_task_stops(client, cluster_name, task_arn)
