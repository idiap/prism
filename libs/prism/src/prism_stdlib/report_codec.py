# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-License-Identifier: MIT

"""Portable recorded-execution reports. Digests are integrity checks, not trust."""

from hashlib import sha256

from prism.language.core import RecordValue
from prism.runtime.replay import content_digest, jsonable
from prism.runtime.results import TRACE_VERSION, RunOutput

from .reports import fail, fields, report_data, sequence, string, validate_report

VERSION = "1"


def attachment_digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def inventory(report):
    """Yield every section/container/tab with its native field/item path."""

    def walk(nodes, path):
        for index, node in enumerate(nodes):
            here = (*path, str(index))
            yield node, here
            key = {"tabs": "tabs", "tab": "sections"}.get(node["kind"])
            if key:
                yield from walk(node[key], (*here, key))

    yield from walk(report["sections"], ("sections",))


def _index(items, path):
    sequence(items, path)
    result = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"{path}[{index}]", "expected object")
        identity = item.get("identity")
        string(identity, f"{path}[{index}].identity", nonempty=True)
        if identity in result:
            fail(path, "duplicate graph identity")
        result[identity] = item
    return result


def _value_references(identity, value, values, activities):
    path = f"native.graph.values[{identity}]"
    fields(
        value,
        {"identity", "activity", "children", "artifact", "dependencies", "entries"},
        path,
    )
    if not isinstance(value["activity"], str) or value["activity"] not in activities:
        fail(path + ".activity", "dangling reference")
    for key in ("children", "entries", "dependencies"):
        sequence(value[key], path + "." + key)
    names = set()
    refs = list(value["dependencies"])
    for pair in value["children"]:
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            fail(path + ".children", "invalid field reference")
        if pair[0] in names:
            fail(path + ".children", "duplicate field reference")
        names.add(pair[0])
        refs.append(pair[1])
    for pair in value["entries"]:
        if not isinstance(pair, list) or len(pair) != 2:
            fail(path + ".entries", "invalid entry reference")
        refs.extend(pair)
    if any(not isinstance(ref, str) or ref not in values for ref in refs):
        fail(path, "dangling reference")


def _graph(graph):
    fields(graph, {"result", "values", "activities"}, "native.graph")
    values = _index(graph["values"], "native.graph.values")
    activities = _index(graph["activities"], "native.graph.activities")
    if not isinstance(graph["result"], str) or graph["result"] not in values:
        fail("native.graph.result", "dangling reference")
    for identity, value in values.items():
        _value_references(identity, value, values, activities)
    for identity, activity in activities.items():
        path = f"native.graph.activities[{identity}]"
        fields(
            activity,
            {
                "identity",
                "kind",
                "operation",
                "inputs",
                "implementation_hash",
                "effect_record",
                "source",
                "source_hash",
                "synthetic",
            },
            path,
        )
        sequence(activity["inputs"], path + ".inputs")
        if any(
            not isinstance(ref, str) or ref not in values for ref in activity["inputs"]
        ):
            fail(path + ".inputs", "dangling reference")
        string(activity["kind"], path + ".kind", nonempty=True)
        string(activity["operation"], path + ".operation")
    return values, activities


def _reference(values, root, path):
    reference = root
    for part in path:
        reference = dict(values[reference]["children"]).get(part)
        if reference not in values:
            fail("report." + ".".join(path), "missing native field/item reference")
    return reference


def _native(value, values, reference, path="report"):
    """Rebuild only inert report records and bind every field to its native digest."""
    if content_digest(value) != values[reference]["artifact"]:
        fail(path, "native content digest mismatch")
    if isinstance(value, dict):
        fields(value, {"type_name", "fields"}, path)
        string(value["type_name"], path + ".type_name", nonempty=True)
        if not isinstance(value["fields"], dict):
            fail(path, "invalid native fields")
        children = value["fields"]
    elif isinstance(value, list):
        children = {str(i): v for i, v in enumerate(value)}
    else:
        return value
    refs = dict(values[reference]["children"])
    if set(refs) != set(children):
        fail(path, "native field/item inventory mismatch")
    decoded = {
        key: _native(item, values, refs[key], path + "." + key)
        for key, item in children.items()
    }
    return (
        RecordValue(value["type_name"], decoded)
        if isinstance(value, dict)
        else list(decoded.values())
    )


def _entity(run_id, reference):
    # Hash the pair instead of relying on unsafe delimiter concatenation.
    return "prism:" + content_digest([run_id, reference]).split(":", 1)[1]


