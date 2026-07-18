# Security policy

## Supported versions

Security fixes are applied to the current `main` branch and the latest tagged
beta source version. Older untagged snapshots are not supported.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository: open the
repository's **Security** tab, choose **Advisories**, and select **Report a
vulnerability**. Do not place API keys, private scripts, project archives,
generated images, local paths, or exploit details in a public issue.

If private vulnerability reporting is not yet enabled, contact the repository
owner through their profile and request a private reporting channel before
sharing technical details.

Include the affected commit, Windows version, reproduction steps, expected
impact, and whether the issue can expose local project data or API credentials.

## Local-first security boundary

Paneloom stores projects locally. Cloud model providers receive data only when
the user explicitly invokes an AI operation. Reports involving a third-party
provider should identify the provider without including credentials.
