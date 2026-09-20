"""Fill weekly_update_template.typ from a JSON content file.

    uv run --frozen python release_updates/fill_update.py content.json out.typ

The content JSON maps each handlebar name to its value:

- ``"date"`` maps to a string, substituted inline.
- every other handlebar maps either to a list of item strings, rendered as a
  Typst numbered list, or to a list of ``[label, [items...]]`` pairs, rendered
  as bold asset groups (which is what the vulnerability cells need).

Two things this exists to get right, both of which are easy to get wrong by
hand and silently wrong in the output:

- **Indentation is taken from the template line the handlebar sits on**, not
  hardcoded. A fixed indent turns the second and subsequent items of a
  column-zero handlebar into a nested sub-list.
- **Every handlebar must be accounted for.** An unknown key, an unused key, or
  a handlebar left in the output is a hard failure rather than a file that
  compiles with a hole in it.
"""

import json
import re
import sys
from pathlib import Path

HANDLEBAR = re.compile(r"^(?P<indent>[ \t]*)\{\{(?P<name>\w+)\}\}[ \t]*$")
INLINE = re.compile(r"\{\{(?P<name>\w+)\}\}")


def render(value: list, indent: str) -> str:
    """Render one handlebar's value as indented Typst markup."""
    lines = []
    for entry in value:
        if isinstance(entry, str):
            lines.append(f"+ {entry}")
            continue
        label, items = entry
        if lines:
            lines.append("")
        lines.append(f"*{label}*")
        lines.extend(f"+ {item}" for item in items)
    return "\n".join(indent + line if line else "" for line in lines).lstrip()


def fill(template: str, content: dict) -> str:
    """Substitute every handlebar in the template, or fail loudly."""
    unused = set(content)
    out = []
    for line in template.splitlines(keepends=True):
        m = HANDLEBAR.match(line.rstrip("\n"))
        if m is None:
            out.append(line)
            continue
        name = m.group("name")
        if name not in content:
            msg = f"no content for handlebar {{{{{name}}}}}"
            raise SystemExit(msg)
        unused.discard(name)
        value = content[name]
        if isinstance(value, str):
            msg = f"{name} is a block handlebar; give it a list"
            raise SystemExit(msg)
        out.append(m.group("indent") + render(value, m.group("indent")) + "\n")

    text = "".join(out)

    # Inline handlebars, e.g. *Week of {{date}}*.
    for name in INLINE.findall(text):
        if name not in content:
            msg = f"no content for inline handlebar {{{{{name}}}}}"
            raise SystemExit(msg)
        unused.discard(name)
        value = content[name]
        if not isinstance(value, str):
            msg = f"{name} is used inline, so it must be a string"
            raise SystemExit(msg)
        text = text.replace("{{" + name + "}}", value)

    if unused:
        msg = f"content keys match no handlebar: {sorted(unused)}"
        raise SystemExit(msg)
    if "{{" in text:
        left = sorted(set(INLINE.findall(text)))
        msg = f"handlebars left in output: {left}"
        raise SystemExit(msg)
    return text


def main() -> int:
    """Fill the template and write the update."""
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    content_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    template = Path(__file__).with_name("weekly_update_template.typ")

    text = fill(
        template.read_text(encoding="utf-8"),
        json.loads(content_path.read_text(encoding="utf-8")),
    )
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    main()
