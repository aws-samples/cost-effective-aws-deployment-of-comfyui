# Deployment Options

## Configuration Method

This solution is configured by changing the parameter in `app.py`.

### How to Change Values in app.py

Change the parameter in [app.py](/app.py). For example, setting `self_sign_up_enabled=True` will enable the Self Sign Up. After setting the context values, run the following command to re-deploy with the new settings.

```bash
npx cdk deploy
```

## Security Related Settings

### Enable Self Sign-Up

You may enable user self-signup so user can easily onboard to the application. You may combine it with email domain restriction described below to restrict user. Alternatively, you can also integrate application to your company SSO by following [SAML Authentication](#saml-authentication).

Set `self_sign_up_enabled` to `True` in the parameter. (The default is `False`)

**Edit [app.py](/app.py)**
```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    self_sign_up_enabled=True,
    ...
)
```

### Enable MFA

You may force user to use MFA.

Set `mfa_required` to `True` in the context. (The default is `False`)

**Edit [app.py](/app.py)**
```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    mfa_required=True,
    ...
)
```

### Restrict the email address domains that can sign up

You can specify a list of allowed domains in the allowed_sign_up_email_domains context (default is `None`).

Specify the values as a list of strings, without including the "@" symbol. A user can sign up if their email address domain matches any of the allowed domains. If `None` is specified, there is no restriction and all domains are allowed. If `[]` is specified, all domains are prohibited and no email addresses can be used to sign up.

If set, users with email addresses from non-allowed domains will get an error when trying to "Create Account" on the Web sign-up page, preventing them from signing up to application. They will also get an error when trying to "Create User" from the Cognito service page in the AWS Management Console.

This setting does not affect existing users in Cognito. It only applies to new sign-ups or user creations.

**Edit [app.py](/app.py)**

Configuration examples:

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    allowed_sign_up_email_domains=["amazon.com", "amazon.co.jp"],
    ...
)
```

### Enable AWS WAF restrictions

#### IP address restrictions

To restrict access to the web application by IP address, you can enable IP restrictions using AWS WAF. In [app.py](/app.py), `allowed_ip_v4_address_ranges` allows you to specify an array of allowed IPv4 CIDR ranges, and `allowed_ip_v6_address_ranges` allows you to specify an array of allowed IPv6 CIDR ranges.

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    allowed_ip_v4_address_ranges=["192.168.0.0/24"],
    allowed_ip_v6_address_ranges=["2001:0db8::/32"],
    ...
)
```

### SAML Authentication

You can integrate with the SAML authentication functionality provided by IdPs such as Google Workspace or Microsoft Entra ID (formerly Azure Active Directory). The following are detailed integration procedures. Please make use of them.

- SAML Integration with Google Workspace
- [SAML Integration with Microsoft Entra ID](SAML_WITH_ENTRA_ID.md)

**Edit [app.py](/app.py)**

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    saml_auth_enabled=True,
    ...
)
```

- saml_auth_enabled: Setting this to `True` will switch to the SAML-only authentication screen. The conventional authentication functionality using Cognito user pools will no longer be available.

## Cost-related Settings

### Spot Instance

You can use spot instance to reduce cost for non-critical workload. (The default is `True`) You can Set `use_spot` to `False` in the context to disable it. You may also modify `spot_price`. Instance will be available only when spot price is below `spot_price`.

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    use_spot=True,
    spot_price="0.752"
    ...
)
```

### Scale Down automatically / on schedule

You can scale down instances to zero to further reduce cost.

- To automatically scale down when there is no activity for an hour, set `auto_scale_down` to `True`.

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    auto_scale_down=True,
    ...
)
```

- To scale down and scale up instance on schedule (i.e. work hour), set `schedule_auto_scaling` to `True`. You can specify scale up/down schedule by cron with `timezone`, `schedule_scale_up`, and `schedule_scale_down`.

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    schedule_auto_scaling=True,
    timezone="Asia/Tokyo",
    schedule_scale_up="0 8 * * 1-5",
    schedule_scale_down="0 19 * * *",
    ...
)
```

### Use NAT Instance instead of NAT Gateway

NAT Instance is cheaper, but have limited availability and network throughput compared to NAT Gateway. For more detail, check [NAT Gateway and NAT instance comparison](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-comparison.html).

NAT Instance is used by default. You can change it to NAT Gateway by setting `cheap_vpc` to `false`.

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    cheap_vpc=True,
    ...
)
```

## Using a Custom Domain

You can use a custom domain as the URL for your website. You must have a public hosted zone already created in Route53 under the same AWS account. For information on public hosted zones, please refer to this: [Working with Public Hosted Zones - Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/AboutHZWorkingWith.html)

If you don't have a public hosted zone under the same AWS account, you can also use manual DNS record addition or email validation during SSL certificate validation with AWS ACM. If you use these methods, please refer to the CDK documentation and customize accordingly: [aws-cdk-lib.aws_certificatemanager module · AWS CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_certificatemanager-readme.html)

Set the following values in app.py:

- `host_name` ... The hostname for your website. The A record will be created by CDK, no need to create it beforehand
- `domain_name` ... The domain name of the pre-created public hosted zone
- `hosted_zone_id` ... The ID of the pre-created public hosted zone

**Edit [app.py](/app.py)**

```python
comfy_ui_stack = ComfyUIStack(
    ...
    # Override Parameters
    host_name="comfyui",
    domain_name="example.com",
    hosted_zone_id="XXXXXXXXXXXXXXXXXXXX",
    ...
)
```
