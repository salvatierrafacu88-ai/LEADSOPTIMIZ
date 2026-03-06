"""
Google Maps Lead Scanner — Flask Backend
Scrapes Google Maps for businesses without a real website,
streams progress via SSE, exposes CSV/XLSX export.
"""

import json
import queue
import threading
import time
import io
import os

import pandas as pd
from flask import (
    Flask, render_template, request, jsonify,
    Response, send_file, stream_with_context
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ─── App Setup ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# Global state (for single-user / demo purposes)
scan_results = []          # list of dicts with lead data
scan_running = False       # True while a scan is in progress
progress_queues: list[queue.Queue] = []   # SSE listeners

EXCLUDE_LIST = [
    "facebook.com", "instagram.com", "whatsapp.com", "linktr.ee",
    "twitter.com", "x.com", "pedidosya.com", "tripadvisor.com",
    "tiktok.com", "youtube.com",
]

MAX_LOCALS = 40  # Maximum number of locals to scan


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _broadcast(event: str, data: dict):
    """Push an SSE message to every connected listener."""
    msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    dead = []
    for q in progress_queues:
        try:
            q.put_nowait(msg)
        except queue.Full:
            dead.append(q)
    for q in dead:
        progress_queues.remove(q)


def _build_driver(headless: bool = True):
    """Create and return a Selenium Chrome driver."""
    chrome_opts = Options()
    if headless:
        chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")
    chrome_opts.add_argument("--lang=es")
    chrome_opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_opts)


def _scroll_results_panel(driver, pause: float = 2.0, max_scrolls: int = 5):
    """Scroll the results sidebar to load more items."""
    try:
        scrollable = driver.find_element(
            By.CSS_SELECTOR, "div[role='feed']"
        )
        for _ in range(max_scrolls):
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;",
                scrollable,
            )
            time.sleep(pause)
    except Exception:
        pass  # If the feed panel isn't found, just continue


