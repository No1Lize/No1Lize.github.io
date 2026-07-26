#!/usr/bin/env python3
"""Match Latin product aliases across spaces, hyphens and slashes."""

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tools" / "refine_venture_research_evidence.py"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    old = '''    if re.fullmatch(r"[A-Za-z0-9.+_-]+", token):
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            )
        )
    return token.casefold() in text.casefold()
'''
    new = '''    if re.fullmatch(r"[A-Za-z0-9.+_ /-]+", token):
        parts = re.findall(r"[A-Za-z0-9]+", token)
        if not parts:
            return False
        pattern = r"[\\s._+/-]+".join(re.escape(part) for part in parts)
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            )
        )
    return token.casefold() in text.casefold()
'''
    if new in text:
        return
    if old not in text:
        raise SystemExit("product alias matcher block not found")
    PATH.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
