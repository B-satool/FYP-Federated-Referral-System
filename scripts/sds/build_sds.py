"""Build, check and release the Software Design Specification (docs/sds).

The SDS has two kinds of content:

* written sections (docs/sds/sections/*.md): architecture, workflows, security and design reasoning,
  maintained by people;
* generated appendices (docs/sds/generated/*.md): ERDs, data dictionary, API inventory, configuration,
  state machines, jobs, contracts, roles, migrations, dependencies, tests. They are read from the code
  (Python syntax trees, JSON and YAML files), never typed by hand, so they cannot drift from the code.

Every released version is frozen in docs/sds/versions/ and listed in docs/sds/CHANGELOG.md with the
structural changes found automatically (tables, columns, endpoints, settings, routes and so on).

  python scripts/sds/build_sds.py build                 # regenerate appendices and docs/sds/SDS.md
  python scripts/sds/build_sds.py check [--strict]      # CI: fail if the SDS is stale or unreleased
  python scripts/sds/build_sds.py release --level minor --summary "What changed"
  python scripts/sds/build_sds.py diff                  # show structural changes since the last release

check fails when (1) the generated files or SDS.md differ from what the code gives, or (2) the system's
structure or the written sections changed since the last released version. With --strict it also fails
when any source file changed since the last release. Static analysis only: no service, database or
network is needed. Requires Python 3.11+ and PyYAML (for the Compose files).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    # Required: without it the Compose inventory would silently differ between machines.
    sys.exit("build_sds.py needs PyYAML: pip install pyyaml (and do not run with python -I if it is a user install)")


class ComposeLoader(yaml.SafeLoader):
    """Safe loader that also accepts Compose's own tags (`!reset`, `!override`) as plain values."""


def _any_tag(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


ComposeLoader.add_multi_constructor("!", _any_tag)

ROOT = Path(__file__).resolve().parents[2]
SDS = ROOT / "docs" / "sds"
SECTIONS = SDS / "sections"
GENERATED = SDS / "generated"
VERSIONS = SDS / "versions"
MANIFEST = SDS / "manifest.json"
CHANGELOG = SDS / "CHANGELOG.md"
OUTPUT = SDS / "SDS.md"
TITLE = "Software Design Specification: Federated Referral Preparation and Follow-through Platform"

CENTRAL = ROOT / "services" / "central" / "app"
PROVIDER = ROOT / "services" / "provider" / "app"
REFCOMMON = ROOT / "libs" / "common" / "refcommon"

# Files whose content counts as "the system" for --strict (source tree fingerprint)
SOURCE_GLOBS = ["services/**/*.py", "libs/**/*.py", "web/src/**/*.ts", "web/src/**/*.tsx", "scripts/**/*.py",
                "infra/**/*", "docker-compose*.yml", "rules/roles/*.json", "rules/medication/*.json",
                "services/*/requirements.txt", "web/package.json", ".env.example", "AGENTS.md"]

# References between tables that are not database foreign keys (same database only). Shown dotted.
LOGICAL_REFS = {
    "central": [
        ("evidence_items", "link_id", "patient_links"),
        ("evidence_items", "ai_run_id", "selection_runs"),
        ("evidence_items", "superseded_by", "evidence_items"),
        ("source_retrievals", "link_id", "patient_links"),
        ("medication_entries", "duplicate_of", "medication_entries"),
        ("medication_flags", "medication_entry_id", "medication_entries"),
        ("medication_flags", "rule_id", "medication_rules"),
        ("suggestion_reviews", "pair_key", "ai_suggestions"),
        ("referrals", "requesting_doctor_id", "users"),
        ("notifications", "recipient_id", "users"),
        ("patient_links", "requested_by_id", "users"),
        ("drug_interactions", "ingredient_a", "ingredients"),
        ("drug_interactions", "ingredient_b", "ingredients"),
        ("label_rules", "ingredient", "ingredients"),
        ("medication_entries", "ingredient", "ingredients"),
        ("medicine_names", "ingredient", "ingredients"),
    ],
    "institution": [
        ("access_grants", "local_patient_id", "patients"),
        ("cases", "local_patient_id", "patients"),
        ("orders", "local_patient_id", "patients"),
    ],
}
# References that cross a database boundary (never joined; the IDs travel in API calls)
CROSS_SYSTEM_REFS = [
    ("institution", "cases.central_referral_id", "central", "referrals.reference", "set from the package envelope"),
    ("institution", "cases.link_request_id", "central", "patient_links.id", "intake link request for the arriving patient"),
    ("institution", "orders.central_referral_id", "central", "referrals.reference", "set from the diagnostic order"),
    ("institution", "orders.order_ref", "central", "diagnostic_requests.reference", "the order reference"),
    ("institution", "orders.link_request_id", "central", "patient_links.id", "intake link request"),
    ("institution", "sent_copies.central_referral_id", "central", "referrals.reference", "the sender's own copy"),
    ("institution", "access_grants.referral_ref", "central", "referrals.reference", "grant opened for a referral"),
    ("central", "referrals.patient_local_id", "institution", "patients.local_id", "the referring institution's record"),
    ("central", "patient_links.requester_local_id / target_local_id", "institution", "patients.local_id",
     "confirmed by the target institution's staff"),
    ("central", "evidence_items.source_record_id + version", "institution", "conditions / visits / medications / lab_results / imaging_reports .id",
     "FHIR resource id and version"),
    ("central", "users.id", "keycloak", "user subject (sub)", "Keycloak is the account authority"),
]

AUTH_CALLS = {"require_roles", "require_service", "load_referral", "require_own", "_require_central", "deny",
              "check_version", "ensure_clinical_edit_allowed", "decide_access", "_get_case", "_case_for",
              "require_admin", "_require_admin", "_require_reviewer", "require_reviewer", "load_order", "_get_order",
              "_require_diagnostics", "require_institution", "forbid", "_mine", "has_any"}


# --------------------------------------------------------------------------- small helpers
def psorted(paths) -> list[Path]:
    """Sort paths by their POSIX text, so Windows (case-insensitive) and Linux give the same order."""
    return sorted(paths, key=lambda p: p.as_posix())


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def parse(p: Path) -> ast.Module:
    return ast.parse(read(p), filename=str(p))


def first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def code(text: str) -> str:
    return f"`{text}`" if text else ""


def sha(data: Any) -> str:
    raw = data if isinstance(data, str) else json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:  # noqa: BLE001
        return None


def trailing_comment(lines: list[str], lineno: int) -> str:
    line = lines[lineno - 1]
    in_str: str | None = None
    for i, ch in enumerate(line):
        if ch in "\"'" and (i == 0 or line[i - 1] != "\\"):
            in_str = None if in_str == ch else (ch if in_str is None else in_str)
        elif ch == "#" and in_str is None:
            return line[i + 1:].strip()
    return ""


def leading_comment(lines: list[str], lineno: int) -> str:
    out: list[str] = []
    i = lineno - 2
    while i >= 0 and lines[i].strip().startswith("#"):
        out.insert(0, lines[i].strip().lstrip("#").strip())
        i -= 1
    return " ".join(out)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_None._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(md_escape(str(c)) if c is not None else "" for c in r) + " |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- data model
SQL_FROM_PY = {"str": "String", "int": "Integer", "bool": "Boolean", "datetime": "DateTime", "date": "Date",
               "float": "Float", "dict": "JSON", "list": "JSON", "bytes": "LargeBinary"}
MERMAID_TYPE = {"String": "string", "Text": "text", "Integer": "int", "Boolean": "bool", "DateTime": "datetime",
                "Date": "date", "Float": "float", "JSON": "json", "LargeBinary": "bytes"}


def _model_classes(files: list[Path]) -> dict[str, dict]:
    classes: dict[str, dict] = {}
    for f in files:
        tree = parse(f)
        lines = read(f).splitlines()
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            info = {"name": node.name, "file": rel(f), "bases": [ast.unparse(b) for b in node.bases],
                    "doc": ast.get_docstring(node) or "", "table": None, "columns": [], "uniques": []}
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in stmt.targets):
                    info["table"] = literal(stmt.value)
                elif isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__table_args__" for t in stmt.targets):
                    for c in ast.walk(stmt.value):
                        if isinstance(c, ast.Call) and ast.unparse(c.func) == "UniqueConstraint":
                            cols = [literal(a) for a in c.args]
                            name = next((literal(k.value) for k in c.keywords if k.arg == "name"), None)
                            info["uniques"].append({"columns": cols, "name": name})
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and isinstance(stmt.value, ast.Call) \
                        and ast.unparse(stmt.value.func) == "mapped_column":
                    info["columns"].append(_column(stmt, lines))
            classes[node.name] = info
    return classes


