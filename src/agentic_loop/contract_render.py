"""Governance-contract template rendering (pure stdlib).

The package ships de-tooled governance contract templates (``templates/*.tmpl``)
whose tool- and project-specific names are ``string.Template`` placeholders
(``$consultant``, ``$quality_gate_commands``, ...). This module turns a project's
``.agentic/config.toml`` values into those placeholder substitutions, renders a
template deterministically, and stamps each rendered file with a
``template_version`` + ``config_checksum`` header so ``agentic contract check``
(a later WP) can detect drift.

Everything here is pure and standard-library only: no third-party dependency, no
network, no hidden IO beyond ``load_template`` reading packaged data.
"""
import hashlib
import json
from string import Template

try:  # 3.9+: importlib.resources.files exists but files()/joinpath is the stable path
    from importlib.resources import files as _resources_files
except ImportError:  # pragma: no cover - <3.9 not supported anyway
    _resources_files = None

# Bump when the template wording/structure changes in a way that should prompt
# adopting projects to re-render (via `agentic contract diff`).
CONTRACT_TEMPLATE_VERSION = "6"

_TEMPLATE_PACKAGE = "agentic_loop"
_TEMPLATE_SUBDIR = "templates"

# Placeholders that always carry a value; build_values guarantees each is present
# so Template.substitute (strict) never raises on a well-formed config.
_REQUIRED_PLACEHOLDERS = (
    "project_name",
    "orchestrator",
    "developer",
    "reviewer",
    "consultant",
    "observer",
    "iterations_dir",
    "quality_gate_commands",
    "forbidden_paths",
    "production_paths",
    "min_independence",
    "lock_owner_source",
    "lock_ttl_minutes",
    "developer_dispatch_hint",
    "default_output_language",
    "merge_gate_cmd",
    "health_check_cmd",
)


def render(template_text, values):
    """Render ``template_text`` with ``values`` using strict substitution.

    Strict on purpose: a missing placeholder raises ``KeyError`` rather than
    leaving a literal ``$foo`` in the output. Templates escape a literal dollar
    as ``$$``.
    """
    return Template(template_text).substitute(values)


def _fmt_list(items):
    """Deterministic human-readable rendering of a list value."""
    if not items:
        return "(none)"
    return ", ".join(str(x) for x in items)


def _fmt_role(value):
    """A role maps to one adapter name, a primary/fallback array, or a table
    (adapter + provider)."""
    if isinstance(value, dict):
        adapter = value.get("adapter")
        provider = value.get("provider")
        if provider:
            return "{} (provider: {})".format(adapter, provider)
        return str(adapter or value)
    if isinstance(value, (list, tuple)):
        names = [str(x) for x in value]
        if not names:
            return "(unassigned)"
        if len(names) == 1:
            return names[0]
        return "{} (primary; fallback: {})".format(names[0], ", ".join(names[1:]))
    return str(value)


def _primary_role_name(value, default):
    """The bare adapter name of a role, for prose that needs a tool name only.

    Accepts the same three binding forms as :func:`_fmt_role`. A table yields
    its ``adapter``, not the table's repr; an array yields its primary entry.

    This exists because building the primary name by list-wrapping the role and
    taking ``[0]`` silently breaks on the table form: a dict is not a
    list/tuple, so the dict itself came back and ``str()`` emitted a Python repr
    straight into ``$developer_dispatch_hint`` -- i.e. into the body of
    AGENTS.md and CLAUDE.md:

        dispatch the developer role (configured tool: {'adapter': 'kimi',
        'fallback_provider': 'deepseekflash'}) into an isolated worktree
    """
    if isinstance(value, dict):
        adapter = value.get("adapter")
        return str(adapter) if adapter else default
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else default
    text = str(value)
    return text if text else default


def _command_gate_rules(config):
    """Return the command-gate rule list from the unified ``[[gate]]`` array.

    The execution engine (quality-gate.sh) reads ``[[gate]]`` (kind="command",
    stage="pre_review"); this mirrors it so the rendered §9 lists exactly what
    the gate will run. Falls back to the legacy ``[quality_gate]`` section for
    pre-0.3.0 configs.
    """
    if not isinstance(config, dict):
        return []
    gates = config.get("gate")
    if isinstance(gates, list):
        for gate in gates:
            if (
                isinstance(gate, dict)
                and gate.get("kind") == "command"
                and gate.get("stage") == "pre_review"
            ):
                rules = gate.get("rule")
                if isinstance(rules, list):
                    return rules
    qg = config.get("quality_gate")
    if isinstance(qg, dict):
        rules = qg.get("rule")
        if isinstance(rules, list):
            return rules
    return []


def _fmt_quality_gate(rules):
    """Render a rule (match->run) list as readable lines for the §9 section."""
    if not rules:
        return "(no project-specific quality-gate rules configured)"
    lines = []
    for r in rules:
        match = r.get("match", "?")
        run = r.get("run", [])
        run_str = " && ".join(str(c) for c in run) if isinstance(run, (list, tuple)) else str(run)
        lines.append("  - {} -> {}".format(match, run_str))
    return "\n".join(lines)


