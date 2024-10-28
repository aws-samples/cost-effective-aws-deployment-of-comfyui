# Deployment Options

## Configuration Method

This solution is configured by changing the context in AWS CDK.

**While the CDK context can also be specified with '-c', we recommend to change the settings in the cdk.json file.**

### How to Change Values in cdk.json

Change the values under the context section in [cdk.json](/cdk.json). For example, setting `"useSpot": true` will enable the Spot Instance. After setting the context values, run the following command to re-deploy with the new settings.

```bash
cdk deploy
```

## Security Related Settings

### Enable Self Sign-Up

You may enable user self-signup so user can easily onboard to the application. You may combine it with email domain restriction described below to restrict user. Alternatively, you can also integrate application to your company SSO by following [SAML Authentication](#saml-authentication).

Set `selfSignUpEnabled` to `true` in the context. (The default is `false`)

**Edit [cdk.json](/cdk.json)**
```
{
  "context": {
    "selfSignUpEnabled": true,
  }
}
```

### Enable MFA

You may force user to use MFA.

Set `mfaRequired` to `true` in the context. (The default is `false`)

**Edit [cdk.json](/cdk.json)**
```
{
  "context": {
    "mfaRequired": true,
  }
}
```

### Restrict the email address domains that can sign up

You can specify a list of allowed domains in the allowedSignUpEmailDomains context (default is `null`).

Specify the values as a list of strings, without including the "@" symbol. A user can sign up if their email address domain matches any of the allowed domains. If `null` is specified, there is no restriction and all domains are allowed. If `[]` is specified, all domains are prohibited and no email addresses can be used to sign up.

If set, users with email addresses from non-allowed domains will get an error when trying to "Create Account" on the Web sign-up page, preventing them from signing up to application. They will also get an error when trying to "Create User" from the Cognito service page in the AWS Management Console.

This setting does not affect existing users in Cognito. It only applies to new sign-ups or user creations.

**Edit [cdk.json](/cdk.json)**

Configuration examples:

- To allow sign-ups with email addresses from the `amazon.com` domain:

```json
{
  "context": {
    "allowedSignUpEmailDomains": ["amazon.com"] // Change from null to specify allowed domains
  }
}
```

- To allow sign-ups with email addresses from either `amazon.com` or `amazon.jp` domains:

```json
{
  "context": {
    "allowedSignUpEmailDomains": ["amazon.com", "amazon.jp"] // Change from null to specify allowed domains
  }
}
```

### Enable AWS WAF restrictions

#### IP address restrictions

To restrict access to the web application by IP address, you can enable IP restrictions using AWS WAF. In [cdk.json](/cdk.json), `allowedIpV4AddressRanges` allows you to specify an array of allowed IPv4 CIDR ranges, and `allowedIpV6AddressRanges` allows you to specify an array of allowed IPv6 CIDR ranges.

```json
  "context": {
    "allowedIpV4AddressRanges": ["192.168.0.0/24"], // Change from null to specify allowed CIDR list
    "allowedIpV6AddressRanges": ["2001:0db8::/32"], // Change from null to specify allowed CIDR list
  }
```

### SAML Authentication

You can integrate with the SAML authentication functionality provided by IdPs such as Google Workspace or Microsoft Entra ID (formerly Azure Active Directory). The following are detailed integration procedures. Please make use of them.

- SAML Integration with Google Workspace
- [SAML Integration with Microsoft Entra ID](SAML_WITH_ENTRA_ID.md)

**Edit [cdk.json](/cdk.json)**

```json
  "samlAuthEnabled": true,
```
- samlAuthEnabled: Setting this to `true` will switch to the SAML-only authentication screen. The conventional authentication functionality using Cognito user pools will no longer be available.

## Cost-related Settings

### Spot Instance

You can use spot instance to reduce cost for non-critical workload. (The default is `true`) You can Set `useSpot` to `false` in the context to disable it. You may also modify `spotPrice`. Instance will be available only when spot price is below `spotPrice`.

```json
    "useSpot": true,
    "spotPrice": "0.752",
```

### Scale Down automatically / on schedule

You can scale down instances to zero to further reduce cost.

- To automatically scale down when there is no activity for an hour, set `autoScaleDown` to `true`.

```json
    "autoScaleDown": true,
```

- To scale down and scale up instance on schedule (i.e. work hour), set `scheduleAutoScaling` to `true`. You can specify scale up/down schedule by cron with `timezone`, `scheduleScaleUp`, and `scheduleScaleDown`.


```json
    "scheduleAutoScaling": true,
    "timezone": "Asia/Tokyo",
    "scheduleScaleUp": "0 9 * * 1-5",
    "scheduleScaleDown": "0 18 * * *",
```

### Use NAT Instance instead of NAT Gateway

NAT Instance is cheaper, but have limited availability and network throughput compared to NAT Gateway. For more detail, check [NAT Gateway and NAT instance comparison](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-comparison.html).

NAT Instance is used by default. You can change it to NAT Gateway by setting `cheapVpc` to `false`.

```json
    "cheapVpc": false,
```

## Using a Custom Domain

You can use a custom domain as the URL for your website. You must have a public hosted zone already created in Route53 under the same AWS account. For information on public hosted zones, please refer to this: [Working with Public Hosted Zones - Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/AboutHZWorkingWith.html)

If you don't have a public hosted zone under the same AWS account, you can also use manual DNS record addition or email validation during SSL certificate validation with AWS ACM. If you use these methods, please refer to the CDK documentation and customize accordingly: [aws-cdk-lib.aws_certificatemanager module · AWS CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_certificatemanager-readme.html)

Set the following values in cdk.json:

- `hostName` ... The hostname for your website. The A record will be created by CDK, no need to create it beforehand
- `domainName` ... The domain name of the pre-created public hosted zone
- `hostedZoneId` ... The ID of the pre-created public hosted zone

**Edit [cdk.json](/cdk.json)**

```json
{
  "context": {
    "hostName": "comfyui",
    "domainName": "example.com",
    "hostedZoneId": "XXXXXXXXXXXXXXXXXXXX"
  }
}
```