# Run a field survey report in Lunar

This package contains source and a registered workflow, not a saved report.
The editable `observation` input becomes an asserted notebook observation.
PRISM computes the formatted narrative and returns a typed `Report` with two
Markdown sections and a structural template. No model or network is used.

From the sibling `lunar-platform` checkout:

```sh
uv run --group mcp-backend python scripts/build_typed_report_run_package.py \
  --example ../prism/examples/language/typed_report_run \
  --output /tmp/field-survey-run.zip
```

In Lunar:

1. Import `/tmp/field-survey-run.zip` using **Import ZIP**.
2. Click **Prepare runtime** and wait for **Runtime: ready**.
3. Open **Prism**, select **Field survey report**, and click **Run**.
4. Enter a field observation and run it. Wait for **completed**.
5. Open the report: the observation and method are typed Markdown sections.
   The structural template is shown above them; the executed PRISM source is
   available under **Source files** and in **Repository**.
6. Click the observation section's **Provenance** link. Inspect its native value,
   recorded execution, computation and assertion ancestry. Click graph nodes
   for details; download PROV-JSON or JSON-LD. Back returns to the same section.

The run also retains `typed-report.json` as a downloadable artifact, with
native result, graph, assurance trace, section mappings and integrity digests.
The host validates the typed report before publishing the successful result.
Provenance records how the notebook text was used; it does not establish that
the observation is true.

For this local Git dependency setup, rebuild the application images from Lunar:

```sh
python3 scripts/build_local_prism_images.py --target worker
python3 scripts/build_local_prism_images.py --target backend
docker build -t lunar-frontend:local app/frontend
# With the existing app environment and storage path:
docker compose -f app/docker-compose.yml up -d --no-build --no-deps backend frontend
```

The helper supplies the declared local Git repository to Docker so `uv.lock`
can resolve the pinned revision. It does not push or publish code.

Automated acceptance (use only a disposable database ending `_e2e_test`):

```sh
LUNAR_WORKER_IMAGE=lunar-worker:local \
LUNAR_E2E_DATABASE_URL=postgresql://.../lunar_typed_e2e_test \
uv run --group mcp-backend pytest --run-e2e -m e2e tests/e2e/test_typed_report_run.py
```

This test uses the actual ZIP import, PostgreSQL, Docker worker, browser, report
renderer and provenance APIs, including edited input, exact native ancestry,
source display, reload and both standards exports.

## Visualization and package validation

The executable `field_survey` workflow declares three real steps:
`read_notebook` → `format_observation` → `assemble_report`. `main` solves that
workflow. The package builder compiles this source and projects its checked
occurrence types, dependencies and source spans into the declared viewer bundle.
Concrete examples include an actual deterministic sample execution.

After import, the **Prism** section provides **Project atlas**, **Workflow graph**,
**Prism files**, **Input examples**, and **Run**. The report and per-section
provenance remain available after exporting and re-importing the package.
Slide decks are optional presentation assets; this example does not include one.

Lunar's shared package validator requires a source-bound visualization bundle
for every registered PRISM workflow. A missing workflow, invalid graph, stale
source, omitted packaged source, broken edge or invalid source span prevents
both import and export publication. Report-only archives without registered
workflows do not acquire an execution-visualization requirement.
