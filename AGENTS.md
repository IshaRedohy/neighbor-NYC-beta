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

- **Tool-first preference (owner instruction):** Proactively discover and use relevant connected MCP tools and plugins for inspection, setup, execution, and verification before asking the owner to perform manual steps. Follow applicable plugin skills. If one tool or terminal path fails, check supported alternatives within the authorized scope before handing work back. Ask the owner only for missing information, authentication, required approval, or an action that available tools cannot complete; explain the specific blocker and provide the smallest necessary manual step. Never claim a tool action or verification succeeded without evidence.

Prior sessions recorded OAuth connections for Neon, Neo4j, GitHub, and AWS. Resource identities, dated verification evidence, owner-reported checks, and remaining hosted work are maintained in `docs/AWS_DEPLOYMENT.md`; read its current status before acting. Do not repeat the obsolete assumption that Neon is still on Free or that Aura and application schemas have not been provisioned. Reuse the recorded resources. Discover the tools actually exposed in the current session before use; configuration alone does not prove authentication, resource access, or a running service. Prefer the relevant MCP for supported operations. If unavailable, report the gap and use an authenticated CLI for equivalent checks when available; do not claim unperformed checks passed.

- **Neon MCP:** inspect organizations, projects, branches, computes, and schema before creating anything. Pass explicit project and branch IDs where supported; on an unscoped connection, always supply `project_id` for tools that accept it. An empty list only establishes what the current account/scope can see. Use read-only inspection first. Any tool marked `destructiveHint: true` requires explicit user approval before invocation.
- **Neo4j MCP:** verify which instance/database it targets and use read-only schema or bounded queries for inspection. A hosted `https://<instance-id>.mcp-instances.neo4j.io` endpoint is for MCP; the Python app needs the instance's driver URI and `NEO4J_USER` / `NEO4J_PASSWORD`. Do not infer that local Docker data exists in Aura. Verify the instance in Aura before creating another. Keep projection writes in the application's sync workflow; graph rebuild deletes `Person` nodes and requires a confirmed dedicated target.
- **AWS MCP:** verify account, role, region, and existing CloudFormation resources before deployment work. Check the relevant stage's stack outputs and secret metadata without retrieving secret values unnecessarily. Follow the repository's CDK/release workflow; installing MCP does not deploy a stack or supply runtime database credentials.
- **GitHub MCP:** use the branch/PR/commit checks below to prevent conflicting work and mixed commits.

### Project skill

The repository skill is `.agents/skills/neighbor-project/SKILL.md` (invoke as `$neighbor-project` when available). Use it for Neighbor NYC feature changes, debugging, verification, and operations. It routes to the maintained project guides; this file remains the source of project-wide rules. If a newly added skill is absent from the session catalog, read its file directly and refresh/restart Codex if necessary.

### Useful integrations and discovery inventory

This inventory was inspected on **2026-11-12**. Rediscover tools each session: an exposed namespace, a plugin directory listing, an OAuth connection, and a successful resource query are different evidence. This list documents capabilities; it does not install plugins, grant permissions, or authorize infrastructure changes.

