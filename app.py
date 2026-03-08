import json
import queue
import threading
import time
import io
import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, Response, send_file
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ─── Configuración de la App ─────────────────────────────────────────────────
app = Flask(__name__)

# Estado global para el escaneo
scan_results = []
scan_running = False
progress_queues = []

EXCLUDE_LIST = [
    "facebook.com", "instagram.com", "whatsapp.com", "linktr.ee",
    "twitter.com", "x.com", "pedidosya.com", "tripadvisor.com",
    "tiktok.com", "youtube.com",
]

# ─── Lógica del Scraper ──────────────────────────────────────────────────────

def _broadcast(event, data):
    """Envía actualizaciones en tiempo real a la interfaz web."""
    msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    for q in progress_queues:
        try:
            q.put_nowait(msg)
        except:
            pass

def _run_scan(rubro, depto, limite):
    global scan_results, scan_running
    scan_running = True
    scan_results = []
    
    _broadcast("status", {"message": "Iniciando navegador...", "progress": 10})
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Obligatorio para Railway
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        query = f"{rubro} en {depto}"
        driver.get(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")
        time.sleep(5)

        # Lógica de scroll básica
        _broadcast("status", {"message": "Buscando locales...", "progress": 30})
        
        locales = driver.find_elements(By.CLASS_NAME, "hfpxzc")
        total_a_escanear = min(len(locales), limite)

        for i in range(total_a_escanear):
            try:
                # Refrescar lista de elementos
                locales = driver.find_elements(By.CLASS_NAME, "hfpxzc")
                if i >= len(locales): break
                
                nombre = locales[i].get_attribute("aria-label")
                locales[i].click()
                time.sleep(2)

                website = "N/A"
                try:
                    web_el = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                    website = web_el.get_attribute("href")
                except:
                    pass

                # Filtrar si no tiene web o es solo redes sociales
                es_red_social = any(domain in website.lower() for domain in EXCLUDE_LIST)
                
                lead = {
                    "Nombre": nombre,
                    "Web": website,
                    "Situacion": "Sin Web" if website == "N/A" else ("Solo Redes Sociales" if es_red_social else "Tiene Web")
                }

                if website == "N/A" or es_red_social:
                    scan_results.append(lead)
                    _broadcast("lead", lead)

                progreso = int(30 + (i / total_a_escanear) * 60)
                _broadcast("status", {"message": f"Analizando: {nombre}", "progress": progreso})

            except Exception:
                continue

        _broadcast("status", {"message": "Escaneo finalizado", "progress": 100})
        _broadcast("done", {"total": len(scan_results)})

    except Exception as e:
        _broadcast("error", {"message": str(e)})
    finally:
        if driver:
            driver.quit()
        scan_running = False

# ─── Rutas de Flask ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_scan():
    global scan_running
    if scan_running:
        return jsonify({"error": "Escaneo ya en curso"}), 400
        
    data = request.json
    rubro = data.get('rubro')
    depto = data.get('depto')
    limite = int(data.get('limite', 15))
    
    threading.Thread(target=_run_scan, args=(rubro, depto, limite)).start()
    return jsonify({"status": "started"})

@app.route('/events')
def events():
    def stream():
        q = queue.Queue()
        progress_queues.append(q)
        try:
            while True:
                yield q.get()
        except GeneratorExit:
            progress_queues.remove(q)
    return Response(stream(), mimetype='text/event-stream')

@app.route('/export')
def export():
    if not scan_results:
        return "No hay datos", 404
    df = pd.DataFrame(scan_results)
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    )

# ─── Configuración para Railway ──────────────────────────────────────────────
if __name__ == "__main__":
    # Railway inyecta el puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
