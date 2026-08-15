"""WP-02 overlay equivalence: the jst three-crosscut-gate scenario.

The §3.4 overlay feature exists to eliminate *inline duplication*: jst has three
cross-skill gates (formula / collision / reachability) that today are copied into
every skill rule's ``run`` list. After migration they are declared ONCE as an
``apply="overlay"`` gate matching ``skills/**``, with skill-specific rules kept
separate.

These tests pin the equivalence property:

    overlay-declared-once  ≡  original inline copy

for the *execution set* (any changed-path combination under ``skills/**``), and
also pin that the frozen declaration order (overlay gate before the
skill-specific gate, per the §3.4 example) reproduces the inline *order* exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.runner.gate_runner import plan_commands  # noqa: E402

# The three jst cross-cutting gates (§3.4 example).
FORMULA = "python3 .ci/formula_gate.py"
COLLISION = "python3 .ci/collision_gate.py"
REACHABILITY = "python3 .ci/reachability_gate.py"
CROSSCUT = [FORMULA, COLLISION, REACHABILITY]

# Skill-specific commands (kept separate in the overlay config).
SKILL_RULES = [
    ("skills/ad/optimization/**",
     ["python3 -m compileall skills/ad/optimization", "python3 .ci/score.py --routing"]),
    ("skills/ad/diagnosis/**", ["python3 .ci/diag_test.py"]),
    ("skills/trade/journal/**", ["python3 .ci/journal_test.py"]),
]


def _gate(name, apply, rules):
    return {"name": name, "kind": "command", "stage": "pre_review",
            "apply": apply, "blocking": True, "enabled": True, "rule": rules}


def _inline_gate():
    """The old ugly form: crosscut commands copied into every skill rule."""
    rules = []
    for match, skill_cmds in SKILL_RULES:
        rules.append({"match": match, "run": CROSSCUT + skill_cmds})
    return _gate("skills_inline", "first_match", rules)


def _overlay_gates():
    """The migrated form: crosscut declared once, skills kept separate."""
    crosscut = _gate("skills_crosscut", "overlay",
                     [{"match": "skills/**", "run": CROSSCUT}])
    specific = _gate(
        "skill_specific", "first_match",
        [{"match": m, "run": c} for m, c in SKILL_RULES],
    )
    return crosscut, specific


def test_overlay_once_equals_inline_copy_execution_set():
    crosscut, specific = _overlay_gates()
    inline = _inline_gate()

    changed = ["skills/ad/optimization/x.py", "skills/trade/journal/y.py"]
    inline_plan = plan_commands([inline], "pre_review", changed)
    overlay_plan = plan_commands([crosscut, specific], "pre_review", changed)

    assert set(overlay_plan) == set(inline_plan)
    # The crosscut commands run exactly once (global de-dup), never three times.
    for cmd in CROSSCUT:
        assert overlay_plan.count(cmd) == 1


def test_overlay_declared_first_matches_inline_order():
    crosscut, specific = _overlay_gates()
    inline = _inline_gate()

    changed = ["skills/ad/optimization/x.py"]
    assert plan_commands([crosscut, specific], "pre_review", changed) == \
        plan_commands([inline], "pre_review", changed)


def test_overlay_declared_first_matches_inline_order_multiple_skills():
    crosscut, specific = _overlay_gates()
    inline = _inline_gate()

    changed = ["skills/ad/optimization/x.py", "skills/trade/journal/y.py"]
    inline_plan = plan_commands([inline], "pre_review", changed)
    overlay_plan = plan_commands([crosscut, specific], "pre_review", changed)

    assert overlay_plan == inline_plan
    assert overlay_plan == CROSSCUT + [
        "python3 -m compileall skills/ad/optimization",
        "python3 .ci/score.py --routing",
        "python3 .ci/journal_test.py",
    ]


def test_overlay_matches_any_skill_change():
    """Any skills/** change triggers all three crosscut gates once."""
    crosscut, specific = _overlay_gates()
    for changed in [
        "skills/ad/diagnosis/d.py",
        "skills/trade/journal/j.py",
        "skills/unknown/u.py",
    ]:
        plan = plan_commands([crosscut, specific], "pre_review", [changed])
        for cmd in CROSSCUT:
            assert cmd in plan, (changed, cmd, plan)
