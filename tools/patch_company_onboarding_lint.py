#!/usr/bin/env python3
"""One-time cleanup for the candidate onboarding client component."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "components" / "tracking-company-onboarding.tsx"
text = path.read_text(encoding="utf-8")
text = text.replace('  const [username, setUsername] = useState("");\n', "", 1)
text = text.replace('      setUsername(user.login);\n', "", 1)
text = text.replace('      setUsername("");\n', "", 1)
old = '''  useEffect(() => {\n    const saved = currentToken();\n    if (saved) void load(saved);\n  }, [load]);'''
new = '''  useEffect(() => {\n    const saved = currentToken();\n    if (!saved) return;\n    const timer = window.setTimeout(() => {\n      void load(saved);\n    }, 0);\n    return () => window.clearTimeout(timer);\n  }, [load]);'''
if new not in text:
    if old not in text:
        raise SystemExit("onboarding effect patch target not found")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
