import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. CONFIGURACIÓN Y DISEÑO CSS ---
st.set_page_config(page_title="Lead Hunter Pro", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #FF4B4B; color: white; font-weight: bold; }
    .lead-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        border-left: 5px solid #FF4B4B;
    }
    .lead-card h3 { margin-top: 0; color: #1f1f1f; }
    .call-button {
        display: inline-block;
        padding: 10px 20px;
        background-color: #25D366;
        color: white !important;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        width: 100%;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INTERFAZ ---
st.title("🎯 Lead Hunter Pro")
st.subheader("Encuentra clientes sin presencia web")

with st.sidebar:
    st.header("Configuración")
    rubro = st.text_input("Rubro", placeholder="Ej: Veterinaria")
    depto = st.text_input("Ciudad/Departamento", placeholder="Ej: Paysandú")
    limite = st.slider("Locales a escanear", 5, 50, 15)
    btn_buscar = st.button("🚀 INICIAR ESCANEO")

# --- 3. LÓGICA DEL SCRAPER ---
def scannear_google_maps(rubro, depto, limite):
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # Compatibilidad con servidores Linux
    if os.path.exists("/usr/bin/chromium"):
        opts.binary_location = "/usr/bin/chromium"

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        
        query = f"{rubro} en {depto}"
        driver.get(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")
        time.sleep(5)

        leads = []
        elementos = driver.find_elements(By.CLASS_NAME, "hfpxzc")
        
        progreso = st.progress(0)
        status_text = st.empty()

        for i, el in enumerate(elementos[:limite]):
            progreso.progress((i + 1) / limite)
            try:
                el.click()
                time.sleep(2)
                
                nombre = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
                status_text.text(f"Analizando: {nombre}...")

                # Extraer Teléfono
                try:
                    tel = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Copiar el número de teléfono']").get_attribute("aria-label")
                    tel = tel.replace("Teléfono: ", "")
                except:
                    tel = "No disponible"

                # Lógica de Prospecto (LINEA CORREGIDA AQUÍ)
                es_prospecto = False
                nota = ""
                try:
                    # Aquí estaba el error, ahora la línea está completa:
                    web_el = driver.find_element(By.CSS_SELECTOR, "a[aria-label*='Sitio web']")
                    web_url = web_el.get_attribute("href").lower()
                    
                    redes = ["facebook.com", "instagram.com", "linktr.ee", "whatsapp.com"]
                    if any(red in web_url for red in redes):
                        es_prospecto = True
                        nota = "Solo redes sociales"
                except:
                    es_prospecto = True
                    nota = "Sin sitio web"

                if es_prospecto:
                    leads.append({"nombre": nombre, "tel": tel, "nota": nota})
            except:
                continue
        
        driver.quit()
        status_text.empty()
        return leads
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return []

# --- 4. MOSTRAR RESULTADOS ---
if btn_buscar:
    if rubro and depto:
        with st.spinner("Escaneando Google Maps..."):
            resultados = scannear_google_maps(rubro, depto, limite)
            
        if resultados:
            st.success(f"¡Se encontraron {len(resultados)} prospectos!")
            for lead in resultados:
                # Diseño de tarjeta personalizada
                st.markdown(f"""
                    <div class="lead-card">
                        <h3>📍 {lead['nombre']}</h3>
                        <p>🚩 <b>Estado:</b> {lead['nota']}</p>
                        <p>📞 <b>Teléfono:</b> {lead['tel']}</p>
                        <a href="tel:{lead['tel'].replace(' ', '')}" class="call-button">📞 LLAMAR AHORA</a>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Botón de descarga al final
            df = pd.DataFrame(resultados)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Descargar Excel (CSV)", csv, "leads.csv", "text/csv")
        else:
            st.info("No se hallaron locales que cumplan los requisitos.")
    else:
        st.error("Por favor completa los campos en la barra lateral.")