def _column(stmt: ast.AnnAssign, lines: list[str]) -> dict:
    call: ast.Call = stmt.value  # type: ignore[assignment]
    ann = ast.unparse(stmt.annotation)
    inner = ann[len("Mapped["):-1] if ann.startswith("Mapped[") else ann
    kw = {k.arg: k.value for k in call.keywords if k.arg}
    sql_type, fk = None, None
    for a in call.args:
        text = ast.unparse(a)
        if isinstance(a, ast.Call) and ast.unparse(a.func) == "ForeignKey":
            fk = literal(a.args[0])
        elif sql_type is None:
            sql_type = text
    base_py = inner.split("|")[0].strip().split("[")[0]
    if sql_type is None:
        sql_type = SQL_FROM_PY.get(base_py, base_py)
    nullable = "None" in inner
    if "nullable" in kw:
        nullable = bool(literal(kw["nullable"]))
    if literal(kw.get("primary_key", ast.Constant(False))):
        nullable = False
    comment = trailing_comment(lines, stmt.lineno) or leading_comment(lines, stmt.lineno)
    return {
        "name": stmt.target.id,  # type: ignore[union-attr]
        "py_type": inner,
        "sql_type": sql_type,
        "pk": bool(literal(kw.get("primary_key", ast.Constant(False)))),
        "fk": fk,
        "unique": bool(literal(kw.get("unique", ast.Constant(False)))),
        "index": bool(literal(kw.get("index", ast.Constant(False)))),
        "nullable": nullable,
        "default": ast.unparse(kw["default"]) if "default" in kw else (
            f"server: {ast.unparse(kw['server_default'])}" if "server_default" in kw else ""),
        "onupdate": ast.unparse(kw["onupdate"]) if "onupdate" in kw else "",
        "comment": comment,
    }


def model_inventory() -> dict[str, list[dict]]:
    mixin_files = [REFCOMMON / "sourcekit.py"]
    central_files = psorted((CENTRAL / "models").glob("*.py"))
    provider_files = [PROVIDER / "models.py"]
    mixins = _model_classes(mixin_files)
    out: dict[str, list[dict]] = {}
    for db, files in (("central", central_files), ("institution", provider_files)):
        classes = {**mixins, **_model_classes(files)}
        tables = []
        for c in classes.values():
            if not c["table"] or c["file"].endswith("sourcekit.py"):
                continue
            cols = list(c["columns"])
            for b in c["bases"]:
                if b in classes and not classes[b]["table"]:
                    for col in classes[b]["columns"]:
                        cols.append({**col, "inherited_from": b})
            tables.append({"table": c["table"], "class": c["name"], "file": c["file"], "doc": c["doc"],
                           "columns": cols, "uniques": c["uniques"],
                           "group": Path(c["file"]).stem})
        out[db] = sorted(tables, key=lambda t: (t["group"], t["table"]))
    return out


def _mermaid_col(col: dict) -> str:
    base = col["sql_type"].split("(")[0]
    typ = MERMAID_TYPE.get(base, "string")
    keys = [k for k, on in (("PK", col["pk"]), ("FK", bool(col["fk"])), ("UK", col["unique"])) if on]
    note = ("nullable" if col["nullable"] else "not null")
    if col["sql_type"] not in MERMAID_TYPE and "(" in col["sql_type"]:
        note += ", " + col["sql_type"]
    return f'        {typ} {col["name"]}{(" " + ",".join(keys)) if keys else ""} "{note}"'


def erd(db: str, tables: list[dict], with_columns: bool = True, only: set[str] | None = None) -> str:
    names = {t["table"] for t in tables}
    shown = [t for t in tables if only is None or t["table"] in only]
    shown_names = {t["table"] for t in shown}
    lines = ["```mermaid", "erDiagram"]
    for t in shown:
        if with_columns:
            lines.append(f"    {t['table']} {{")
            lines += [_mermaid_col(c) for c in t["columns"]]
            lines.append("    }")
    rels = []
    for t in tables:
        for c in t["columns"]:
            if c["fk"]:
                target = c["fk"].split(".")[0]
                if target in names and (t["table"] in shown_names or target in shown_names):
                    card = "|o--o{" if c["nullable"] else "||--o{"
                    rels.append(f'    {target} {card} {t["table"]} : "{c["name"]}"')
    for src, col, target in LOGICAL_REFS.get(db, []):
        if src in names and target in names and (src in shown_names or target in shown_names):
            rels.append(f'    {target} |o..o{{ {src} : "{col} (logical)"')
    if not with_columns:  # overview: primary key only, so every table is declared in a form all renderers accept
        for t in shown:
            lines.append(f"    {t['table']} {{")
            lines += [_mermaid_col(c) for c in t["columns"] if c["pk"]] or ['        string id "no primary key"']
            lines.append("    }")
    lines += sorted(set(rels))
    lines.append("```")
    return "\n".join(lines)


