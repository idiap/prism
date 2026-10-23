# Typed field report

`main.prism` returns a report with an immutable structural template.
`no_template.prism` returns the same section tree without a template.
`content.prism` authors all content with `prism.reporting.report` types: Markdown,
HTML, an attachment image, two outer tabs, and two nested tabs.

The notebook observation is asserted evidence; `describe` deterministically
formats it. Neither computation, rendering, import, nor structural validation
promotes the observation to a proved claim. Every section and tab retains its
actual field/item reference and recorded upstream production activities.

From the PRISM repository:

```sh
uv sync --all-packages
uv run prism check examples/language/typed_reports/main.prism
uv run prism compile examples/language/typed_reports/main.prism
uv run prism run examples/language/typed_reports/main.prism --handler fake
uv run prism run examples/language/typed_reports/no_template.prism --handler fake
uv run pytest -n0 tests/test_typed_reports.py
```

Annotate mixed variant values as `r.Section` or `r.TemplateSection` before
assembling their lists. The compiler checks typed payloads. After execution,
`prism_stdlib.reports.report_data(output.result)` checks structure: IDs must be
unique across sections and tabs, tab groups must be nonempty, and an optional
template must match IDs, kinds, order, and nesting exactly. Tab labels and leaf
content can vary. Templates have their own identity/title and contain no content.

Use `prism_stdlib.report_codec.export_report(output, attachments={"figure":
image_bytes})` to produce the version `"1"` JSON contract. It validates structure,
binds content/assets/template to SHA-256 digests, preserves the native result,
graph and assurance trace, and projects execution-scoped PROV-JSON identities.
`decode_report(payload, attachments={"figure": image_bytes})` validates the
transported contract and actual attachment bytes. Without the optional bytes,
it validates declarations and digests; the package importer additionally binds
those declarations to verified archive file hashes. Digests detect corruption;
they do not authenticate an uploader's recorded execution.

## Build and upload through Lunar

Lunar-specific archive construction lives in Lunar's
`scripts/build_typed_report_package.py`, using `ArchiveBuilder`. It executes this
example through Lunar's installed PRISM packages, includes all source files and
the image, and writes the exact export into `metadata.typed_report`, the template
into `template_snapshot`, and the native/projection JSON into package files.
It does not import Python modules from the sibling PRISM checkout.

From the sibling `lunar-platform` repository:

```sh
uv sync --group mcp-backend
uv run --group mcp-backend python scripts/build_typed_report_package.py \
  --example ../prism/examples/language/typed_reports \
  --output /tmp/typed-field-report.zip
uv run --group mcp-backend python scripts/build_typed_report_package.py \
  --example ../prism/examples/language/typed_reports \
  --without-template --output /tmp/typed-field-report-no-template.zip
```

Destinations must not already exist. The installed PRISM revision is declared
in Lunar's `pyproject.toml` and `uv.lock`. This implementation uses an explicitly
authorized local Git URL; move that URL to an accessible repository when sharing
with another machine, retaining an installable commit pin.

Sign in to Lunar, select **Package ZIP**, and choose the ZIP. Wait for
**Package imported**, open **Reports**, and open **Typed field report**. Select
**Details**, then **Figure** or **Method**. Each section and tab has a provenance
link; **Back** from provenance restores its containing tabs. Images come from
authenticated package-file URLs. HTML is isolated in a sandbox with no scripts
or remote resources. Imported typed reports are read-only.

Automated upload acceptance, from Lunar, uses an isolated PostgreSQL database
whose name ends in `_e2e_test` and installed Playwright Chromium or local Chrome:

```sh
LUNAR_E2E_DATABASE_URL=postgresql://USER@HOST/lunar_typed_e2e_test \
uv run --group mcp-backend pytest --run-e2e -m e2e tests/e2e/test_typed_report_upload.py
```

The test resets that disposable database, uploads both actual examples, checks
all section/tab provenance routes and loaded images, and rejects a structurally
mismatched package. It requires no model provider or worker image.
