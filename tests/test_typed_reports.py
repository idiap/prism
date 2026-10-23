# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-License-Identifier: MIT

from copy import deepcopy
from pathlib import Path

import pytest
from prism.language import check, compile, elaborate, parse_source
from prism.language.developer.diagnostics import PrismTypeError
from prism.runtime import FakeEffectHandler, run
from prism.sdk.workspace import WorkspaceModuleLoader
from prism_stdlib.reports import ReportValidationError, report_data, validate_report

ROOT = Path(__file__).resolve().parents[1]
SOURCE = """import prism.reporting.report as r

def main() -> r.Report:
    leaf: r.Section = r.Markdown(id="markdown", text="same text")
    html: r.Section = r.Html(id="html", text="<p>HTML</p>")
    image: r.Section = r.Image(id="image", attachment="figure", alt="A figure")
    nested: r.Section = r.Tabs(id="nested", tabs=[r.Tab(id="inner", label="Inner", sections=[image])])
    sections: List[r.Section] = [r.Tabs(id="outer", tabs=[r.Tab(id="first", label="First", sections=[leaf]), r.Tab(id="second", label="Second", sections=[html, nested])])]
    html_slot: r.TemplateSection = r.HtmlSlot(id="html")
    nested_slot: r.TemplateSection = r.TabsSlot(id="nested", tabs=[r.TemplateTab(id="inner", sections=[r.ImageSlot(id="image")])])
    slots: List[r.TemplateSection] = [r.TabsSlot(id="outer", tabs=[r.TemplateTab(id="first", sections=[r.MarkdownSlot(id="markdown")]), r.TemplateTab(id="second", sections=[html_slot, nested_slot])])]
    template = r.WithTemplate(snapshot=r.Template(id="layout", title="Layout", sections=slots))
    return r.Report(id="sample", title="Sample", sections=sections, template=template)
"""


def execute(source=SOURCE, *, project_root=ROOT):
    checked = check(
        parse_source(source),
        module_loader=WorkspaceModuleLoader(project_root=project_root),
    )
    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())
    assert output.status == "accepted", output.diagnostics
    return output


@pytest.mark.parametrize("template", [True, False])
def test_recursive_sections_compile_and_execute(template, tmp_path):
    source = (
        SOURCE
        if template
        else SOURCE.replace("template=template", "template=r.NoTemplate()")
    )
    data = report_data(execute(source, project_root=tmp_path).result)
    assert (data["template"] is not None) == template
    assert (
        data["sections"][0]["tabs"][1]["sections"][1]["tabs"][0]["sections"][0]["kind"]
        == "image"
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ('text="same text"', "text=42"),
        ('attachment="figure"', "attachment=42"),
        ('label="Inner"', "label=True"),
        ("tabs=[r.Tab", "tabs=[r.Markdown"),
    ],
)
def test_wrong_payload_fails_checking(old, new):
    with pytest.raises(PrismTypeError):
        execute(SOURCE.replace(old, new))


@pytest.fixture
def report():
    return report_data(execute().result)


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "kind",
        "payload",
        "empty",
        "id",
        "order",
        "nesting",
        "template_duplicate",
    ],
)
def test_structure_errors_have_paths(report, case):
    outer = report["sections"][0]
    children = outer["tabs"][1]["sections"]
    if case == "duplicate":
        children[0]["id"] = "outer"
    elif case == "kind":
        children[0]["kind"] = "video"
    elif case == "payload":
        children[0]["text"] = 17
    elif case == "empty":
        outer["tabs"] = []
    elif case == "id":
        children[0]["id"] = "renamed"
    elif case == "order":
        outer["tabs"].reverse()
    elif case == "nesting":
        children.append(children.pop()["tabs"][0]["sections"][0])
    else:
        report["template"]["sections"].append(
            deepcopy(report["template"]["sections"][0])
        )
    with pytest.raises(ReportValidationError, match=r"report\.(sections|template).*\["):
        validate_report(report)


def test_template_kind_mismatch(report):
    report["template"]["sections"][0]["tabs"][0]["sections"][0]["kind"] = "html"
    with pytest.raises(ReportValidationError, match="template ID/kind/order mismatch"):
        validate_report(report)


def artifact(source=SOURCE):
    from prism_stdlib.report_codec import export_report

    return export_report(execute(source), attachments={"figure": b"image bytes"})


def test_codec_roundtrip():
    import json

    from prism_stdlib.report_codec import decode_report, inventory

    for source in (
        SOURCE,
        SOURCE.replace("template=template", "template=r.NoTemplate()"),
    ):
        payload = json.loads(json.dumps(artifact(source)))
        report = decode_report(payload, attachments={"figure": b"image bytes"})
        assert report == report_data(execute(source).result)
        assert len(payload["sections"]) == len(list(inventory(report))) == 8
        assert all(
            item["entity"] in payload["provenance"]["entity"]
            for item in payload["sections"].values()
        )


