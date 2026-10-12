# Security policy

StrainScope runs online at [strainscope.streamlit.app](https://strainscope.streamlit.app), and anyone can run it on their own computer or connect an AI assistant app to it. If you find a way to make it do something it promises not to do, please tell me privately first, so it can be fixed before others read about it.

## What counts

- a way around the SQL guards: changing the database, reading or writing files, or a query that never stops (the guards are in [`docs/03-harmonization-qc.md`](docs/03-harmonization-qc.md) and [`docs/07-app.md`](docs/07-app.md));
- a way to make an MCP tool change something, or to make one return more than it says ([`docs/08b-mcp-server.md`](docs/08b-mcp-server.md));
- a way to make a language model see data it shouldn't, or the online copy go past its daily cap ([`docs/08-deployment-ai.md`](docs/08-deployment-ai.md));
- an uploaded file that ends up stored, or that runs code;
- a key, a password or a personal path that made it into the repository despite the safety gate.

The data in StrainScope is simulated, and the app keeps no record of its visitors, so there's no personal data to leak. A mistake in a result or a guide is welcome as an ordinary issue.

## How to report

Use GitHub's private reporting: on the repository's page open **Security**, then **Advisories**, then **Report a vulnerability** ([the direct link](https://github.com/akannan2987/strainscope/security/advisories/new)). Only you and the maintainer see it. Please don't open a public issue for these.

Say what you did, what happened, and which version (the app's *About this copy* page shows it). I'll answer in the report, and once it's fixed, the fix is listed in [`CHANGELOG.md`](CHANGELOG.md).

## Which versions get fixes

The latest release (see [`CHANGELOG.md`](CHANGELOG.md)) and `master`, which is what the online copy runs. Older tags stay as they are.