def _projection(run_id, values, activities):
    entity = {ref: _entity(run_id, ref) for ref in values}
    activity = {ref: _entity(run_id, ref) for ref in activities}
    document = {
        "prefix": {
            "prism": "https://idiap.ch/prism/recorded/",
            "prov": "http://www.w3.org/ns/prov#",
        },
        "entity": {},
        "activity": {},
        "wasGeneratedBy": {},
        "used": {},
        "wasDerivedFrom": {},
    }
    for ref, value in values.items():
        document["entity"][entity[ref]] = {
            "prov:label": ref,
            "prism:native_reference": ref,
            "prism:artifact": value["artifact"],
        }
        document["wasGeneratedBy"][
            _entity(run_id, f"generation:{len(document['wasGeneratedBy'])}")
        ] = {
            "prov:entity": entity[ref],
            "prov:activity": activity[value["activity"]],
        }
        upstream = [
            *value["dependencies"],
            *(r for _, r in value["children"]),
            *(r for pair in value["entries"] for r in pair),
            *activities[value["activity"]]["inputs"],
        ]
        for parent in dict.fromkeys(upstream):
            document["wasDerivedFrom"][
                _entity(run_id, f"derivation:{len(document['wasDerivedFrom'])}")
            ] = {
                "prov:generatedEntity": entity[ref],
                "prov:usedEntity": entity[parent],
            }
    for ref, value in activities.items():
        document["activity"][activity[ref]] = {
            "prov:label": value["operation"],
            "prism:origin": value["kind"],
        }
        for parent in value["inputs"]:
            document["used"][_entity(run_id, f"use:{len(document['used'])}")] = {
                "prov:activity": activity[ref],
                "prov:entity": entity[parent],
            }
    return document


def _mappings(report, graph, values, run_id):
    result = {}
    for node, path in inventory(report):
        reference = _reference(values, graph["result"], path)
        result[node["id"]] = {
            "reference": reference,
            "entity": _entity(run_id, reference),
            "digest": content_digest(node),
        }
    return result


def export_report(
    output: RunOutput, *, attachments: dict[str, bytes] | None = None
) -> dict:
    """Export a successful run, including its unchanged native graph and assurance trace."""
    if output.status != "accepted" or output.provenance is None:
        fail("run", "expected successful execution with provenance")
    report = report_data(output.result)
    graph = jsonable(output.provenance)
    values, activities = _graph(graph)
    run_id = output.metadata.get("run_id")
    string(run_id, "run.id", nonempty=True)
    assets = attachments or {}
    payload = {
        "version": VERSION,
        "report": report,
        "attachments": {key: attachment_digest(value) for key, value in assets.items()},
        "native": {
            "run_id": run_id,
            "source_hash": output.source_hash,
            "trace_version": output.trace_version,
            "trace": jsonable(output.trace),
            "result": jsonable(output.result),
            "graph": graph,
        },
        "sections": _mappings(report, graph, values, run_id),
        "provenance": _projection(run_id, values, activities),
        "template_digest": content_digest(report["template"]),
    }
    payload["digest"] = content_digest(payload)
    decode_report(payload, attachments=assets)
    return payload


def decode_report(
    payload: dict, *, attachments: dict[str, bytes] | None = None
) -> dict:
    """Validate a portable artifact; supplied attachment bytes are verified as well."""
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        fail("version", "unsupported typed report version")
    fields(
        payload,
        {
            "version",
            "report",
            "attachments",
            "native",
            "sections",
            "provenance",
            "template_digest",
            "digest",
        },
        "typed_report",
    )
    report = payload["report"]
    validate_report(report)
    native = payload["native"]
    fields(
        native,
        {"run_id", "source_hash", "trace_version", "trace", "result", "graph"},
        "native",
    )
    string(native["run_id"], "native.run_id", nonempty=True)
    if native["trace_version"] != TRACE_VERSION:
        fail("native.trace_version", "unsupported trace version")
    sequence(native["trace"], "native.trace")
    values, activities = _graph(native["graph"])
    result = _native(native["result"], values, native["graph"]["result"])
    if report_data(result) != report:
        fail("report", "content differs from native result")
    if payload["sections"] != _mappings(
        report, native["graph"], values, native["run_id"]
    ):
        fail("sections", "conflicting or missing section provenance mappings/digests")
    if payload["provenance"] != _projection(native["run_id"], values, activities):
        fail("provenance", "projection differs from native graph")
    if payload["template_digest"] != content_digest(report["template"]):
        fail("report.template", "template digest mismatch")
    _attachments(report, payload["attachments"], attachments)
    if payload["digest"] != content_digest(
        {key: value for key, value in payload.items() if key != "digest"}
    ):
        fail("typed_report.digest", "artifact digest mismatch")
    return report


def _attachments(report, assets, attachments):
    if not isinstance(assets, dict):
        fail("attachments", "expected attachment digests")
    for node, path in inventory(report):
        if node["kind"] == "image" and node["attachment"] not in assets:
            fail("report." + ".".join(path), "missing image attachment")
    for key, digest in assets.items():
        string(key, "attachments.id", nonempty=True)
        if (
            not isinstance(digest, str)
            or len(digest) != 71
            or not digest.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in digest[7:])
        ):
            fail(f"attachments.{key}", "invalid attachment digest")
        if attachments is not None and (
            key not in attachments or attachment_digest(attachments[key]) != digest
        ):
            fail(f"attachments.{key}", "missing attachment or digest mismatch")
