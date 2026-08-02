#!/usr/bin/env python3
"""Descarga TLP (full-res) secuencia a secuencia desde Google Drive, reintentando
mientras la cuota del propietario esté agotada.

Diseño y por qué:

- **Por secuencia, no el archivo unico de 87 GB.** La cuota de Drive es por fichero, asi
  que 50 tar independientes fallan independientemente: cada pasada puede traerse las que
  hayan liberado cuota y dejar el resto para la siguiente. Exito parcial = secuencias
  usables, no cero.
- **Sin cron.** El bucle vive dentro del proceso (`--daemon`). Editar un crontab ya costo
  un incidente en este repo y un `@reboot` no aporta nada aqui: si la maquina se reinicia,
  se relanza a mano. Una instancia como mucho, garantizada por lockfile con el PID dentro.
- **Idempotente.** Un tar ya extraido se salta; un tar a medias se borra y se reintenta. Se
  puede matar y relanzar en cualquier momento sin perder trabajo ni duplicarlo.
- **Verificacion antes de dar por buena una descarga.** Un descargador puede escribir
  felizmente el HTML de la pagina de error de Drive y salir bien. Un fichero es valido solo
  si `tarfile.is_tarfile` lo acepta y lista miembros.
- **Sin gdown, urllib a pelo en dos pasos.** No porque gdown se equivoque — se comprobo
  2026-08-02 que acierta — sino para quitar una dependencia opaca de en medio y poder
  distinguir a que altura falla. Flujo real: `uc?export=download&id=` sirve *siempre* una
  pagina de confirmacion ("Virus scan warning") con un `uuid` de un solo uso, y la descarga
  esta en `drive.usercontent.google.com/download` con ese uuid. La cuota aparece en el
  segundo paso, como HTML de 2009 bytes con status 200.

  Medido el mismo dia, y es la trampa que casi cuela un falso positivo: una peticion con
  `Range` *acotado* de <= 1 MB se sirve (206, application/octet-stream) aunque la cuota
  este agotada; sin `Range`, con `Range: bytes=0-` abierto, o con un tramo de 4 MB, sale el
  HTML de cuota. O sea que una sonda de "los primeros 4 KB llegan" **no** mide que el
  fichero se pueda descargar. Por eso `download()` pide el fichero entero y no trocea.

Uso:
    python tools/fetch_tlp.py --daemon          # bucle, reintento cada 5 min
    python tools/fetch_tlp.py --status          # que hay hecho y que falta
    python tools/fetch_tlp.py --once            # una pasada y salir
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import sys
import tarfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIST = HERE / "tlp_files.json"
DEST = REPO / "data" / "TLP"

UA = "Mozilla/5.0"
CONFIRM_URL = "https://drive.google.com/uc?export=download&id={fid}"
DOWNLOAD_URL = (
    "https://drive.usercontent.google.com/download"
    "?id={fid}&export=download&confirm=t&uuid={uuid}"
)

LOG = DEST / "_fetch.log"
LOCK = DEST / "_fetch.lock"
STATUS = DEST / "_fetch_status.json"

PASS_SLEEP = 300  # entre pasadas completas
ITEM_SLEEP = 10  # entre ficheros dentro de una pasada, para no martillear Drive
MIN_FREE_GB = 15  # por debajo de esto se para: TLP full son ~87 GB


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}  {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def free_gb() -> float:
    return shutil.disk_usage(DEST if DEST.exists() else REPO).free / 1e9


def entries() -> list[dict]:
    items = json.loads(LIST.read_text())
    for it in items:
        it["name"] = Path(it["path"]).stem  # Alladin.tar -> Alladin
        it["id"] = it["url"].split("id=")[-1]
    return items


def valid_tar(path: Path) -> bool:
    """gdown puede dejar el HTML de error de Drive con exit code 0. Solo cuenta un tar
    que se abre y lista."""
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        if not tarfile.is_tarfile(path):
            return False
        with tarfile.open(path) as tf:
            return bool(tf.getnames())
    except (tarfile.TarError, OSError):
        return False


def is_done(item: dict) -> bool:
    return (DEST / item["name"]).is_dir()


def extract(tar: Path, name: str) -> bool:
    tmp = DEST / f".{name}.extracting"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        with tarfile.open(tar) as tf:
            tf.extractall(tmp)
    except (tarfile.TarError, OSError) as exc:
        log(f"    extraccion fallida ({exc}); se descarta el tar")
        shutil.rmtree(tmp, ignore_errors=True)
        tar.unlink(missing_ok=True)
        return False
    # el tar puede traer la carpeta dentro o los ficheros sueltos
    inner = [p for p in tmp.iterdir()]
    if len(inner) == 1 and inner[0].is_dir():
        inner[0].rename(DEST / name)
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        tmp.rename(DEST / name)
    tar.unlink(missing_ok=True)
    return True


def _open(url: str, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def download(fid: str, out: Path) -> str:
    """Descarga en dos pasos con reanudacion por Range. -> 'ok' | 'quota' | 'error:<que>'

    El `.part` sobrevive entre pasadas a proposito: 529 MB cortados a la mitad se retoman
    donde iban, no desde cero. El uuid es de un solo uso, asi que se pide uno nuevo en cada
    intento aunque se reanude.
    """
    part = out.with_suffix(out.suffix + ".part")

    with _open(CONFIRM_URL.format(fid=fid)) as r:
        page = r.read(65536).decode("utf-8", "replace")
    if "too many users have viewed" in page.lower():
        return "quota"
    m = re.search(r'name="uuid" value="([^"]+)"', page)
    if not m:
        return "error:sin pagina de confirmacion"

    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with _open(DOWNLOAD_URL.format(fid=fid, uuid=m.group(1)), headers) as r:
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            head = r.read(8192).decode("utf-8", "replace").lower()
            return "quota" if "too many users have viewed" in head else "error:html"
        if have and r.status != 206:  # el servidor ignoro el Range: empezar de cero
            have = 0
        with part.open("ab" if have else "wb") as fh:
            shutil.copyfileobj(r, fh, 1 << 20)

    part.rename(out)
    return "ok"


def fetch(item: dict) -> str:
    """-> 'done' | 'quota' | 'error'"""
    name, fid = item["name"], item["id"]
    tar = DEST / item["path"]

    if not valid_tar(tar):
        tar.unlink(missing_ok=True)
        try:
            res = download(fid, tar)
        except Exception as exc:  # red, timeout, 5xx: se reintenta en la pasada siguiente
            res = f"error:{type(exc).__name__}: {exc}"
        if res == "quota":
            return "quota"
        if res != "ok" or not valid_tar(tar):
            log(f"    {name}: descarga invalida ({res})")
            tar.unlink(missing_ok=True)
            return "error"

    size_gb = tar.stat().st_size / 1e9
    if not extract(tar, name):
        return "error"
    log(f"    {name}: OK ({size_gb:.2f} GB) -> data/TLP/{name}/")
    return "done"


def one_pass(items: list[dict]) -> dict:
    tally = {"done": 0, "quota": 0, "error": 0, "skip": 0}
    pending = [it for it in items if not is_done(it)]
    log(f"pasada: {len(items) - len(pending)}/{len(items)} ya estan, {len(pending)} pendientes")

    for it in pending:
        if free_gb() < MIN_FREE_GB:
            log(f"PARADA: quedan {free_gb():.0f} GB libres (< {MIN_FREE_GB})")
            tally["halt"] = True
            return tally
        res = fetch(it)
        tally[res] += 1
        if res != "done":
            time.sleep(ITEM_SLEEP)

    STATUS.write_text(
        json.dumps(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "total": len(items),
                "done": sum(1 for it in items if is_done(it)),
                "last_pass": tally,
                "free_gb": round(free_gb(), 1),
            },
            indent=2,
        )
    )
    return tally


def take_lock() -> None:
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, ProcessLookupError, PermissionError):
            log(f"lockfile huerfano ({LOCK}); se reclama")
        else:
            sys.exit(f"ya hay una instancia viva (pid {pid}); nada que hacer")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(os.getpid()))


def release(*_a) -> None:
    LOCK.unlink(missing_ok=True)
    sys.exit(0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true", help="bucle hasta completar")
    ap.add_argument("--once", action="store_true", help="una pasada y salir")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--sleep", type=int, default=PASS_SLEEP)
    args = ap.parse_args()

    items = entries()
    DEST.mkdir(parents=True, exist_ok=True)

    if args.status:
        done = [it["name"] for it in items if is_done(it)]
        print(f"TLP: {len(done)}/{len(items)} secuencias en {DEST}")
        print(f"libres: {free_gb():.0f} GB")
        if LOCK.exists():
            print(f"demonio: pid {LOCK.read_text().strip()}")
        missing = [it["name"] for it in items if not is_done(it)]
        if missing:
            print("faltan: " + ", ".join(missing))
        return

    take_lock()
    signal.signal(signal.SIGTERM, release)
    signal.signal(signal.SIGINT, release)

    try:
        n = 0
        while True:
            n += 1
            log(f"--- pasada {n} ---")
            tally = one_pass(items)
            log(f"    resultado: {tally}")
            if tally.get("halt"):
                break
            if all(is_done(it) for it in items):
                log("COMPLETO: las 50 secuencias estan en data/TLP/")
                break
            if args.once:
                break
            log(f"    duermo {args.sleep}s")
            time.sleep(args.sleep)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
