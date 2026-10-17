"""POC (14/10/2026): más evidencia visual en movimiento para un capítulo.

Javier: "los videos son muy planos y es solo texto". Para cada nota que el
guion ya cita (las que Claude abrió y verificó) se arma, sin gastar Claude:

  - una GRABACIÓN de la nota: entra el titular, baja hasta el párrafo del dato
    y lo resalta (Playwright graba la pantalla). Es la prueba en movimiento.
  - sus FOTOS y, si el medio lo permite, sus VIDEOS, según
    plus_datos/reglas_medios.json (opción b de Javier: verde = fotos y video
    con crédito; amarillo = solo fotos; rojo = nada). Siempre con crédito.
Y además tomas de ARCHIVO de Pexels (gratis, con crédito, marcadas como
archivo: son ambiente, no prueba).

Deja todo en C:\\Android_in\\<slug>\\multimedia\\ con un manifest.json que lee
render_plus.py. Corre con el Python del bot (trae Playwright y evidencia.py):

    C:\\dato-mata-gato-bot\\.venv\\Scripts\\python.exe poc_remotion\\scripts\\multimedia.py <slug> [--archivo "consulta" ...]
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

sys.path.insert(0, r"C:\dato-mata-gato-bot\src")
from dato_mata_gato_bot import evidencia  # noqa: E402  (UA y limpieza de anuncios)

POC = Path(__file__).resolve().parents[1]
ANDROID_IN = Path(r"C:\Android_in")
REGLAS = json.loads((POC / "plus_datos" / "reglas_medios.json").read_text(encoding="utf-8"))
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def plano_txt(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def regla(url: str) -> dict:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for dominio, r in REGLAS["medios"].items():
        if host == dominio or host.endswith("." + dominio):
            return r
    return {"nivel": "amarillo", "credito": host}


def claves_de(url: str, guion: dict) -> list[str]:
    """Las palabras del dato que se tomó de esa nota (lo que dice _schema.fuentes
    de esa URL): con ellas se encuentra el párrafo a resaltar."""
    texto = " ".join(str(v) for v in (guion.get("_schema") or {}).get("fuentes", {}).values() if url in str(v))
    texto = texto.replace(url, " ")
    return sorted({w for w in re.findall(r"[a-z0-9ñ]+", plano_txt(texto)) if len(w) >= 5 or w.isdigit()})


_JS_PARRAFOS = """(claves) => {
  const plano = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
  let mejor = null, puntos = 0;
  for (const p of document.querySelectorAll('article p, main p, p')) {
    const crudo = p.innerText || '';
    const t = plano(crudo);
    // Fuera el bloque de autor/foto/fecha (en La Jornada Maya ganaba por las palabras del lugar).
    if (t.length < 80 || /foto:|fotos:|por:\\s|redaccion|\\d{1,2} de [a-z]+ de \\d{4}/.test(t)
        || crudo.split('\\n').length > 3) continue;
    const r = p.getBoundingClientRect();
    if (r.width < 200) continue;
    const n = claves.filter(k => t.includes(k)).length;
    if (n > puntos) { puntos = n; mejor = p; }
  }
  if (!mejor) return null;
  mejor.setAttribute('data-dmg', 'dato');
  return {puntos, texto: (mejor.innerText || '').slice(0, 160)};
}"""

_JS_FOTOS = """() => {
  const fuera = e => e.closest('header, footer, nav, aside, [class*="related"], [class*="relacionad"], [class*="sidebar"]');
  const urls = [];
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) urls.push(og.content);
  for (const img of document.images) {
    if (img.naturalWidth >= 600 && !fuera(img)) urls.push(img.currentSrc || img.src);
  }
  const videos = [];
  for (const v of document.querySelectorAll('video source, video')) if (v.src) videos.push(v.src);
  for (const f of document.querySelectorAll('iframe')) {
    if (/youtube|youtu\\.be|facebook\\.com\\/plugins\\/video|vimeo/.test(f.src)) videos.push(f.src);
  }
  return {fotos: [...new Set(urls)], videos: [...new Set(videos)]};
}"""


ESCALA = 2.5  # ventana de 432 px CSS -> captura de 1080 px de ancho


def capturar_nota(navegador, url: str, claves: list[str], destino: Path) -> dict:
    """Captura ALTA y nítida de la nota (del titular al párrafo del dato) y
    dónde quedó ese párrafo, para que Remotion haga la bajada y el resaltado.

    Primero se grabó la pantalla con Playwright, pero el video sale al tamaño
    de la ventana (432 px) en una esquina con fondo gris (14/10/2026); la
    captura con device_scale_factor sale a 1080 px de ancho y bien nítida.
    Devuelve también las fotos/videos que trae la página.
    """
    ctx = navegador.new_context(viewport={"width": 432, "height": 768}, device_scale_factor=ESCALA,
                                user_agent=NAVEGADOR["User-Agent"], locale="es-MX")
    pagina = ctx.new_page()
    medios, hallado, caja, alto = {"fotos": [], "videos": []}, None, None, 0
    try:
        pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
        pagina.wait_for_timeout(2500)
        for texto in ("Aceptar", "Acepto", "Entendido", "Cerrar", "No, gracias"):
            try:
                pagina.get_by_role("button", name=texto).first.click(timeout=500)
            except Exception:  # noqa: BLE001
                pass
        pagina.evaluate(evidencia._JS_LIMPIAR)
        medios = pagina.evaluate(_JS_FOTOS)
        hallado = pagina.evaluate(_JS_PARRAFOS, claves)
        caja = pagina.evaluate("""() => { const p = document.querySelector('[data-dmg="dato"]');
            if (!p) return null; const r = p.getBoundingClientRect();
            return {x: r.left, y: r.top + window.scrollY, w: r.width, h: r.height}; }""")
        total = pagina.evaluate("document.documentElement.scrollHeight")
        fondo = caja["y"] + caja["h"] + 420 if caja else 1500
        alto = int(min(total, max(fondo, 900), 5200))
        pagina.evaluate("window.scrollTo(0, 0)")
        pagina.wait_for_timeout(400)
        pagina.screenshot(path=str(destino), full_page=True, clip={"x": 0, "y": 0, "width": 432, "height": alto})
    finally:
        pagina.close()
        ctx.close()
    ok = destino.exists() and destino.stat().st_size > 30_000
    escalada = {k: round(v * ESCALA) for k, v in caja.items()} if caja else None
    return {"ok": ok, "parrafo": hallado, "caja": escalada, "alto": round(alto * ESCALA), **medios}


def bajar_fotos(urls: list[str], base: Path, prefijo: str, maximo: int) -> list[str]:
    out = []
    for u in urls:
        if len(out) >= maximo:
            break
        if re.search(r"logo|icon|avatar|banner|publicidad|sprite", u, re.I):
            continue
        try:
            r = requests.get(u, headers=NAVEGADOR, timeout=30)
            r.raise_for_status()
            ruta = base / f"{prefijo}_foto{len(out) + 1}.jpg"
            ruta.write_bytes(r.content)
            im = Image.open(ruta).convert("RGB")
            if im.width < 600 or im.height < 340:
                ruta.unlink()
                continue
            im.save(ruta, quality=90)
            out.append(ruta.name)
        except Exception:  # noqa: BLE001
            continue
    return out


def bajar_video(url: str, destino: Path, segundos: int) -> bool:
    """Solo para medios en verde: los primeros segundos con yt-dlp."""
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "-f", "mp4/best", "--download-sections",
                        f"*0-{segundos}", "-o", str(destino), url], capture_output=True, text=True,
                       creationflags=_SIN_VENTANA)
    return r.returncode == 0 and destino.exists()


def archivo_pexels(consultas: list[str], base: Path) -> list[dict]:
    clave = (os.getenv("DMG_ARCHIVO_PEXELS_KEY") or "").strip()
    if not clave:
        return []
    out = []
    for i, q in enumerate(consultas, start=1):
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": clave}, timeout=30,
                         params={"query": q, "orientation": "portrait", "per_page": 6, "size": "medium"}).json()
        for v in r.get("videos", []):
            archivos = sorted((f for f in v.get("video_files", []) if (f.get("height") or 0) >= 1280
                               and (f.get("width") or 0) < (f.get("height") or 0)), key=lambda f: f["height"])
            if not archivos:
                continue
            crudo = base / f"archivo{i}_crudo.mp4"
            crudo.write_bytes(requests.get(archivos[0]["link"], timeout=120).content)
            final = base / f"archivo{i}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(crudo), "-t", "5", "-an",
                            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", str(final)],
                           check=False, creationflags=_SIN_VENTANA)
            crudo.unlink(missing_ok=True)
            if final.exists():
                out.append({"src": final.name, "consulta": q,
                            "credito": f"Archivo: {v.get('user', {}).get('name', 'Pexels')} / Pexels"})
                break
    return out


def preparar(slug: str, consultas_archivo: list[str]) -> Path:
    from playwright.sync_api import sync_playwright

    guion = json.loads((ANDROID_IN / slug / "guion.json").read_text(encoding="utf-8"))
    base = ANDROID_IN / slug / "multimedia"
    base.mkdir(exist_ok=True)
    manifest = {"notas": {}, "archivo": []}
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for pieza in guion.get("evidencia", []):
            if pieza.get("tipo") not in ("prensa", "documento") or not pieza.get("url") or evidencia._es_pdf(pieza["url"]):
                continue
            r = regla(pieza["url"])
            if r["nivel"] == "rojo":
                continue
            pid = pieza["id"]
            print(f"{pid}: {r['credito']} ({r['nivel']})", flush=True)
            try:
                g = capturar_nota(navegador, pieza["url"], claves_de(pieza["url"], guion), base / f"{pid}_nota.png")
            except Exception as exc:  # noqa: BLE001
                print(f"  sin grabación: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            nota = {"credito": r["credito"], "nivel": r["nivel"],
                    "captura": f"{pid}_nota.png" if g["ok"] else None, "caja": g["caja"], "alto": g["alto"],
                    "parrafo": (g["parrafo"] or {}).get("texto"),
                    "fotos": bajar_fotos(g["fotos"], base, pid, REGLAS["fotos_por_nota"]), "videos": []}
            if r["nivel"] == "verde":
                for k, v in enumerate(g["videos"][:1], start=1):
                    if bajar_video(v, base / f"{pid}_video{k}.mp4", REGLAS["segundos_video"]):
                        nota["videos"].append(f"{pid}_video{k}.mp4")
            manifest["notas"][pid] = nota
            print(f"  captura={'sí' if nota['captura'] else 'no'} párrafo={'sí' if nota['parrafo'] else 'no'} "
                  f"fotos={len(nota['fotos'])} videos={len(nota['videos'])}", flush=True)
        navegador.close()
    manifest["archivo"] = archivo_pexels(consultas_archivo, base)
    print(f"archivo: {len(manifest['archivo'])} tomas de Pexels", flush=True)
    ruta = base / "manifest.json"
    ruta.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(r"C:\illustrated-narrator\.env")
    args = sys.argv[1:]
    slug = args[0]
    consultas = args[args.index("--archivo") + 1:] if "--archivo" in args else []
    print(preparar(slug, consultas))
