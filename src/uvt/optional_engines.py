from __future__ import annotations

import base64
import json
import urllib.request


ARGOS_PAIRS = (("en", "it"), ("es", "en"), ("fr", "en"), ("de", "en"))
ARGOS_INDEX_API = (
    "https://api.github.com/repos/argosopentech/argospm-index/"
    "contents/index.json?ref=main"
)


def _update_argos_index(destination) -> None:
    request = urllib.request.Request(
        ARGOS_INDEX_API,
        headers={"User-Agent": "UniversalVideoTranslator/0.2.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        encoded = "".join(str(payload["content"]).split())
        index = base64.b64decode(encoded, validate=True)
        parsed = json.loads(index)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("indice vuoto")
    except Exception as error:
        raise RuntimeError(
            "Indice Argos non raggiungibile tramite GitHub API. "
            "Controlla firewall, DNS o filtro web."
        ) from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(index)
    temporary.replace(destination)


def install_argos_packages() -> None:
    import argostranslate.package
    import argostranslate.settings

    _update_argos_index(argostranslate.settings.local_package_index)
    available = argostranslate.package.get_available_packages()
    for source, target in ARGOS_PAIRS:
        package = next(
            (
                item
                for item in available
                if item.from_code == source and item.to_code == target
            ),
            None,
        )
        if package is None:
            raise RuntimeError(
                f"Pacchetto Argos {source}->{target} non trovato."
            )
        print(f"Installazione Argos {source}->{target}...", flush=True)
        argostranslate.package.install_from_path(package.download())
