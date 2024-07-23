import boto3
import sys
import os

client = boto3.client('cognito-idp', 
    region_name = os.getenv('AWS_DEFAULT_REGION')
)
pool_ids_json = client.list_user_pools(
    # NextToken='string',
    MaxResults=60
)
poolname = "ComfyUIuserPool"
pool_ids = [pool["Name"] for pool in pool_ids_json["UserPools"] if poolname in pool["Name"] ]
# print(pool_ids)

pool_id = [ pool["Id"] for pool in pool_ids_json["UserPools"] if poolname in pool["Name"] ]

if len(pool_id) != 1:
    print("\nCan't reliably find the Cognito User Pool! Exiting...\n")
    print("Found these:",pool_ids)
    sys.exit(1)

pool_id = pool_id[0]
# print(pool_id)

# CREATE ADMIN USER for the User Pool
user_password = 'xPassw0rd!_x' # Change password before running the script!
response = client.admin_create_user(
    UserPoolId = pool_id,
    Username = "admin",
    UserAttributes = [
        # {"Name": "first_name", "Value": "admin"},
        # {"Name": "last_name", "Value": "admin"},
        {"Name": "email", "Value": "admin@admin.com"},
        { "Name": "email_verified", "Value": "true" }
    ],
    TemporaryPassword=user_password,
    # DesiredDeliveryMediums = ['EMAIL']
)

print("Created admin user and force password without reset")
response = client.admin_set_user_password(
    UserPoolId=pool_id,
    Username="admin",
    Password=user_password,
    Permanent=True
)


# ENFORCE LOWER CASE FOR CALLBACK URLS
pool_clients_json = client.list_user_pool_clients(
    UserPoolId=pool_id,
    MaxResults=60,
    # NextToken='string'
)
# print(pool_clients_json)
pool_client_id = pool_clients_json["UserPoolClients"][0]["ClientId"]

user_pool_client_json = client.describe_user_pool_client(
    UserPoolId=pool_id,
    ClientId=pool_client_id
)
# print(user_pool_client_json["UserPoolClient"])

user_pool_client_CallbackURLs = user_pool_client_json["UserPoolClient"]["CallbackURLs"]
user_pool_client_LogoutURLs = user_pool_client_json["UserPoolClient"]["LogoutURLs"]

# print(user_pool_client_CallbackURLs)
# print(user_pool_client_LogoutURLs)

# enforce lower case on URLs

print("Force lower case in Cognito CallbackURLs and LogoutURLs")
user_pool_client_CallbackURLs = [url.lower() for url in user_pool_client_CallbackURLs]
user_pool_client_LogoutURLs = [url.lower() for url in user_pool_client_LogoutURLs]

response = client.update_user_pool_client(
    UserPoolId=pool_id,
    ClientId=pool_client_id,
    CallbackURLs=user_pool_client_CallbackURLs,
    LogoutURLs=user_pool_client_LogoutURLs,
    SupportedIdentityProviders=user_pool_client_json["UserPoolClient"]["SupportedIdentityProviders"],
    AllowedOAuthFlows=user_pool_client_json["UserPoolClient"]["AllowedOAuthFlows"],
    AllowedOAuthScopes=user_pool_client_json["UserPoolClient"]["AllowedOAuthScopes"],
    AllowedOAuthFlowsUserPoolClient=user_pool_client_json["UserPoolClient"]["AllowedOAuthFlowsUserPoolClient"],
)