"""
explainer.py — turns source code into line-by-line plain-English "translations".

This is a rule-based engine, not a full parser: each line is tested against an
ordered list of patterns (most specific first) and the first match wins. A
small bracket-depth stack gives it just enough memory to talk about multi-line
statements (e.g. a dict literal spread across several lines) sensibly.

WHY RULE-BASED FOR A PROTOTYPE
Rules are transparent, free to run, and need no API key — good for a demo.
They only cover the patterns below, though. See README "extend first" notes
for how to swap in (or blend with) an LLM call for open-ended coverage.
"""

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Known imports get hand-written, extra-friendly explanations. Add more here.
# ---------------------------------------------------------------------------
KNOWN_IMPORTS = {
    ("django.db.models", "Q"): "Bring in Django's special `Q` tool so we can write complex search logic using OR conditions.",
    ("django.shortcuts", "render"): "Bring in the `render` helper to combine our database results with an HTML template.",
    ("django.shortcuts", "redirect"): "Bring in the `redirect` helper so we can send the visitor to a different page.",
    ("django.http", "JsonResponse"): "Bring in `JsonResponse` so we can send data back as JSON instead of HTML.",
    ("django.contrib.auth.decorators", "login_required"): "Bring in `login_required` so we can lock a page down to signed-in users only.",
}

FRIENDLY_KEYS = {
    "query": "the search text",
    "results": "the matching records",
    "context": "extra page data",
    "request": "the incoming request",
}

OPERATOR_WORDS = [
    (r"==", " equals "),
    (r"!=", " is not equal to "),
    (r">=", " is at least "),
    (r"<=", " is at most "),
    (r"\bnot\s+in\b", " is not in "),
    (r"\bin\b", " is in "),
    (r">", " is greater than "),
    (r"<", " is less than "),
    (r"\band\b", " and "),
    (r"\bor\b", " or "),
    (r"\bnot\b", " not "),
]


def humanize_expr(expr: str) -> str:
    """Loosely translate comparison/boolean operators into words."""
    text = expr.strip()
    for pattern, word in OPERATOR_WORDS:
        text = re.sub(pattern, word, text)
    return re.sub(r"\s+", " ", text).strip()


def indent_level(raw_line: str) -> int:
    stripped = raw_line.lstrip(" ")
    return (len(raw_line) - len(stripped)) // 4


def bracket_delta(line: str) -> int:
    """Crude open-minus-close bracket count. Ignores brackets inside string
    literals — a known limitation worth fixing if you extend this file."""
    opens = len(re.findall(r"[\(\[\{]", line))
    closes = len(re.findall(r"[\)\]\}]", line))
    return opens - closes


class Ctx:
    __slots__ = ("kind", "meta")

    def __init__(self, kind: str, meta: Optional[dict] = None):
        self.kind = kind
        self.meta = meta or {}


# ---------------------------------------------------------------------------
# Individual line rules. Each is (regex, handler). handler(match, ctx_stack)
# returns (explanation, new_context_kind_or_None).
# ---------------------------------------------------------------------------

def _rule_import_from(m, stack):
    module, names = m.group("module"), m.group("names")
    parts = []
    for raw_name in names.split(","):
        name = raw_name.strip().split(" as ")[0].strip()
        key = (module, name)
        if key in KNOWN_IMPORTS:
            parts.append(KNOWN_IMPORTS[key])
        elif module.startswith("."):
            local = module.lstrip(".") or "this app"
            parts.append(f"Import the `{name}` blueprint from our local `{local}` module so we can use it here.")
        else:
            parts.append(f"Bring in `{name}` from `{module}` so it's available to use in this file.")
    return " ".join(parts), None


def _rule_import_plain(m, stack):
    module, alias = m.group("module"), m.group("alias")
    alias_txt = f" (calling it `{alias}`)" if alias else ""
    return f"Import the `{module}` module{alias_txt} so we can use its features in this file.", None


def _rule_decorator(m, stack):
    return f"Apply the `@{m.group('dec')}` decorator to the function right below — it wraps extra behavior around it.", None


def _rule_class_def(m, stack):
    bases = m.group("bases")
    extends = f", inheriting from `{bases}`" if bases else ""
    return f"Define a new class called `{m.group('name')}`{extends}.", None


def _rule_func_def(m, stack):
    name, args = m.group("name"), m.group("args").strip()
    args_txt = f" (taking in {args})" if args else ""
    if "request" in args:
        trigger = "that runs whenever someone visits this page or makes this request"
    else:
        trigger = "that runs whenever it's called"
    return f"Define a function named `{name}`{args_txt} {trigger}.", None


