"""Tests for the governance-contract template render engine (pure stdlib)."""
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import contract_render as cr  # noqa: E402

_SAMPLE_CFG = {
    "roles": {
        "orchestrator": "claude",
        "developer": ["kimi", "claude"],
        "reviewer": "claude",
        "consultant": "codex",
    },
    "project": {"iterations_dir": "docs/plans"},
    "safety": {
        "forbidden_paths": ["profiles/", ".env", ".context/"],
        "production_paths": ["~/.hermes/profiles/baofu-data"],
    },
    "review_policy": {"min_independence": "strong"},
    "locks": {"owner_source": "env:CLAUDE_CODE_SESSION_ID", "ttl_minutes": 30},
    "quality_gate": {
        "rule": [
            {"match": "packages/engine/**", "run": ["uv run pytest packages/engine/tests -q"]},
        ]
    },
}


def test_render_deterministic_and_strict():
    tpl = "role: $consultant / indep: $min_independence"
    vals = {"consultant": "codex", "min_independence": "strong"}
    out1 = cr.render(tpl, vals)
    out2 = cr.render(tpl, vals)
    assert out1 == out2 == "role: codex / indep: strong"

    with pytest.raises(KeyError):
        cr.render("$missing_placeholder", {})


def test_render_dollar_escape():
    # literal dollar is written as $$ in a template
    assert cr.render("cost is $$5 for $item", {"item": "x"}) == "cost is $5 for x"


def test_build_values_deterministic_and_flattened():
    v1 = cr.build_values(_SAMPLE_CFG, project_name="baofu")
    v2 = cr.build_values(_SAMPLE_CFG, project_name="baofu")
    assert v1 == v2
    # array role flattened to a string
    assert isinstance(v1["developer"], str)
    assert "kimi" in v1["developer"] and "claude" in v1["developer"]
    # every required placeholder present
    for key in cr._REQUIRED_PLACEHOLDERS:
        assert key in v1, "missing placeholder %s" % key
        assert isinstance(v1[key], str)


def test_build_values_defaults_on_minimal_config():
    v = cr.build_values({}, project_name="proj")
    # neutral, tool-agnostic defaults; no baked-in tool names
    assert v["min_independence"] == "strong"
    assert v["iterations_dir"] == "docs/plans"
    assert v["forbidden_paths"] == "(none)"
    # neutral language default when the project does not configure one
    assert v["default_output_language"] == "English"
    for key in cr._REQUIRED_PLACEHOLDERS:
        assert key in v


def test_default_output_language_from_config():
    cfg = {"project": {"default_output_language": "Chinese"}}
    v = cr.build_values(cfg, project_name="proj")
    assert v["default_output_language"] == "Chinese"


def test_command_gate_reads_unified_gate_array():
    cfg = {
        "gate": [
            {
                "name": "tests",
                "kind": "command",
                "stage": "pre_review",
                "rule": [{"match": "skills/**", "run": ["python3 .ci/formula_gate.py"]}],
            }
        ]
    }
    v = cr.build_values(cfg, project_name="proj")
    assert "skills/**" in v["quality_gate_commands"]
    assert "python3 .ci/formula_gate.py" in v["quality_gate_commands"]


def test_command_gate_falls_back_to_legacy_quality_gate():
    cfg = {"quality_gate": {"rule": [{"match": "src/**", "run": ["pytest"]}]}}
    v = cr.build_values(cfg, project_name="proj")
    assert "src/**" in v["quality_gate_commands"]
    assert "pytest" in v["quality_gate_commands"]


def test_script_cmd_placeholders_default_to_cli():
    # de-tooled templates reference $merge_gate_cmd / $health_check_cmd; the
    # engine default is the portable `agentic` CLI entry point (which resolves
    # the real wrapper, main-repo or wheel-bundled).
    v = cr.build_values({}, project_name="proj")
    assert v["merge_gate_cmd"] == "agentic gate"
    assert v["health_check_cmd"] == "agentic health"


def test_script_cmd_placeholders_overridable():
    cfg = {"scripts": {"merge_gate": "tools/gate.sh", "health_check": "tools/hc.sh"}}
    v = cr.build_values(cfg, project_name="proj")
    assert v["merge_gate_cmd"] == "tools/gate.sh"
    assert v["health_check_cmd"] == "tools/hc.sh"


def test_rendered_templates_have_no_tool_proper_names_by_default_config():
    # with a tool-agnostic config, no rendered contract should carry codex/kimi
    tool_agnostic = {
        "roles": {"orchestrator": "A", "developer": "B", "reviewer": "A", "consultant": "C"},
        "project": {"iterations_dir": "docs/plans", "default_output_language": "English"},
        "scripts": {"merge_gate": "scripts/ci/merge_gate.sh",
                    "health_check": "scripts/ci/health.sh"},
    }
    for name in ("AGENTS.md.tmpl", "CLAUDE.md.tmpl", "OPERATING_MODEL.md.tmpl"):
        out = cr.render_template(name, tool_agnostic, project_name="proj")
        assert "codex_merge_gate.sh" not in out
        assert "kimi-health.sh" not in out
        # templates teach the portable CLI, never the in-repo scripts/agentic path
        assert "scripts/agentic/" not in out


def test_config_checksum_deterministic_and_sensitive():
    v = cr.build_values(_SAMPLE_CFG, project_name="baofu")
    c1 = cr.canonical_checksum(v)
    c2 = cr.canonical_checksum(v)
    assert c1 == c2 and len(c1) == 16

    cfg2 = json.loads(json.dumps(_SAMPLE_CFG))
    cfg2["roles"]["consultant"] = "gemini"
    v2 = cr.build_values(cfg2, project_name="baofu")
    assert cr.canonical_checksum(v2) != c1


