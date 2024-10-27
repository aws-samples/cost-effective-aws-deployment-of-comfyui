import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as elbv2Actions from "aws-cdk-lib/aws-elasticloadbalancingv2-actions";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53Targets from "aws-cdk-lib/aws-route53-targets";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cr from "aws-cdk-lib/custom-resources";
import * as events from "aws-cdk-lib/aws-events";
import * as eventTargets from "aws-cdk-lib/aws-events-targets";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as wafv2 from "aws-cdk-lib/aws-wafv2";
import { Construct } from "constructs";
import { NagSuppressions } from "cdk-nag";

interface AlbConstructProps {
  vpc: ec2.Vpc;
  hostName?: string;
  domainName?: string;
  hostedZoneId?: string;
  isSagemakerStudio: boolean;
  allowedIpV4AddressRanges?: string[];
  allowedIpV6AddressRanges?: string[];
}

export class AlbConstruct extends Construct {
  public readonly alb: elbv2.ApplicationLoadBalancer;
  public readonly albSecurityGroup: ec2.SecurityGroup;
  public readonly certificate: acm.ICertificate;
  public listener: elbv2.ApplicationListener;
  public lambdaAdminRule: elbv2.ApplicationListenerRule;

  constructor(scope: Construct, id: string, props: AlbConstructProps) {
    super(scope, id);

    const {
      vpc,
      hostName,
      domainName,
      hostedZoneId,
      isSagemakerStudio,
      allowedIpV4AddressRanges,
      allowedIpV6AddressRanges,
    } = props;

    const albSecurityGroup = new ec2.SecurityGroup(this, "ALBSecurityGroup", {
      vpc,
      description: "Security Group for ALB",
    });

    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      "Allow inbound traffic on port 443"
    );

    const alb = new elbv2.ApplicationLoadBalancer(this, "ComfyUIALB", {
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
    });

    // Redirect Load Balancer traffic on port 80 to port 443
    alb.addRedirect({
      sourceProtocol: elbv2.ApplicationProtocol.HTTP,
      sourcePort: 80,
      targetProtocol: elbv2.ApplicationProtocol.HTTPS,
      targetPort: 443,
    });

    let certificate: acm.ICertificate;

    if (hostName && domainName && hostedZoneId) {
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        {
          hostedZoneId,
          zoneName: domainName,
        }
      );

