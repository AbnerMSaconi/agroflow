"""Sobe o servidor local das telas /prod e /press.

Uso:
  python scripts/app.py
  python scripts/app.py --porta 8000 --sem-navegador
  python scripts/app.py --host 0.0.0.0 --porta 8000 --sem-navegador
"""
import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agroflow.web import app  # noqa: E402


def _abrir_navegador(url: str) -> None:
    time.sleep(1.0)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Servidor web local do AgroFlow (/prod e /press)")
    ap.add_argument("--host", default="127.0.0.1", help="Endereço de escuta (padrão: 127.0.0.1)")
    ap.add_argument("--porta", type=int, default=8000, help="Porta HTTP (padrão: 8000)")
    ap.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador automaticamente")
    args = ap.parse_args()

    host_exibicao = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    url_prod = f"http://{host_exibicao}:{args.porta}/prod"
    url_press = f"http://{host_exibicao}:{args.porta}/press"

    print(f"AgroFlow Operação (/prod):     {url_prod}")
    print(f"AgroFlow Apresentação (/press): {url_press}")

    if not args.sem_navegador:
        threading.Thread(target=_abrir_navegador, args=(url_prod,), daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.porta)


if __name__ == "__main__":
    main()
