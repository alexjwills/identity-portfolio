# Identity portfolio: Okta, Entra ID and AWS

Eleven hands-on identity builds, done in an Okta Integrator free trial tenant, with a Microsoft Entra ID tenant for the federation work and an AWS account for the cloud work. I had full admin rights in all three, so I could build each scenario, break it, work out why and put it right.

They were all built through the admin consoles and Okta Workflows rather than as code, apart from one Python script, so this repository is mostly the write-up: what each build does, how I set it up, what went wrong along the way, and why the pattern matters in an organisation. My later projects build the same ideas as code. See [Where this led](#where-this-led).

## Scope

This is lab work in sandboxed free trial tenants, with test users and mock applications. It shows that I understand how these controls fit together and can configure them end to end. It isn't production experience, and I haven't run any of it for real users.

## What's covered

| Area | Projects |
| --- | --- |
| Authentication protocols: OIDC, OAuth 2.0, SAML 2.0, SCIM 2.0 | 1, 2, 6 |
| Joiner, mover and leaver lifecycle | 2, 5, 6 |
| Privileged access and zero standing privileges | 9 |
| Identity threat detection and response, non-human identities | 10 |
| Identity governance: access certifications, self-service requests, approvals | 4, 8 |
| Role and attribute based access control | 1, 2, 5, 6 |
| Zero trust and context-aware authentication | 3 |
| Automation: Python, Okta Workflows, REST APIs | 7, 9, 10 |
| Cross-vendor federation and troubleshooting (Entra ID and Okta) | 6 |
| Federation into cloud infrastructure (AWS IAM, `AssumeRoleWithSAML`) | 11 |

The projects are numbered in the order I built them. Below they're grouped by theme.

## Privileged access and threat response

### Project 9: Zero standing privileges with Okta Workflows

**Goal:** give access to a high-risk application only for a set window, then take it away automatically, with no manual offboarding step.

- Authorised the Okta Workflows engine against the tenant with OAuth 2.0 client credentials, so it could change group membership through the API.
- Built a flow triggered by **User Added to Group** on a scoped entitlement group, `App-Mock-Finance-SPA-ReadOnly-JIT`, which grants read-only access to a mock finance application.
- Added a **Continue If** check on the group ID, so the flow only runs for that group and not for every group change in the tenant.
- Added a **Wait For** timer followed by a **Remove User from Group** call, which removes access as soon as the window closes.
- Turned on flow logging, so every grant and removal is recorded.

**Why it matters:** nobody holds access to the sensitive application between uses, so there's nothing to forget to remove and less for an attacker or an insider to misuse. The flow log gives a record of who had access and when, without anyone maintaining it by hand.

### Project 10: Identity threat detection and response

**Goal:** detect a security signal on an account and contain it within seconds, including revoking the tokens that applications and services hold for that identity.

- Gave the automation its own identity: an OAuth 2.0 client credentials service app with admin API rights, separate from any human admin account.
- **Detection flow:** listens for **Suspicious Activity Reported** and **User Locked Out**, and adds the affected user to a `Trigger-Security-Quarantine` group.
- **Remediation flow:** a separate flow triggered by that group membership, with a **Continue If** check that it's the quarantine group. It clears the user's sessions, revoking session cookies and OAuth access and refresh tokens across connected applications, then sets the account to **Suspended**.
- Logged the user ID, IP context, triggering event and action taken for each run.

**Why it matters:** an attacker who has stolen a session or token can carry on even after a password reset. Revoking tokens and suspending the account closes that gap in seconds rather than waiting for someone to act. Keeping detection and remediation as two flows means each can be tested and changed on its own.

## Lifecycle and governance

### Project 2: Automated provisioning with SCIM

**Goal:** replace ticket-based provisioning with an automated joiner, mover and leaver process driven by user attributes.

- Set up SCIM 2.0 provisioning, the HTTP and JSON standard an identity provider uses to create, update and remove accounts in other applications (`POST` to create, `PATCH` or `PUT` to update, `DELETE` or deactivate to remove).
- Built dynamic group rules on the `department` attribute, so changing a user's department re-evaluates their groups and access straight away. That's the mover step.
- Used a long-lived OAuth bearer token for the system-to-system connection between Okta and the application's SCIM API. That's a different thing from the OIDC tokens users get when they sign in, and I wanted to be clear on the difference.

**Why it matters:** the leaver step is where manual processes fail most often. With SCIM, removing someone in the identity provider removes them from the connected applications too, with no delay and no CSV imports.

### Project 5: End-to-end joiner, mover and leaver with RBAC

**Goal:** prove that one change to a user's department moves all of their access with it, with no manual steps.

- Used `department` on the user profile as the single source of truth, evaluated continuously by Okta's group rules.
- When `user.department == "Finance"`, the user is added to the Finance group, its security group and the Finance application. Changing it to `Engineering` removes all of that and grants the Engineering equivalents in the same step.
- Tested the full round trip on a test user: the Finance application tile disappeared from their dashboard and the Engineering one appeared, with nothing done by hand.

**Why it matters:** access follows the role, so people don't build up permissions from every job they've had. Because access comes from groups rather than individual assignments, it's also easy to report on who has what.

### Project 4: Device trust and access certifications

**Goal:** check the device as well as the person at sign-in, and review access regularly so permissions that are no longer needed get removed.

- Built app sign-in policies with network and device conditions that have to be met before a token is issued.
- Created iOS device assurance policies (minimum OS version, passcode required) as separate policies from the app rules, so device requirements can change without editing every application's policy.
- Enforced Okta FastPass, a phishing-resistant factor using the device's biometrics, with re-authentication every two hours.
- Set up a recurring access certification campaign, where resource owners and managers review access and stale permissions are removed.

**Why it matters:** access granted once and never checked again drifts out of date. Regular reviews keep it current, and they're the kind of evidence frameworks such as ISO 27001 and SOC 2 ask for.

### Project 8: Self-service access requests

**Goal:** give someone outside a department, such as a risk and compliance auditor, a controlled way to request temporary access to a sensitive application, instead of a permanent grant or an informal favour.

- Created the scoped entitlement group `App-Mock-Finance-SPA-ReadOnly-JIT`, bound to the mock finance application's OIDC sign-in.
- Turned on Okta self-service access requests, with a required business justification and approval by a named application owner.
- Tested the whole path with a test user in the risk and compliance department: request, approval in the admin console, and the application tile appearing on their dashboard.

**Why it matters:** every grant has a reason, an approver and a record. Combined with Project 9, which uses the same group, approved access also ends on its own.

## Authentication, zero trust and federation

### Project 3: Context-aware MFA

**Goal:** make the strength of sign-in depend on where the request comes from, rather than treating every login the same.

- Created an IP-based network zone, `Mock-Corp-Trusted-Network`, standing in for a corporate network.
- Built a sign-in policy with two rules in priority order: from outside the zone, a phishing-resistant MFA challenge; from inside it, password only.
- Tested both paths with the OIDC Debugger, including a simulated sign-in from Belgium, outside the trusted zone.

**Why it matters:** a stolen password on its own isn't enough from an unfamiliar network, while people on the trusted network aren't slowed down by prompts on every sign-in.

### Project 1: OIDC sign-in for a single-page application

**Goal:** add secure sign-in to a single-page application without putting a client secret in front-end code.

- Used OpenID Connect with the OAuth 2.0 authorisation code flow and PKCE, the standard pattern for public clients that can't keep a secret.
- Mapped a test user's department to a security group and assigned that group to the application.
- Added an authentication policy requiring MFA, and an authorisation server access policy that only allows this application's client ID.

**Why it matters:** PKCE protects against an intercepted authorisation code being swapped for tokens. Everything else in this portfolio builds on these standards.

### Project 6: Entra ID to Okta federation with just-in-time accounts

**Goal:** federate Microsoft Entra ID, as the main identity provider, with Okta, as the service provider, over SAML 2.0, creating Okta accounts on first sign-in.

- In Entra ID, created a test user with a custom department attribute, a dynamic group based on it, and a security group assigned to the Okta enterprise application, so only matching users can use it.
- Configured Okta as the service provider with just-in-time account creation, and mapped the SAML claims (user principal name, email, given name, surname) to the Okta profile.

**Why it matters:** many organisations run two identity providers while they migrate from one to the other, and the integration between them is where things break. Most of the value here was in the debugging below.

#### Findings

**Accounts weren't being created.** Sign-ins failed with a just-in-time error. The Okta System Log showed a Name ID format mismatch: Okta was set to require a persistent Name ID, while Entra ID was sending the user principal name under a strict "Email address" format, and the assertion was being dropped. I turned off the persistent Name ID requirement in Okta and changed Entra ID's Name ID format to "Unspecified", so the raw user principal name came through.

**The login field was empty.** The next error was "login field failed validation with value 'null'". Okta was mapping the SAML subject to the login field, and because of the format problem above, the value arrived empty. The Name ID fix solved this one too.

**A mapping pointed at an attribute that didn't exist.** The last error was "Unknown Profile Attribute". The mapping referred to `userprincipalname`, which isn't defined in Okta's identity provider profile. I pointed the mappings at Okta's built-in attributes, `appuser.userName` and `appuser.email`, and set the username to come from `idpuser.userName`. After that, accounts were created on first sign-in.

The pattern across all three: the claims an identity provider sends have to match what the service provider's schema expects, exactly. The useful information was in the lower-level event rows and debug data in the System Log, not in the first error shown.

## Automation

### Project 7: Dormant account report from the Okta API

**Goal:** find accounts that haven't been used for 60 days and produce a report for review, without manual portal checks or paid add-ons.

- Created a dedicated API token for the script, named `Last-Logon-Audit-Script-Token` so its activity is easy to find in the System Log. Okta API calls use the header `Authorization: SSWS <token>`.
- Called `GET /api/v1/users` and read the nested JSON (`profile.email`, `status`, `lastLogin`).
- Converted the ISO 8601 timestamps and flagged anyone inactive for 60 days or more, handling accounts that had never signed in (`lastLogin` is null) separately.
- Wrote the results to a CSV for managers to review.

The script is in [`scripts/dormant_users_report.py`](scripts/dormant_users_report.py). For publishing I changed it to read the Okta domain and token from the `OKTA_DOMAIN` and `OKTA_API_TOKEN` environment variables rather than from the file, and to follow Okta's pagination, since a single request returns at most 200 users. The report itself contains user emails, so `*.csv` is in `.gitignore`.

```bash
pip install requests
export OKTA_DOMAIN="https://your-org.okta.com"
export OKTA_API_TOKEN="..."
python3 scripts/dormant_users_report.py
```

**Why it matters:** dormant accounts are an easy way in for an attacker and a common audit finding. A script that produces the list on demand is cheaper and more repeatable than checking by hand.

| Response | Meaning |
| --- | --- |
| 401 Unauthorized | The token is missing, wrong or expired |
| 403 Forbidden | The token is valid but its admin role can't use that endpoint |

## Federation into cloud infrastructure

### Project 11: Okta to AWS with no standing credentials

**Goal:** sign in through Okta and land in AWS as a temporary role session, with no IAM user and no access keys anywhere.

- Created a SAML identity provider in AWS IAM from Okta's metadata, so AWS trusts assertions signed by the Okta org.
- Created an IAM role with a SAML federation trust policy and the `ReadOnlyAccess` policy, as a low-risk starting point.
- Configured Okta's AWS Account Federation app for SAML 2.0, with the identity provider ARN field set to the combined `idp-arn,role-arn` value AWS expects, so the assertion names a specific role.
- Tested as a separate end user, not the admin account that built it. The AWS console showed an assumed-role session (`arn:aws:sts::...:assumed-role/Okta-Federated-ReadOnly/...`), not an IAM user.
- Tried a write action, creating an EC2 key pair, and got an explicit `not authorized to perform: ec2:CreateKeyPair`, so the read-only policy was really being enforced.

**Why it matters:** this is a different kind of federation from Project 6. Entra ID to Okta creates a user account. Okta to AWS creates a temporary role session through `AssumeRoleWithSAML`, which expires on its own. Nobody holds long-lived AWS credentials, which is the same zero standing privileges idea as Project 9, applied to cloud infrastructure.

#### Findings and decisions

**Okta's default guide needs a stored access key.** Okta's "Amazon AWS IAM Role" setup guide uses an IAM user with long-lived access keys stored in Okta, to sync roles. I didn't use it, because it puts a standing credential back into a design meant to have none. The identity provider ARN field builds the SAML role attribute directly, with nothing stored.

**The admin account couldn't test it.** Signing in as the super admin kept going back to the Admin Console rather than an end-user dashboard. I tested from a separate end-user account instead, which is also the right way to test single sign-on: as the person who'll use it, not the account that configured it.

**Most of the advanced sign-on fields weren't needed.** The settings page has fields for other patterns (a SWA login URL, an account ID, a provisioning user). Only the identity provider ARN field matters for SAML role assumption, so I left the rest at their defaults.

## Where this led

The same ideas run through my later projects, built as code:

- [terraform-portfolio](https://github.com/alexjwills/terraform-portfolio): AWS IAM in Terraform, including attribute-based access control on S3 tags and permission boundaries.
- [abac-ecs-fargate](https://github.com/alexjwills/abac-ecs-fargate): a container on ECS Fargate reading S3 as a tagged IAM role, with no stored credentials.
- [kubernetes-portfolio](https://github.com/alexjwills/kubernetes-portfolio): the same workload on EKS with IAM Roles for Service Accounts, plus a troubleshooting lab.
- [abac-azure-container-apps](https://github.com/alexjwills/abac-azure-container-apps): the same access rule rebuilt in Azure with managed identities, deployed by GitHub Actions that sign in to Azure and AWS with OIDC instead of stored keys.

## Tools

Okta Integrator free trial (Universal Directory, group rules, authentication policies, network zones, device assurance, FastPass, self-service access requests, access certifications, Workflows, System Log, SCIM provisioning, authorisation servers), Microsoft Entra ID (dynamic groups, enterprise applications, SAML single sign-on), AWS IAM (SAML identity provider, roles, `AssumeRoleWithSAML`), OIDC Debugger, Python with the Okta REST API.