def gen_data_model(models: dict[str, list[dict]]) -> dict[str, str]:
    docs: dict[str, str] = {}
    titles = {"central": "Central platform database (`central_db`)",
              "institution": "Institution service database (one per institution: `drali_db`, `chughtai_db`, `ziauddin_db`, `akuh_db`)"}
    for db, tables in models.items():
        out = [f"## {titles[db]}\n",
               "Generated from the SQLAlchemy models. Solid lines are database foreign keys; dotted lines are "
               "logical references held as plain columns (no constraint). PK primary key, FK foreign key, "
               "UK unique.\n",
               f"### Overview: all {len(tables)} tables and their relationships\n",
               erd(db, tables, with_columns=False), ""]
        groups: dict[str, list[dict]] = {}
        for t in tables:
            groups.setdefault(t["group"], []).append(t)
        if db == "central":
            for g, ts in groups.items():
                out += [f"### ERD: `{g}` domain ({len(ts)} tables, `{ts[0]['file']}`)\n",
                        erd(db, tables, with_columns=True, only={t['table'] for t in ts}), ""]
        else:
            out += ["### ERD with all columns\n", erd(db, tables, with_columns=True), ""]
        docs[f"erd-{db}"] = "\n".join(out)

        dd = [f"## Data dictionary: {titles[db]}\n"]
        for t in tables:
            dd.append(f"### `{t['table']}` ({t['class']}, `{t['file']}`)\n")
            if t["doc"]:
                dd.append(" ".join(t["doc"].split()) + "\n")
            rows = []
            for c in t["columns"]:
                keys = ", ".join(k for k, on in (("PK", c["pk"]), (f"FK → {c['fk']}" if c["fk"] else "", bool(c["fk"])),
                                                  ("unique", c["unique"]), ("indexed", c["index"])) if on)
                note = c["comment"]
                if c.get("inherited_from"):
                    note = f"(from {c['inherited_from']}) {note}".strip()
                rows.append([code(c["name"]), c["sql_type"], "yes" if c["nullable"] else "no", keys,
                             code(c["default"]) if c["default"] else "", note])
            dd.append(table(["Column", "Type", "Null", "Keys", "Default", "Meaning"], rows))
            if t["uniques"]:
                dd.append("Unique constraints: " + "; ".join(
                    f"({', '.join(u['columns'])})" + (f" `{u['name']}`" if u["name"] else "") for u in t["uniques"]) + "\n")
        docs[f"data-dictionary-{db}"] = "\n".join(dd)

    cross = ["## References across system boundaries\n",
             "These identifiers point into another service's database. They are never joined: each service "
             "owns its database, and the values travel only in authenticated API calls (AGENTS.md invariant 1).\n",
             table(["Held in", "Column", "Points to", "Target", "How it is set"],
                   [[a, code(b), c, code(d), e] for a, b, c, d, e in CROSS_SYSTEM_REFS])]
    docs["erd-cross-system"] = "\n".join(cross)
    return docs


# --------------------------------------------------------------------------- API inventory
def _module_constants(tree: ast.Module) -> dict[str, list[str]]:
    consts: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            val = literal(node.value)
            if isinstance(val, (tuple, list, set, frozenset)) and all(isinstance(v, str) for v in val):
                consts[node.targets[0].id] = sorted(val) if isinstance(val, (set, frozenset)) else list(val)
            elif isinstance(val, str) and node.targets[0].id.isupper():
                consts[node.targets[0].id] = [val]
    return consts


def _render_call(call: ast.Call, consts: dict[str, list[str]]) -> str:
    name = ast.unparse(call.func).split(".")[-1]
    parts: list[str] = []
    for a in call.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            parts.append(a.value)
        elif isinstance(a, ast.Starred) and isinstance(a.value, ast.Name) and a.value.id in consts:
            parts += consts[a.value.id]
        elif isinstance(a, ast.Name) and a.id in consts and a.id.isupper():
            parts += consts[a.id]
    for k in call.keywords:
        if k.arg in ("roles", "what", "action"):
            v = literal(k.value)
            if isinstance(k.value, ast.Name) and k.value.id in consts:
                v = consts[k.value.id]
            if v is not None:
                parts.append(f"{k.arg}={v}")
    return f"{name}({', '.join(map(str, parts))})"


def _direct_checks(fn: ast.AST, consts: dict[str, list[str]]) -> list[str]:
    out = [_render_call(c, consts) for c in ast.walk(fn)
           if isinstance(c, ast.Call) and ast.unparse(c.func).split(".")[-1] in AUTH_CALLS]
    # inline role tests such as `if "svc_central" not in principal.roles`
    for c in ast.walk(fn):
        if isinstance(c, ast.Compare) and "principal.roles" in ast.unparse(c) and isinstance(c.left, ast.Constant):
            out.append(f"role {c.left.value} required")
    return out


def _checks(fn: ast.AST, consts: dict[str, list[str]], helpers: dict[str, ast.AST], depth: int = 0) -> list[str]:
    """Authorisation calls in a handler, following calls to helper functions of the same module (2 levels)."""
    out = _direct_checks(fn, consts)
    if depth >= 2:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in helpers and c.func.id not in AUTH_CALLS:
            out += [f"{c.func.id} → {x}" for x in _checks(helpers[c.func.id], consts, helpers, depth + 1)]
    return out


