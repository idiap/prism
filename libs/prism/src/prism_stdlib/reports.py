# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-License-Identifier: MIT

"""Typed report normalization and structural validation, independent of renderers."""

from typing import cast

from prism.language.core import RecordValue


class ReportValidationError(ValueError):
    """Invalid report data, with a path identifying the offending value."""


def fail(path: str, message: str):
    raise ReportValidationError(f"{path}: {message}")


def fields(value, required, path):
    if not isinstance(value, dict) or set(value) != set(required):
        fail(path, f"expected fields {sorted(required)}")


def string(value, path, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        fail(path, "expected nonempty string" if nonempty else "expected string")


def sequence(value, path):
    if not isinstance(value, list):
        fail(path, "expected ordered list")


def _record(value, path):
    if not isinstance(value, RecordValue):
        fail(path, "expected named PRISM record or variant")
    return value.type_name.rsplit(".", 1)[-1], dict(value.fields)


def _normalize(value, path):
    if isinstance(value, list):
        return [_normalize(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if not isinstance(value, RecordValue):
        return value
    name, data = _record(value, path)
    kinds = {
        "Markdown": "markdown",
        "Html": "html",
        "Image": "image",
        "Tabs": "tabs",
        "MarkdownSlot": "markdown",
        "HtmlSlot": "html",
        "ImageSlot": "image",
        "TabsSlot": "tabs",
        "Tab": "tab",
        "TemplateTab": "tab",
    }
    if name == "NoTemplate":
        fields(data, (), path)
        return None
    if name == "WithTemplate":
        fields(data, ("snapshot",), path)
        return _normalize(data["snapshot"], path)
    if name not in {*kinds, "Report", "Template"}:
        fail(path, f"unknown report type {name!r}")
    normalized = {key: _normalize(item, f"{path}.{key}") for key, item in data.items()}
    if name in kinds:
        normalized["kind"] = kinds[name]
    return normalized


def report_data(value: RecordValue) -> dict:
    """Validate a executed PRISM Report before exporting any content."""
    name, _ = _record(value, "report")
    if name != "Report":
        fail("report", "expected Report")
    data = cast(dict, _normalize(value, "report"))
    validate_report(data)
    return data


def _section_fields(kind, template):
    required = {"id", "kind"}
    if kind == "tabs":
        required.add("tabs")
    elif kind == "tab":
        required.add("sections")
        if not template:
            required.add("label")
    elif not template:
        required.update({"attachment", "alt"} if kind == "image" else {"text"})
    return required


def _tree(nodes, path, seen, *, template=False, tabs=False):
    sequence(nodes, path)
    if tabs and not nodes:
        fail(path, "empty tab group")
    shape = []
    for index, node in enumerate(nodes):
        here = f"{path}[{index}]"
        if not isinstance(node, dict):
            fail(here, "expected section object")
        kind = node.get("kind")
        allowed = {"tab"} if tabs else {"markdown", "html", "image", "tabs"}
        if not isinstance(kind, str) or kind not in allowed:
            fail(here + ".kind", "unknown section kind")
        required = _section_fields(kind, template)
        fields(node, required, here)
        identity = node["id"]
        string(identity, here + ".id", nonempty=True)
        if identity in seen:
            fail(here + ".id", f"duplicate ID {identity!r}")
        seen.add(identity)
        for key in required - {"kind", "id", "tabs", "sections"}:
            string(node[key], here + "." + key, nonempty=key == "attachment")
        children = []
        if kind in {"tabs", "tab"}:
            key = "tabs" if kind == "tabs" else "sections"
            children = _tree(
                node[key],
                here + "." + key,
                seen,
                template=template,
                tabs=kind == "tabs",
            )
        shape.append((identity, kind, children))
    return shape


def _match(actual, expected, path):
    if len(actual) != len(expected):
        fail(path, "template section count mismatch")
    for index, (a, e) in enumerate(zip(actual, expected)):
        here = f"{path}[{index}]"
        if a[:2] != e[:2]:
            fail(here, "template ID/kind/order mismatch")
        _match(a[2], e[2], here + (".tabs" if a[1] == "tabs" else ".sections"))


def validate_report(data: dict) -> None:
    """Validate the portable tree; templates match IDs, kinds, order and nesting."""
    fields(data, {"id", "title", "sections", "template"}, "report")
    string(data["id"], "report.id", nonempty=True)
    string(data["title"], "report.title")
    shape = _tree(data["sections"], "report.sections", set())
    template = data["template"]
    if template is not None:
        fields(template, {"id", "title", "sections"}, "report.template")
        string(template["id"], "report.template.id", nonempty=True)
        string(template["title"], "report.template.title")
        expected = _tree(
            template["sections"], "report.template.sections", set(), template=True
        )
        _match(shape, expected, "report.sections")
