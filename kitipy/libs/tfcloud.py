import requests
import sys
from typing import Callable, Dict, List


def _headers(token: str):
    return {
        "Authorization": "Bearer "+token,
    }


def _build_url(pattern: str, **kwargs):
    endpoint = pattern.format(**kwargs).lstrip('/')
    return "https://app.terraform.io/api/v2/" + endpoint


def get_current_state_version_outputs(
    token: str,
    workspace_id: str,
) -> Dict:
    """Fetch the outputs for the current state version.

    Args:
        token (str):
            The bearer token to use when calling the API.
        workspace_id (str):
            ID of the Terraform Cloud workspace that should be queried.
    
    Returns:
        Dict: The raw API response.
    """

    current_url = _build_url("/workspaces/{workspace_id}/current-state-version",
                             workspace_id=workspace_id)

    # current-state-version endpoint has an include parameter which can take
    # "output" to include the output values of that state version.
    # Unfortunately, that parmeter seem broken since the output names in the
    # response have their underscores transformed into hyphens for whatever
    # reason. Thus, we fetch it only to get the URL of the raw state file 
    # as stored by Terraform.
    current_r = requests.get(current_url, headers=_headers(token))
    if current_r.status_code != requests.codes.ok:
        raise RuntimeError(
            "Request to %s failed with code %d" % (current_url, current_r.status_code))

    # We then download the raw state file and extract the outputs from there.
    current_state = current_r.json()
    state_url = current_state["data"]["attributes"]["hosted-state-download-url"]
    state_r = requests.get(state_url, headers=_headers(workspace_id))
    if current_r.status_code != requests.codes.ok:
        raise RuntimeError(
            "Request to %s failed with code %d" % (state_url, state_r.status_code))
    
    state = state_r.json()
    return {k: v["value"] for k, v in state["outputs"].items()}
