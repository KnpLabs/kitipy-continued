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


@kitipy.group()
def ecs():
    """Manage API stack on AWS infra."""
    pass


@ecs.task()
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
