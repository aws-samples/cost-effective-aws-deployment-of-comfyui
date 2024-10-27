#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { Aspects, Tags } from 'aws-cdk-lib';
import { ComfyUIStack } from '../lib/comfyui-stack';
import { AwsSolutionsChecks, NagSuppressions } from 'cdk-nag';
import { defaultParameter, overrideParameter } from '../parameter';

const app = new cdk.App();
const comfyUiStack = new ComfyUIStack(app, 'ComfyUIStack', {
  description: 'ComfyUI on AWS (uksb-ggn3251wsp)',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  tags: {
    'Repository': 'aws-samples/cost-effective-aws-deployment-of-comfyui',
  },
  ...defaultParameter,
  ...overrideParameter,
});

Aspects.of(app).add(new AwsSolutionsChecks({ verbose: false }));
NagSuppressions.addStackSuppressions(comfyUiStack, [
  {
    id: 'AwsSolutions-L1',
    reason: 'Lambda Runtime is provided by custom resource provider and drain ecs hook implicitely and not critical for sample',
  },
  {
    id: 'AwsSolutions-IAM4',
    reason: 'For sample purposes the managed policy is sufficient',
  },
  {
    id: 'AwsSolutions-IAM5',
    reason: 'Some rules require \'*\' wildcard as an example ACM operations, and other are sufficient for Sample',
  },
  {
    id: 'CdkNagValidationFailure',
    reason: 'Suppression for cdk-nag validation failure',
  }
]);

app.synth();