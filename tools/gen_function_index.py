"""
Regenerate docs/strategy/09_function_index.md: every class / function / method of the project's
own code, with a clickable file:line link and the first line of its docstring.

    python tools/gen_function_index.py           # rewrite the index
    python tools/gen_function_index.py --check   # exit 1 if the index is out of date (use before a commit)

Run it after every code change, so the report always points at the right lines.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "strategy", "09_function_index.md")

# (section title, files) in reading order
SECTIONS = [
    ("Tournament entry point", ["main.py", "ai_agent.py", "network.py", "game_state.py"]),
    ("Splitter: exact rules and state", ["splitter/rules.py", "splitter/state.py"]),
    ("Splitter: plan generator", ["splitter/planner.py"]),
    ("Splitter: evaluation", ["splitter/evaluate.py"]),
    ("Splitter: search", ["splitter/mcts.py"]),
    ("Splitter: agent and safety net", ["splitter/agent.py"]),
    ("Arena (benchmarking)", ["arena/maps.py", "arena/opponents.py", "arena/referee.py", "arena/run.py",
                              "arena/replay.py", "arena/snapshot.py", "arena/fetch_opponents.py",
                              "arena/history.py"]),
    ("Tools", ["tools/fake_server.py", "tools/teammate_matches.py", "tools/server_match.py",
               "tools/probe_server.py", "tools/play_bot.py",
               "tools/gen_function_index.py", "tools/tune_eval.py", "tools/informative_slots.py"]),
    ("Tests", ["tests/test_rules.py", "tests/test_planner.py", "tests/test_agent.py",
               "tests/test_protocol.py", "tests/test_arena.py"]),
]


def _doc(node) -> str:
    """First line of a node's docstring (escaped for a markdown table)."""
    d = ast.get_docstring(node)
    if not d:
        return ""
    first = d.strip().splitlines()[0].strip()
    return first.replace("|", "\\|")


def _entries(path: str):
    """(name, kind, line, doc) for every top-level function, class and method of a file."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, "function", node.lineno, _doc(node)))
        elif isinstance(node, ast.ClassDef):
            out.append((node.name, "class", node.lineno, _doc(node)))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((f"{node.name}.{sub.name}", "method", sub.lineno, _doc(sub)))
                    # nested helpers (e.g. registry builders) are documented through their parent
    return out


def render() -> str:
    """The whole markdown index."""
    lines = [
        "# 09 · Function index (generated)",
        "",
        "Every class, function and method of our code, with a link to its line.",
        "**Do not edit by hand**: run `python tools/gen_function_index.py` after changing the code.",
        "Chapters 01–08 explain *why*; this page answers *where*.",
        "",
    ]
    for title, files in SECTIONS:
        lines.append(f"## {title}")
        lines.append("")
        for f in files:
            if not os.path.exists(os.path.join(ROOT, f)):
                continue
            lines.append(f"### [{f}](../../{f})")
            lines.append("")
            lines.append("| Name | Kind | Line | Purpose (first docstring line) |")
            lines.append("|---|---|---|---|")
            for name, kind, line, doc in _entries(f):
                lines.append(f"| `{name}` | {kind} | [{line}](../../{f}#L{line}) | {doc} |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


LINK = re.compile(r"\[`?([A-Za-z_][\w.]*)(?:\([^)\]]*\))?`?\]\(\.\./\.\./([\w/.-]+\.py)#L(\d+)\)")


def check_chapter_links() -> list:
    """Every chapter link to a definition (`name` + file + #L line) must point at the line defining `name`."""
    problems = []
    folder = os.path.dirname(OUT)
    for md in sorted(os.listdir(folder)):
        if not md.endswith(".md") or md == os.path.basename(OUT):
            continue
        with open(os.path.join(folder, md), encoding="utf-8") as f:
            text = f.read()
        for name, rel, line in LINK.findall(text):
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                problems.append(f"{md}: {rel} does not exist")
                continue
            with open(path, encoding="utf-8") as f:
                src = f.read().splitlines()
            ident = name.split(".")[-1]
            n = int(line)
            target = src[n - 1] if 0 < n <= len(src) else ""
            if not re.search(rf"\b{re.escape(ident)}\b", target):
                where = [i + 1 for i, s in enumerate(src)
                         if re.match(rf"\s*(def|class)\s+{re.escape(ident)}\b|{re.escape(ident)}\s*=", s)]
                problems.append(f"{md}: {name} -> {rel}#L{line} is wrong (defined at line {where or '?'})")
    return problems


def _definition_lines(src_lines, tree, name: str) -> list:
    """Candidate definition lines of `name` ('Class.method', a function, class, constant or field)."""
    if "." in name:
        cls, meth = name.split(".", 1)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == cls:
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == meth:
                        return [sub.lineno]
                    if isinstance(sub, ast.AnnAssign) and getattr(sub.target, "id", None) == meth:
                        return [sub.lineno]
        name = meth
    pat = re.compile(rf"\s*(?:def|class)\s+{re.escape(name)}\b|\s*{re.escape(name)}\s*[:=]")
    return [i + 1 for i, s in enumerate(src_lines) if pat.match(s)]


def fix_chapter_links() -> int:
    """Move every chapter line link to the current definition line of the function it names."""
    folder = os.path.dirname(OUT)
    fixed = 0
    for md in sorted(os.listdir(folder)):
        if not md.endswith(".md") or md == os.path.basename(OUT):
            continue
        path_md = os.path.join(folder, md)
        with open(path_md, encoding="utf-8") as f:
            text = f.read()

        def repl(m):
            nonlocal fixed
            name, rel, line = m.group(1), m.group(2), int(m.group(3))
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                return m.group(0)
            with open(path, encoding="utf-8") as f:
                src = f.read()
            lines = src.splitlines()
            ident = name.split(".")[-1]
            if 0 < line <= len(lines) and re.search(rf"\b{re.escape(ident)}\b", lines[line - 1]):
                return m.group(0)
            cands = _definition_lines(lines, ast.parse(src), name)
            if not cands:
                return m.group(0)
            best = min(cands, key=lambda c: abs(c - line))
            fixed += 1
            return m.group(0).replace(f"#L{line})", f"#L{best})")

        new = LINK.sub(repl, text)
        if new != text:
            with open(path_md, "w", encoding="utf-8") as f:
                f.write(new)
    return fixed


def main():
    """Write the index, or with --check fail if it (or a chapter's line link) is out of date."""
    if "--fix" in sys.argv:
        print(f"fixed {fix_chapter_links()} chapter line links")
    text = render()
    if "--check" in sys.argv:
        old = ""
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8") as f:
                old = f.read()
        problems = check_chapter_links()
        if old != text:
            problems.insert(0, "09_function_index.md is out of date: run python tools/gen_function_index.py")
        for p in problems:
            print("  !!", p)
        if problems:
            sys.exit(1)
        print("function index and all chapter line links are up to date")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
