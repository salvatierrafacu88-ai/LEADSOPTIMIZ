import streamlit as st
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Scanner de Leads", layout="centered")

st.title("🔍 Google Maps Lead Hunter")
st.markdown("Busca locales que **no tienen web** o solo usan redes sociales.")

# --- ENTRADAS DE USUARIO ---
with st.sidebar:
    st.header("Parámetros")
    rubro = st.text_input("Rubro", placeholder="Ej: Veterinaria")
    depto = st.text_input("Departamento", placeholder="Ej: Paysandú")
    limite = st.slider("Locales a escanear", 5, 40, 15)
    btn_buscar = st.button("🚀 Iniciar Escaneo")

# --- LÓGICA DEL SCRAPER (HEADLESS) ---
def buscar_leads_cloud(rubro, departamento, limite):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # CRÍTICO PARA EL HOSTING
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    exclude_list = ["facebook.com", "instagram.com", "whatsapp.com", "linktr.ee", "twitter.com", "pedidosya.com", "tripadvisor.com"]

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        query = f"{rubro}+en+{departamento}"
        driver.get(f"https://www.google.com/maps/search/{query}")
        time.sleep(5)

        leads_finales = []
        locales = driver.find_elements(By.CLASS_NAME, "hfpxzc") 
        
        progreso = st.progress(0)
        
        for i, local in enumerate(locales[:limite]):
            try:
                progreso.progress((i + 1) / limite)
                driver.execute_script("arguments[0].scrollIntoView();", local)
                local.click()
                time.sleep(2.5)
                
                nombre = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
                
                # Estrellas y Reseñas
                try:
                    estrellas = driver.find_element(By.CSS_SELECTOR, "span.ce9N9c").text
                    resenas = driver.find_element(By.CSS_SELECTOR, "button.HHvVdb").text.replace("(","").replace(")","")
                except:
                    estrellas, resenas = "N/A", "0"

                # Teléfono
                try:
                    telefono = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Copiar el número de teléfono']").text
                except:
                    telefono = "No disponible"

                # Verificación de Web
                prospecto = False
                nota = ""
                try:
                    web_btn = driver.find_element(By.CSS_SELECTOR, "a[aria-label*='Sitio web']")
                    url_real = web_btn.get_attribute("href").lower()
                    if any(red in url_real for red in exclude_list):
                        nota = "Solo redes sociales"
                        prospecto = True
                except:
                    nota = "Sin presencia web"
                    prospecto = True

                if prospecto:
                    leads_finales.append({
                        "Nombre": nombre,
                        "Estrellas": estrellas,
                        "Reseñas": resenas,
                        "Telefono": telefono,
                        "Situacion": nota
                    })
            except:
                continue

        driver.quit()
        return leads_finales
    except Exception as e:
        st.error(f"Error en el servidor: {e}")
        return []

# --- RESULTADOS EN PANTALLA ---
if btn_buscar:
    if rubro and depto:
        with st.spinner("Escaneando Google Maps..."):
            data = buscar_leads_cloud(rubro, depto, limite)
            
        if data:
            st.success(f"¡Se encontraron {len(data)} prospectos!")
            df = pd.DataFrame(data)
            
            # Vista para Celular (Expanders)
            for _, row in df.iterrows():
                with st.expander(f"📍 {row['Nombre']}"):
                    st.write(f"📞 **Tel:** {row['Telefono']}")
                    st.write(f"⭐ **Puntos:** {row['Estrellas']} | 💬 **Reseñas:** {row['Reseñas']}")
                    st.write(f"🚩 **Estado:** {row['Situacion']}")
                    
                    # Botón de llamada rápida para móvil
                    tel_url = row['Telefono'].replace(" ", "").replace("\n", "")
                    st.markdown(f"[📞 Llamar ahora](tel:{tel_url})")

            # Botón de descarga
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Descargar Excel (CSV)", csv, "leads.csv", "text/csv")
        else:
            st.info("No se encontraron prospectos.")
    else:
        st.error("Faltan datos de búsqueda.")

if __name__ == "__main__":
    import os
    # Railway te da el puerto en esta variable. Si no existe, usa el 5000.
    port = int(os.environ.get("PORT", 5000))
    # Es vital que el host sea '0.0.0.0'
    app.run(host='0.0.0.0', port=port)


