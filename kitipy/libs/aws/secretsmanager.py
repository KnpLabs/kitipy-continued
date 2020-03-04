"""This module is a little wrapper around boto3 API providing methods commonly
used in kitipy tasks.

@TODO:

* Add proper mypy stub for describe_secret_with_current_value() return value ;
"""

import kitipy
import boto3
from mypy_boto3_secretsmanager.client import SecretsManagerClient, GetSecretValueResponseTypeDef


def new_client() -> SecretsManagerClient:
    return boto3.client("secretsmanager")  # type: ignore


def describe_secret_with_current_value(client: SecretsManagerClient,
                                       secret_id: str) -> dict:
    """Retrieves the details of a secret with its current value.

    Args:
        client (SecretsManagerClient): A boto3 SecretsManager client instance.
        secret_id (str): ARN of the secret to retrieve.

    Returns:
        Dict: The response of both desribe_secret and get_secret_value are
              mxied together. See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html.
    """
    secret = client.describe_secret(SecretId=secret_id)

    value: GetSecretValueResponseTypeDef = {'SecretString': ''}
    try:
        value = client.get_secret_value(SecretId=secret_id)
    except client.exceptions.ResourceNotFoundException:
        pass

    return {**secret, **value}


def put_secret_value(client: SecretsManagerClient, secret_id: str,
                     value: str) -> None:
    """Store a new secret value.

    Args:
        client (SecretsManagerClient): A boto3 SecretsManager client instance.
        secret_id (str): ARN of the secret to edit.
        value (str): The new secret value.
    """

    client.put_secret_value(SecretId=secret_id, SecretString=value)
