"""This module exposes common tasks for managing docker-compose and Swarm
stacks.
"""

import click
import kitipy
from . import stack, actions
from .filters import compose_only, swarm_only
import kitipy.docker.filters
from typing import List


@kitipy.group()
@kitipy.pass_context
def docker_tasks(kctx: kitipy.Context):
    if not isinstance(kctx.stack, stack.BaseStack):
        kctx.fail("No valid Docker stack available in kipity Context.")


@docker_tasks.task()
@click.argument('services', nargs=-1, type=str)
@click.option('--tag', type=str, default='dev')
def build(kctx: kitipy.Context, tag: str = 'dev', services: List[str] = []):
    validate_tag(kctx, tag)
    kctx.stack.build(services)


@docker_tasks.task()
@click.argument('services', nargs=-1, type=str)
@click.option('--tag', type=str, default='dev')
def push(kctx: kitipy.Context, tag: str = 'dev', services: List[str] = []):
    validate_tag(kctx, tag)
    kctx.stack.push(services)


@docker_tasks.task()
@click.argument('services', nargs=-1, type=str)
@click.option('--tag', type=str, default='dev')
def up(kctx: kitipy.Context, tag: str = 'dev', services: List[str] = []):
    kctx.stack.up(services, detach=True)


@docker_tasks.task()
def down(kctx: kitipy.Context):
    kctx.stack.down()


@docker_tasks.task()
def ps(kctx: kitipy.Context):
    kctx.stack.ps()


@docker_tasks.task()
@click.argument('services', nargs=-1, type=str)
@click.option('--since', type=str, default="1m")
def logs(kctx: kitipy.Context, services: List[str], since: str):
    kctx.stack.logs(services, since=since, follow=True)


@docker_tasks.task()
@click.argument('services', nargs=-1, type=str)
def restart(kctx: kitipy.Context, services: List[str]):
    kctx.stack.restart(services)


@docker_tasks.task()
@click.argument('service', nargs=1, type=str)
@click.argument('cmd', nargs=-1, type=str)
def exec(kctx: kitipy.Context, service: str, cmd: List[str]):
    kctx.stack.exec(service, cmd)


@docker_tasks.task()
@click.argument('service', nargs=1, type=str)
def shell(kctx: kitipy.Context, service: str):
    shell = actions.find_default_shell(kctx, service)
    shell = shell if shell else '/bin/sh'
    kctx.stack.exec(service, shell)


@docker_tasks.task()
@click.argument('service', type=str, required=True)
@click.argument('cmd', nargs=-1, type=str)
@click.option('-u', 'user', default=None)
def run(kctx: kitipy.Context, service: str, user, cmd: List[str]):
    if len(cmd) == 0:
        cmd = ["/bin/sh"]
    kctx.stack.run(service, ' '.join(cmd), user=user)


@docker_tasks.task()
@click.argument('service', type=str, required=True)
@click.argument('replica_id', type=int, default=1)
def inspect(kctx: kitipy.Context, service: str, replica_id: int):
    kctx.stack.inspect(service, replica_id)


@docker_tasks.task(filters=[compose_only])
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def compose(kctx: kitipy.Context, args: List[str] = []):
    """Run raw docker-compose commands against the current stack."""
    kctx.stack.raw(args)


def validate_tag(kctx: kitipy.Context, image_ref: str):
    """Check if the given image reference exists on a remote Docker registry.
    
    Args:
        kctx (kitipy.Context): The current kitipy Context.
        image_ref (str):
            A full image reference composed of: the repository to check, the
            base image name and the image tag.

    Raises:
        click.Exception: When the given image tag doesn't exist.
    """
    if len(image_ref) == 0:
        kctx.fail(
            "No image tag provided. You can provide it through --tag flag or IMAGE_TAG env var."
        )

    images = (service['image'] for service in kctx.stack.config['services'])
    for image in images:
        result = actions.buildx_imagetools_inspect(image_ref, _check=False)
        if result.returncode != 0:
            kctx.fail('Image %s not found on remote registry.' % (image_ref))
