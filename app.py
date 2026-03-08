import streamlit as st
import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. ESTILOS CSS PARA DISEÑO "APP" ---
st.set_page_config(page_title="Lead Hunter Pro", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #FF4B4B; color: white; }
    .lead-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        border-left: 5px solid #FF4B4B;
    }
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
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INTERFAZ ---
st.title("🎯 Lead Hunter Pro")
st.subheader("Encuentra clientes sin sitio web")

with st.sidebar:
    st.header("Configuración")
    rubro = st.text_input("¿Qué buscas?", placeholder="Ej: Odontólogo")
    depto = st.text_input("¿Dónde?", placeholder="Ej: Montevideo")
    limite = st.slider("Cantidad", 5, 50, 15)
    btn_buscar = st.button("🚀 EMPEZAR ESCANEO")

# --- 3. LÓGICA DEL BOT ---
def scannear_google_maps(rubro, depto, limite):
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    if os.path.exists("/usr/bin/chromium"):
        opts.binary_location = "/usr/bin/chromium"

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(f"https://www.google.com/maps/search/{rubro}+in+{depto}")
        time.sleep(5)

        leads = []
        elementos = driver.find_elements(By.CLASS_NAME, "hfpxzc")
        
        progreso = st.progress(0)
        for i, el in enumerate(elementos[:limite]):
            progreso.progress((i + 1) / limite)
            try:
                el.click()
                time.sleep(2)
                nombre = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
                
                # Intentar sacar teléfono
                try:
                    tel = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Copiar el número de teléfono']").text
                except:
                    tel = "Sin teléfono"

                # Lógica de Prospecto (Si no hay web o es red social)
                es_prospecto = False
                nota = ""
                try:
                    web = driver.find_element(By.CSS_SELECTOR, "a[aria
