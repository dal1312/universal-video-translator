from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from uvt.gui import TranslatorWindow  # noqa: E402
from uvt.settings import SettingsStore  # noqa: E402


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="uvt-smoke-") as temporary:
        window = TranslatorWindow(
            settings_store=SettingsStore(Path(temporary) / "settings.json"),
            check_updates=False,
        )

        def verify() -> None:
            try:
                window.update_idletasks()
                required = (
                    "file_mode_button",
                    "live_mode_button",
                    "document_mode_button",
                    "settings_card",
                    "status_dot",
                )
                missing = [name for name in required if not hasattr(window, name)]
                if missing:
                    failures.append(f"Widget mancanti: {', '.join(missing)}")
                if window.settings_visible:
                    failures.append("Il pannello impostazioni deve partire chiuso")
                window._toggle_settings_panel()
                window.update_idletasks()
                if not window.settings_visible:
                    failures.append("Il pannello impostazioni non si apre")
                window._toggle_settings_panel()
                window.update_idletasks()
                if window.settings_visible:
                    failures.append("Il pannello impostazioni non si chiude")
            except Exception as error:
                failures.append(f"Verifica GUI fallita: {error}")
            finally:
                window._close()

        window.after(1200, verify)
        window.mainloop()
    for failure in failures:
        print(f"ERRORE: {failure}", file=sys.stderr)
    if failures:
        return 1
    print("Smoke GUI Windows: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
