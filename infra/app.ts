import * as cdk from "aws-cdk-lib";
import { BetaStack, SignupStack } from "./stack";
const app = new cdk.App();
const stage = app.node.tryGetContext("stage") || "staging";
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: "us-east-1" };
new BetaStack(app, `Neighbor-${stage}`, { env });
if (app.node.tryGetContext("signup") === "true")
  new SignupStack(app, `Neighbor-${stage}-Signup`, { env });
