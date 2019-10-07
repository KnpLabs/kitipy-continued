"""Common kitipy commands and command groups filters for Docker tasks.

These filters have to be used with kitipy.Command and kitipy.Group classes, or 
through kitipy.command() and kitipy.group() decorators.
"""

import click
import kitipy
from . import ComposeStack, SwarmStack
from typing import Callable, Type


def _only_stack_type(stack_type: Type) -> Callable[[click.Context], bool]:
    def only(click_ctx: click.Context) -> bool:
        """Check if the current kitipy stack has the expected type.

        Args:
            click_ctx (click.Context): Current click context.
        
        Returns:
            bool: Either the stack of the desired type.

            It returns False if no kitipy Context could be found or if the
            stack is not of the desired type.
        """

        kctx = click_ctx.find_object(kitipy.Context)
        if kctx is None or not isinstance(kctx.stack, stack_type):
            return False

        return True

    return only


compose_only = _only_stack_type(ComposeStack)
"""This filter function can be used to filter out commands in a stack-scoped
command tree when the loaded stack isn't based on docker-compose.
"""

swarm_only = _only_stack_type(SwarmStack)
"""This filter function can be used to filter out commands in a stage-scoped
command tree when the loaded stage isn't based on docker swarm.
"""
