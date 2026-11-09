import * as cdk from "aws-cdk-lib";
import { Template, Match } from "aws-cdk-lib/assertions";
import { BetaStack, SignupStack } from "./stack";
const app = new cdk.App({ context: { stage: "staging" } });
const template = Template.fromStack(new BetaStack(app, "Test"));
template.resourceCountIs("AWS::Lambda::Function", 3);
template.hasResourceProperties("AWS::Lambda::Function", {
  MemorySize: 512,
  Environment: {
    Variables: Match.objectLike({
      DEMO_MODE: "false",
      GRAPH_ENABLED: "false",
      DB_POOL_MAX: "2",
    }),
  },
  VpcConfig: Match.absent(),
});
template.hasResourceProperties("AWS::CloudFront::Distribution", {
  DistributionConfig: {
    CacheBehaviors: Match.arrayWith([
      Match.objectLike({
        PathPattern: "api/*",
        CachePolicyId:
          cdk.aws_cloudfront.CachePolicy.CACHING_DISABLED.cachePolicyId,
        OriginRequestPolicyId:
          cdk.aws_cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
            .originRequestPolicyId,
      }),
    ]),
  },
});
template.hasResourceProperties("AWS::SQS::Queue", {
  RedrivePolicy: Match.objectLike({ maxReceiveCount: 5 }),
});
template.hasResourceProperties("AWS::Budgets::Budget", {
  NotificationsWithSubscribers: Match.arrayWith([
    Match.objectLike({
      Notification: {
        ComparisonOperator: "GREATER_THAN",
        NotificationType: "ACTUAL",
        Threshold: 50,
        ThresholdType: "ABSOLUTE_VALUE",
      },
    }),
  ]),
});
const signup = Template.fromStack(new SignupStack(new cdk.App(), "SignupTest"));
signup.hasResourceProperties("AWS::Cognito::UserPool", {
  UserPoolTier: "ESSENTIALS",
  Policies: { SignInPolicy: { AllowedFirstAuthFactors: ["EMAIL_OTP"] } },
});
console.log("Infrastructure assertions passed.");
