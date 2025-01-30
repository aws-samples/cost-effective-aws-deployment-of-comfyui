import os


def handler(event, context):
    redirect_url = os.environ['REDIRECT_URL']

    return {
        'statusCode': 302,
        'headers': {
            'Set-Cookie': 'AWSELBAuthSessionCookie-0=; max-age=0',
            'Set-CookiE': 'AWSELBAuthSessionCookie-1=; max-age=0',
            'Access-Control-Allow-Methods': 'GET',
            'Location': redirect_url
        }
    }
