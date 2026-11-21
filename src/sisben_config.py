"""
sisben_config.py — configuración compartida de los scripts del pipeline.

Ninguna ruta, URL, usuario ni correo está escrita en el código. Cada valor sale
de (en orden de prioridad):

  1. los argumentos de línea de comandos de cada script,
  2. las variables de entorno,
  3. un archivo `.env` local en la raíz del repositorio (ver `.env.example`),
  4. los valores por defecto, que solo apuntan a archivos públicos de `data/`
     o a la carpeta de salida local `out/`.

El repositorio nunca contiene microdatos: cada instalación configura sus propias rutas.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "out"


def load_dotenv(path: str | os.PathLike | None = None) -> None:
    """Carga pares CLAVE=valor de un archivo .env. Las variables ya definidas no se pisan."""
    env_path = Path(path) if path else REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def env(name: str, default: str | None = None) -> str | None:
    """Devuelve la variable de entorno `name`, o `default` si no existe o está vacía."""
    value = os.environ.get(name, "").strip()
    return value or default


def output_dir() -> Path:
    """Carpeta local para todo lo que produce el pipeline (ignorada por git)."""
    return Path(env("SISBEN_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))


def require(value: str | None, setting: str, hint: str = "") -> str:
    """Termina con un mensaje claro si falta una configuración obligatoria."""
    if not value:
        raise SystemExit(f"Falta la configuración {setting}. {hint}".strip())
    return value


def join_url(base: str | None, *parts: str, suffix: str | None = None) -> str:
    """Arma una URL de publicación a partir de la base configurada. Sin base, devuelve la ruta relativa."""
    rel = "/".join(p.strip("/") for p in parts if p)
    if not base:
        return rel
    url = base.rstrip("/") + "/" + rel
    return url + (suffix or "")
