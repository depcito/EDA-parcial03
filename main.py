"""Punto de entrada: `python main.py` abre la GUI; `python main.py --cli` imprime el análisis."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Sistema de donaciones post-sismo")
    ap.add_argument("--data", default=str(ROOT / "data"), help="carpeta con los CSV/JSON")
    ap.add_argument("--cli", action="store_true", help="sin GUI: imprime el análisis")
    a = ap.parse_args()
    if a.cli:
        sys.argv = [sys.argv[0], "--data", a.data]
        from donaciones import analysis
        analysis.main()
    else:
        from donaciones import gui
        gui.run(a.data)


if __name__ == "__main__":
    main()