def api_inventory() -> list[dict]:
    files = psorted(CENTRAL.rglob("*.py")) + [PROVIDER / "main.py", REFCOMMON / "sourcekit.py"]
    shared = _module_constants(parse(CENTRAL / "security.py"))
    shared.update(_module_constants(parse(REFCOMMON / "sourcekit.py")))
    endpoints = []
    for f in files:
        tree = parse(f)
        consts = {**shared, **_module_constants(tree)}
        helpers = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) for d in n.decorator_list)}
        service = "institution" if f.is_relative_to(PROVIDER) or f.name == "sourcekit.py" else "central"

        def router_prefixes(scope: ast.AST) -> dict[str, tuple[str, list[str]]]:
            found: dict[str, tuple[str, list[str]]] = {}
            body = scope.body if hasattr(scope, "body") else []
            for node in body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func).endswith("APIRouter"):
                    kw = {k.arg: literal(k.value) for k in node.value.keywords}
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            found[t.id] = (kw.get("prefix") or "", kw.get("tags") or [])
            return found

        module_prefixes = router_prefixes(tree)
        scoped: list[tuple[ast.AST, dict]] = []
        for top in tree.body:
            if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local = {**module_prefixes, **router_prefixes(top)}
                scoped += [(n, local) for n in ast.walk(top) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node, prefixes in scoped:
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                method = dec.func.attr
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                owner = ast.unparse(dec.func.value)
                if owner not in prefixes and owner not in ("app", "router"):
                    continue
                path = literal(dec.args[0]) if dec.args else ""
                if not isinstance(path, str):
                    path = "<dynamic>"
                prefix, tags = prefixes.get(owner, ("", []))
                kw = {k.arg: k.value for k in dec.keywords}
                tags = literal(kw["tags"]) if "tags" in kw else tags
                checks = _checks(node, consts, helpers)
                body_params = []
                for a in node.args.args + node.args.kwonlyargs:
                    if a.annotation is None or a.arg in ("db", "principal", "request", "self"):
                        continue
                    ann = ast.unparse(a.annotation)
                    if ann in ("Session", "Principal", "Request"):
                        continue
                    body_params.append(f"{a.arg}: {ann}")
                endpoints.append({
                    "service": service, "method": method.upper(), "path": (prefix + path) or "/",
                    "handler": node.name, "file": rel(f), "line": node.lineno,
                    "tags": tags or [], "status": literal(kw["status_code"]) if "status_code" in kw else None,
                    "summary": first_line(ast.get_docstring(node)) or node.name.replace("_", " ").strip().capitalize() + ".",
                    "auth": sorted(set(checks)) or (["valid access token (any role)"] if any(
                        a.arg == "principal" for a in node.args.args + node.args.kwonlyargs) else ["public (no token)"]),
                    "params": body_params,
                })
    return sorted(endpoints, key=lambda e: (e["service"], (e["tags"] or [""])[0], e["path"], e["method"]))


def gen_api(endpoints: list[dict]) -> str:
    out = ["## API inventory\n",
           "Generated from the FastAPI route decorators. *Access checks* lists the authorisation calls made inside "
           "each handler (roles, institution scope, service identity, optimistic-concurrency checks). Every endpoint "
           "except `/health` and `/ready` also requires a valid Keycloak access token (verified signature, issuer, "
           "audience and introspection). Parameters exclude the database session and the caller's identity.\n"]
    for service, title in (("central", "Central platform API (`central`, port 8000)"),
                           ("institution", "Institution service API (`drali` 8001, `chughtai` 8002, `ziauddin` 8003, `akuh` 8004)")):
        eps = [e for e in endpoints if e["service"] == service]
        out.append(f"### {title}: {len(eps)} endpoints\n")
        groups: dict[str, list[dict]] = {}
        for e in eps:
            groups.setdefault((e["tags"] or ["untagged"])[0], []).append(e)
        for tag, es in groups.items():
            out.append(f"#### {tag}\n")
            out.append(table(["Method", "Path", "Purpose", "Access checks", "Parameters", "Handler"],
                             [[e["method"], code(e["path"]), e["summary"], "; ".join(e["auth"]),
                               "; ".join(e["params"]), f"{e['handler']} ({e['file']}:{e['line']})"] for e in es]))
    return "\n".join(out)


# --------------------------------------------------------------------------- pydantic schemas and contracts
def pydantic_models(files: list[Path]) -> list[dict]:
    out = []
    for f in files:
        tree = parse(f)
        lines = read(f).splitlines()
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and any(ast.unparse(b) in ("BaseModel",) or ast.unparse(b).endswith("In")
                                                      for b in node.bases):
                fields = []
                for s in node.body:
                    if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                        default = ast.unparse(s.value) if s.value is not None else "(required)"
                        fields.append([code(s.target.id), ast.unparse(s.annotation), default,
                                       trailing_comment(lines, s.lineno)])
                out.append({"name": node.name, "file": rel(f), "doc": first_line(ast.get_docstring(node)), "fields": fields})
    return out


def gen_contracts() -> str:
    tree = parse(REFCOMMON / "exchange.py")
    consts, event_types, hashed = {}, [], []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.endswith("_VERSION") or name == "CONTRACT_NOTE":
                consts[name] = literal(node.value)
            elif name == "ProviderEventType":
                event_types = [literal(e) for e in node.value.slice.elts]  # type: ignore[attr-defined]
            elif name == "HASHED_PACKAGE_FIELDS":
                hashed = list(literal(node.value) or [])
    outbox = {}
    for node in parse(CENTRAL / "delivery" / "outbox.py").body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "ENDPOINTS":
            outbox = literal(node.value) or {}
    out = ["## Exchange contracts (`libs/common/refcommon/exchange.py`)\n",
           "Project API contracts between the central platform and the institution services. They are not standard "
           "FHIR resources; a FHIR R4 4.0.1 Bundle travels inside the referral package unchanged.\n",
           table(["Constant", "Value"], [[code(k), code(str(v))] for k, v in consts.items()]),
           "### Provider event types\n",
           "Events an institution service sends to `POST /inbound/provider-events` (deduplicated by `event_key`):\n",
           ", ".join(code(e) for e in event_types) + "\n",
           "### Outbox message kinds (central → institution)\n",
           table(["Outbox kind", "Institution endpoint"], [[code(k), code(v)] for k, v in outbox.items()]),
           "### Fields covered by the package SHA-256\n",
           "Transport fields (delivery key, FHIR bundle timestamp) are excluded so a retry never changes the hash: "
           + ", ".join(code(h) for h in hashed) + "\n"]
    for m in pydantic_models([REFCOMMON / "exchange.py"]):
        out += [f"### `{m['name']}`\n", (m["doc"] + "\n") if m["doc"] else "",
                table(["Field", "Type", "Default", "Note"], m["fields"])]
    req = pydantic_models(psorted(CENTRAL.rglob("*.py")) + [PROVIDER / "main.py", REFCOMMON / "sourcekit.py"])
    out.append("## Request bodies (API input models)\n")
    for m in req:
        out += [f"### `{m['name']}` ({m['file']})\n", (m["doc"] + "\n") if m["doc"] else "",
                table(["Field", "Type", "Default", "Note"], m["fields"])]
    return "\n".join(out)


# --------------------------------------------------------------------------- configuration
ENV_FUNCS = {"os.environ.get", "os.getenv", "_bool", "_env_bool", "environ.get"}


def config_inventory() -> list[dict]:
    files = psorted(list(CENTRAL.rglob("*.py")) + list(PROVIDER.rglob("*.py")) + list(REFCOMMON.rglob("*.py")))
    seen: dict[str, dict] = {}
    for f in files:
        lines = read(f).splitlines()
        for node in ast.walk(parse(f)):
            is_get = isinstance(node, ast.Call) and ast.unparse(node.func) in ENV_FUNCS
            is_index = isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ"
            if not (is_get or is_index):
                continue
            arg = node.args[0] if is_get and node.args else (node.slice if is_index else None)
            name = literal(arg) if arg is not None else None
            if not (isinstance(name, str) and name.isupper()):
                continue
            default = ast.unparse(node.args[1]) if is_get and len(node.args) > 1 else ("(required)" if is_index else "")
            note = trailing_comment(lines, node.lineno) or leading_comment(lines, node.lineno)
            entry = seen.setdefault(name, {"name": name, "default": default, "files": [], "note": note})
            entry["files"].append(f"{rel(f)}:{node.lineno}")
            if not entry["note"] and note:
                entry["note"] = note
    for e in seen.values():
        e["files"] = sorted(set(e["files"]))
    return sorted(seen.values(), key=lambda e: e["name"])


def compose_inventory() -> dict:
    out: dict[str, Any] = {}
    for name in ("docker-compose.yml", "docker-compose.prod.yml", "docker-compose.dbaccess.yml"):
        p = ROOT / name
        if not p.exists():
            continue
        doc = yaml.load(read(p), Loader=ComposeLoader) or {}
        services = {}
        for svc, cfg in (doc.get("services") or {}).items():
            cfg = cfg or {}
            env = cfg.get("environment") or {}
            env_keys = sorted(env.keys()) if isinstance(env, dict) else sorted(str(e).split("=")[0] for e in env)
            build = cfg.get("build")
            services[svc] = {
                "image": cfg.get("image") or (f"build: {build.get('dockerfile', 'Dockerfile') if isinstance(build, dict) else build}"
                                               if build else ""),
                "ports": [str(x) for x in (cfg.get("ports") or [])],
                "depends_on": sorted((cfg.get("depends_on") or {}).keys()) if isinstance(cfg.get("depends_on"), dict)
                else list(cfg.get("depends_on") or []),
                "env": env_keys, "volumes": [str(v) for v in (cfg.get("volumes") or [])],
                "command": " ".join(map(str, cfg["command"])) if isinstance(cfg.get("command"), list) else (cfg.get("command") or ""),
                "healthcheck": "yes" if cfg.get("healthcheck") else "",
            }
        out[name] = {"services": services, "volumes": sorted((doc.get("volumes") or {}).keys())}
    return out


def env_example_keys() -> list[list[str]]:
    p = ROOT / ".env.example"
    rows, note = [], []
    for line in read(p).splitlines():
        s = line.strip()
        if s.startswith("#"):
            note.append(s.lstrip("#").strip())
        elif "=" in s:
            key = s.split("=", 1)[0]
            secret = any(w in key for w in ("PASSWORD", "SECRET", "KEY"))
            rows.append([code(key), "secret: set per installation" if secret else code(s.split("=", 1)[1]), " ".join(note)])
            note = []
        else:
            note = []
    return rows


def gen_config(cfg: list[dict], compose: dict) -> str:
    out = ["## Configuration\n", "### Environment variables read by the code\n",
           "Every variable read with `os.environ.get`, `os.getenv` or a boolean helper, with its default and where it is read.\n",
           table(["Variable", "Default", "Meaning", "Read in"],
                 [[code(c["name"]), code(c["default"]) if c["default"] else "(none)", c["note"], ", ".join(c["files"])] for c in cfg]),
           "### `.env.example` (installation settings)\n",
           "Secret values are never shown here. Copy `.env.example` to `.env` and set every secret per installation.\n",
           table(["Key", "Example value", "Comment"], env_example_keys())]
    for fname, doc in compose.items():
        out.append(f"### `{fname}`\n")
        out.append(table(["Service", "Image / build", "Ports", "Depends on", "Environment keys", "Volumes", "Command", "Health check"],
                         [[code(s), v["image"], ", ".join(v["ports"]), ", ".join(v["depends_on"]), ", ".join(v["env"]),
                           ", ".join(v["volumes"]), code(v["command"]) if v["command"] else "", v["healthcheck"]]
                          for s, v in doc["services"].items()]))
        if doc["volumes"]:
            out.append("Named volumes: " + ", ".join(code(v) for v in doc["volumes"]) + "\n")
    return "\n".join(out)


# --------------------------------------------------------------------------- state machines and jobs
def state_inventory() -> dict:
    tree = parse(CENTRAL / "referrals" / "state.py")
    vals: dict[str, Any] = {}
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) else (node.target if isinstance(node, ast.AnnAssign) else None)
        if isinstance(target, ast.Name) and target.id in ("TRANSITIONS", "STATUS_LABELS", "PRE_SUBMISSION", "IN_FLIGHT",
                                                          "CLINICAL_LOCKED", "TERMINAL"):
            v = literal(node.value)
            vals[target.id] = {k: sorted(x) for k, x in v.items()} if isinstance(v, dict) and target.id == "TRANSITIONS" else (
                sorted(v) if isinstance(v, set) else v)
    # other status columns, from the comments on their model columns
    return vals


