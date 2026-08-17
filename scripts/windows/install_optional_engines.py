from __future__ import annotations

import argparse

from uvt.optional_engines import install_argos_packages


def main() -> int:
    parser = argparse.ArgumentParser(description="Installa motori opzionali UVT")
    parser.add_argument("--argos", action="store_true")
    args = parser.parse_args()
    if args.argos:
        install_argos_packages()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
