import boto3
import mypy_boto3_cloudfront
import time
from typing import List, Optional


def new_client() -> mypy_boto3_cloudfront.CloudFrontClient:
    return boto3.client('cloudfront')


def invalidate(client: mypy_boto3_cloudfront.CloudFrontClient,
               distribution_id: str,
               paths: List[str],
               caller_reference: Optional[str] = None) -> str:
    """Create a cache invalidation for a CloudFront distribution.

    Args:
        client (mypy_boto3_cloudfront.CloudFrontClient):
            A CloudFront API client.
        distribution_id (str):
            The ID of the CloudFront distribution to invalidate.
        paths (List[str]):
            A list of paths to invalidate (wildcards are supported).
        caller_reference (Optional[str]):
            A string used for request idempotency. The current timestamp is
            used if left empty.
    
    Returns:
        str:
            The ID of the CloudFront invalidation created.
    """
    invalidation_batch: mypy_boto3_cloudfront.type_defs.InvalidationBatchTypeDef = {
        'Paths': {
            'Quantity': len(paths),
            'Items': paths,
        },
        'CallerReference': caller_reference or str(time.time()),
    }
    resp = client.create_invalidation(DistributionId=distribution_id,
                                      InvalidationBatch=invalidation_batch)

    return resp['Invalidation']['Id']


def wait_until_invalidation_completed(
    client: mypy_boto3_cloudfront.CloudFrontClient, distribution_id: str,
    invalidation_id: str):
    """Wait until a CloudFront invalidation has completed.

    Args:
        client (mypy_boto3_cloudfront.CloudFront):
            A CloudFront API client.
        distribution_id (str):
            The ID of the CloudFront distribution associated to the
            invalidation to watch.
        invalidation_id (str):
            The ID of the CloudFront invalidation to watch.
    """
    waiter = client.get_waiter('invalidation_completed')
    waiter.wait(DistributionId=distribution_id, Id=invalidation_id)
