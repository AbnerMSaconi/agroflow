"""Pipeline local orientado a eventos: espelho do GCS + Cloud Function.

bucket/entrada/**   arquivo novo dispara o processamento (= finalize no GCS)
bucket/processados  arquivos que deram certo
bucket/rejeitados   arquivos inválidos, com o motivo em bucket/rejeitados.log

Uso:
  python scripts/watch_bucket.py           # fica escutando
  python scripts/watch_bucket.py --once    # processa o que já está lá e sai
"""
import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sojatech import config  # noqa: E402
from sojatech.pipeline import ArquivoInvalido, process_file  # noqa: E402

ENTRADA = config.BUCKET / "entrada"
PROCESSADOS = config.BUCKET / "processados"
REJEITADOS = config.BUCKET / "rejeitados"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler(config.BUCKET / "pipeline.log", encoding="utf-8")])
log = logging.getLogger("bucket")


def mover(path: Path, destino: Path):
    alvo = destino / path.relative_to(ENTRADA)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), alvo)


def handle(path: Path):
    if not path.is_file():
        return
    try:
        rows = process_file(path)
        resumo = ", ".join(f"{r.campo}={r.valor} ({r.confidence})" for r in rows
                           if r.tipo != "folha_baseline" and r.confidence is not None)
        log.info("%s -> %s", path.name, resumo)
        mover(path, PROCESSADOS)
    except ArquivoInvalido as e:
        log.warning("REJEITADO %s: %s", path.name, e)
        with open(config.BUCKET / "rejeitados.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{path.name}\t{e}\n")
        mover(path, REJEITADOS)
    except Exception:
        log.exception("erro inesperado em %s (arquivo mantido na entrada)", path.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    for d in (ENTRADA / "notas", ENTRADA / "imagens", PROCESSADOS, REJEITADOS):
        d.mkdir(parents=True, exist_ok=True)

    for p in sorted(ENTRADA.rglob("*")):
        handle(p)
    if args.once:
        return

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class OnCreate(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                time.sleep(0.5)  # espera a cópia terminar
                handle(Path(event.src_path))

    obs = Observer()
    obs.schedule(OnCreate(), str(ENTRADA), recursive=True)
    obs.start()
    log.info("escutando %s (Ctrl+C para sair)", ENTRADA)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


if __name__ == "__main__":
    main()
