import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as targets from "aws-cdk-lib/aws-elasticloadbalancingv2-targets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as autoscaling from "aws-cdk-lib/aws-autoscaling";
import * as events from "aws-cdk-lib/aws-events";
import * as eventTargets from "aws-cdk-lib/aws-events-targets";

import { Construct } from "constructs";
import { NagSuppressions } from "cdk-nag";

interface AdminConstructProps {
  vpc: ec2.Vpc;
  cluster: ecs.Cluster;
  service: ecs.IService;
  autoScalingGroup: autoscaling.AutoScalingGroup;
}

export class AdminConstruct extends Construct {
  public readonly restartDockerLambda: lambda.Function;
  public readonly scaleinListenerLambda: lambda.Function;
  public readonly scaleupListenerLambda: lambda.Function;
  public readonly lambdaAdminTargetGroup: elbv2.ApplicationTargetGroup;
  public readonly lambdaRestartDockerTargetGroup: elbv2.ApplicationTargetGroup;
  public readonly lambdaShutdownTargetGroup: elbv2.ApplicationTargetGroup;
  public readonly lambdaScaleupTargetGroup: elbv2.ApplicationTargetGroup;

  constructor(scope: Construct, id: string, props: AdminConstructProps) {
    super(scope, id);

    const { vpc, cluster, service, autoScalingGroup } = props;

    const lambdaRole = new iam.Role(this, "LambdaExecutionRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AutoScalingFullAccess"),
      ],
    });

    lambdaRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: [
          "ecs:DescribeServices",
          "ecs:ListTasks",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:ModifyRule",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeListeners",
          "ecs:DescribeServices",
          "ecs:UpdateService",
          "ssm:SendCommand",
        ],
        resources: ["*"],
      })
    );

    // Lambda

    const adminLambda = new lambda.Function(this, "AdminFunction", {
      handler: "admin.handler",
      code: lambda.Code.fromAsset("./lambda/admin_lambda"),
      role: lambdaRole,
      runtime: lambda.Runtime.PYTHON_3_12,
      timeout: cdk.Duration.seconds(60),
      environment: {
        ASG_NAME: autoScalingGroup.autoScalingGroupName,
        ECS_CLUSTER_NAME: cluster.clusterName,
        ECS_SERVICE_NAME: service.serviceName,
      },
    });

    const restartDockerLambda = new lambda.Function(
      this,
      "RestartDockerFunction",
      {
        handler: "restart_docker.handler",
        code: lambda.Code.fromAsset("./lambda/admin_lambda"),
        role: lambdaRole,
        runtime: lambda.Runtime.PYTHON_3_12,
        timeout: cdk.Duration.seconds(60),
        environment: {
          ASG_NAME: autoScalingGroup.autoScalingGroupName,
          ECS_CLUSTER_NAME: cluster.clusterName,
          ECS_SERVICE_NAME: service.serviceName,
        },
      }
    );

    const shutdownLambda = new lambda.Function(this, "ShutdownFunction", {
      handler: "shutdown.handler",
      code: lambda.Code.fromAsset("./lambda/admin_lambda"),
      role: lambdaRole,
      runtime: lambda.Runtime.PYTHON_3_12,
      timeout: cdk.Duration.seconds(60),
      environment: {
        ASG_NAME: autoScalingGroup.autoScalingGroupName,
      },
    });

    const scaleupTriggerLambda = new lambda.Function(
      this,
      "ScaleUpTriggerFunction",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        role: lambdaRole,
        handler: "scaleup_trigger.handler",
        code: lambda.Code.fromAsset("./lambda/admin_lambda"),
        timeout: cdk.Duration.seconds(60),
        environment: {
          ASG_NAME: autoScalingGroup.autoScalingGroupName,
          ECS_CLUSTER_NAME: cluster.clusterName,
          ECS_SERVICE_NAME: service.serviceName,
        },
      }
    );

    const scaleinListenerLambda = new lambda.Function(
      this,
      "ScaleinListenerFunction",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        role: lambdaRole,
        handler: "scalein_listener.handler",
        code: lambda.Code.fromAsset("./lambda/admin_lambda"),
        timeout: cdk.Duration.seconds(60),
        environment: {
          ASG_NAME: autoScalingGroup.autoScalingGroupName,
        },
      }
    );

    const scaleupListenerLambda = new lambda.Function(
      this,
      "ScaleupListenerFunction",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        role: lambdaRole,
        handler: "scaleup_listener.handler",
        code: lambda.Code.fromAsset("./lambda/admin_lambda"),
        timeout: cdk.Duration.seconds(60),
        environment: {
          ASG_NAME: autoScalingGroup.autoScalingGroupName,
          ECS_CLUSTER_NAME: cluster.clusterName,
          ECS_SERVICE_NAME: service.serviceName,
        },
      }
    );

    // Target Group

    const lambdaAdminTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "LambdaAdminTargetGroup",
      {
        vpc,
        targetType: elbv2.TargetType.LAMBDA,
        targets: [new targets.LambdaTarget(adminLambda)],
      }
    );

    const lambdaRestartDockerTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "LambdaRestartDockerTargetGroup",
      {
        vpc,
        targetType: elbv2.TargetType.LAMBDA,
        targets: [new targets.LambdaTarget(restartDockerLambda)],
      }
    );

    const lambdaShutdownTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "LambdaShutdownTargetGroup",
      {
        vpc,
        targetType: elbv2.TargetType.LAMBDA,
        targets: [new targets.LambdaTarget(shutdownLambda)],
      }
    );

    const lambdaScaleupTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "LambdaScaleupTargetGroup",
      {
        vpc,
        targetType: elbv2.TargetType.LAMBDA,
        targets: [new targets.LambdaTarget(scaleupTriggerLambda)],
      }
    );

    // Event

    const scaleInEventRule = new events.Rule(this, "ScaleInEventRule", {
      eventPattern: {
        source: ["aws.autoscaling"],
        detailType: ["EC2 Instance-terminate Lifecycle Action"],
        detail: {
          AutoScalingGroupName: [autoScalingGroup.autoScalingGroupName],
        },
      },
      targets: [new eventTargets.LambdaFunction(scaleinListenerLambda)],
    });

    const ecsTaskStateChangeEventRule = new events.Rule(
      this,
      "EcsTaskStateChangeRule",
      {
        eventPattern: {
          source: ["aws.ecs"],
          detailType: ["ECS Task State Change"],
          detail: {
            clusterArn: [cluster.clusterArn],
            lastStatus: ["RUNNING"],
          },
        },
        targets: [new eventTargets.LambdaFunction(scaleupListenerLambda)],
      }
    );

    // Nag

    NagSuppressions.addResourceSuppressions(
      [autoScalingGroup],
      [
        {
          id: "AwsSolutions-SNS2",
          reason:
            "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes.",
        },
        {
          id: "AwsSolutions-SNS3",
          reason:
            "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes.",
        },
      ],
      true
    );

    // Output

    this.restartDockerLambda = restartDockerLambda;
    this.scaleinListenerLambda = scaleinListenerLambda;
    this.scaleupListenerLambda = scaleupListenerLambda;

    this.lambdaAdminTargetGroup = lambdaAdminTargetGroup;
    this.lambdaRestartDockerTargetGroup = lambdaRestartDockerTargetGroup;
    this.lambdaShutdownTargetGroup = lambdaShutdownTargetGroup;
    this.lambdaScaleupTargetGroup = lambdaScaleupTargetGroup;
  }

  public addEnvironment(props: {
    lambdaAdminRule: elbv2.ApplicationListenerRule;
  }) {
    const { lambdaAdminRule } = props;

    this.restartDockerLambda.addEnvironment(
      "LISTENER_RULE_ARN",
      lambdaAdminRule.listenerRuleArn
    );

    this.scaleinListenerLambda.addEnvironment(
      "LISTENER_RULE_ARN",
      lambdaAdminRule.listenerRuleArn
    );

    this.scaleupListenerLambda.addEnvironment(
      "LISTENER_RULE_ARN",
      lambdaAdminRule.listenerRuleArn
    );
  }
}