| Integration | Project use and preferred capabilities | Observed session availability |
| --- | --- | --- |
| GitHub MCP (`mcp__github`) | Repository identity, default branch, branch tips, commits, PRs, reviews and checks; authorized branch/PR changes. Use `get_me`, `search_repositories`, `list_branches`, `list_commits`, `list_pull_requests`, and `pull_request_read` as appropriate. | Tools exposed; account and `IshaRedohy/neighbor-NYC-beta` repository access verified, default branch `main`. The separate directory GitHub plugin is listed as uninstalled; it is not required to use this working MCP. |
| Neon MCP (`mcp__Neon`) and `neon-postgres` skills | Project/branch/compute/schema inspection and scoped database work when those tools are exposed. Use `neon-postgres:neon-postgres` for existing SQL/schema/connections and `neon-postgres:neon` for broader backend setup. | Only `get_neon_auth_config`, `provision_neon_auth`, and `provision_neon_data_api` exposed in this session; no project/branch/SQL inspection tools. Skills are available, while the directory plugin reports uninstalled. Resource access was not reverified. These provisioning tools do not substitute for database inspection. |
| Neo4j/Aura MCP | Confirm instance/database, inspect schema and run bounded read-only Cypher; use application sync for projection writes. | Prior connection recorded; no Neo4j tools exposed in this session. Plugin search returned no matches, which does not establish directory-wide absence. Use an authenticated supported CLI or the existing Python driver for equivalent authorized checks. |
| AWS MCP | Account/role/region, CloudFormation stacks/outputs, secret metadata, Lambda, SQS/DLQ, CloudWatch, S3 backup and CloudFront inspection for the selected stage. Follow CDK/release scripts for changes. | Prior connection recorded; no AWS tools exposed in this session. Search found AWS Data Analytics, which covers Glue/Athena/S3 Tables and does not replace this app's deployment tooling. Use authenticated AWS CLI where supported. |
| In-app Browser skill and Node REPL (`mcp__node_repl`) | Local frontend interaction, network inspection, screenshots, mobile/desktop checks and synthetic member journeys from `docs/TESTING.md`. Read `browser:control-in-app-browser` before browser use. | Skill and REPL tools available; browser attachment and app availability must be checked at use time. |
| OpenAI Developer Docs MCP (`mcp__openaiDeveloperDocs`) and `openai-docs` skill | Official guidance for Codex configuration, repository skills and OpenAI product/API questions. Search, then fetch the relevant page. | Documentation search/fetch tools exposed. For Next.js changes, the installed Next.js guides above remain required. |
| Plugin Management (`mcp__codex_apps__plugin_management`) | Discover missing provider integrations; inspect permissions/dependencies and suggest the smallest useful set when a connection is needed. Follow `plugin-management:plugin-management`. | Search, suggestion and management tools exposed; Neon, Neo4j, GitHub and AWS searches performed. Search results do not prove installation or authentication. |
| Built-in web search and image generation | Current primary vendor documentation; requested visual assets when they help the existing app. Follow the `imagegen` skill for raster generation/editing. | Tools available. Use web search for documentation and connected provider tools for account-specific state. |

Other available skills are conditional: use `documents:documents`, `pdf:pdf`, `spreadsheets:Spreadsheets`, or `presentations:Presentations` only for requested document/report artifacts. Additional Neon Auth, Realtime, Functions, Object Storage and AI Gateway skills are available for explicitly scoped features; availability is not a reason to replace the existing Google OAuth/Cognito, FastAPI, SQL outbox, or AWS architecture. Sites is for a separately requested Sites workflow, not the default implementation path for this repository. Discover design or Google-service plugins only when a task actually needs their external data; keep private Forms responses out of repository artifacts.

## GitHub branches and commits

1. Before edits, inspect local `git status --short --branch`, remotes, upstream tracking, and existing worktrees. Preserve user changes and unrelated untracked files.
2. Use GitHub MCP to verify the intended repository, default/base branch, current remote branch tips, relevant open PRs (head and base), and recent commits. Compare local HEAD with the remote base/upstream. Do not assume cached `origin/*` refs are current; fetch or check remote refs when needed.
3. Choose a task branch from the intended base for implementation. Before switching or creating a worktree, ensure existing edits belong to that work and will not be carried into another task. Do not reset, discard, or silently stash user work to obtain a clean tree.
4. Before committing, review the diff and stage only intended files/hunks. Inspect the staged diff and commit range against the base; avoid broad staging that includes credentials, MCP configuration, private data, or unrelated work. Do not duplicate already merged commits through cherry-picks or merges.
5. Before pushing, opening/updating a PR, or merging, refresh the remote comparison and use GitHub MCP to check the PR's latest head/base SHAs, mergeability, required checks, and reviews. Resolve any conflicts deliberately and rerun relevant checks. Unknown/pending mergeability is not a passing result. Avoid force pushes or published-history rewrites unless explicitly authorized.
6. Report what was verified and any remaining gaps. Local absence of conflict markers does not establish GitHub PR mergeability, and a successful check can become stale if the base branch moves.
