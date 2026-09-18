import pathlib,re,importlib.util
exec(open("/Users/admin/.claude/jobs/8a8bf01e/tmp/probe-wp25-b38/probe3.py").read().split('IND="The following')[0])
IND="The following are non-binding historical examples only:"
# residual-escape hunt: keep leg(i) skeleton AND leg(ii) prev-unit text identical
ESC=[
 ("X1 inducement folded into an EARLIER bullet of the same section",
  lambda t:t.replace("- Freeze product scope and acceptance criteria before dispatch.",
                     "- Freeze product scope and acceptance criteria before dispatch.\n  "+IND)),
 ("X2 inducement into the h2 heading line itself",
  lambda t:t.replace("## Dispatch","## Dispatch (non-binding historical examples)",1)),
 ("X3 inducement in a DIFFERENT section (## Session start)",
  lambda t:t.replace("## Session start","## Session start\n\n"+IND,1)),
 ("X4 inducement in the document preamble",
  lambda t:t.replace("# Orchestrator Protocol","# Orchestrator Protocol\n\n"+IND,1)),
 ("X5 replace prev bullet wholesale with same-kind bullet carrying inducement",
  lambda t:t.replace("- After every background developer dispatch, start a Monitor that calls",
                     "- "+IND+" After every background developer dispatch, start a Monitor that calls")),
]
print("baseline R7 = %s\n"%crit_R7(T))
for n,f in ESC:
    mut=f(T); assert mut!=T,"no-op guard: %s"%n
    got=crit_R7(mut)
    print("%-62s R7=%-18s %s"%(n,got,"ESCAPES" if got=="GREEN" else "caught"))
