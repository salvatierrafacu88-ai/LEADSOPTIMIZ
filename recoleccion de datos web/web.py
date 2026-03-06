import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

def buscar_leads_con_metricas(rubro, departamento):
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    
    query = f"{rubro}+en+{departamento}"
    driver.get(f"https://www.google.com/maps/search/{query}")
    time.sleep(6)

    leads_finales = []
    # Redes que consideramos como "No tiene web propia"
    exclude_list = ["facebook.com", "instagram.com", "whatsapp.com", "linktr.ee", "twitter.com", "pedidosya.com", "tripadvisor.com"]

    locales = driver.find_elements(By.CLASS_NAME, "hfpxzc") 

    for local in locales[:20]: # Aumenté a 20 para tener más datos
        try:
            driver.execute_script("arguments[0].scrollIntoView();", local)
            local.click()
            time.sleep(3)
            
            nombre = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
            
            # --- Extraer Estrellas ---
            try:
                # Busca el texto que dice algo como "4.5 estrellas"
                estrellas = driver.find_element(By.CSS_SELECTOR, "span.ce9N9c").text
            except:
                estrellas = "N/A"

            # --- Extraer Cantidad de Reseñas ---
            try:
                # Busca el botón o span que tiene el número de reseñas
                resenas_texto = driver.find_element(By.CSS_SELECTOR, "button.HHvVdb").text
                # Limpiamos el texto para dejar solo el número (ej: "(150)" -> "150")
                resenas = resenas_texto.replace("(", "").replace(")", "").replace(" reseñas", "")
            except:
                resenas = "0"

            # --- Extraer Teléfono ---
            try:
                telefono = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Copiar el número de teléfono']").text
            except:
                telefono = "No disponible"

            # --- Lógica de Filtrado de Link ---
            nota = ""
            prospecto = False
            
            try:
                web_btn = driver.find_element(By.CSS_SELECTOR, "a[aria-label*='Sitio web']")
                url_real = web_btn.get_attribute("href").lower()
                
                if any(red in url_real for red in exclude_list):
                    nota = f"Solo redes ({url_real})"
                    prospecto = True
            except:
                nota = "Sin presencia web"
                prospecto = True

            if prospecto:
                print(f"🔥 PROSPECTO: {nombre} | ⭐ {estrellas} | 💬 {resenas}")
                leads_finales.append({
                    "Nombre": nombre,
                    "Estrellas": estrellas,
                    "Reseñas": resenas,
                    "Telefono": telefono,
                    "Situacion": nota
                })

        except Exception:
            continue

    driver.quit()
    
    if leads_finales:
        df = pd.DataFrame(leads_finales)
        # Ordenar por más reseñas para atacar primero a los más "importantes"
        df['Reseñas'] = pd.to_numeric(df['Reseñas'], errors='coerce').fillna(0)
        df = df.sort_values(by="Reseñas", ascending=False)
        
        df.to_csv("leads_calificados.csv", index=False, encoding='utf-8-sig')
        print(f"\n✅ ¡Éxito! Archivo 'leads_calificados.csv' creado con {len(leads_finales)} prospectos.")
    else:
        print("\n❌ No se encontraron prospectos.")

# Ejecución
buscar_leads_con_metricas("Veterinarias", "Paysandú")