def test_stamp_fills_only_header_and_preserves_rest():
    # stamp runs on an UN-rendered template: it fills the two header fields and
    # leaves every other placeholder for the strict render() that follows.
    txt = "head: v=$contract_template_version c=$config_checksum body: $consultant"
    out = cr.stamp(txt, template_version="1", config_checksum="abc123")
    assert "v=1 c=abc123" in out
    assert "$consultant" in out  # non-stamp placeholder untouched


def test_stamp_fails_closed_when_header_missing():
    # a template that lost its stamp header must raise, not silently pass through
    with pytest.raises(KeyError):
        cr.stamp("no header here", template_version="1", config_checksum="x")


def test_load_template_all_three():
    for name in ("AGENTS.md.tmpl", "CLAUDE.md.tmpl", "OPERATING_MODEL.md.tmpl"):
        txt = cr.load_template(name)
        assert len(txt) > 0
        assert "agentic-contract:" in txt  # stamp header present


def test_render_template_official_flow_no_unfilled():
    # the supported end-to-end path: load -> stamp header -> strict render,
    # WITHOUT hand-injecting stamp fields into values.
    for name in ("AGENTS.md.tmpl", "CLAUDE.md.tmpl", "OPERATING_MODEL.md.tmpl"):
        out = cr.render_template(name, _SAMPLE_CFG, project_name="baofu")
        assert "agentic-contract: template_version={}".format(cr.CONTRACT_TEMPLATE_VERSION) in out
        # no unfilled placeholder tokens remain (after $$ collapses to $)
        collapsed = out.replace("$$", "")
        assert "${" not in collapsed
        assert "$consultant" not in collapsed and "$config_checksum" not in collapsed


def test_render_template_stamps_deterministic_checksum():
    # same config -> identical rendered output (checksum stable in header)
    a = cr.render_template("AGENTS.md.tmpl", _SAMPLE_CFG, project_name="baofu")
    b = cr.render_template("AGENTS.md.tmpl", _SAMPLE_CFG, project_name="baofu")
    assert a == b


# ---- project name must not follow a linked worktree's directory name --------

def test_project_name_for_linked_worktree_resolves_to_main_repo(tmp_path):
    """A worktree must render the same contract as its main checkout.

    Rendering inside .worktrees/<wp> previously produced
    "# <wp> Agent Operating Contract", which then failed contract check in the
    main repo after the merge (WP-41 rev2 blocker).
    """
    from agentic_loop.contract_cmd import project_name_for

    main = tmp_path / "my_project"
    (main / ".git" / "worktrees" / "wp-x").mkdir(parents=True)
    assert project_name_for(main) == "my_project"

    wt = main / ".worktrees" / "wp-x"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(
        "gitdir: %s\n" % (main / ".git" / "worktrees" / "wp-x"), encoding="utf-8"
    )
    assert project_name_for(wt) == "my_project"


def test_project_name_for_plain_directory_uses_its_own_name(tmp_path):
    from agentic_loop.contract_cmd import project_name_for

    plain = tmp_path / "standalone"
    (plain / ".git").mkdir(parents=True)
    assert project_name_for(plain) == "standalone"


# ---- a table-form role must render as a bare tool name, never a repr --------
#
# `build_values` used to compute the dispatch hint by list-wrapping the role and
# taking [0]. A dict is not a list/tuple, so a table-form binding came back as
# the dict itself and str() wrote a Python repr into AGENTS.md / CLAUDE.md:
#
#   dispatch the developer role (configured tool: {'adapter': 'kimi',
#   'fallback_provider': 'deepseekflash'}) into an isolated worktree; ...
#
# This is load-bearing, not cosmetic: .agentic/config.toml in this repo uses the
# table form, so `agentic contract check` reported CONFIG_DRIFT on three files.

@pytest.mark.parametrize(
    "role,expected",
    [
        ({"adapter": "kimi", "provider": "deepseekflash"}, "kimi"),
        ({"adapter": "kimi", "fallback_provider": "deepseekflash"}, "kimi"),
        ({"adapter": "kimi"}, "kimi"),
        ("kimi", "kimi"),
        (["kimi", "claude"], "kimi"),
        ([], "the developer tool"),
        ({}, "the developer tool"),
    ],
)
def test_dispatch_hint_uses_bare_tool_name_for_every_binding_form(role, expected):
    v = cr.build_values({"roles": {"developer": role}}, project_name="proj")
    hint = v["developer_dispatch_hint"]
    assert "configured tool: {})".format(expected) in hint, hint
    # no structured value ever leaks into contract prose
    assert "{'" not in hint and "adapter" not in hint and "provider" not in hint


def test_rendered_contracts_carry_no_python_repr_for_table_form_developer():
    """Render-level: the emitted files themselves must be free of the struct."""
    cfg = dict(_SAMPLE_CFG)
    cfg["roles"] = dict(
        _SAMPLE_CFG["roles"],
        developer={"adapter": "kimi", "fallback_provider": "deepseekflash"},
    )
    for name in ("AGENTS.md.tmpl", "CLAUDE.md.tmpl", "OPERATING_MODEL.md.tmpl"):
        out = cr.render_template(name, cfg, project_name="proj")
        assert "{'adapter'" not in out, name
        assert "'fallback_provider':" not in out, name
    # positive control: the provider detail is still rendered where it belongs,
    # so a "fix" that scrubs the struct by dropping information fails too
    v = cr.build_values(
        {"roles": {"developer": {"adapter": "kimi", "provider": "deepseekflash"}}},
        project_name="proj",
    )
    assert v["developer"] == "kimi (provider: deepseekflash)"
