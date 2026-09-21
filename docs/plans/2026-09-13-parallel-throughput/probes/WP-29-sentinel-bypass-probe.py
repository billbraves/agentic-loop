"""Test codex's claim: a first/last-line sentinel is bypassed by commenting
everything BETWEEN the sentinels."""
import pathlib
T = pathlib.Path("/Users/admin/vibe/wp29-render-scope-decision/src/agentic_loop/templates/WORK_PACKAGE.md.tmpl").read_text(encoding="utf-8")
lines = T.split("\n")
first, last = lines[0], [l for l in lines if l.strip()][-1]
print("first line:", repr(first))
print("last  line:", repr(last))

def crit_sentinel(t):
    ls = t.split("\n")
    nb = [l for l in ls if l.strip()]
    ok = ls[0] == first and nb[-1] == last
    return "GREEN" if ok else "RED"

def attack_inner_comment(t):
    """codex's bypass: keep first+last line byte-identical, comment the middle."""
    ls = t.split("\n")
    nb_idx = [i for i,l in enumerate(ls) if l.strip()]
    lo, hi = nb_idx[1], nb_idx[-2]      # everything strictly between
    return "\n".join(ls[:lo] + ["<!--"] + ls[lo:hi+1] + ["-->"] + ls[hi+1:])

def attack_unclosed_after_first(t):
    """codex's variant: unclosed <!-- right after the first line."""
    ls = t.split("\n")
    return "\n".join([ls[0], "<!--"] + ls[1:])

def attack_edge_prefix(t):
    """The shape the sentinel IS meant to catch."""
    return "<!--\n" + t + "\n-->"

for name, fn in [("inner comment (codex bypass)", attack_inner_comment),
                 ("unclosed after first line", attack_unclosed_after_first),
                 ("edge prefix/suffix wrap", attack_edge_prefix)]:
    mut = fn(T)
    assert mut != T, "no-op guard: %s changed nothing" % name
    print("%-32s sentinel=%s" % (name, crit_sentinel(mut)))
print("%-32s sentinel=%s (must be GREEN)" % ("baseline", crit_sentinel(T)))
