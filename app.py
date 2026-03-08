import streamlit as st
import pandas as pd
import time
import os
import io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="Scanner de Leads", layout="wide")

st.title("🔍 Google Maps Lead Hunter")
st.markdown("Extrae negocios de Google Maps que **no tienen sitio web** o solo usan redes sociales.")

# --- PARÁMETROS EN LA BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración de Búsqueda")
    rubro = st.text_input("Rubro", placeholder="Ej: Veterinaria")
    depto = st.text_input("Departamento o Ciudad", placeholder="Ej: Paysandú")
    limite = st.slider("Cantidad de locales a revisar", 5, 50, 15)
    
    st.divider()
    st.info("El escaneo filtrará automáticamente los locales que ya tengan una página web propia.")
    btn_buscar = st.button("🚀 Iniciar Escaneo", use_container_width=True)

# --- LISTA DE EXCLUSIÓN ---
EXCLUDE_LIST = [
    "facebook.com", "instagram.com", "whatsapp.com", "linktr.ee", 
    "twitter.com", "x.com", "tiktok.com", "youtube.com"
]

# --- FUNCIÓN DEL NAVEGADOR ---
def iniciar_escaneo(rubro, depto, limite):
    opts = Options()
    opts.add_argument("--headless")  # Necesario para servidores
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # Intentar detectar Chromium en servidores Linux
    if os.path.exists("/usr/bin/chromium"):
        opts.binary_location = "/usr/bin/chromium"

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        query = f"{rubro} en {depto}"
        driver.get(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")
        time.sleep(5)

        leads = []
        # Obtener los elementos de la lista de resultados
        elementos = driver.find_elements(By.CLASS_NAME, "hfpxzc")
        total = min(len(elementos), limite)
        
        progreso = st.progress(0)
        status_text = st.empty()

        for i in range(total):
            try:
                # Actualizar barra de progreso
                progreso.progress((i + 1) / total)
                
                # Re-obtener elementos para evitar que caduquen
                elementos = driver.find_elements(By.CLASS_NAME, "hfpxzc")
                el = elementos[i]
                nombre = el.get_attribute("aria-label")
                status_text.text(f"Analizando: {nombre}...")
                
                el.click()
                time.sleep(2.5)

                # Verificar sitio web
                web = "N/A"
                es_prospecto = False
                nota = ""

                try:
                    web_btn = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                    web = web_btn.get_attribute("href").lower()
                    if any(red in web for red in EXCLUDE_LIST):
                        nota = "Solo redes sociales"
                        es_prospecto = True
                except:
                    nota = "Sin presencia web"
                    es_prospecto = True

                if es_prospecto:
                    leads.append({
                        "Nombre": nombre,
                        "Sitio Web Detectado": web,
                        "Situación": nota
                    })
            except Exception:
                continue

        driver.quit()
        status_text.text("✅ Escaneo completado.")
        return leads

    except Exception as e:
        st.error(f"Error en el navegador: {e}")
        return []

# --- ACCIÓN DE BÚSQUEDA ---
if btn_buscar:
    if rubro and depto:
        resultados = iniciar_escaneo(rubro, depto, limite)
        
        if resultados:
            st.success(f"¡Se encontraron {len(resultados)} prospectos calificados!")
            df = pd.DataFrame(resultados)
            
            # Mostrar tabla interactiva
            st.dataframe(df, use_container_width=True)
            
            # Botón para descargar CSV
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Leads (CSV)",
                data=csv_data,
                file_name=f"leads_{rubro}_{depto}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No se encontraron locales que cumplan con los criterios de filtrado.")
    else:
        st.error("Por favor, ingresa el rubro y el departamento en la barra lateral.")
