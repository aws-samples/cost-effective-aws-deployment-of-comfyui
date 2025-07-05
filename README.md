English | [日本語](./README_ja.md) | [中文](./README_cn.md)

# ComfyUI on AWS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This sample repository provides a seamless and cost-effective solution to deploy ComfyUI, a powerful AI-driven image generation tool, on AWS. This repository provides a comprehensive infrastructure code and configuration setup, leveraging the power of ECS, EC2, and other AWS services. Experience a hassle-free deployment process while enjoying uncompromised security and scalability.

💡 Note: this solution will incur AWS costs. You can find more information about it in the costs section.

![comfy](docs/assets/comfy.png)
![comfy gallery](docs/assets/comfy_gallery.png)

## Solution Features

1. **Effortless Deployment** 🚀: Harness the power of [Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) for a streamlined and automated deployment process.
2. **Cost Optimization** 💰: Leverage cost-saving options like Spot Instances, Automatic Shutdown, and Scheduled Scaling to maximize your budget efficiency.
3. **Robust Security** 🔒: Enjoy peace of mind with robust security measures, including Authentication (with SAML such as Microsoft Entra ID / Google Workspace), Email Domain Restriction, IP Restriction, Custom Domain SSL, Security Scans, etc.

## Architecture Overview

![AWS Architecture](docs/drawio/ComfyUI.drawio.png)

## Services

