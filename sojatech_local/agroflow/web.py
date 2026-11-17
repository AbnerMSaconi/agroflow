"""Servidor FastAPI das telas /prod e /press."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .fluxo import Fluxo, FluxoOcupado

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB por arquivo


def _pagina_html(nome: str) -> FileResponse:
    caminho = STATIC_DIR / nome
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail=f"Página {nome} não encontrada")
    return FileResponse(caminho)


def criar_app(fluxo: Fluxo | None = None, *, iniciar_fluxo: bool = True) -> FastAPI:
    """Cria a aplicação FastAPI conectada a um motor `Fluxo`."""
    motor = fluxo if fluxo is not None else Fluxo()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if iniciar_fluxo:
            motor.iniciar()
        try:
            yield
        finally:
            if iniciar_fluxo:
                motor.parar()

    app = FastAPI(title="SojaTech AgroFlow", lifespan=lifespan)
    app.state.fluxo = motor

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def raiz():
        return RedirectResponse(url="/prod", status_code=307)

    @app.get("/prod")
    def pagina_prod():
        return _pagina_html("prod.html")

    @app.get("/press")
    def pagina_press():
        return _pagina_html("press.html")

    @app.get("/api/estado")
    def api_estado(desde: int | None = None):
        return motor.estado(desde=desde)

    @app.post("/api/enviar")
    async def api_enviar(
        files: list[UploadFile] | None = File(default=None),
        arquivos: list[UploadFile] | None = File(default=None),
    ):
        recebidos_upload = (files or []) + (arquivos or [])
        if not recebidos_upload:
            return {"recebidos": 0}

        lote: list[tuple[str, bytes]] = []
        for up in recebidos_upload:
            dados = await up.read()
            if len(dados) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Arquivo {up.filename or ''} excede o limite de 25 MB.",
                )
            lote.append((up.filename or "arquivo", dados))

        n = motor.enviar_arquivos(lote)
        return {"recebidos": n}

    @app.post("/api/exemplos")
    def api_exemplos():
        motor.enviar_exemplos()
        return {"status": "ok"}

    @app.post("/api/limpar")
    def api_limpar():
        try:
            motor.limpar()
        except FluxoOcupado as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return {"status": "ok"}

    @app.get("/api/midia/{item_id}")
    def api_midia(item_id: int):
        caminho = motor.caminho_midia(item_id)
        if caminho is None or not caminho.is_file():
            raise HTTPException(status_code=404, detail="Mídia não encontrada")
        return FileResponse(caminho)

    return app


app = criar_app()
