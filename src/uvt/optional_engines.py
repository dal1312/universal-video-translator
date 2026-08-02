from __future__ import annotations


ARGOS_PAIRS = (("en", "it"), ("es", "it"), ("fr", "it"), ("de", "it"))


def install_argos_packages() -> None:
    import argostranslate.package

    argostranslate.package.update_package_index()
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
            raise RuntimeError(f"Pacchetto Argos {source}→{target} non trovato.")
        print(f"Installazione Argos {source}→{target}…", flush=True)
        argostranslate.package.install_from_path(package.download())
