import boto3
from botocore.exceptions import ClientError
import argparse
from datetime import datetime

def delete_cache_behavior(cloudfront, distribution_id, path_pattern):
    """
    Deletes a cache behavior for a specific path pattern.
    """
    try:
        response = cloudfront.get_distribution_config(
            Id=distribution_id
        )
        
        etag = response['ETag']
        config = response['DistributionConfig']
        
        # Find and remove the behavior for the specified path
        if 'CacheBehaviors' in config and config['CacheBehaviors']['Items']:
            original_length = len(config['CacheBehaviors']['Items'])
            config['CacheBehaviors']['Items'] = [
                behavior for behavior in config['CacheBehaviors']['Items']
                if behavior['PathPattern'] != path_pattern
            ]
            new_length = len(config['CacheBehaviors']['Items'])
            
            if new_length < original_length:
                config['CacheBehaviors']['Quantity'] = new_length
                
                cloudfront.update_distribution(
                    DistributionConfig=config,
                    Id=distribution_id,
                    IfMatch=etag
                )
                print(f"Successfully deleted cache behavior for path pattern: {path_pattern}")
            else:
                print(f"No cache behavior found for path pattern: {path_pattern}")
                
    except ClientError as e:
        print(f"Error deleting cache behavior: {e}")
        raise

def manage_cache_behavior(distribution_id, path_pattern, enable_caching=True):
    """
    Manages cache behavior for a CloudFront distribution path pattern.
    Either adds a new cache behavior or invalidates cache and deletes the rule for the path.
    
    Args:
        distribution_id (str): The CloudFront distribution ID
        path_pattern (str): The path pattern to match (e.g., '/about-us/*')
        enable_caching (bool): If True, adds cache behavior. If False, invalidates cache and deletes rule
    """
    cloudfront = boto3.client('cloudfront')
    
    if enable_caching:
        try:
            # Get the current distribution config
            response = cloudfront.get_distribution_config(
                Id=distribution_id
            )
            
            etag = response['ETag']
            config = response['DistributionConfig']
            
            new_behavior = {
                'PathPattern': path_pattern,
                'TargetOriginId': config['Origins']['Items'][0]['Id'],
                'ViewerProtocolPolicy': 'https-only',
                'CachePolicyId': 'xxxx-xxx-xxx-xxxx',  # Managed-CachingOptimized
                'OriginRequestPolicyId': 'xxxx-xxx-xxx-xxxx',  # Managed-AllViewer
                'AllowedMethods': {
                    'Quantity': 7,
                    'Items': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
                    'CachedMethods': {
                        'Quantity': 2,
                        'Items': ['GET', 'HEAD']
                    }
                },
                'Compress': True,
                'SmoothStreaming': False,
                'FieldLevelEncryptionId': '',
                'LambdaFunctionAssociations': {
                    'Quantity': 0,
                    'Items': []
                }
            }
            
            if 'CacheBehaviors' not in config:
                config['CacheBehaviors'] = {'Quantity': 0, 'Items': []}
                
            # Check if behavior already exists for this path pattern
            existing_behavior_index = None
            for i, behavior in enumerate(config['CacheBehaviors']['Items']):
                if behavior['PathPattern'] == path_pattern:
                    existing_behavior_index = i
                    break
            
            if existing_behavior_index is not None:
                # Update existing behavior
                config['CacheBehaviors']['Items'][existing_behavior_index] = new_behavior
            else:
                # Add new behavior
                config['CacheBehaviors']['Items'].append(new_behavior)
                config['CacheBehaviors']['Quantity'] += 1
            
            cloudfront.update_distribution(
                DistributionConfig=config,
                Id=distribution_id,
                IfMatch=etag
            )
            
            return f"Successfully added/updated cache behavior for path pattern: {path_pattern}"
            
        except ClientError as e:
            print(f"Error updating distribution: {e}")
            raise
            
    else:
        try:
            # First create cache invalidation
            invalidation = cloudfront.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': [path_pattern]
                    },
                    'CallerReference': str(datetime.now().timestamp())
                }
            )
            
            invalidation_id = invalidation['Invalidation']['Id']
            
            # Then delete the cache behavior rule
            delete_cache_behavior(cloudfront, distribution_id, path_pattern)
            
            return {
                "invalidation_id": invalidation_id,
                "message": f"Successfully invalidated cache and deleted rule for path pattern: {path_pattern}"
            }
            
        except ClientError as e:
            print(f"Error in invalidation/deletion process: {e}")
            raise

def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    Expected event format:
    {
        "distribution_id": "XXX",
        "path_pattern": "/about-us/*",
        "enable_caching": true
    }
    """
    distribution_id = event.get('distribution_id')
    path_pattern = event.get('path_pattern')
    enable_caching = event.get('enable_caching', True)
    
    if not distribution_id or not path_pattern:
        return {
            'statusCode': 400,
            'body': 'Missing required parameters: distribution_id and path_pattern are required'
        }
    
    try:
        result = manage_cache_behavior(distribution_id, path_pattern, enable_caching)
        
        if enable_caching:
            return {
                'statusCode': 200,
                'body': result
            }
        else:
            return {
                'statusCode': 200,
                'body': {
                    'invalidation_id': result['invalidation_id'],
                    'message': result['message']
                }
            }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }

# For local testing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Manage CloudFront cache behavior')
    parser.add_argument('--distribution-id', required=True, help='CloudFront distribution ID')
    parser.add_argument('--path-pattern', required=True, help='Path pattern to manage')
    parser.add_argument('--enable-caching', action='store_true', help='Enable caching for the path')
    
    args = parser.parse_args()
    
    result = manage_cache_behavior(
        distribution_id=args.distribution_id,
        path_pattern=args.path_pattern,
        enable_caching=args.enable_caching
    )
    
    if isinstance(result, dict):
        print(f"Invalidation ID: {result['invalidation_id']}")
        print(result['message'])
    else:
        print(result)