def gen_states(states: dict, models: dict[str, list[dict]]) -> str:
    tr = states.get("TRANSITIONS", {})
    labels = states.get("STATUS_LABELS", {})
    lines = ["```mermaid", "stateDiagram-v2", "    [*] --> draft"]
    for src, dests in tr.items():
        for d in dests:
            lines.append(f"    {src} --> {d}")
    for t in states.get("TERMINAL", []):
        lines.append(f"    {t} --> [*]")
    lines.append("```")
    out = ["## Referral status state machine (`services/central/app/referrals/state.py`)\n",
           "Enforced on the server by `transition()`: any move not listed raises `409 invalid_transition`. "
           "Each transition writes a `referral_events` row and an audit event, and updates the working-set expiry.\n",
           "\n".join(lines), "",
           table(["Status", "Label", "Allowed next statuses"],
                 [[code(s), labels.get(s, ""), ", ".join(code(d) for d in tr.get(s, [])) or "(final)"] for s in tr]),
           "Status groups: " + "; ".join(f"**{k}** = {', '.join(code(x) for x in states.get(k, []))}"
                                         for k in ("PRE_SUBMISSION", "IN_FLIGHT", "CLINICAL_LOCKED", "TERMINAL")) + "\n",
           "### Other status fields (from the model column comments)\n"]
    rows = []
    for db, tables in models.items():
        for t in tables:
            for c in t["columns"]:
                if c["name"] in ("status", "kind", "review_state", "verification_status", "mapping_status", "decision",
                                 "selection_source", "origin", "delivery_status", "procedure_status") and c["comment"]:
                    rows.append([db, code(f"{t['table']}.{c['name']}"), c["comment"], code(c["default"]) if c["default"] else ""])
    out.append(table(["Database", "Column", "Values", "Default"], rows))
    return "\n".join(out)


def jobs_inventory() -> dict:
    tree = parse(CENTRAL / "tasks.py")
    beat, tasks = {}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("conf.update"):
            for k in node.keywords:
                if k.arg == "beat_schedule":
                    beat = literal(k.value) or {}
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and ast.unparse(dec.func).endswith("task"):
                    name = next((literal(k.value) for k in dec.keywords if k.arg == "name"), node.name)
                    doc = first_line(ast.get_docstring(node)) or node.name.replace("_", " ").capitalize() + "."
                    tasks.append({"task": name, "function": node.name, "doc": doc})
    return {"beat": beat, "tasks": tasks}


def gen_jobs(jobs: dict) -> str:
    sched = {v["task"]: v["schedule"] for v in jobs["beat"].values()}
    return "\n".join(["## Background jobs (`services/central/app/tasks.py`, Celery worker with beat)\n",
                      "Redis is the queue only; job state lives in PostgreSQL (`jobs` table).\n",
                      table(["Task", "Schedule", "Purpose", "Function"],
                            [[code(t["task"]), f"every {sched[t['task']]:g} s" if t["task"] in sched else "on demand",
                              t["doc"], code(t["function"])] for t in jobs["tasks"]])])


# --------------------------------------------------------------------------- web, roles, realm
def web_inventory() -> dict:
    app = read(ROOT / "web" / "src" / "App.tsx")
    routes = sorted(set(re.findall(r'<Route path="([^"]+)" element=\{<(?:PublicFrame>|ReviewerOnly>)?<?(\w+)', app)))
    features = {}
    for d in psorted((ROOT / "web" / "src" / "features").iterdir()):
        if d.is_dir():
            features[d.name] = sorted(p.name for p in d.iterdir() if p.is_file())
    pkg = json.loads(read(ROOT / "web" / "package.json"))
    templates = json.loads(read(ROOT / "rules" / "roles" / "templates.v1.json"))
    return {"routes": routes, "features": features, "scripts": pkg.get("scripts", {}),
            "dependencies": {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})},
            "screens": templates["screens"], "templates": templates["templates"]}


def realm_inventory() -> dict:
    r = json.loads(read(ROOT / "infra" / "keycloak" / "import" / "referral-realm.json"))
    return {
        "realm": r.get("realm"),
        "roles": [[x["name"], x.get("description", "")] for x in r.get("roles", {}).get("realm", [])],
        "clients": [[c["clientId"], "public" if c.get("publicClient") else "confidential",
                     ", ".join(f for f, on in (("authorization code + PKCE", c.get("standardFlowEnabled")),
                                                ("client credentials", c.get("serviceAccountsEnabled")),
                                                ("password grant (dev only)", c.get("directAccessGrantsEnabled"))) if on)]
                    for c in r.get("clients", [])],
        "groups": [[g["name"], ", ".join(s["name"] for s in g.get("subGroups", []))] for g in r.get("groups", [])],
        "users": [[u["username"], ", ".join(u.get("realmRoles", [])), ", ".join(u.get("groups", []) or [])]
                  for u in r.get("users", []) if not u["username"].startswith("service-account")],
        "tokens": {k: r.get(k) for k in ("accessTokenLifespan", "ssoSessionIdleTimeout", "ssoSessionMaxLifespan",
                                         "bruteForceProtected")},
    }