def _rule_empty_list(m, stack):
    return f"Start with an empty list called `{m.group('var')}` to collect things into.", None


def _rule_empty_dict(m, stack):
    return f"Start with an empty lookup table (dictionary) called `{m.group('var')}`.", None


def _rule_get_default_strip(m, stack):
    var, method, key = m.group("var"), m.group("method"), m.group("key")
    where = "URL parameters" if method == "GET" else "submitted form data"
    return (f"Look at the {where} for `{key}` (what the user typed), default to an empty "
            f"string if it's missing, and trim off any extra spacing. Store the result in `{var}`."), None


def _rule_if_truthy(m, stack):
    return f"Check if `{m.group('cond')}` actually has a value (isn't empty, zero, or None).", None


def _rule_if_expr(m, stack):
    return f"Check if {humanize_expr(m.group('cond'))}.", None


def _rule_elif(m, stack):
    return f"Otherwise, check if {humanize_expr(m.group('cond'))}.", None


def _rule_else(m, stack):
    return "Otherwise (if none of the conditions above were true):", None


def _rule_for(m, stack):
    return f"Loop through `{m.group('iter')}`, one item at a time, calling each one `{m.group('var')}`.", None


def _rule_orm_filter_open(m, stack):
    var, model = m.group("var"), m.group("model")
    return f"Ask the database to filter through every `{model}` record, keeping any that match what follows...", "filter_call"


def _rule_q_or(m, stack):
    a_field = m.group("a").split("__")[0]
    b_field = m.group("b").split("__")[0]
    return (f"...specifically, keep it if the `{a_field}` field OR the `{b_field}` field contains "
            f"the search text (case-insensitive, thanks to `icontains`)."), None


def _rule_distinct_close(m, stack):
    return "Close that filter, then make sure each matching record only shows up once, even if it matched on more than one field.", None


def _rule_return_render_open(m, stack):
    template = m.group("template")
    return f"Send everything over to the `{template}` page to display, along with this data:", "render_dict"


def _rule_return_render_inline(m, stack):
    template = m.group("template")
    return f"Send the results over to the `{template}` page so it can be displayed to the user.", None


def _rule_dict_close(m, stack):
    return "That's the complete set of data handed to the template.", None


def _rule_return(m, stack):
    return f"Send back {humanize_expr(m.group('expr'))} as the result of this function.", None


def _rule_assign_call(m, stack):
    return f"Run `{m.group('call')}` and store whatever it gives back in a variable called `{m.group('var')}`.", None


def _rule_assign_generic(m, stack):
    return f"Store `{m.group('expr')}` in a variable called `{m.group('var')}`.", None


def _rule_bare_call(m, stack):
    return f"Call `{m.group('call')}`.", None


LINE_RULES = [
    (re.compile(r"^from\s+(?P<module>[\w\.]+)\s+import\s+(?P<names>.+)$"), _rule_import_from),
    (re.compile(r"^import\s+(?P<module>[\w\.]+)(?:\s+as\s+(?P<alias>\w+))?$"), _rule_import_plain),
    (re.compile(r"^@(?P<dec>[\w\.\(\)'\",= ]+)$"), _rule_decorator),
    (re.compile(r"^class\s+(?P<name>\w+)\s*(\((?P<bases>.*)\))?\s*:$"), _rule_class_def),
    (re.compile(r"^(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<args>.*)\)\s*(->\s*[\w\[\],\. ]+)?:$"), _rule_func_def),
    (re.compile(r"^(?P<var>\w+)\s*=\s*\[\]$"), _rule_empty_list),
    (re.compile(r"^(?P<var>\w+)\s*=\s*(\{\}|dict\(\))$"), _rule_empty_dict),
    (re.compile(r"^(?P<var>\w+)\s*=\s*request\.(?P<method>GET|POST)\.get\(\s*['\"](?P<key>\w+)['\"]\s*,\s*['\"]{2}\s*\)\.strip\(\)$"), _rule_get_default_strip),
    (re.compile(r"^if\s+(?P<cond>\w+)\s*:$"), _rule_if_truthy),
    (re.compile(r"^if\s+(?P<cond>.+):$"), _rule_if_expr),
    (re.compile(r"^elif\s+(?P<cond>.+):$"), _rule_elif),
    (re.compile(r"^else\s*:$"), _rule_else),
    (re.compile(r"^for\s+(?P<var>\w+)\s+in\s+(?P<iter>.+):$"), _rule_for),
    (re.compile(r"^(?P<var>\w+)\s*=\s*(?P<model>[\w\.]+)\.objects\.filter\(\s*$"), _rule_orm_filter_open),
    (re.compile(r"^Q\((?P<a>[\w_]+)__icontains=\w+\)\s*\|\s*Q\((?P<b>[\w_]+)__icontains=\w+\)$"), _rule_q_or),
    (re.compile(r"^\)\.distinct\(\)$"), _rule_distinct_close),
    (re.compile(r"^return render\(request,\s*['\"](?P<template>[\w\./]+)['\"]\s*,\s*\{$"), _rule_return_render_open),
    (re.compile(r"^return render\(request,\s*['\"](?P<template>[\w\./]+)['\"]\s*,.*\)$"), _rule_return_render_inline),
    (re.compile(r"^\}\)$"), _rule_dict_close),
    (re.compile(r"^return\s+(?P<expr>.+)$"), _rule_return),
    (re.compile(r"^(?P<var>\w+)\s*=\s*(?P<call>[\w\.]+\(.*\))$"), _rule_assign_call),
    (re.compile(r"^(?P<var>[\w\.\[\]'\"]+)\s*=\s*(?P<expr>.+)$"), _rule_assign_generic),
    (re.compile(r"^(?P<call>[\w\.]+\(.*\))\.?$"), _rule_bare_call),
]


