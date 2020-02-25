import json
import kitipy
import os
from .tfcloud import get_current_state_version_outputs
from typing import Any, Dict, Optional


def _get_token():
    return os.getenv("TFCLOUD_API_TOKEN")


def _output(kctx: kitipy.Context, stage: str) -> dict:
    workspace_id = kctx.stage["tfcloud_workspace_id"]
    return get_current_state_version_outputs(_get_token(), workspace_id)


def _memoize(fn):
    memo = {}

    def helper(kctx: kitipy.Context,
               stage: Optional[str] = None) -> Dict[str, Any]:
        if stage is None:
            stage == kctx.stage['name']

        if stage not in memo:
            memo[stage] = fn(kctx, stage)
        return memo[stage]

    return helper


output = _memoize(_output)
"""Get the Terraform outputs associated with a Terraform workspace from Terraform
Cloud. The workspace ID is looked for in the config of the given stage, in the
kitipy Context.

Note that this lib expects the API token for Terraform Cloud to be specified
via the env var TFCLOUD_API_TOKEN.

Args:
    kctx (kitipy.Context):
        The current kitipy context.
    stage (Optional[str]):
        Name of the stage where the Terraform workspace ID is looked for. If
        no stage name is passed, the name of the current stage is used.

Returns:
    Dict[str, Any]: The outputs of the last state version of the workspace.
"""
