# Neighbor deployment identity

`deployment-identity.json` creates `neighbor-deployer` (no password or access keys) and `NeighborDeploymentRole`. The user can only assume that role. The role has initial access to Neighbor secrets/stacks and CDK assets in us-east-1. It has no AdministratorAccess or IAM-management permissions. It is not yet a complete CDK bootstrap/release policy: CDK bootstrap execution roles and additional permissions must be configured and verified before deployment. Access Analyzer reported no policy findings for the resolved role policy; this is not a deployment success test.

The stack was submitted through AWS MCP as `Neighbor-DeploymentIdentity` in account `418272785819`, region `us-east-1`. Root credentials are used only for this initial identity setup. Existing application stacks are unchanged.

To reproduce from a trusted administrative CLI profile (do not run again if the stack already exists):

```sh
aws cloudformation deploy --template-file infra/bootstrap/deployment-identity.json --stack-name Neighbor-DeploymentIdentity --capabilities CAPABILITY_NAMED_IAM --region us-east-1 --profile YOUR_ADMIN_PROFILE
```

For local CLI access, create an access key for `neighbor-deployer` through the AWS console and enter it interactively; never paste it into chat or commit it. This optional local access key is separate from AWS MCP's remote authentication.

```sh
aws configure --profile neighbor-source
aws configure set role_arn arn:aws:iam::418272785819:role/NeighborDeploymentRole --profile neighbor-deploy
aws configure set source_profile neighbor-source --profile neighbor-deploy
aws configure set region us-east-1 --profile neighbor-deploy
aws sts get-caller-identity --profile neighbor-deploy
```

The last command must return an `assumed-role/NeighborDeploymentRole/` ARN. Only then use `AWS_PROFILE=neighbor-deploy` for local deployment helpers. If using console authentication for AWS MCP, enable console access and MFA for the new IAM user, sign in as that user, switch to NeighborDeploymentRole, and reconnect the integration using a supported role-session authentication flow. Role creation does not change the active MCP session; verify GetCallerIdentity after reconnecting. Do not assume the remote MCP uses local CLI profiles.

The identity stack itself needs an administrator for updates. Keep its template under review; do not broaden the deployment role to modify unrelated identities or stacks to bypass a missing permission.
