"""Zip com o que os scripts dos labs precisam, para subir pelo Upload do Cloud Shell.

Em lab de poucos minutos, autenticar no GitHub e clonar o repositório privado custa tempo;
o zip (cerca de 10 MB) leva só os scripts, o pacote agroflow e os conjuntos de teste.

Uso: python scripts/empacotar_lab.py     # grava sojatech_cloud/build/agroflow-lab.zip
"""
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent  # raiz do repositório
ITENS = [
    "sojatech_cloud/scripts/vision_minimo.py",
    "sojatech_cloud/scripts/docai_minimo.py",
    "sojatech_cloud/scripts/lab_a.sh",
    "sojatech_cloud/scripts/lab_b.sh",
    "sojatech_cloud/agroflow",
    "data/leaves/test",
    "data/leaves/campo/teste",
    "data/invoices/holdout_s9",
    "data/invoices/validacao_s8",  # teste rápido do lab B, sem gastar o holdout
]


def main():
    saida = RAIZ / "sojatech_cloud" / "build" / "agroflow-lab.zip"
    saida.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for item in ITENS:
            caminho = RAIZ / item
            if not caminho.exists():
                sys.exit(f"não achei {item}")
            for f in ([caminho] if caminho.is_file() else sorted(caminho.rglob("*"))):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, f.relative_to(RAIZ).as_posix())
                    n += 1
    print(f"{n} arquivos, {saida.stat().st_size / 1e6:.1f} MB em {saida}")


if __name__ == "__main__":
    main()
