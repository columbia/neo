# NEO: Detecting Privilege Escalation in Polyglot Microservices via Agentic Program Analysis

NEO detects privilege-escalation vulnerabilities in microservice applications:
places where a request can reach a privileged operation (changing a role,
writing a record, running a command) without an adequate authentication or
authorization check. Because a request may cross several services in different
languages, and because whether a check suffices is a semantic question, NEO
pairs CodeQL with an LLM. CodeQL builds per-service data-flow and call graphs
and stitches them into end-to-end paths from a user-facing entry point to a
privileged sink in another service; an LLM agent then inspects each path to
confirm the operation, locate the checks along it, and judge whether they hold,
and a constraint solver discards infeasible paths.

## Setup

```bash
git clone <this-repo> neo && cd neo
scripts/setup.sh                 # Python deps + CodeQL standard library + src/.env
scripts/setup.sh --codebases     # also fetch the upstream evaluation apps (large)
```

Then edit `src/.env`: set `CODEQL_BIN`, and either an API key
(`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / Vertex AI) or `NEO_LLM_PROVIDER` to a
local agent CLI (`claude_cli`, `agy_cli`, `gemini_cli`; no API key needed). All
variables are documented in `src/.env.example`.

## Usage

Single application: sources at `codebases/<app>/`, a CodeQL database at
`databases/<app>/`:

```bash
codeql database create databases/<app> --language=<java|go|cpp|python|csharp|javascript> \
  --source-root=codebases/<app> [--command="<build>"] --overwrite

cd src && python3 main.py --app <app> --agent --find-sinks --find-flows --validate-flows
```

Stages (`--agent`, `--find-sinks`, `--find-flows`, `--global-flows`,
`--validate-flows`) can also be run individually; each writes a marker to
`status/`, and `--cleanrun` resets. Results:
`<workdir>/validation/vulnerabilities.json` and `validation_summary.json`.

Polyglot application: list the services in a manifest
(`codebases/<name>/neo.services.yaml`):

```yaml
name: shop
services:
  - {name: gateway, app: shop-gateway, role: gateway, aliases: ["localhost:8080"]}
  - {name: orders,  app: shop-orders,  role: internal, aliases: ["orders-svc:9000"]}
```

Analyse each service, then stitch and validate across them:

```bash
python3 main.py --app shop-gateway --find-sinks --find-flows
python3 main.py --app shop-orders  --find-sinks --find-flows
python3 main.py --app codebases/shop/neo.services.yaml --global-flows
python3 main.py --app codebases/shop/neo.services.yaml --validate-flows
```

`--global-flows` accepts `--no-codeql` for a heuristic fallback; on a manifest,
`--validate-flows` automatically targets the stitched flows.

Offline demo (no CodeQL, no LLM): `python3 examples/run_demo.py`.

## Tests

```bash
pytest tests/     # ~95 tests, fully offline
```

## Authors

Neo was developed by [Penghui Li](https://github.com/peng-hui) and
[Hong Yau Chong](https://github.com/Labcoxyzl) at Columbia University.

## Citation

The paper appears at IEEE S&P 2026:
<https://ieeexplore.ieee.org/document/11573425>

```bibtex
@inproceedings{sp26:neo,
  title     = {Detecting Privilege Escalation in Polyglot Microservices via Agentic Program Analysis},
  author    = {Penghui Li and Hong Yau Chong and Yinzhi Cao and Junfeng Yang},
  booktitle = {Proceedings of the 47th IEEE Symposium on Security and Privacy (S\&P)},
  year      = {2026},
  month     = may,
}
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
