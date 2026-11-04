"""Los mensajes de error del motor y la API tienen traducción al inglés en la interfaz."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAISED = re.compile(r"""(?:raise \w+\(|detail=)f?"([^"{]{6,})""")


def test_every_error_message_is_translated():
    js = (ROOT / "web/static/js/i18n.js").read_text(encoding="utf-8")
    keys = re.findall(r'^    "([^"]+)": "', js[js.index("const ERRORS"):js.index("function error")], re.M)
    assert len(keys) > 30
    missing = set()
    for path in [*(ROOT / "forensix_hash").glob("*.py"), ROOT / "web/server.py"]:
        for message in RAISED.findall(path.read_text(encoding="utf-8")):
            if not any(message.startswith(key) for key in keys) and path.name != "cli.py":
                missing.add(f"{path.name}: {message}")
    assert not missing, sorted(missing)
