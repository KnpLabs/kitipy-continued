import base64
import boto3
import kitipy
import mypy_boto3_ecr
from typing import Dict, List, Optional


def new_client() -> mypy_boto3_ecr.ECRClient:
    return boto3.client('ecr')


def get_authorizaiton_token(
        client: mypy_boto3_ecr.ECRClient,
        registry_ids: Optional[List[str]] = None) -> List[Dict[str, str]]:
    args = {}
    if registry_ids is not None:
        args["registryIds"] = registry_ids

    resp = client.get_authorization_token(**args)
    tokens = []

    for data in resp["authorizationData"]:
        token = data["authorizationToken"]
        decoded = str(base64.b64decode(token), encoding='utf-8')
        user, password = decoded.split(sep=':', maxsplit=2)

        tokens.append({
            "server": data["proxyEndpoint"],
            "username": user,
            "password": password,
        })

    return tokens


def authenticate():
    client = new_client()

    for token in get_authorizaiton_token(client):
        kitipy.docker.actions.registry_authenticate(**token)