- **[Amazon VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)** - A VPC with public and private subnets is created to host the ECS cluster
- **[ECS Cluster](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/clusters.html)** - An ECS cluster is created to run the ComfyUI task
- **[Auto Scaling Group](https://docs.aws.amazon.com/autoscaling/ec2/userguide/auto-scaling-groups.html)** - An ASG is created and associated with ECS as a capacity provider. It launches GPU instances to host ECS tasks.
- **[ECS Task Definition](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)** - Defines the ComfyUI container and mounts EBS volume for persistence
- **[ECS Service](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html)** - Creates an ECS service to run the ComfyUI task definition
- **[Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html)** - An ALB is setup to route traffic to the ECS service 
- **[Amazon ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html)** - Holds the ComfyUI Docker image
- **[CloudWatch Log Group](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html)** - Stores logs from the ECS task
- **[Amazon Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html)** - User directory for having authentication in front of the ALB
- **[AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html)** - Block access by IP and rate limiting for DDoS protection
- **[AWS Lambda](https://docs.aws.amazon.com/lambda/)** - To manage ComfyUI state

## Getting Started

### Prepare the AWS environment

For the sake of reproducability and consistency, we recommend using [Amazon SageMaker Studio Code Editor](https://docs.aws.amazon.com/sagemaker/latest/dg/code-editor.html) for deploying and testing this solution.

ℹ️ You can use your local development environment, but you will need to **make sure that you have AWS CLI, AWS CDK and Docker properly setup**.

<details>
<summary>Click to see environment estup with Amazon SageMaker Studio Code Editor</summary>

1. Launch Amazon SageMaker Studio Code Editor using CloudFormation template from link in [sagemaker-studio-code-editor-template](https://github.com/aws-samples/sagemaker-studio-code-editor-template/). (This template launches Code Editor with some necessary capabilities including Docker, auto termination)
2. Open SageMaker Studio from url in CloudFormation Output.
3. Navigate to Code Editor from Application section in top left.
</details>

<details>
<summary>Click to see environment setup with Local environment</summary>

If you do not have AWS CLI, follow [AWS CLI Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

If you do not have CDK, follow [CDK Start Guide](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)

If you do not have Docker follow [Docker Install Guide](https://docs.docker.com/engine/install/)

If you haven't setup AWS CLI after installation, execute the following commands on your local environment:

```bash
aws configure
```

When prompted, enter your AWS Access Key ID, Secret Access Key, and then the default region name (eg. us-east-1). You can leave the output format field as default or specify it as per your preference.
</details>

> [!NOTE]
> Make sure your account has quota for GPU instance. Go to [Service Quota](https://us-west-2.console.aws.amazon.com/servicequotas/home/services/ec2/quotas/L-3819A6DF) and set `All G and VT Spot Instance Requests` to at least 4.

### Deploying ComfyUI

1. (First time only) Clone this repo (`git clone https://github.com/aws-samples/cost-effective-aws-deployment-of-comfyui.git`)
2. (First time only) cd into repo directory (`cd cost-effective-aws-deployment-of-comfyui`)
3. Run `make`

Depending on your custom_nodes and extenstions in the dockerfile, the deployment will take approx. 8-10 minutes to have ComfyUI ready
 
```
 ✅  ComfyUIStack

✨  Deployment time: 579.07s

Outputs:
ComfyUIStack.CognitoDomainName = comfyui-alb-auth-XXXXXXX
ComfyUIStack.Endpoint = ComfyUiALB-XXXXX.uw-west-2.elb.amazonaws.com
ComfyUIStack.UserPoolId = us-west-2_XXXXXXX
Stack ARN:
arn:aws:cloudformation:[us-east-1]:[your-account-id]:stack/ComfyUIStack/[uuid]

✨  Total time: 582.53s
```

You can access application from output value of `ComfyUIStack.Endpoint`.

### Uploading models

1. You can install models, loras, embedding, controlnets over ComfyUI-Manager or other extension (custom node). See [User Guide](docs/USER_GUIDE.md#model-installation) for detail.
2. You can extend (optional) and execute the upload script in this repo with a preselected list of models, controlnets etc. If the SSM command is not working, make sure that the role you are using is allowed to access the EC2. You'll find some additional examples in the `/scripts/upload_models.sh` file.

```bash
# 1. SSM into EC2
aws ssm start-session --target "$(aws ec2 describe-instances --filters "Name=tag:Name,Values=ComfyUIStack/Host" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].[InstanceId]' --output text)" --region $AWS_DEFAULT_REGION

# 2. SSH into Container
container_id=$(sudo docker container ls --format '{{.ID}} {{.Image}}' | grep 'comfyui:latest$' | awk '{print $1}')
sudo docker exec -it $container_id /bin/bash

# 3. install models, loras, controlnets or whatever you need (you can also include all in a script and execute it to install)

# FACE SWAP EXAMPLE Upscaler - https://huggingface.co/ai-forever/Real-ESRGAN
wget -c https://huggingface.co/ai-forever/Real-ESRGAN/blob/main/RealESRGAN_x2.pth -P ./models/upscale_models/
```

### Access ComfyUI

The deployed solution provides an EC2 accessible through an Application Load Balancer. The Load Balancer requires authentication through Amazon Cognito User Pool. 

You may [enable self-signup](docs/DEPLOY_OPTION.md#enable-self-sign-up), enable [SAML authentication](docs/DEPLOY_OPTION.md#saml-authentication), or manually create user in Cognito console.

### User Guide

To unlock the full potential of ComfyUI and ensure a seamless experience, explore our detailed [User Guide](docs/USER_GUIDE.md). This comprehensive resource will guide you through every step, from installation to advanced configurations, empowering you to harness the power of AI-driven image generation with ease.

- [Installing Extensions (Custom Nodes)](docs/USER_GUIDE.md#installing-extensions-custom-nodes)
    - [Recommended Extensions](docs/USER_GUIDE.md#recommended-extensions)
        - [ComfyUI Workspace Manager](docs/USER_GUIDE.md#comfyui-workspace-manager)
- [Installing Models](docs/USER_GUIDE.md#installing-models)
    - [Using ComfyUI-Manager](docs/USER_GUIDE.md#using-comfyui-manager)
    - [Using Other Extensions](docs/USER_GUIDE.md#using-other-extensions)
    - [Manual Installation](docs/USER_GUIDE.md#manual-installation)
- [Running a Workflow](docs/USER_GUIDE.md#running-a-workflow)

### Deploy Option

With our comprehensive Deploy Options, you have the power to craft a tailored solution that aligns perfectly with your security requirements, and budget constraints. Unlock the full potential of ComfyUI on AWS with unparalleled flexibility and control.You can enable following features with just few steps.

- [Configuration Method](docs/DEPLOY_OPTION.md#configuration-method)
    - [How to Change Values in cdk.json](docs/DEPLOY_OPTION.md#how-to-change-values-in-cdkjson)
- [Security Related Settings](docs/DEPLOY_OPTION.md#security-related-settings)
    - [Enable Self Sign-Up](docs/DEPLOY_OPTION.md#enable-self-sign-up)
    - [Enable MFA](docs/DEPLOY_OPTION.md#enable-mfa)
    - [Restrict the email address domains that can sign up](docs/DEPLOY_OPTION.md#restrict-the-email-address-domains-that-can-sign-up)
    - [Enable AWS WAF restrictions](docs/DEPLOY_OPTION.md#enable-aws-waf-restrictions)
        - [IP address restrictions](docs/DEPLOY_OPTION.md#ip-address-restrictions)
        - [Rate limiting](docs/DEPLOY_OPTION.md#rate-limiting)
    - [SAML Authentication](docs/DEPLOY_OPTION.md#saml-authentication)
- [Cost-related Settings](docs/DEPLOY_OPTION.md#cost-related-settings)
    - [Spot Instance](docs/DEPLOY_OPTION.md#spot-instance)
    - [Scale Down automatically / on schedule](docs/DEPLOY_OPTION.md#scale-down-automatically--on-schedule)
    - [Use NAT Insatnce instead of NAT Gateway](docs/DEPLOY_OPTION.md#use-nat-insatnce-instead-of-nat-gateway)
- [Monitoring and Notifications](docs/DEPLOY_OPTION.md#monitoring-and-notifications)
    - [Slack Integration](docs/DEPLOY_OPTION.md#slack-integration)
- [Using a Custom Domain](docs/DEPLOY_OPTION.md#using-a-custom-domain)



### Delete deployments and cleanup resources

For the sake of preventing data loss from accidental deletions and keeping the example as straightforward as possible, the deletion of the complete deployment and resources is semi-automated. To cleanup and remove everything you've deployed you need to do following:

1. Delete the Auto Scaling Group manually:
- Login to your AWS console
- Search for Auto Scaling Groups (EC2 featuer) in the search bar
- Select ComfyASG
- Press Actions and then delete
- Confirm deletion

2. After ASG deletion you just can run following command in your terminal. This command will delete all remaining resources, but EBS and the Cognito User pool.
```bash
npx cdk destroy
```

3. Delete EBS Volume
- Login to your AWS console
- Search Volumes (EC2 featuer) in the search bar
- Select ComfyUIVolume
- Press Actions and then delete
- Confirm deletion

4. Delete Cognito User Pool
- Login to your AWS console
- Search for Cognito in the serach bar
- Select ComfyUIuserPool..
- Press delete
- Confirm deletion

5. Delete ECR Repository
- Login to your AWS console
- Search for ECR (Elastic Container Regsitry) in the search bar
- Select comfyui
- Press delete
- Type delete to confirm deletion

## Notes and Additional Information

### Cost Estimation

This section provides cost estimations for running the application on AWS. Please note that these are rough estimations, and you should refine them based on your project's specific requirements and usage patterns.

#### Flexible Workload (Default)

For non-critical business workloads, which should apply to the majority of applications of this type, you can use Spot Instances to benefit from cost savings. Spot Instances offer an average historical discount of 71% (us-east-1, October 2024) for the `g4dn.xlarge` instance type. Additionally, you can replace the NAT Gateway with a NAT Instance to further reduce costs.

The following assumptions are made for the cost estimation:

- No services from the AWS Free Tier are included.
- Instance Type: `g4dn.xlarge` with 4 vCPU, 16 GiB memory, and 1 Nvidia T4 Tensor Core GPU (Spot Instance with 71% discount).
- 250 GB SSD storage.
- 1 Application Load Balancer.
- VPC with NAT Instance.
- Elastic Container Registry (ECR) with 10 GB of data stored per month.
- 5 GB of logging data per month.

| Service \ Runtime  | 2h/day Mon-Fri | 8h/day Mon-Fri | 12h/day Mon-Fri | 24/7          |
|--------------------|----------------|----------------|-----------------|---------------|
| Compute            | $7             | $26            | $40             | $111          |
| Storage            | -              | -              | -               | $20           |
| ALB                | -              | -              | -               | $20           |
| Networking         | -              | -              | -               | $6            |
| Registry           | -              | -              | -               | $1            |
| Logging            | -              | -              | -               | $3            |
| Total Monthly Cost | $60            | $79            | $93             | $164          |

#### Business-Critical Workload

For business-critical workloads, you can use On-Demand instances and a NAT Gateway for high availability.

The following assumptions are made for the cost estimation:

- Instance Type: `g4dn.xlarge` with 4 vCPU, 16 GiB memory, and 1 Nvidia T4 Tensor Core GPU (On-Demand pricing).
- VPC with 50 GB of data processed per NAT Gateway per month.
- Other assumptions are the same as the Flexible Workload scenario.

| Service \ Runtime  | 2h/day Mon-Fri | 8h/day Mon-Fri | 12h/day Mon-Fri | 24/7          |
|--------------------|----------------|----------------|-----------------|---------------|
| Compute            | $23            | $91            | $137            | $384          |
| Storage            | -              | -              | -               | $20           |
| ALB                | -              | -              | -               | $20           |
| Networking         | -              | -              | -               | $70           |
| Registry           | -              | -              | -               | $1            |
| Logging            | -              | -              | -               | $3            |
| Total Monthly Cost | $137           | $205           | $251            | $498          |

### Useful Commands

* `npx cdk ls`          list all stacks in the app
* `npx cdk synth`       emits the synthesized CloudFormation template
* `npx cdk deploy`      deploy this stack to your default AWS account/region
* `npx cdk destroy`     destroy the deployed stack in your default AWS account/region
* `npx cdk diff`        compare deployed stack with current state
* `npx cdk docs`        open CDK documentation

## Q&A

#### Does the Dockerfile already pre-install models?

Dockerfile includes only ComfyUI and ComfyUI-Manager. To install models either go over ComfyUI-Manager after deployment or over the section [Upload Models](README.md#uploading-models).

#### Can I contribute to this project?

Yes, feel free to follow the [contribution](CONTRIBUTING.md#security-issue-notifications) guide.

#### Can this be consiered for production deployments?

Consider this setup as an sample deployment for personal or non-production use.

## Contributors

[![contributors](https://contrib.rocks/image?repo=aws-samples/cost-effective-aws-deployment-of-comfyui&max=1500)](https://github.com/aws-samples/cost-effective-aws-deployment-of-comfyui/graphs/contributors)
 
## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

- [License](LICENSE) of the project.
- [Code of Conduct](CONTRIBUTING.md#code-of-conduct) of the project.
- [THIRD-PARTY](THIRD-PARTY) for more information about third party usage