@pytest.mark.parametrize(
    "case",
    [
        "version",
        "trace_version",
        "content",
        "template",
        "dangling",
        "missing_child",
        "mapping",
        "section_digest",
        "asset",
        "projection",
        "digest",
        "duplicate_id",
    ],
)
def test_codec_rejects_tampering(case):
    from prism_stdlib.report_codec import decode_report

    payload = artifact()
    targets = {
        "version": (payload, "version", "2"),
        "trace_version": (payload["native"], "trace_version", "0"),
        "content": (payload["report"], "title", "altered"),
        "template": (payload["report"]["template"], "title", "altered"),
        "dangling": (payload["native"]["graph"]["values"][0], "activity", "missing"),
        "missing_child": (payload["native"]["graph"]["values"][-1], "children", []),
        "mapping": (payload["sections"], "markdown", payload["sections"]["html"]),
        "section_digest": (
            payload["sections"]["markdown"],
            "digest",
            "sha256:" + "0" * 64,
        ),
        "asset": (payload, "attachments", {}),
        "projection": (payload["provenance"], "entity", {}),
        "duplicate_id": (
            payload["report"],
            "sections",
            payload["report"]["sections"] * 2,
        ),
        "digest": (payload, "digest", "sha256:" + "0" * 64),
    }
    target, key, value = targets[case]
    target[key] = value
    with pytest.raises(ReportValidationError, match=": "):
        decode_report(payload)


def test_codec_verifies_actual_attachment_bytes():
    from prism_stdlib.report_codec import decode_report

    with pytest.raises(ReportValidationError, match="attachments.figure"):
        decode_report(artifact(), attachments={"figure": b"altered"})


def test_codec_scopes_independent_runs():
    first, second = artifact(), artifact()
    for collection in (
        "entity",
        "activity",
        "wasGeneratedBy",
        "wasDerivedFrom",
        "used",
    ):
        assert set(first["provenance"][collection]).isdisjoint(
            second["provenance"][collection]
        )


def test_codec_retains_distinct_producers_and_ancestry():
    from prism_stdlib.report_codec import export_report

    source = (
        SOURCE.replace(
            "def main()",
            """def identity(value: String) -> String:
    return value

def main()""",
        )
        .replace(
            "    leaf: r.Section",
            """    assertion = observe("same text", source="author")
    computation = compute(assertion.value, procedure=identity)
    leaf: r.Section""",
        )
        .replace('text="same text"', "text=computation.value")
        .replace('text="<p>HTML</p>"', 'text="same text"')
    )
    output = execute(source)
    payload = export_report(output, attachments={"figure": b"image"})
    graph = payload["native"]["graph"]
    values = {v["identity"]: v for v in graph["values"]}
    activities = {v["identity"]: v for v in graph["activities"]}

    def ancestry(reference):
        seen, pending = set(), [reference]
        while pending:
            ref = pending.pop()
            if ref in seen:
                continue
            seen.add(ref)
            value = values[ref]
            pending.extend(activities[value["activity"]]["inputs"])
            pending.extend(value["dependencies"])
            pending.extend(child for _, child in value["children"])
        return {activities[values[ref]["activity"]]["kind"] for ref in seen}

    markdown = payload["sections"]["markdown"]["reference"]
    html = payload["sections"]["html"]["reference"]
    assert markdown != html
    assert {"asserted", "computed"} <= ancestry(markdown)
    assert "asserted" not in ancestry(html)
    assert "asserted" in ancestry(payload["sections"]["outer"]["reference"])
    from prism.runtime.replay import jsonable

    assert payload["native"]["trace"] == jsonable(output.trace)
    assert all(
        "assurance" not in attrs for attrs in payload["provenance"]["entity"].values()
    )


@pytest.mark.parametrize("origin", ["imported", "generated"])
def test_codec_does_not_strengthen_recorded_origin(origin):
    from dataclasses import replace

    from prism_stdlib.report_codec import decode_report, export_report

    output = execute()
    graph = output.provenance
    assert graph is not None
    output.provenance = replace(
        graph, activities=tuple(replace(a, kind=origin) for a in graph.activities)
    )
    payload = export_report(output, attachments={"figure": b"image"})
    decode_report(payload)
    assert {a["prism:origin"] for a in payload["provenance"]["activity"].values()} == {
        origin
    }
    assert all("assurance" not in a for a in payload["provenance"]["entity"].values())


@pytest.mark.parametrize("entry", ["main.prism", "no_template.prism"])
def test_runnable_report_example(entry):
    from prism_stdlib.report_codec import decode_report, export_report

    directory = ROOT / "examples/language/typed_reports"
    output = execute((directory / entry).read_text(), project_root=directory)
    attachments = {"figure": (directory / "figure.svg").read_bytes()}
    payload = export_report(output, attachments=attachments)
    report = decode_report(payload, attachments=attachments)
    assert (report["template"] is not None) == (entry == "main.prism")
    assert len(payload["sections"]) == 10
    assert {"asserted", "computed"} <= {
        a["kind"] for a in payload["native"]["graph"]["activities"]
    }