      new route53.ARecord(this, "AliasRecord", {
        zone: hostedZone,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.LoadBalancerTarget(alb)
        ),
        recordName: `${hostName}.${domainName}`,
      });

      certificate = new acm.Certificate(this, "Certificate", {
        domainName: `${hostName}.${domainName}`,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });
    } else {
      const certificate_config = {
        self_signed_certificate: {
          email_address: "customer@example.com",
          common_name: "*.elb.amazonaws.com",
          city: ".",
          state: ".",
          country_code: "AT",
          organization: ".",
          organizational_unit: ".",
          validity_seconds: 157680000,
        },
      };

      const certFunction = new lambda.Function(this, "RegisterSelfSignedCert", {
        handler: "function.lambda_handler",
        code: lambda.Code.fromAsset("./lambda/cert_lambda", {
          bundling: {
            image: lambda.Runtime.PYTHON_3_10.bundlingImage,
            command: [
              "bash",
              "-c",
              "pip install -r requirements.txt -t /asset-output --platform manylinux_2_12_x86_64 --only-binary=:all: && cp -au . /asset-output",
            ],
            platform: "linux/amd64",
            network: isSagemakerStudio ? "sagemaker" : undefined,
          },
        }),
        runtime: lambda.Runtime.PYTHON_3_10,
        timeout: cdk.Duration.seconds(120),
      });

      certFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ["acm:ImportCertificate"],
          resources: ["*"],
        })
      );

      certFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ["acm:AddTagsToCertificate"],
          resources: ["*"],
        })
      );

      const provider = new cr.Provider(
        this,
        "SelfSignedCertCustomResourceProvider",
        {
          onEventHandler: certFunction,
        }
      );

      const customResource = new cdk.CustomResource(
        this,
        "SelfSignedCertCustomResource",
        {
          serviceToken: provider.serviceToken,
          properties: {
            email_address:
              certificate_config.self_signed_certificate.email_address,
            common_name: certificate_config.self_signed_certificate.common_name,
            city: certificate_config.self_signed_certificate.city,
            state: certificate_config.self_signed_certificate.state,
            country_code:
              certificate_config.self_signed_certificate.country_code,
            organization:
              certificate_config.self_signed_certificate.organization,
            organizational_unit:
              certificate_config.self_signed_certificate.organizational_unit,
            validity_seconds:
              certificate_config.self_signed_certificate.validity_seconds,
          },
        }
      );

      certFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ["acm:DeleteCertificate"],
          resources: ["*"],
        })
      );

      certificate = acm.Certificate.fromCertificateArn(
        this,
        "SelfSignedCert",
        customResource.ref
      );
    }

    if (allowedIpV4AddressRanges || allowedIpV6AddressRanges) {
      const wafRules: wafv2.CfnWebACL.RuleProperty[] = [];

      if (allowedIpV4AddressRanges) {
        const ipv4 = new wafv2.CfnIPSet(this, "IpV4Set", {
          addresses: allowedIpV4AddressRanges,
          ipAddressVersion: "IPV4",
          scope: "REGIONAL",
        });

        wafRules.push({
          name: "IpV4SetRule",
          priority: 1,
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: "IpV4SetRule",
            sampledRequestsEnabled: true,
          },
          statement: {
            ipSetReferenceStatement: { arn: ipv4.attrArn },
          },
          action: {
            allow: {},
          },
        });
      }

      if (allowedIpV6AddressRanges) {
        const ipv6 = new wafv2.CfnIPSet(this, "IpV6Set", {
          addresses: allowedIpV6AddressRanges,
          ipAddressVersion: "IPV6",
          scope: "REGIONAL",
        });

        wafRules.push({
          name: "IpV6SetRule",
          priority: 2,
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: "IpV6SetRule",
            sampledRequestsEnabled: true,
          },
          statement: {
            ipSetReferenceStatement: { arn: ipv6.attrArn },
          },
          action: {
            allow: {},
          },
        });
      }

      const waf = new wafv2.CfnWebACL(this, "WebACL", {
        defaultAction: { block: {} },
        scope: "REGIONAL",
        visibilityConfig: {
          cloudWatchMetricsEnabled: true,
          metricName: "WebACL",
          sampledRequestsEnabled: true,
        },
        rules: wafRules,
      });

      new wafv2.CfnWebACLAssociation(this, "WebACLAssociation", {
        resourceArn: alb.loadBalancerArn,
        webAclArn: waf.attrArn,
      });
    }

    // Nag

    NagSuppressions.addResourceSuppressions(
      [albSecurityGroup],
      [
        {
          id: "AwsSolutions-EC23",
          reason:
            "The Security Group and ALB needs to allow 0.0.0.0/0 inbound access for the ALB to be publicly accessible. Additional security is provided via Cognito authentication.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      [alb],
      [
        {
          id: "AwsSolutions-ELB2",
          reason:
            "Adding access logs requires extra S3 bucket so removing it for sample purposes.",
        },
      ],
      true
    );

    // Output
    this.albSecurityGroup = albSecurityGroup;
    this.alb = alb;
    this.certificate = certificate;
  }

  public associateResources(props: {
    ecsTargetGroup: elbv2.ApplicationTargetGroup;
    lambdaAdminTargetGroup: elbv2.ApplicationTargetGroup;
    lambdaRestartDockerTargetGroup: elbv2.ApplicationTargetGroup;
    lambdaShutdownTargetGroup: elbv2.ApplicationTargetGroup;
    lambdaScaleupTargetGroup: elbv2.ApplicationTargetGroup;
    userPool: cognito.UserPool;
    userPoolClient: cognito.UserPoolClient;
    userPoolCustomDomain: cognito.UserPoolDomain;
  }) {
    const {
      ecsTargetGroup,
      lambdaAdminTargetGroup,
      lambdaRestartDockerTargetGroup,
      lambdaShutdownTargetGroup,
      lambdaScaleupTargetGroup,
      userPool,
      userPoolClient,
      userPoolCustomDomain,
    } = props;

    const listener = this.alb.addListener("Listener", {
      certificates: [this.certificate],
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      defaultAction: elbv2.ListenerAction.forward([ecsTargetGroup]),
    });

    const lambdaAdminRule = new elbv2.ApplicationListenerRule(
      this,
      "LambdaAdminRule",
      {
        listener: listener,
        priority: 5,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/admin"])],
        action: new elbv2Actions.AuthenticateCognitoAction({
          next: elbv2.ListenerAction.forward([lambdaAdminTargetGroup]),
          userPool,
          userPoolClient,
          userPoolDomain: userPoolCustomDomain,
        }),
      }
    );

    const lambdaRestartDockerRule = new elbv2.ApplicationListenerRule(
      this,
      "LambdaRestartDockerRule",
      {
        listener: listener,
        priority: 10,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/admin/restart"])],
        action: new elbv2Actions.AuthenticateCognitoAction({
          next: elbv2.ListenerAction.forward([lambdaRestartDockerTargetGroup]),
          userPool,
          userPoolClient,
          userPoolDomain: userPoolCustomDomain,
        }),
      }
    );

    const lambdaShutdownRule = new elbv2.ApplicationListenerRule(
      this,
      "LambdaShutdownRule",
      {
        listener: listener,
        priority: 15,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/admin/shutdown"])],
        action: new elbv2Actions.AuthenticateCognitoAction({
          next: elbv2.ListenerAction.forward([lambdaShutdownTargetGroup]),
          userPool,
          userPoolClient,
          userPoolDomain: userPoolCustomDomain,
        }),
      }
    );

    const lambdaScaleupRule = new elbv2.ApplicationListenerRule(
      this,
      "LambdaScaleupRule",
      {
        listener: listener,
        priority: 20,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/admin/scaleup"])],
        action: new elbv2Actions.AuthenticateCognitoAction({
          next: elbv2.ListenerAction.forward([lambdaScaleupTargetGroup]),
          userPool,
          userPoolClient,
          userPoolDomain: userPoolCustomDomain,
        }),
      }
    );

    const authRule = listener.addAction("AuthenticateRule", {
      priority: 25,
      action: new elbv2Actions.AuthenticateCognitoAction({
        next: elbv2.ListenerAction.forward([ecsTargetGroup]),
        userPool,
        userPoolClient,
        userPoolDomain: userPoolCustomDomain,
      }),
      conditions: [elbv2.ListenerCondition.pathPatterns(["/*"])],
    });

    this.listener = listener;
    this.lambdaAdminRule = lambdaAdminRule;
  }
}
