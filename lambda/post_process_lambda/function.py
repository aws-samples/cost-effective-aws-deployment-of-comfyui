import os
import boto3

cognito_idp = boto3.client('cognito-idp')


def lambda_handler(event, context):
    try:
        print(event)
        request_type = event['RequestType']
        if request_type == 'Create' or request_type == 'Update':
            cognito_user_pool_id = os.environ['COGNITO_USER_POOL_ID']
            cognito_client_id = os.environ['COGNITO_CLIENT_ID']

            # Get current Cognito client settings
            user_pool_client_json = cognito_idp.describe_user_pool_client(
                UserPoolId=cognito_user_pool_id,
                ClientId=cognito_client_id
            )
            user_pool_client_CallbackURLs = user_pool_client_json["UserPoolClient"]["CallbackURLs"]
            user_pool_client_LogoutURLs = user_pool_client_json["UserPoolClient"]["LogoutURLs"]

            print("Force lower case in Cognito CallbackURLs and LogoutURLs")
            user_pool_client_CallbackURLs = [
                url.lower() for url in user_pool_client_CallbackURLs]
            user_pool_client_LogoutURLs = [
                url.lower() for url in user_pool_client_LogoutURLs]

            # Update Cognito callback URLs and sign-out URL
            response = cognito_idp.update_user_pool_client(
                UserPoolId=cognito_user_pool_id,
                ClientId=cognito_client_id,
                CallbackURLs=user_pool_client_CallbackURLs,
                LogoutURLs=user_pool_client_LogoutURLs,
                SupportedIdentityProviders=user_pool_client_json[
                    "UserPoolClient"]["SupportedIdentityProviders"],
                AllowedOAuthFlows=user_pool_client_json["UserPoolClient"]["AllowedOAuthFlows"],
                AllowedOAuthScopes=user_pool_client_json["UserPoolClient"]["AllowedOAuthScopes"],
                AllowedOAuthFlowsUserPoolClient=user_pool_client_json[
                    "UserPoolClient"]["AllowedOAuthFlowsUserPoolClient"],
            )

            return {}
        elif request_type == 'Delete':
            return {}
    except Exception as e:
        print(e)
        raise
