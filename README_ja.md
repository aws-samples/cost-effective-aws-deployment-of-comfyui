[English](./README.md) | 日本語 | [中文](./README_cn.md)

# ComfyUI on AWS

[![ライセンス:MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

このサンプルリポジトリは、強力な AI 駆動型画像生成ツールである ComfyUI を AWS 上にシームレスかつコスト効率の高い方法でデプロイするソリューションを提供します。このリポジトリは、ECS、EC2、その他の AWS サービスを活用した包括的なインフラストラクチャコードと構成設定を提供しています。セキュリティと拡張性を損なうことなく、手間のかからないデプロイプロセスを体験できます。

💡 注意: このソリューションでは AWS の費用が発生します。費用に関する詳細情報は、コスト セクションを参照してください。

![comfy](docs/assets/comfy.png)
![comfy gallery](docs/assets/comfy_gallery.png)

## ソリューションの機能

1. **簡単なデプロイ** 🚀 : [Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) を活用し、簡単で自動化されたデプロイが可能です。
2. **コスト最適化** 💰: スポットインスタンス、自動シャットダウン、スケジュールされたスケーリングなどのコスト削減オプションを活用し、コスト効率を最大化します。
3. **堅牢なセキュリティ** 🔒: 認証 (SAML の Microsoft Entra ID / Google Workspace など)、メールドメイン制限、IP 制限、カスタムドメイン SSL、セキュリティスキャンなど、堅牢なセキュリティ対策により安心を得られます。

## アーキテクチャの概要

![AWS アーキテクチャ](docs/drawio/ComfyUI.drawio.png)

## サービス

- **[Amazon VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)** - ECS クラスターをホストするためのパブリックおよびプライベートサブネットを持つ VPC が作成されます
- **[ECS クラスター](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/clusters.html)** - ComfyUI タスクを実行する ECS クラスターが作成されます
- **[Auto Scaling グループ](https://docs.aws.amazon.com/autoscaling/ec2/userguide/auto-scaling-groups.html)** - ASG が作成され、ECS のキャパシティープロバイダーとして関連付けられます。GPU インスタンスを起動して ECS タスクをホストします。
- **[ECS タスク定義](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)** - ComfyUI コンテナを定義し、EBS ボリュームをマウントして永続化します
- **[ECS サービス](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html)** - ComfyUI タスク定義を実行する ECS サービスを作成します
- **[Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html)** - ALB が設定され、ECS サービスにトラフィックをルーティングします
- **[Amazon ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html)** - ComfyUI Docker イメージを保持します
- **[CloudWatch ロググループ](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html)** - ECS タスクからのログを保存します
- **[Amazon Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html)** - ALB の前に認証を設けるユーザーディレクトリ
- **[AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html)** - IP によるアクセスをブロックします
- **[AWS Lambda](https://docs.aws.amazon.com/lambda/)** - ComfyUI の状態を管理します


## Getting Started

### AWS 環境の準備

再現性と一貫性を確保するために、このソリューションのデプロイとテストには [Amazon SageMaker Studio Code Editor](https://docs.aws.amazon.com/sagemaker/latest/dg/code-editor.html) の使用をお勧めします。

ℹ️ ローカル開発環境を使用することもできますが、AWS CLI、AWS CDK、Docker が適切に設定されていることを確認する必要があります。

<details>
<summary>Amazon SageMaker Studio Code Editor での環境設定を (クリックして表示) </summary>

1. [sagemaker-studio-code-editor-template](https://github.com/aws-samples/sagemaker-studio-code-editor-template/) のリンクから CloudFormation テンプレートを使用して、Amazon SageMaker Studio Code Editor を起動します (このテンプレートは、Docker、自動終了などの必要な機能を含む Code Editor を起動します)。
2. CloudFormation の出力から URL を使用して SageMaker Studio を開きます。
3. 左上のアプリケーションセクションから Code Editor に移動します。
</details>

<details>
<summary> ローカル環境での環境設定 (クリックして表示) </summary>

AWS CLI がない場合は、[AWS CLI インストールガイド](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) に従ってください。

CDK がない場合は、[CDK スタートガイド](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) に従ってください。

Docker がない場合は、[Docker インストールガイド](https://docs.docker.com/engine/install/) に従ってください。

インストール後に AWS CLI をセットアップしていない場合は、ローカル環境で次のコマンドを実行します。

```bash
aws configure
```

プロンプトが表示されたら、AWS アクセスキー ID、シークレットアクセスキー、デフォルトのリージョン名 (例 : us-east-1) を入力します。出力フォーマットフィールドはデフォルトのままにするか、好みに応じて指定できます。
</details>

> [!NOTE]
> アカウントにGPUインスタンスの割り当てがあることを確認してください。[Service Quota](https://us-west-2.console.aws.amazon.com/servicequotas/home/services/ec2/quotas/L-3819A6DF)に移動し、`All G and VT Spot Instance Requests`を 4 以上に設定してください。

### ComfyUI のデプロイ

1. (初回のみ) このリポジトリをクローンします (`git clone https://github.com/aws-samples/cost-effective-aws-deployment-of-comfyui.git`)
2. (初回のみ) リポジトリのディレクトリに移動します (`cd cost-effective-aws-deployment-of-comfyui`)
3. `make` を実行しデプロイ

Dockerfile のカスタムノードと拡張機能によっては、ComfyUI が使用可能になるまで約 8〜10 分かかります。

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

`ComfyUIStack.Endpoint` の出力値からアプリケーションにアクセスできます。

### モデルのアップロード

1. ComfyUI-Manager や他の拡張機能 (カスタムノード) を使用して、モデル、lora、埋め込み、controlnet をインストールできます。詳細は[ユーザーガイド](docs/USER_GUIDE.md#model-installation) を参照してください。
2. ( オプション) このリポジトリのアップロードスクリプトを拡張して実行し、事前選択されたモデル、controlnet などをインストールできます。SSM コマンドが機能しない場合は、使用しているロールに EC2 へのアクセス権限があることを確認してください。`/scripts/upload_models.sh` ファイルに他の例があります。

```bash
# 1. SSM で EC2 に接続
aws ssm start-session --target "$(aws ec2 describe-instances --filters "Name=tag:Name,Values=ComfyUIStack/Host" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].[InstanceId]' --output text)" --region $AWS_DEFAULT_REGION

# 2. コンテナに SSH 接続
container_id=$(sudo docker container ls --format '{{.ID}} {{.Image}}' | grep 'comfyui:latest$' | awk '{print $1}')
sudo docker exec -it $container_id /bin/bash

# 3. 必要なモデル、lora、controlnet などをインストール (すべてをスクリプトに含めて実行することもできます)

# 顔入れ替え用アップスケーラーの例 - https://huggingface.co/ai-forever/Real-ESRGAN
wget -c https://huggingface.co/ai-forever/Real-ESRGAN/blob/main/RealESRGAN_x2.pth -P ./models/upscale_models/
```

### ComfyUI へのアクセス

デプロイされたソリューションは、Application Load Balancer を介してアクセス可能な EC2 を提供します。Load Balancer には、Amazon Cognito User Pool を介した認証が必要です。

[Self Signup](docs/DEPLOY_OPTION.md#enable-self-sign-up) を有効にする、[SAML 認証](docs/DEPLOY_OPTION.md#saml-authentication)を有効にする、または Cognito コンソールでユーザーを手動で作成することができます。

### ユーザーガイド

ComfyUI の機能を最大限に活用し、シームレスな体験を確保するには、詳細な[ユーザーガイド](docs/USER_GUIDE.md) をご覧ください。このガイドでは、インストールから高度な設定まで、AI 駆動の画像生成の力を簡単に活用するためのすべてのステップを説明しています。

- [拡張機能 (カスタムノード) のインストール](docs/USER_GUIDE.md#installing-extensions-custom-nodes)
    - [推奨される拡張機能](docs/USER_GUIDE.md#recommended-extensions)
        - [ComfyUI Workspace Manager](docs/USER_GUIDE.md#comfyui-workspace-manager)
- [モデルのインストール](docs/USER_GUIDE.md#installing-models)
    - [ComfyUI-Manager の使用](docs/USER_GUIDE.md#using-comfyui-manager)
    - [他の拡張機能の使用](docs/USER_GUIDE.md#using-other-extensions)
    - [手動インストール](docs/USER_GUIDE.md#manual-installation)
- [ワークフローの実行](docs/USER_GUIDE.md#running-a-workflow)

### デプロイオプション

包括的なデプロイオプションにより、セキュリティ要件や予算制約に完全に合わせたソリューションを作成できます。AWS 上で ComfyUI の機能を最大限に活用できるよう、柔軟性と制御力を備えています。次の機能を数ステップで有効にできます。

- [設定方法](docs/DEPLOY_OPTION.md#configuration-method)
    - [cdk.json の値を変更する方法](docs/DEPLOY_OPTION.md#how-to-change-values-in-cdkjson)
- [セキュリティ関連の設定](docs/DEPLOY_OPTION.md#security-related-settings)
    - [自己登録を有効にする](docs/DEPLOY_OPTION.md#enable-self-sign-up)
    - [MFA を有効にする](docs/DEPLOY_OPTION.md#enable-mfa)
    - [サインアップできるメールアドレスのドメインを制限する](docs/DEPLOY_OPTION.md#restrict-the-email-address-domains-that-can-sign-up)
    - [AWS WAF の制限を有効にする](docs/DEPLOY_OPTION.md#enable-aws-waf-restrictions)
        - [IP アドレスの制限](docs/DEPLOY_OPTION.md#ip-address-restrictions)
        - [Rate limiting](docs/DEPLOY_OPTION.md#rate-limiting)
    - [SAML 認証](docs/DEPLOY_OPTION.md#saml-authentication)
- [コスト関連の設定](docs/DEPLOY_OPTION.md#cost-related-settings)
    - [スポットインスタンス](docs/DEPLOY_OPTION.md#spot-instance)
    - [自動/スケジュールでスケールダウン](docs/DEPLOY_OPTION.md#scale-down-automatically--on-schedule)
    - [NAT ゲートウェイの代わりに NAT インスタンスを使用する](docs/DEPLOY_OPTION.md#use-nat-insatnce-instead-of-nat-gateway)
- [監視と通知](docs/DEPLOY_OPTION.md#monitoring-and-notifications)
    - [Slack Integration](docs/DEPLOY_OPTION.md#slack-integration)
- [カスタムドメインの使用](docs/DEPLOY_OPTION.md#using-a-custom-domain)

### デプロイメントを削除してリソースをクリーンアップする

誤って削除してデータを失うことを防ぎ、できるだけ単純にするために、完全なデプロイメントとリソースの削除は半自動化されています。デプロイしたすべてのものをクリーンアップして削除するには、次の手順を実行する必要があります。

1. Auto Scaling Group を手動で削除する:
- AWS コンソールにログインする
- 検索バーで Auto Scaling Groups (EC2 機能) を検索する
- ComfyASG を選択する
- アクションを押して削除を選択する
- 削除を確認する

2. ASG 削除後、ターミナルで次のコマンドを実行すると、EBS と Cognito User Pool を除くすべての残りのリソースが削除されます。
```bash
npx cdk destroy
```

3. EBS ボリュームを削除する
- AWS コンソールにログインする
- 検索バーで Volumes (EC2 機能) を検索する
- ComfyUIVolume を選択する
- アクションを押して削除を選択する
- 削除を確認する

4. Cognito User Pool を削除する
- AWS コンソールにログインする
- 検索バーで Cognito を検索する
- ComfyUIuserPool.. を選択する
- 削除を押す
- 削除を確認する

5. ECR リポジトリを削除する
- AWS コンソールにログインする
- 検索バーで ECR (Elastic Container Registry) を検索する
- comfyui を選択する
- 削除を押す
- delete と入力して削除を確認する


## メモと追加情報

### コスト見積もり

このセクションでは、AWS 上でこのアプリケーションを実行するためのコスト見積もりを提供します。これらは概算であり、プロジェクトの具体的な要件と使用パターンに基づいて調整する必要があることに注意してください。

#### フレキシブルなワークロード (デフォルト)

ビジネス上重要でない作業負荷の場合、このタイプのアプリケーションの大半に該当すると思われますが、スポットインスタンスを使用してコスト削減の恩恵を受けることができます。スポットインスタンスは、`g4dn.xlarge` インスタンスタイプで平均 71% (us-east-1、2024 年 10 月) の割引を提供します。さらに、NAT ゲートウェイを NAT インスタンスに置き換えることで、コストをさらに削減できます。

コスト見積もりの前提条件は次のとおりです。

- AWS フリーティアのサービスは含まれていません。
- インスタンスタイプ : `g4dn.xlarge` (4 vCPU、16 GiB メモリ、1 Nvidia T4 Tensor Core GPU)、スポットインスタンス (71% 割引)。
- 250 GB SSD ストレージ。
- 1 Application Load Balancer。
- NAT インスタンスを備えた VPC。
- 月に 10 GB のデータを格納する Elastic Container Registry (ECR)。
- 月に 5 GB のログデータ。

| サービス \ 実行時間 | 平日2時間/日 | 平日8時間/日 | 平日 12 時間/日 | 24 時間 /7 日 |
|------------------|----------------|----------------|-----------------|---------------|
| コンピューティング  | $7             | $26            | $40             | $111          |
| ストレージ         | -              | -              | -               | $20           |
| ALB              | -              | -              | -               | $20           |
| ネットワーキング    | -              | -              | -               | $6            |
| レジストリ         | -              | -              | -               | $1            |
| ログ              | -              | -              | -               | $3            |
| 月額合計           | $60            | $79            | $93             | $164          |

#### ビジネス重要ワークロード

ビジネス上重要な作業負荷の場合は、オンデマンドインスタンスと NAT ゲートウェイを使用して可用性を高めることができます。

コスト見積もりの前提条件は次のとおりです。

- インスタンスタイプ : `g4dn.xlarge` (4 vCPU、16 GiB メモリ、1 Nvidia T4 Tensor Core GPU)、オンデマンド価格。
- 月に 50 GB のデータを NAT ゲートウェイで処理。
- その他の前提条件はフレキシブルワークロードのシナリオと同じです。

| サービス \ 実行時間 | 平日2時間/日 | 平日8時間/日 | 平日 12 時間/日 | 24 時間 /7 日 |
|------------------|----------------|----------------|-----------------|---------------|
| コンピューティング  | $23            | $91            | $137            | $384          |
| ストレージ         | -              | -              | -               | $20           |
| ALB              | -              | -              | -               | $20           |
| ネットワーキング    | -              | -              | -               | $70           |
| レジストリ         | -              | -              | -               | $1            |
| ロギング           | -              | -              | -               | $3            |
| 月額合計           | $137           | $205           | $251            | $498          |

### CDK 便利なコマンド

* `npx run cdk ls`          アプリ内のすべてのスタックを一覧表示
* `npx run cdk synth`       合成された CloudFormation テンプレートを出力
* `npx run cdk deploy`      デフォルトの AWS アカウント/リージョンにこのスタックをデプロイ
* `npx run cdk destroy`     デフォルトの AWS アカウント/リージョンからデプロイされたスタックを破棄
* `npx run cdk diff`        デプロイされたスタックと現在の状態を比較
* `npx run cdk docs`        CDK ドキュメントを開く

## Q&A

#### Dockerfile にモデルがあらかじめインストールされていますか?

Dockerfile には ComfyUI と ComfyUI-Manager のみが含まれています。モデルをインストールするには、デプロイ後に ComfyUI-Manager を使用するか、[モデルのアップロード](README.md#uploading-models) のセクションを参照してください。

#### このプロジェクトに貢献できますか?

はい、[CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) に従ってください。

#### 本番環境のデプロイに使用できますか?

この設定は個人利用または非本番環境での使用を想定したサンプルデプロイと考えてください。

## Contributors

[![contributors](https://contrib.rocks/image?repo=aws-samples/cost-effective-aws-deployment-of-comfyui&max=1500)](https://github.com/aws-samples/cost-effective-aws-deployment-of-comfyui/graphs/contributors)
 
## セキュリティ

詳細は [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) を参照してください。

## ライセンス

このライブラリは MIT-0 ライセンスの下で公開されています。LICENSE ファイルを参照してください。

- [License](LICENSE) of the project.
- [Code of Conduct](CONTRIBUTING.md#code-of-conduct) of the project.
- [THIRD-PARTY](THIRD-PARTY) for more information about third party usage
