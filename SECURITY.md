English | [简体中文](SECURITY.zh-CN.md)

# Security reporting

MathCoffee is an early alpha. Maintainers focus on the latest published alpha and the default
branch; there is no long-term support or guaranteed response-time policy yet.

If the repository's [private vulnerability reporting page](https://github.com/sdt201909/MathCoffee/security/advisories/new)
is available, use it to report a vulnerability privately. If it is unavailable, use the contact
options on the [maintainer's profile](https://github.com/sdt201909) to arrange a private channel.
Do not put exploit details, credentials, private narration or production assets into a public issue.

A useful report includes the affected version or commit, operating system and architecture,
a minimal synthetic reproduction, expected impact and any workaround. Redact personal paths,
secrets, model tokens and private project content. Share only files you have permission to provide.

The framework invokes local tools and may execute user-authored scene modules. Treat untrusted
projects, plugins, shell commands and assets as code or data requiring review; a successful package
hash check does not establish that a contributed scene is safe to execute. Keep plugin installations,
runtimes, model caches and user productions separate. Never grant a repair workflow permission to
wipe a user's media library.

Ordinary installation errors and feature requests belong in the public issue templates after
sensitive information has been removed. See [contributing](CONTRIBUTING.md).
