<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Project and database workflow

- Read `README.md`, `docs/AWS_DEPLOYMENT.md`, and `docs/GRAPH.md` before database setup or deployment work. PostgreSQL is authoritative; Neo4j is a rebuildable relationship projection.
- Local development uses Docker PostgreSQL and Neo4j via `.env`. Hosted staging and beta use separate Neon projects and separate ignored `.env.hosted.staging` / `.env.hosted.beta` files. Never overwrite local connections while setting up hosted access.
- Keep staging and ordinary development data synthetic. For hosted schema work, use an isolated branch of the synthetic staging project; track its project/branch IDs separately from the Git branch. A Git checkout does not select a database, and merging code does not apply a migration.
- Keep migrations in the repository and use `scripts/hosted.py migrate --env-file <target-file>` for hosted migrations. Runtime uses pooled `DATABASE_URL`; migrations and backups use direct `DIRECT_DATABASE_URL`. Preserve these exact names used by the code.
- Confirm target environment, database identity, and existing resources before provisioning or writing. A documentation review does not authorize cloud provisioning, database changes, or deployment. Never print or commit credentials, private exports, or populated environment files.

## MCP tools

As of 2026-11-09, the user has only connected Neon, Neo4j, GitHub, and AWS MCP servers through OAuth; they have not provisioned the hosted databases or AWS application infrastructure. The GitHub repository and local Docker databases already exist. Treat hosted setup as initial provisioning unless later work establishes otherwise. Discover the tools actually exposed in the current session before use; configuration alone does not prove authentication, resource access, or a running service. Prefer the relevant MCP for supported operations. If unavailable, report the gap and use an authenticated CLI for equivalent checks when available; do not claim unperformed checks passed.

- **Neon MCP:** inspect organizations, projects, branches, computes, and schema before creating anything. Pass explicit project and branch IDs where supported; on an unscoped connection, always supply `project_id` for tools that accept it. An empty list only establishes what the current account/scope can see. Use read-only inspection first. Any tool marked `destructiveHint: true` requires explicit user approval before invocation.
- **Neo4j MCP:** verify which instance/database it targets and use read-only schema or bounded queries for inspection. A hosted `https://<instance-id>.mcp-instances.neo4j.io` endpoint is for MCP; the Python app needs the instance's driver URI and `NEO4J_USER` / `NEO4J_PASSWORD`. Do not infer that local Docker data exists in Aura. Verify the instance in Aura before creating another. Keep projection writes in the application's sync workflow; graph rebuild deletes `Person` nodes and requires a confirmed dedicated target.
- **AWS MCP:** verify account, role, region, and existing CloudFormation resources before deployment work. Check the relevant stage's stack outputs and secret metadata without retrieving secret values unnecessarily. Follow the repository's CDK/release workflow; installing MCP does not deploy a stack or supply runtime database credentials.
- **GitHub MCP:** use the branch/PR/commit checks below to prevent conflicting work and mixed commits.

## GitHub branches and commits

1. Before edits, inspect local `git status --short --branch`, remotes, upstream tracking, and existing worktrees. Preserve user changes and unrelated untracked files.
2. Use GitHub MCP to verify the intended repository, default/base branch, current remote branch tips, relevant open PRs (head and base), and recent commits. Compare local HEAD with the remote base/upstream. Do not assume cached `origin/*` refs are current; fetch or check remote refs when needed.
3. Choose a task branch from the intended base for implementation. Before switching or creating a worktree, ensure existing edits belong to that work and will not be carried into another task. Do not reset, discard, or silently stash user work to obtain a clean tree.
4. Before committing, review the diff and stage only intended files/hunks. Inspect the staged diff and commit range against the base; avoid broad staging that includes credentials, MCP configuration, private data, or unrelated work. Do not duplicate already merged commits through cherry-picks or merges.
5. Before pushing, opening/updating a PR, or merging, refresh the remote comparison and use GitHub MCP to check the PR's latest head/base SHAs, mergeability, required checks, and reviews. Resolve any conflicts deliberately and rerun relevant checks. Unknown/pending mergeability is not a passing result. Avoid force pushes or published-history rewrites unless explicitly authorized.
6. Report what was verified and any remaining gaps. Local absence of conflict markers does not establish GitHub PR mergeability, and a successful check can become stale if the base branch moves.
