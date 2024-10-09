import os
import json

ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR = os.environ.get(
    'ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR')
ALLOWED_SIGN_UP_EMAIL_DOMAINS = json.loads(
    ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR) if ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR else []

# Check if the email domain is allowed


def check_email_domain(email: str) -> bool:
    # If the email doesn't contain exactly one '@', it's not allowed
    if email.count('@') != 1:
        return False

    # If the email domain is in the allowed list (or the list is empty), it's allowed
    domain = email.split('@')[1]
    return domain in ALLOWED_SIGN_UP_EMAIL_DOMAINS


def handler(event, context):
    try:
        print('Received event:', json.dumps(event, indent=2))

        email = event['request']['userAttributes']['email']
        is_allowed = check_email_domain(email)
        if is_allowed:
            # If allowed, return the event object
            return event
        else:
            # If not allowed, raise an error
            raise ValueError('Invalid email domain')
    except Exception as e:
        print('Error occurred:', e)
        # If the error is a known exception, raise it
        if isinstance(e, Exception):
            raise e
        else:
            # If the error is unknown, raise a generic error
            raise Exception('An unknown error occurred.')
