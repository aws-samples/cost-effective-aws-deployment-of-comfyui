import * as cdk from "aws-cdk-lib";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cr from "aws-cdk-lib/custom-resources";
import { Construct } from "constructs";

interface AuthConstructProps extends cdk.StackProps {
  suffix: string;
  hostName?: string;
  domainName?: string;
  alb: elbv2.ApplicationLoadBalancer;
  samlAuthEnabled: boolean;
  selfSignUpEnabled: boolean;
  mfaRequired: boolean;
  allowedSignUpEmailDomains?: string[];
}

export class AuthConstruct extends Construct {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly userPoolCustomDomain: cognito.UserPoolDomain;
  public readonly applicationDnsName: string;

  constructor(scope: Construct, id: string, props: AuthConstructProps) {
    super(scope, id);

    const {
      suffix,
      hostName,
      domainName,
      alb,
      samlAuthEnabled,
      selfSignUpEnabled,
      mfaRequired,
      allowedSignUpEmailDomains,
    } = props;

    const cognitoCustomDomain = `comfyui-alb-auth-${suffix}`;
    const applicationDnsName =
      hostName && domainName
        ? `${hostName}.${domainName}`
        : alb.loadBalancerDnsName;

    const userPool = new cognito.UserPool(this, "ComfyUIuserPool", {
      accountRecovery: cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
      autoVerify: { email: true, phone: true },
      selfSignUpEnabled: !samlAuthEnabled && selfSignUpEnabled,
      standardAttributes: {
        email: { mutable: true, required: true },
        givenName: { mutable: true, required: true },
        familyName: { mutable: true, required: true },
      },
      passwordPolicy: {
        minLength: 12,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      advancedSecurityMode: cognito.AdvancedSecurityMode.ENFORCED,
      mfaSecondFactor: { otp: true, sms: true },
      mfa:
        !samlAuthEnabled && mfaRequired
          ? cognito.Mfa.REQUIRED
          : cognito.Mfa.OPTIONAL,
    });

    const userPoolCustomDomain = userPool.addDomain("user-pool-domain", {
      cognitoDomain: {
        domainPrefix: cognitoCustomDomain,
      },
    });

    const userPoolClient = userPool.addClient("alb-app-client", {
      generateSecret: true,
      oAuth: {
        callbackUrls: [
          `https://${applicationDnsName}/oauth2/idpresponse`,
          `https://${applicationDnsName}`,
        ],
        flows: {
          authorizationCodeGrant: true,
        },
        scopes: [cognito.OAuthScope.OPENID],
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
    });

    const userPoolClientCf = userPoolClient.node
      .defaultChild as cognito.CfnUserPoolClient;
    userPoolClientCf.logoutUrLs = [`https://${applicationDnsName}`];

    const userPoolFullDomain = userPoolCustomDomain.baseUrl();
    const redirectUri = encodeURIComponent(`https://${applicationDnsName}`);
    const userPoolLogoutUrl = `${userPoolFullDomain}/logout?client_id=${userPoolClient.userPoolClientId}&logout_uri=${redirectUri}`;
    const userPoolUserInfoUrl = `${userPoolFullDomain}/oauth2/userInfo`;

    // Limit sign up domains

    if (allowedSignUpEmailDomains) {
      const checkEmailDomainFunction = new lambda.Function(
        this,
        "checkEmailDomainFunction",
        {
          runtime: lambda.Runtime.PYTHON_3_12,
          handler: "check_email_domain.handler",
          code: lambda.Code.fromAsset("./lambda/auth_lambda"),
          timeout: cdk.Duration.seconds(60),
          environment: {
            ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR: JSON.stringify(
              allowedSignUpEmailDomains
            ),
          },
        }
      );

      userPool.addTrigger(
        cognito.UserPoolOperation.PRE_SIGN_UP,
        checkEmailDomainFunction
      );
    }

    // Post Deploy Fix

    const postProcessFunction = new lambda.Function(
      this,
      "UpdateCognitoCallbackUrlFunction",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        code: lambda.Code.fromAsset("./lambda/post_process_lambda"),
        handler: "function.lambda_handler",
        environment: {
          COGNITO_USER_POOL_ID: userPool.userPoolId,
          COGNITO_CLIENT_ID: userPoolClient.userPoolClientId,
        },
      }
    );

    postProcessFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "cognito-idp:DescribeUserPoolClient",
          "cognito-idp:UpdateUserPoolClient",
        ],
        resources: ["*"],
      })
    );

    const postProcessProvider = new cr.Provider(
      this,
      "UpdateCognitoCallbackUrlProvider",
      {
        onEventHandler: postProcessFunction,
      }
    );

    new cdk.CustomResource(this, "UpdateCognitoCallbackUrl", {
      serviceToken: postProcessProvider.serviceToken,
    });

    // Output

    this.userPool = userPool;
    this.userPoolClient = userPoolClient;
    this.userPoolCustomDomain = userPoolCustomDomain;
    this.applicationDnsName = applicationDnsName;
  }
}
