import boto3


def ensure_is_right_account(expected: str):
    """Check if the current AWS account id matches the given one.

    Args:
        expected (str): The expected AWS account id.

    Raises:
        RuntimeError:
            Whenever the actual account id doesn't match the expected one.
    """

    # @TODO: fix typing issue
    client = boto3.client('sts')  # type: ignore
    identity = client.get_caller_identity()
    current = identity['Account']

    if current != expected:
        raise RuntimeError(("You're not using the right AWS account. " +
                            "Current account: {current} - Expected: %s").format(
                                current=current, expected=expected))