def _dict_entry_explanation(line: str) -> Optional[str]:
    m = re.match(r"^['\"](?P<key>\w+)['\"]\s*:\s*(?P<val>.+?),?$", line)
    if not m:
        return None
    key, val = m.group("key"), m.group("val")
    friendly = FRIENDLY_KEYS.get(key, f"the `{key}` value")
    return f"Include `{key}` ({friendly}, currently `{val}`) in the data sent to the template."


def explain_code(code: str) -> List[Dict]:
    raw_lines = code.rstrip("\n").split("\n") if code.strip() else []
    out: List[Dict] = []
    stack: List[Ctx] = []

    for i, raw in enumerate(raw_lines, start=1):
        line = raw.strip()
        entry = {"line": i, "code": raw, "indent": indent_level(raw), "kind": "generic", "explanation": ""}

        if not line:
            entry["kind"] = "blank"
            out.append(entry)
            continue

        if line.startswith("#"):
            entry["kind"] = "comment"
            entry["explanation"] = f"Note to self: {line.lstrip('#').strip()}"
            out.append(entry)
            continue

        # Strip a trailing inline comment before matching (crude: ignores '#'
        # inside string literals, a fine tradeoff for a prototype).
        inline_comment = None
        if "#" in line:
            code_part, _, comment_part = line.partition("#")
            if code_part.strip():
                line = code_part.strip()
                inline_comment = comment_part.strip()

        # Purely-closing lines pop whatever context we opened earlier.
        if re.match(r"^[\)\]\}]+(\.\w+\(\))?,?$", line) and stack:
            ctx = stack.pop()
            trailer = re.search(r"\.(\w+)\(\)$", line)
            base = {
                "render_dict": "That's the complete set of data handed to the template.",
                "filter_call": "Close that filter.",
                "call": "Close that call.",
                "dict": "That's everything in this lookup table.",
                "list": "That's everything in this list.",
            }.get(ctx.kind, "Close that block.")
            if trailer and trailer.group(1) == "distinct":
                base += " Then make sure each matching record only shows up once, even if it matched on more than one field."
            entry["kind"] = "close"
            entry["explanation"] = base
            out.append(entry)
            continue

        # Inside a dict we opened for render(): describe each key/value line.
        if stack and stack[-1].kind == "render_dict":
            dict_expl = _dict_entry_explanation(line)
            if dict_expl:
                entry["kind"] = "dict_entry"
                entry["explanation"] = dict_expl
                out.append(entry)
                continue

        matched = False
        for pattern, handler in LINE_RULES:
            m = pattern.match(line)
            if m:
                explanation, new_ctx = handler(m, stack)
                entry["explanation"] = explanation
                entry["kind"] = handler.__name__.replace("_rule_", "")
                if new_ctx:
                    stack.append(Ctx(new_ctx))
                matched = True
                break

        if not matched:
            delta = bracket_delta(line)
            if delta > 0:
                stack.append(Ctx("call"))
            entry["explanation"] = f"This line runs: `{line}`"
            entry["kind"] = "fallback"

        if inline_comment:
            entry["explanation"] += f" (side note: {inline_comment})"

        out.append(entry)

    return out