def gen_web_and_roles(web: dict, realm: dict) -> str:
    out = ["## Web application (`web/`)\n", "### Routes (`web/src/App.tsx`)\n",
           table(["Path", "Screen component"], [[code(p), code(c)] for p, c in web["routes"]]),
           "### Feature modules (`web/src/features`)\n",
           table(["Feature", "Files"], [[code(k), ", ".join(v)] for k, v in web["features"].items()]),
           "### Role templates and menus (`rules/roles/templates.v1.json`)\n",
           "The menu is built from `GET /me`; it only hides screens. The API checks are the enforcement.\n",
           table(["Screen", "Route", "Menu group", "Roles that see it"],
                 [[code(k), code(v["route"]), v["group"], ", ".join(v["roles"])] for k, v in web["screens"].items()]),
           table(["Template", "Name", "Realm roles", "Institution kinds", "Default grant days", "Home", "Menu"],
                 [[code(t["template_id"]), t["name"], ", ".join(t["roles"]), ", ".join(t["institution_kinds"]),
                   t.get("default_grant_days", ""), t["home"], ", ".join(t["menu"])] for t in web["templates"]]),
           "### npm scripts\n", table(["Script", "Command"], [[code(k), code(v)] for k, v in web["scripts"].items()]),
           f"## Identity provider (Keycloak realm `{realm['realm']}`, `infra/keycloak/import/referral-realm.json`)\n",
           "### Realm roles\n", table(["Role", "Meaning"], [[code(a), b] for a, b in realm["roles"]]),
           "### Clients\n", table(["Client", "Type", "Flows"], realm["clients"]),
           "### Institutions and departments (groups)\n",
           "A user's institution is their top-level group; the department is the subgroup.\n",
           table(["Institution group", "Department subgroups"], realm["groups"]),
           "### Demonstration accounts (synthetic; passwords are not listed)\n",
           table(["Username", "Realm roles", "Groups"], realm["users"]),
           "### Token and session settings\n",
           table(["Setting", "Value"], [[code(k), v] for k, v in realm["tokens"].items()])]
    return "\n".join(out)


# --------------------------------------------------------------------------- migrations, deps, assets, tests, docs
def migrations_inventory() -> dict:
    out = {}
    for svc in ("central", "provider"):
        revs = []
        for p in psorted((ROOT / "services" / svc / "migrations" / "versions").glob("*.py")):
            t = read(p)
            rid = re.search(r"Revision ID: (\w+)", t)
            down = re.search(r"Revises: ([\w, ]*)", t)
            revs.append({"revision": rid.group(1) if rid else p.stem.split("_")[0],
                         "down": (down.group(1).strip() if down else "") or None,
                         "message": first_line(ast.get_docstring(parse(p))).split(" Revision ID")[0], "file": rel(p)})
        order, by_down = [], {r["down"]: r for r in revs}
        cur = by_down.get(None)
        while cur:
            order.append(cur)
            cur = by_down.get(cur["revision"])
        out[svc] = order or revs
    return out


def deps_inventory() -> dict:
    out = {}
    for p in psorted(ROOT.glob("services/*/requirements.txt")):
        out[rel(p)] = [l.strip() for l in read(p).splitlines() if l.strip() and not l.startswith("#")]
    pp = ROOT / "libs" / "common" / "pyproject.toml"
    m = re.search(r"dependencies\s*=\s*\[(.*?)\]", read(pp), re.S)
    out[rel(pp)] = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    return out


def assets_inventory() -> list[list[str]]:
    rows = []
    for p in psorted((ROOT / "rules").rglob("*")):
        if not p.is_file():
            continue
        size = len(p.read_bytes().replace(b"\r\n", b"\n"))  # same on Windows (CRLF checkout) and Linux
        summary = ""
        if p.suffix == ".json":
            try:
                d = json.loads(read(p))
                if isinstance(d, dict):
                    summary = ", ".join(f"{k}: {len(v)}" if isinstance(v, (list, dict)) else f"{k}" for k, v in list(d.items())[:6])
                elif isinstance(d, list):
                    summary = f"{len(d)} items"
            except ValueError:
                summary = "(not JSON)"
        elif p.suffix in (".csv", ".jsonl"):
            with p.open(encoding="utf-8", errors="replace") as fh:
                summary = f"{sum(1 for _ in fh) - (1 if p.suffix == '.csv' else 0)} rows"
        rows.append([code(rel(p)), f"{size / 1024:,.0f} KB", summary])
    return rows