def _run_scan(rubro: str, departamento: str, headless: bool):
    """Core scraping logic — runs in a background thread."""
    global scan_results, scan_running

    scan_running = True
    scan_results = []
    leads = []

    _broadcast("status", {"message": "Iniciando navegador…", "progress": 0})

    driver = None
    try:
        driver = _build_driver(headless)

        query = f"{rubro} en {departamento}"
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        driver.get(url)
        _broadcast("status", {"message": "Cargando Google Maps…", "progress": 5})
        time.sleep(6)

        # Accept cookies / consent if present
        try:
            consent_btn = driver.find_element(
                By.CSS_SELECTOR, "button[aria-label='Aceptar todo']"
            )
            consent_btn.click()
            time.sleep(2)
        except Exception:
            pass

        # Scroll to load more results
        _broadcast("status", {"message": "Cargando resultados…", "progress": 10})
        _scroll_results_panel(driver)

        locales = driver.find_elements(By.CLASS_NAME, "hfpxzc")
        total = min(len(locales), MAX_LOCALS)

        if total == 0:
            _broadcast("status", {"message": "No se encontraron locales.", "progress": 100})
            scan_running = False
            _broadcast("done", {"results": []})
            return

        _broadcast("status", {
            "message": f"Se encontraron {len(locales)} locales. Escaneando {total}…",
            "progress": 12,
        })

        for idx, local in enumerate(locales[:total]):
            pct = 12 + int((idx + 1) / total * 85)  # 12–97 %
            try:
                driver.execute_script("arguments[0].scrollIntoView();", local)
                local.click()
                time.sleep(3)

                # Name
                nombre = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
                _broadcast("status", {
                    "message": f"Escaneando: {nombre}",
                    "progress": pct,
                    "current": idx + 1,
                    "total": total,
                })

                # Stars
                try:
                    estrellas = driver.find_element(By.CSS_SELECTOR, "span.ceNzKf").get_attribute("aria-label")
                    # Extract the numeric value, e.g. "4,5 estrellas" -> "4.5"
                    estrellas = estrellas.split(" ")[0].replace(",", ".")
                except Exception:
                    try:
                        estrellas = driver.find_element(By.CSS_SELECTOR, "span.ce9N9c").text
                    except Exception:
                        estrellas = "N/A"

                # Review count
                try:
                    resenas_texto = driver.find_element(By.CSS_SELECTOR, "button.HHrUdb, button.HHvVdb").text
                    resenas = (
                        resenas_texto.replace("(", "").replace(")", "")
                        .replace(" reseñas", "").replace(" reseña", "")
                        .replace(".", "").replace(",", "").strip()
                    )
                except Exception:
                    resenas = "0"

                # Phone
                try:
                    telefono = driver.find_element(
                        By.CSS_SELECTOR, "[data-tooltip='Copiar el número de teléfono']"
                    ).text
                except Exception:
                    telefono = "No disponible"

                # Website detection
                nota = ""
                prospecto = False
                try:
                    web_btn = driver.find_element(
                        By.CSS_SELECTOR, "a[aria-label*='Sitio web'], a[data-tooltip='Abrir el sitio web']"
                    )
                    url_real = web_btn.get_attribute("href").lower()
                    if any(red in url_real for red in EXCLUDE_LIST):
                        nota = f"Solo redes ({url_real})"
                        prospecto = True
                except Exception:
                    nota = "Sin presencia web"
                    prospecto = True

                if prospecto:
                    leads.append({
                        "Nombre": nombre,
                        "Estrellas": estrellas,
                        "Reseñas": resenas,
                        "Telefono": telefono,
                        "Situacion": nota,
                    })

            except Exception as e:
                _broadcast("status", {
                    "message": f"Error en local #{idx+1}, continuando…",
                    "progress": pct,
                })
                continue

        # Build final results
        if leads:
            df = pd.DataFrame(leads)
            df["Reseñas"] = pd.to_numeric(df["Reseñas"], errors="coerce").fillna(0).astype(int)
            df = df.sort_values(by="Reseñas", ascending=False)
            scan_results = df.to_dict(orient="records")
        else:
            scan_results = []

        _broadcast("status", {"message": "¡Escaneo completado!", "progress": 100})
        _broadcast("done", {"results": scan_results, "count": len(scan_results)})

    except Exception as e:
        _broadcast("error", {"message": f"Error fatal: {str(e)}"})
    finally:
        if driver:
            driver.quit()
        scan_running = False


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan", methods=["POST"])
def start_scan():
    global scan_running
    if scan_running:
        return jsonify({"error": "Ya hay un escaneo en progreso."}), 409

    data = request.get_json(force=True)
    rubro = data.get("rubro", "").strip()
    departamento = data.get("departamento", "").strip()
    headless = data.get("headless", True)

    if not rubro or not departamento:
        return jsonify({"error": "Rubro y departamento son requeridos."}), 400

    thread = threading.Thread(
        target=_run_scan,
        args=(rubro, departamento, headless),
        daemon=True,
    )
    thread.start()
    return jsonify({"ok": True, "message": "Escaneo iniciado."})


@app.route("/progress")
def progress_stream():
    """SSE endpoint — each client registers its own queue."""
    q: queue.Queue = queue.Queue(maxsize=200)
    progress_queues.append(q)

    def generate():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in progress_queues:
                progress_queues.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/export/<fmt>")
def export(fmt):
    if not scan_results:
        return jsonify({"error": "No hay datos para exportar."}), 404

    # Apply optional minimum reviews filter
    min_reviews = request.args.get("min_reviews", 0, type=int)
    df = pd.DataFrame(scan_results)
    df["Reseñas"] = pd.to_numeric(df["Reseñas"], errors="coerce").fillna(0).astype(int)
    if min_reviews > 0:
        df = df[df["Reseñas"] >= min_reviews]

    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads.csv"},
        )
    elif fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="leads.xlsx",
        )
    else:
        return jsonify({"error": "Formato no soportado. Usa csv o xlsx."}), 400


@app.route("/results")
def get_results():
    """Return current results as JSON (for page reload)."""
    return jsonify({"results": scan_results, "running": scan_running})


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
