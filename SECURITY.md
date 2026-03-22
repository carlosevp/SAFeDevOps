# Security policy

Thank you for helping keep this project and its users safe. Please read this page before reporting a security issue.

## Supported versions

Security fixes are applied to the **default branch** (`main`) and, when applicable, backported to the latest tagged release. If you run a fork or an older deployment, upgrade to the latest `main` (or your vendor’s supported build) before reporting when the issue may already be resolved.

## How to report a vulnerability

**Please do not** open a public GitHub issue for undisclosed security vulnerabilities (that can put users at risk).

Preferred channel:

1. Open this repository on GitHub.
2. Go to the **Security** tab.
3. Use **[Report a vulnerability](https://github.com/carlosevp/SAFeDevOps/security/advisories/new)** (private security advisory).

If private reporting is not available for this repo, contact the maintainers through a **private** channel they publish on the repository or organization profile, or ask for a reporting address via a **non-sensitive** issue titled “Security contact request”.

## What to include

- A short description of the issue and its **impact** (confidentiality, integrity, availability).
- **Steps to reproduce** or proof-of-concept, if you can share them safely.
- Affected **component** (e.g. API route, frontend, Docker image, dependency) and **version** / commit if known.
- Whether you believe the issue is **already exploitable** in a typical deployment.

## What we commit to

- We will **acknowledge** receipt of credible reports in a reasonable timeframe.
- We will **investigate** and work toward a **fix** or mitigation on supported branches.
- We will **coordinate disclosure** with you before making details public when possible.

We are volunteers / maintainers of an open-source pilot; response times may vary around holidays and weekends.

## Scope (in scope examples)

- Authentication, authorization, and session handling bugs in this codebase.
- Injection, path traversal, unsafe deserialization, or other flaws in the API or export paths.
- Secrets handling and configuration mistakes **documented in this repo** (e.g. accidental logging of credentials).
- **Dependency** vulnerabilities affecting the shipped application when upgraded through normal means (you may also use [Dependabot](https://github.com/carlosevp/SAFeDevOps/security/dependabot) / advisories on the Security tab).

## Out of scope (examples)

- **Social engineering** or physical attacks.
- **Rate limiting** or denial-of-service issues without a clear, practical impact on this small pilot app.
- Findings that require **already-compromised** admin credentials or impossible user interaction, with no practical path for typical deployments.
- **Third-party services** (e.g. OpenAI, hosting provider); please report those to the respective vendor, though you may still notify us if our integration is unsafe.

## Safe harbor

If you make a good-faith effort to follow this policy and avoid harm to users or data, we will not pursue legal action against you for research or reporting. Do not access data that is not yours, and do not disrupt production systems without explicit written permission from their owner.

---

Thank you for responsible disclosure.
