import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sources from "aws-cdk-lib/aws-lambda-event-sources";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as secrets from "aws-cdk-lib/aws-secretsmanager";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as logs from "aws-cdk-lib/aws-logs";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as actions from "aws-cdk-lib/aws-cloudwatch-actions";
import * as sns from "aws-cdk-lib/aws-sns";
import * as subscriptions from "aws-cdk-lib/aws-sns-subscriptions";
import * as budgets from "aws-cdk-lib/aws-budgets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cognito from "aws-cdk-lib/aws-cognito";
import path from "node:path";

export class BetaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    const stage = this.node.tryGetContext("stage") || "staging";
    if (!["staging", "beta"].includes(stage))
      throw new Error("stage must be staging or beta");
    const secretArn = new cdk.CfnParameter(this, "AppSecretArn", {
      type: "String",
      description: "Secrets Manager ARN for this environment only",
    });
    const alertEmail = new cdk.CfnParameter(this, "AlertEmail", {
      type: "String",
      allowedPattern: ".+@.+",
    });
    const secret = secrets.Secret.fromSecretCompleteArn(
      this,
      "Configuration",
      secretArn.valueAsString,
    );
    const site = new s3.Bucket(this, "Site", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [{ noncurrentVersionExpiration: cdk.Duration.days(30) }],
    });
    const backups = new s3.Bucket(this, "Backups", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(30),
          noncurrentVersionExpiration: cdk.Duration.days(7),
        },
      ],
    });
    const dlq = new sqs.Queue(this, "GraphDeadLetters", {
      retentionPeriod: cdk.Duration.days(14),
      enforceSSL: true,
    });
    const scheduleDlq = new sqs.Queue(this, "ScheduleDeadLetters", {
      retentionPeriod: cdk.Duration.days(14),
      enforceSSL: true,
    });
    const queue = new sqs.Queue(this, "GraphNotifications", {
      visibilityTimeout: cdk.Duration.seconds(720),
      retentionPeriod: cdk.Duration.days(4),
      enforceSSL: true,
      deadLetterQueue: { queue: dlq, maxReceiveCount: 5 },
    });
    const image = (handler: string) =>
      lambda.DockerImageCode.fromImageAsset(path.join(__dirname, ".."), {
        file: "backend/Dockerfile.lambda",
        cmd: [handler],
        platform: cdk.aws_ecr_assets.Platform.LINUX_AMD64,
      });
    const env = {
      ENVIRONMENT: "production",
      DEMO_MODE: "false",
      APP_SECRET_ARN: secretArn.valueAsString,
      DB_POOL_MAX: "2",
      GRAPH_ENABLED: stage === "beta" ? "true" : "false",
      NATIVE_SIGNUP: "false",
    };
    const create = (
      name: string,
      handler: string,
      timeout: number,
      concurrency: number,
    ) => {
      const fn = new lambda.DockerImageFunction(this, name, {
        code: image(handler),
        memorySize: 512,
        architecture: lambda.Architecture.X86_64,
        timeout: cdk.Duration.seconds(timeout),
        reservedConcurrentExecutions: concurrency,
        environment: env,
        logGroup: new logs.LogGroup(this, name + "Logs", {
          retention: logs.RetentionDays.TWO_WEEKS,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      });
      secret.grantRead(fn);
      return fn;
    };
    const apiFunction = create("Api", "backend.lambda_handler.handler", 29, 5);
    apiFunction.addEnvironment("GRAPH_QUEUE_URL", queue.queueUrl);
    queue.grantSendMessages(apiFunction);
    const sync = create("GraphSync", "backend.sync_lambda.handler", 120, 2);
    sync.addEventSource(
      new sources.SqsEventSource(queue, {
        batchSize: 1,
        reportBatchItemFailures: true,
        maxConcurrency: 2,
      }),
    );
    new events.Rule(this, "HourlyRecovery", {
      schedule: events.Schedule.rate(cdk.Duration.hours(1)),
      targets: [
        new targets.LambdaFunction(sync, {
          deadLetterQueue: scheduleDlq,
          retryAttempts: 2,
        }),
      ],
    });
    const backup = create("Backup", "backend.backup_lambda.handler", 300, 1);
    backup.addEnvironment("BACKUP_BUCKET", backups.bucketName);
    backups.grantPut(backup);
    new events.Rule(this, "DailyBackup", {
      schedule: events.Schedule.cron({ minute: "15", hour: "8" }),
      targets: [
        new targets.LambdaFunction(backup, {
          deadLetterQueue: scheduleDlq,
          retryAttempts: 2,
        }),
      ],
    });
    const http = new apigw.HttpApi(this, "HttpApi", {
      createDefaultStage: true,
      defaultIntegration: new integrations.HttpLambdaIntegration(
        "FastAPI",
        apiFunction,
      ),
    });
    const stageResource = http.defaultStage!.node
      .defaultChild as apigw.CfnStage;
    stageResource.defaultRouteSettings = {
      throttlingBurstLimit: 20,
      throttlingRateLimit: 10,
    };
    const accessLog = new logs.LogGroup(this, "ApiAccessLogs", {
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    stageResource.accessLogSettings = {
      destinationArn: accessLog.logGroupArn,
      format: JSON.stringify({
        requestId: "$context.requestId",
        status: "$context.status",
        latency: "$context.responseLatency",
      }),
    };
    const securityHeaders = new cloudfront.ResponseHeadersPolicy(
      this,
      "SecurityHeaders",
      {
        securityHeadersBehavior: {
          contentTypeOptions: { override: true },
          frameOptions: {
            frameOption: cloudfront.HeadersFrameOption.DENY,
            override: true,
          },
          referrerPolicy: {
            referrerPolicy: cloudfront.HeadersReferrerPolicy.NO_REFERRER,
            override: true,
          },
          strictTransportSecurity: {
            accessControlMaxAge: cdk.Duration.days(365),
            includeSubdomains: true,
            override: true,
          },
          contentSecurityPolicy: {
            override: true,
            contentSecurityPolicy:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://*.amazoncognito.com",
          },
        },
        customHeadersBehavior: {
          customHeaders: [
            {
              header: "Permissions-Policy",
              value: "camera=(), microphone=(), geolocation=()",
              override: true,
            },
          ],
        },
      },
    );
    const routing = new cloudfront.Function(this, "StaticRoutes", {
      code: cloudfront.FunctionCode.fromInline(`function handler(event) {
      var r=event.request; var known=['/','/login','/discover','/community','/messages','/profile','/admin','/signup'];
      var uri=r.uri.length>1?r.uri.replace(/\\/$/,''):r.uri;
      if(known.indexOf(uri)>=0) r.uri=uri==='/'?'/index.html':uri+'.html';
      return r;
    }`),
    });
    const distribution = new cloudfront.Distribution(this, "App", {
      defaultRootObject: "index.html",
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(site),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        responseHeadersPolicy: securityHeaders,
        functionAssociations: [
          {
            function: routing,
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          },
        ],
      },
      additionalBehaviors: {
        "_next/static/*": {
          origin: origins.S3BucketOrigin.withOriginAccessControl(site),
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          responseHeadersPolicy: securityHeaders,
        },
        "api/*": {
          origin: new origins.HttpOrigin(
            cdk.Fn.select(2, cdk.Fn.split("/", http.apiEndpoint)),
          ),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy:
            cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          responseHeadersPolicy: securityHeaders,
        },
      },
    });
    const topic = new sns.Topic(this, "Operations");
    topic.addSubscription(
      new subscriptions.EmailSubscription(alertEmail.valueAsString),
    );
    for (const [name, metric, threshold] of [
      ["ApiErrors", apiFunction.metricErrors(), 1],
      [
        "ApiServerErrors",
        new cloudwatch.Metric({
          namespace: "AWS/ApiGateway",
          metricName: "5xx",
          dimensionsMap: { ApiId: http.apiId },
          statistic: "Sum",
        }),
        1,
      ],
      ["SyncErrors", sync.metricErrors(), 1],
      ["BackupErrors", backup.metricErrors(), 1],
      ["GraphDeadLetters", dlq.metricApproximateNumberOfMessagesVisible(), 1],
      [
        "ScheduleDeadLetters",
        scheduleDlq.metricApproximateNumberOfMessagesVisible(),
        1,
      ],
      ["SyncLag", queue.metricApproximateAgeOfOldestMessage(), 3600],
      [
        "BackupMissing",
        backup.metricInvocations({
          period: cdk.Duration.days(1),
          statistic: "Sum",
        }),
        1,
      ],
    ] as [string, cloudwatch.Metric, number][]) {
      const alarm = new cloudwatch.Alarm(this, name + "Alarm", {
        metric,
        threshold,
        evaluationPeriods: 1,
        comparisonOperator:
          name === "BackupMissing"
            ? cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
            : cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        treatMissingData:
          name === "BackupMissing"
            ? cloudwatch.TreatMissingData.BREACHING
            : cloudwatch.TreatMissingData.NOT_BREACHING,
      });
      alarm.addAlarmAction(new actions.SnsAction(topic));
    }
    new budgets.CfnBudget(this, "MonthlyBudget", {
      budget: {
        budgetName: `neighbor-${stage}`,
        budgetType: "COST",
        timeUnit: "MONTHLY",
        budgetLimit: { amount: 50, unit: "USD" },
      },
      notificationsWithSubscribers: [20, 35, 50].map((amount) => ({
        notification: {
          comparisonOperator: "GREATER_THAN",
          notificationType: "ACTUAL",
          thresholdType: "ABSOLUTE_VALUE",
          threshold: amount,
        },
        subscribers: [
          { subscriptionType: "EMAIL", address: alertEmail.valueAsString },
        ],
      })),
    });
    for (const [name, value] of Object.entries({
      AppUrl: "https://" + distribution.distributionDomainName,
      SiteBucket: site.bucketName,
      DistributionId: distribution.distributionId,
      BackupBucket: backups.bucketName,
      ApiFunction: apiFunction.functionName,
      BackupFunction: backup.functionName,
      GraphFunction: sync.functionName,
      GraphQueue: queue.queueUrl,
      GraphDeadLetterQueue: dlq.queueUrl,
    }))
      new cdk.CfnOutput(this, name, { value });
  }
}

// Phase 5 only: deploy separately after hosted beta feedback and SES sending approval.
export class SignupStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    const appUrl = new cdk.CfnParameter(this, "AppUrl", {
      type: "String",
      allowedPattern: "https://[^/]+",
      description: "Exact CloudFront app origin, no trailing slash",
    });
    const sesArn = new cdk.CfnParameter(this, "SesIdentityArn", {
      type: "String",
    });
    const from = new cdk.CfnParameter(this, "EmailFrom", { type: "String" });
    const secretArn = new cdk.CfnParameter(this, "AppSecretArn", {
      type: "String",
    });
    const secret = secrets.Secret.fromSecretCompleteArn(
      this,
      "GoogleCredentials",
      secretArn.valueAsString,
    );
    const pool = new cognito.CfnUserPool(this, "UserPool", {
      userPoolName: id,
      userPoolTier: "ESSENTIALS",
      usernameAttributes: ["email"],
      autoVerifiedAttributes: ["email"],
      usernameConfiguration: { caseSensitive: false },
      policies: { signInPolicy: { allowedFirstAuthFactors: ["EMAIL_OTP"] } },
      mfaConfiguration: "OFF",
      emailConfiguration: {
        emailSendingAccount: "DEVELOPER",
        sourceArn: sesArn.valueAsString,
        from: from.valueAsString,
      },
      schema: [{ name: "email", required: true, mutable: true }],
      deletionProtection: "ACTIVE",
    });
    const google = new cognito.CfnUserPoolIdentityProvider(this, "Google", {
      userPoolId: pool.ref,
      providerName: "Google",
      providerType: "Google",
      providerDetails: {
        client_id: secret
          .secretValueFromJson("GOOGLE_CLIENT_ID")
          .unsafeUnwrap(),
        client_secret: secret
          .secretValueFromJson("GOOGLE_CLIENT_SECRET")
          .unsafeUnwrap(),
        authorize_scopes: "openid email",
      },
      attributeMapping: {
        email: "email",
        email_verified: "email_verified",
        username: "sub",
      },
    });
    const client = new cognito.CfnUserPoolClient(this, "Client", {
      userPoolId: pool.ref,
      generateSecret: false,
      supportedIdentityProviders: ["COGNITO", "Google"],
      explicitAuthFlows: ["ALLOW_USER_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
      allowedOAuthFlowsUserPoolClient: true,
      allowedOAuthFlows: ["code"],
      allowedOAuthScopes: ["openid", "email"],
      callbackUrLs: [appUrl.valueAsString + "/api/auth/cognito/callback"],
      logoutUrLs: [appUrl.valueAsString],
      preventUserExistenceErrors: "ENABLED",
      enableTokenRevocation: true,
    });
    client.addDependency(google);
    const domain = new cognito.CfnUserPoolDomain(this, "Domain", {
      userPoolId: pool.ref,
      domain: `neighbor-${this.account}-${this.node.tryGetContext("stage") || "staging"}`,
      managedLoginVersion: 2,
    });
    new cognito.CfnManagedLoginBranding(this, "LoginBranding", {
      userPoolId: pool.ref,
      clientId: client.ref,
      useCognitoProvidedValues: true,
    });
    new cdk.CfnOutput(this, "CognitoIssuer", {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${pool.ref}`,
    });
    new cdk.CfnOutput(this, "CognitoDomain", {
      value: `https://${domain.ref}.auth.${this.region}.amazoncognito.com`,
    });
    new cdk.CfnOutput(this, "CognitoClientId", { value: client.ref });
  }
}