def build_values(config, *, project_name):
    """Flatten a parsed ``.agentic/config.toml`` dict into placeholder values.

    Deterministic and pure: array/table values are pre-formatted into strings
    (``string.Template`` has no loops/conditionals). Optional keys fall back to
    neutral, tool-agnostic defaults so a minimal config still renders.
    """
    roles = config.get("roles", {}) if isinstance(config, dict) else {}
    project = config.get("project", {}) if isinstance(config, dict) else {}
    safety = config.get("safety", {}) if isinstance(config, dict) else {}
    review_policy = config.get("review_policy", {}) if isinstance(config, dict) else {}
    locks = config.get("locks", {}) if isinstance(config, dict) else {}
    scripts = config.get("scripts", {}) if isinstance(config, dict) else {}

    developer = roles.get("developer", "Developer")
    primary_developer = _primary_role_name(developer, "the developer tool")

    values = {
        "project_name": project_name,
        "orchestrator": _fmt_role(roles.get("orchestrator", "Orchestrator")),
        "developer": _fmt_role(developer),
        "reviewer": _fmt_role(roles.get("reviewer", "Reviewer")),
        "consultant": _fmt_role(roles.get("consultant", "Consultant")),
        # No dedicated config key today; neutral default. A project may add one later.
        "observer": _fmt_role(roles.get("observer", "Observer")),
        "iterations_dir": str(project.get("iterations_dir", "docs/plans")),
        # Neutral framework default; a project sets [project].default_output_language
        # in its config to render a different communication default (e.g. "Chinese").
        "default_output_language": str(project.get("default_output_language", "English")),
        "quality_gate_commands": _fmt_quality_gate(_command_gate_rules(config)),
        "forbidden_paths": _fmt_list(safety.get("forbidden_paths", [])),
        "production_paths": _fmt_list(safety.get("production_paths", [])),
        "min_independence": str(review_policy.get("min_independence", "strong")),
        "lock_owner_source": str(locks.get("owner_source", "env:AGENTIC_SESSION_ID")),
        "lock_ttl_minutes": str(locks.get("ttl_minutes", 30)),
        # Tool-agnostic dispatch hint keyed off the configured primary developer.
        "developer_dispatch_hint": (
            "dispatch the developer role (configured tool: {}) into an isolated "
            "worktree; record the actual executor tool and session id".format(primary_developer)
        ),
        # Merge-gate and health-check command references. Default to the portable
        # `agentic` CLI entry point (which resolves the real wrapper, main-repo or
        # wheel-bundled); a project overrides via [scripts] to render its own.
        "merge_gate_cmd": str(scripts.get("merge_gate", "agentic gate")),
        "health_check_cmd": str(scripts.get("health_check", "agentic health")),
    }
    return values


def config_checksum(config_repr):
    """Deterministic checksum over a canonical config representation.

    Callers pass a canonical string — recommended:
    ``json.dumps(build_values(...), sort_keys=True)`` — so the checksum tracks the
    *substituted values*, not TOML formatting noise. Returns a short hex digest.
    """
    digest = hashlib.sha256(config_repr.encode("utf-8")).hexdigest()
    return digest[:16]


def canonical_checksum(values):
    """Convenience: checksum of build_values output, excluding stamp fields."""
    payload = {k: v for k, v in values.items()
               if k not in ("contract_template_version", "config_checksum")}
    return config_checksum(json.dumps(payload, sort_keys=True))


_STAMP_FIELDS = ("contract_template_version", "config_checksum")


def stamp(template_text, *, template_version, config_checksum):
    """Fill ONLY the two stamp-header placeholders on an un-rendered template.

    This runs BEFORE :func:`render`: it fills the header's
    ``$contract_template_version`` / ``$config_checksum`` and deliberately leaves
    every other placeholder untouched, so the subsequent strict :func:`render`
    substitutes the rest and raises on anything still missing.

    Fails closed: if the template has lost its stamp header (neither ``$name`` nor
    ``${name}`` form present for a field), raises ``KeyError`` rather than
    silently producing an unstamped contract — the drift the header exists to
    catch.
    """
    missing = [
        name for name in _STAMP_FIELDS
        if ("$" + name) not in template_text and ("${" + name + "}") not in template_text
    ]
    if missing:
        raise KeyError(
            "stamp header placeholder(s) missing from template: " + ", ".join(missing)
        )
    # safe_substitute here is intentional: only the two stamp fields are filled;
    # remaining placeholders survive for the strict render() that must follow.
    return Template(template_text).safe_substitute(
        contract_template_version=template_version,
        config_checksum=config_checksum,
    )


def render_template(name, config, *, project_name):
    """Official end-to-end flow: load -> stamp header -> strict render.

    Stamps the header first (so the strict render does not choke on the two stamp
    fields), then strictly substitutes every remaining placeholder — raising on
    any that stays unfilled. This is the single supported way to render a
    packaged contract template; callers should not hand-inject stamp fields into
    ``values``.
    """
    values = build_values(config, project_name=project_name)
    checksum = canonical_checksum(values)
    stamped = stamp(
        load_template(name),
        template_version=CONTRACT_TEMPLATE_VERSION,
        config_checksum=checksum,
    )
    return render(stamped, values)


def load_template(name):
    """Read a packaged template by filename (e.g. ``AGENTS.md.tmpl``)."""
    if _resources_files is None:  # pragma: no cover
        raise RuntimeError("importlib.resources.files unavailable (need Python >= 3.9)")
    resource = _resources_files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_SUBDIR).joinpath(name)
    return resource.read_text(encoding="utf-8")