def tests_inventory() -> list[dict]:
    out = []
    for p in psorted(list((ROOT / "services" / "central" / "tests").glob("test_*.py")) + list((ROOT / "tests").glob("test_*.py"))):
        tree = parse(p)
        tests = [[n.name, first_line(ast.get_docstring(n))] for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
        kind = "unit (no services)" if "services" in p.parts else "integration (full stack)"
        out.append({"file": rel(p), "kind": kind, "tests": tests})
    for p in psorted((ROOT / "web" / "e2e").glob("*.spec.ts")):
        tests = [[t, ""] for t in re.findall(r"\btest\(\s*[\"'`](.+?)[\"'`]", read(p))]
        out.append({"file": rel(p), "kind": "browser end-to-end (Playwright)", "tests": tests})
    return out


def decisions_inventory() -> list[list[str]]:
    rows = []
    for p in psorted((ROOT / "docs" / "decisions").glob("*.md")):
        t = read(p)
        title = re.search(r"^#\s+(.+)$", t, re.M)
        status = re.search(r"\*\*Status:\*\*\s*(.+)", t)
        rows.append([f"[{p.stem}](../decisions/{p.name})", title.group(1) if title else p.stem,
                     (status.group(1).strip() if status else "")[:220]])
    return rows


def invariants_text() -> str:
    t = read(ROOT / "AGENTS.md")
    m = re.search(r"## Non-negotiable invariants\n(.*?)\n## ", t, re.S)
    return m.group(1).strip() if m else "(not found)"


def gen_misc(migs: dict, deps: dict, assets: list, tests: list, decisions: list, web: dict) -> dict[str, str]:
    mig = ["## Database migrations (Alembic, applied at service start: `alembic upgrade head`)\n"]
    for svc, revs in migs.items():
        mig += [f"### `services/{svc}/migrations`\n",
                table(["Order", "Revision", "Revises", "Change", "File"],
                      [[i + 1, code(r["revision"]), code(r["down"] or "(base)"), r["message"], code(r["file"])]
                       for i, r in enumerate(revs)])]
    dep = ["## Dependencies\n"]
    for k, v in deps.items():
        dep += [f"### `{k}`\n", table(["Package"], [[code(x)] for x in v])]
    dep += ["### `web/package.json`\n", table(["Package", "Version"], [[code(k), code(v)] for k, v in web["dependencies"].items()])]
    tst = ["## Automated tests\n",
           f"{sum(len(t['tests']) for t in tests)} tests in {len(tests)} files.\n"]
    for t in tests:
        tst += [f"### `{t['file']}` ({t['kind']}, {len(t['tests'])})\n", table(["Test", "What it checks"], [[code(a), b] for a, b in t["tests"]])]
    return {
        "migrations": "\n".join(mig),
        "dependencies": "\n".join(dep),
        "rules-and-data": "\n".join(["## Rules and reference data (`rules/`)\n",
                                     "Data files loaded at seed time or read by the services. Large data sets are summarised.\n",
                                     table(["File", "Size", "Contents"], assets)]),
        "tests": "\n".join(tst),
        "decisions": "\n".join(["## Decision records (`docs/decisions`)\n",
                                "Design decisions taken after the SRS, newest last. Each record states what was decided and why.\n",
                                table(["Record", "Title", "Status"], decisions),
                                "## Non-negotiable invariants (from `AGENTS.md`)\n", invariants_text() + "\n"]),
    }


# --------------------------------------------------------------------------- assembly, fingerprint, versions
APPENDIX_ORDER = [
    ("erd-central", "Appendix A. ERD: central platform"),
    ("erd-institution", "Appendix B. ERD: institution service"),
    ("erd-cross-system", "Appendix C. References across system boundaries"),
    ("data-dictionary-central", "Appendix D. Data dictionary: central platform"),
    ("data-dictionary-institution", "Appendix E. Data dictionary: institution service"),
    ("api", "Appendix F. API inventory"),
    ("contracts", "Appendix G. Exchange contracts and request bodies"),
    ("states", "Appendix H. State machines and status values"),
    ("jobs", "Appendix I. Background jobs"),
    ("config", "Appendix J. Configuration and deployment descriptors"),
    ("web-and-roles", "Appendix K. Web application, roles and identity provider"),
    ("migrations", "Appendix L. Database migrations"),
    ("dependencies", "Appendix M. Dependencies"),
    ("rules-and-data", "Appendix N. Rules and reference data"),
    ("tests", "Appendix O. Automated tests"),
    ("decisions", "Appendix P. Decision records and invariants"),
]


def collect() -> tuple[dict[str, str], dict]:
    models = model_inventory()
    endpoints = api_inventory()
    cfg = config_inventory()
    compose = compose_inventory()
    states = state_inventory()
    jobs = jobs_inventory()
    web = web_inventory()
    realm = realm_inventory()
    migs = migrations_inventory()
    deps = deps_inventory()
    tests = tests_inventory()
    gen: dict[str, str] = {}
    gen.update(gen_data_model(models))
    gen["api"] = gen_api(endpoints)
    gen["contracts"] = gen_contracts()
    gen["states"] = gen_states(states, models)
    gen["jobs"] = gen_jobs(jobs)
    gen["config"] = gen_config(cfg, compose)
    gen["web-and-roles"] = gen_web_and_roles(web, realm)
    gen.update(gen_misc(migs, deps, assets_inventory(), tests, decisions_inventory(), web))
    inventory = {
        "tables": {db: {t["table"]: {c["name"]: f"{c['sql_type']}{' null' if c['nullable'] else ''}{' FK ' + c['fk'] if c['fk'] else ''}"
                                     for c in t["columns"]} for t in ts} for db, ts in models.items()},
        "endpoints": sorted(f"{e['service']} {e['method']} {e['path']}" for e in endpoints),
        "endpoint_access": {f"{e['service']} {e['method']} {e['path']}": e["auth"] for e in endpoints},
        "settings": sorted(f"{c['name']}={c['default']}" for c in cfg),
        "compose_services": {f: sorted(d["services"]) for f, d in compose.items()},
        "transitions": states.get("TRANSITIONS", {}),
        "jobs": sorted(f"{t['task']}" for t in jobs["tasks"]),
        "schedule": {v["task"]: v["schedule"] for v in jobs["beat"].values()},
        "web_routes": [p for p, _ in web["routes"]],
        "roles": sorted(r[0] for r in realm["roles"]),
        "templates": sorted(t["template_id"] for t in web["templates"]),
        "migrations": {k: [r["revision"] for r in v] for k, v in migs.items()},
        "dependencies": deps,
        "web_dependencies": web["dependencies"],
        "decisions": [r[0] for r in decisions_inventory()],
    }
    return gen, inventory


def sections() -> list[tuple[str, str]]:
    return [(p.name, read(p)) for p in psorted(SECTIONS.glob("*.md"))]


def source_hash() -> str:
    h = hashlib.sha256()
    files = psorted({p for g in SOURCE_GLOBS for p in ROOT.glob(g) if p.is_file() and "node_modules" not in p.parts
                    and "__pycache__" not in p.parts})
    for p in files:
        h.update(rel(p).encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def fingerprints(gen: dict[str, str], inventory: dict) -> dict[str, str]:
    return {"structure": sha(inventory), "sections": sha([s for _, s in sections()]), "source": source_hash()}


def load_manifest() -> dict:
    return json.loads(read(MANIFEST)) if MANIFEST.exists() else {"version": None, "released": None, "fingerprints": {},
                                                                    "inventory": {}, "history": []}


def headings(md: str) -> list[tuple[int, str]]:
    out, fence = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            fence = not fence
        elif not fence:
            m = re.match(r"^(#{1,2})\s+(.+)$", line)
            if m:
                out.append((len(m.group(1)), m.group(2).strip()))
    return out


def anchor(text: str) -> str:
    a = re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")
    return a


def assemble(gen: dict[str, str], version_label: str, released: str | None, fps: dict[str, str]) -> str:
    body: list[str] = []
    for _, text in sections():
        body.append(text.strip() + "\n")
    for key, title in APPENDIX_ORDER:
        content = gen[key]
        # demote the appendix's own headings one level under the appendix title
        content = re.sub(r"^(#{2,5}) ", lambda m: "#" + m.group(1) + " ", content, flags=re.M)
        body.append(f"# {title}\n\n_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._\n\n{content.strip()}\n")
    text = "\n\n".join(body)
    toc = ["## Contents\n"]
    for level, h in headings(text):
        if level == 1:
            toc.append(f"- [{h}](#{anchor(h)})")
        elif level == 2:
            toc.append(f"  - [{h}](#{anchor(h)})")
    header = [f"# {TITLE}", "",
              "| | |", "|---|---|",
              f"| Document version | **{version_label}** |",
              f"| Released | {released or 'not yet released'} |",
              "| System | Federated referral preparation and follow-through platform (FYP), v2 code base |",
              "| Status | Living document: regenerated from the code on every change, frozen per release in `docs/sds/versions/` |",
              f"| Structure fingerprint | `{fps['structure'][:16]}` |",
              f"| Written-sections fingerprint | `{fps['sections'][:16]}` |",
              f"| Source fingerprint | `{fps['source'][:16]}` |",
              "| Maintained by | The project team. See section 17 for how to update and release it. |", ""]
    return "\n".join(header) + "\n" + "\n".join(toc) + "\n\n" + text


def build(write: bool = True) -> tuple[dict[str, str], dict, str, dict[str, str]]:
    gen, inventory = collect()
    fps = fingerprints(gen, inventory)
    man = load_manifest()
    released = man.get("fingerprints", {})
    unchanged = released.get("structure") == fps["structure"] and released.get("sections") == fps["sections"]
    if man.get("version") and unchanged:
        label, when = f"v{man['version']}", man.get("released")
    else:
        label = f"Working draft after v{man['version']}" if man.get("version") else "Working draft (no release yet)"
        when = None
    doc = assemble(gen, label, when, fps)
    if write:
        GENERATED.mkdir(parents=True, exist_ok=True)
        for key, text in gen.items():
            (GENERATED / f"{key}.md").write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        OUTPUT.write_text(doc, encoding="utf-8", newline="\n")
    return gen, inventory, doc, fps


def _dict_diff(old: dict, new: dict) -> tuple[list[str], list[str], list[str]]:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    return added, removed, changed


def structural_diff(old: dict, new: dict) -> list[str]:
    out: list[str] = []
    if not old:
        return ["First release: the whole system is described."]
    for db in sorted(set(old.get("tables", {})) | set(new.get("tables", {}))):
        o, n = old.get("tables", {}).get(db, {}), new.get("tables", {}).get(db, {})
        a, r, c = _dict_diff(o, n)
        out += [f"Table added ({db}): `{t}`" for t in a] + [f"Table removed ({db}): `{t}`" for t in r]
        for t in c:
            ca, cr, cc = _dict_diff(o[t], n[t])
            out += [f"Column added ({db}): `{t}.{x}` {n[t][x]}" for x in ca]
            out += [f"Column removed ({db}): `{t}.{x}`" for x in cr]
            out += [f"Column changed ({db}): `{t}.{x}` {o[t][x]} → {n[t][x]}" for x in cc]
    for key, label in (("endpoints", "Endpoint"), ("settings", "Setting"), ("jobs", "Background job"),
                       ("web_routes", "Web route"), ("roles", "Realm role"), ("templates", "Role template"),
                       ("decisions", "Decision record")):
        o, n = set(old.get(key, [])), set(new.get(key, []))
        out += [f"{label} added: `{x}`" for x in sorted(n - o)] + [f"{label} removed: `{x}`" for x in sorted(o - n)]
    a, r, c = _dict_diff(old.get("endpoint_access", {}), new.get("endpoint_access", {}))
    out += [f"Access checks changed: `{x}`" for x in c]
    for f in sorted(set(old.get("compose_services", {})) | set(new.get("compose_services", {}))):
        o, n = set(old.get("compose_services", {}).get(f, [])), set(new.get("compose_services", {}).get(f, []))
        out += [f"Compose service added (`{f}`): `{x}`" for x in sorted(n - o)]
        out += [f"Compose service removed (`{f}`): `{x}`" for x in sorted(o - n)]
    if old.get("transitions") != new.get("transitions"):
        out.append("Referral state machine transitions changed")
    if old.get("schedule") != new.get("schedule"):
        out.append("Background job schedule changed")
    for svc in sorted(set(old.get("migrations", {})) | set(new.get("migrations", {}))):
        o, n = old.get("migrations", {}).get(svc, []), new.get("migrations", {}).get(svc, [])
        out += [f"Migration added ({svc}): `{x}`" for x in n if x not in o]
    for f in sorted(set(old.get("dependencies", {})) | set(new.get("dependencies", {}))):
        o, n = set(old.get("dependencies", {}).get(f, [])), set(new.get("dependencies", {}).get(f, []))
        out += [f"Dependency added (`{f}`): `{x}`" for x in sorted(n - o)] + [f"Dependency removed (`{f}`): `{x}`" for x in sorted(o - n)]
    a, r, c = _dict_diff(old.get("web_dependencies", {}), new.get("web_dependencies", {}))
    out += [f"Web dependency added: `{x}`" for x in a] + [f"Web dependency removed: `{x}`" for x in r] + \
           [f"Web dependency changed: `{x}`" for x in c]
    return out


def bump(version: str | None, level: str) -> str:
    if not version:
        return "1.0.0"
    major, minor, patch = (int(x) for x in version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def release(level: str, summary: str, today: str | None = None) -> str:
    man = load_manifest()
    gen, inventory, _, fps = build(write=False)
    changes = structural_diff(man.get("inventory", {}), inventory)
    if man.get("fingerprints", {}).get("sections") != fps["sections"] and man.get("version"):
        changes.append("Written sections changed: " + ", ".join(n for n, _ in sections()))
    if man.get("version") and man.get("fingerprints") == fps:
        raise SystemExit(f"Nothing changed since v{man['version']}; no release made.")
    version = bump(man.get("version"), level)
    when = today or date.today().isoformat()
    man.update({"version": version, "released": when, "fingerprints": fps, "inventory": inventory})
    man.setdefault("history", []).append({"version": version, "date": when, "summary": summary, "changes": len(changes)})
    MANIFEST.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    gen, inventory, doc, fps = build(write=True)
    VERSIONS.mkdir(parents=True, exist_ok=True)
    (VERSIONS / f"SDS-v{version}.md").write_text(doc, encoding="utf-8", newline="\n")
    entry = [f"## v{version} ({when})", "", summary, ""]
    entry += ["Structural changes found automatically:", ""] + [f"- {c}" for c in changes] if changes else []
    entry.append("")
    old = read(CHANGELOG) if CHANGELOG.exists() else "# SDS changelog\n\nNewest first. Each version is frozen in `versions/`.\n"
    head, _, rest = old.partition("\n## ")
    CHANGELOG.write_text(head.rstrip() + "\n\n" + "\n".join(entry) + ("\n## " + rest if rest else ""), encoding="utf-8",
                         newline="\n")
    return version


def check(strict: bool) -> int:
    gen, inventory, doc, fps = build(write=False)
    problems = []
    for key, text in gen.items():
        p = GENERATED / f"{key}.md"
        if not p.exists() or read(p) != text.rstrip() + "\n":
            problems.append(f"generated/{key}.md is out of date")
    if not OUTPUT.exists() or read(OUTPUT) != doc:
        problems.append("SDS.md is out of date")
    man = load_manifest()
    rel_fp = man.get("fingerprints", {})
    if rel_fp.get("structure") != fps["structure"]:
        problems.append(f"the system's structure changed since v{man.get('version')}:\n    "
                        + "\n    ".join(structural_diff(man.get("inventory", {}), inventory)[:40]))
    if rel_fp.get("sections") != fps["sections"]:
        problems.append(f"the written sections changed since v{man.get('version')}")
    if strict and rel_fp.get("source") != fps["source"]:
        problems.append(f"source files changed since v{man.get('version')} (--strict)")
    if problems:
        print("SDS check failed:\n- " + "\n- ".join(problems))
        print("\nUpdate docs/sds/sections where behaviour changed, then run:\n"
              "  python scripts/sds/build_sds.py release --level minor --summary \"<what changed>\"")
        return 1
    print(f"SDS v{man.get('version')} is current.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true")
    r = sub.add_parser("release")
    r.add_argument("--level", choices=["major", "minor", "patch"], default="minor")
    r.add_argument("--summary", required=True)
    r.add_argument("--date")
    sub.add_parser("diff")
    args = ap.parse_args()
    if args.cmd == "build":
        _, _, _, fps = build(write=True)
        print(f"Built {rel(OUTPUT)} ({len(read(OUTPUT).splitlines())} lines); structure {fps['structure'][:12]}")
        return 0
    if args.cmd == "check":
        return check(args.strict)
    if args.cmd == "diff":
        man = load_manifest()
        _, inventory, _, _ = build(write=False)
        print("\n".join(structural_diff(man.get("inventory", {}), inventory)) or "No structural changes.")
        return 0
    v = release(args.level, args.summary, args.date)
    print(f"Released SDS v{v}: {rel(VERSIONS / f'SDS-v{v}.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
