import * as cdk from "aws-cdk-lib";
import {
  AdminConstruct,
  AlbConstruct,
  AsgConstruct,
  AuthConstruct,
  EcsConstruct,
  VpcConstruct,
} from "./construct";
import { Construct } from "constructs";
import * as crypto from "crypto";
import { NagSuppressions } from "cdk-nag";

export interface ComfyUIStackProps extends cdk.StackProps {
  /**
   * VPC
   */
  cheapVpc: boolean;

  /**
   * Spot
   */
  useSpot: boolean;
  spotPrice?: string;

  /**
   * Auto Scale
   */
  autoScaleDown: boolean;
  scheduleAutoScaling: boolean;
  timezone: string;
  scheduleScaleDown: string;
  scheduleScaleUp: string;

  /**
   * Sign up
   */
  selfSignUpEnabled: boolean;
  allowedSignUpEmailDomains?: string[];
  mfaRequired: boolean;
  samlAuthEnabled: boolean;

  /**
   * Network restriction
   */
  allowedIpV4AddressRanges?: string[];
  allowedIpV6AddressRanges?: string[];

  /**
   * Custom Domain
   */
  hostName?: string;
  domainName?: string;
  hostedZoneId?: string;
}

export class ComfyUIStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ComfyUIStackProps) {
    super(scope, id, props);

    // Environment
    const uniqueInput = `${this.account}-${this.region}-${this.stackName}`;
    const uniqueHash = crypto
      .createHash("sha256")
      .update(uniqueInput)
      .digest("hex")
      .slice(0, 10);
    const suffix = uniqueHash.toLowerCase();
    const isSagemakerStudio: boolean =
      process.env["SAGEMAKER_APP_TYPE_LOWERCASE"] !== undefined;

    // VPC
    const vpc = new VpcConstruct(this, "VPC", {
      cheapVpc: props.cheapVpc,
    });

    // ALB
    const alb = new AlbConstruct(this, "ALB", {
      vpc: vpc.vpc,
      hostName: props.hostName,
      domainName: props.domainName,
      hostedZoneId: props.hostedZoneId,
      isSagemakerStudio: isSagemakerStudio,
      allowedIpV4AddressRanges: props.allowedIpV4AddressRanges,
      allowedIpV6AddressRanges: props.allowedIpV6AddressRanges,
    });

    // ASG
    const asg = new AsgConstruct(this, "ASG", {
      vpc: vpc.vpc,
      useSpot: props.useSpot,
      spotPrice: props.spotPrice,
      autoScaleDown: props.autoScaleDown,
      scheduleAutoScaling: props.scheduleAutoScaling,
      timezone: props.timezone,
      scheduleScaleDown: props.scheduleScaleDown,
      scheduleScaleUp: props.scheduleScaleUp,
    });

    // ECS
    const ecs = new EcsConstruct(this, "ECS", {
      vpc: vpc.vpc,
      autoScalingGroup: asg.autoScalingGroup,
      albSecurityGroup: alb.albSecurityGroup,
      isSagemakerStudio: isSagemakerStudio,
      suffix: suffix,
    });

    // Admin Control Plane
    const admin = new AdminConstruct(this, "Admin", {
      vpc: vpc.vpc,
      cluster: ecs.cluster,
      service: ecs.service,
      autoScalingGroup: asg.autoScalingGroup,
    });

    // Auth
    const auth = new AuthConstruct(this, "Auth", {
      suffix: suffix,
      hostName: props.hostName,
      domainName: props.domainName,
      alb: alb.alb,
      samlAuthEnabled: props.samlAuthEnabled,
      selfSignUpEnabled: props.selfSignUpEnabled,
      mfaRequired: props.mfaRequired,
      allowedSignUpEmailDomains: props.allowedSignUpEmailDomains,
    });

    // Associate resources to ALB
    alb.associateResources({
      ecsTargetGroup: ecs.ecsTargetGroup,
      lambdaAdminTargetGroup: admin.lambdaAdminTargetGroup,
      lambdaRestartDockerTargetGroup: admin.lambdaRestartDockerTargetGroup,
      lambdaShutdownTargetGroup: admin.lambdaShutdownTargetGroup,
      lambdaScaleupTargetGroup: admin.lambdaScaleupTargetGroup,
      userPool: auth.userPool,
      userPoolClient: auth.userPoolClient,
      userPoolCustomDomain: auth.userPoolCustomDomain,
    });

    // Add env variables to lambda
    admin.addEnvironment({
      lambdaAdminRule: alb.lambdaAdminRule,
    });

    // Cfn Output
    new cdk.CfnOutput(this, "Endpoint", { value: auth.applicationDnsName });
    new cdk.CfnOutput(this, "UserPoolId", { value: auth.userPool.userPoolId });
    new cdk.CfnOutput(this, "CognitoDomainName", {
      value: auth.userPoolCustomDomain.domainName,
    });
  }
}
