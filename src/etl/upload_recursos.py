# -*- coding: utf-8 -*-
import sys
import os
import shutil
import pandas as pd
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sisben_config as cfg  # noqa: E402

cfg.load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")

# Rutas Locales (configurables; ver .env.example)
LOCAL_INFORMES = cfg.env("SISBEN_INFORMES_DIR")          # carpeta con los PDF de informes municipales
LOCAL_DICCIONARIO = cfg.env("SISBEN_DICTIONARY_PATH")    # diccionario de variables (Variables.xlsx)
DIM_CSV = cfg.env("SISBEN_DIM_CSV", str(cfg.output_dir() / "dim_descargas_municipios.csv"))

# Carpeta de publicación (configurable)
PUBLISH_BASE = cfg.env("SISBEN_PUBLISH_DIR", str(cfg.output_dir() / "publicacion_local"))
PUBLISH_RECURSOS = os.path.join(PUBLISH_BASE, "Variables")
PUBLISH_INFORMES = os.path.join(PUBLISH_BASE, "Informes_Municipales")

# URL base de la carpeta de publicación (opcional) y sufijo opcional de descarga
PUBLISH_BASE_URL = cfg.env("SISBEN_PUBLISH_BASE_URL")
PUBLISH_URL_SUFFIX = cfg.env("SISBEN_PUBLISH_URL_SUFFIX", "")

def setup_directories():
    os.makedirs(PUBLISH_RECURSOS, exist_ok=True)
    os.makedirs(PUBLISH_INFORMES, exist_ok=True)

def procesar_diccionario():
    if LOCAL_DICCIONARIO and os.path.exists(LOCAL_DICCIONARIO):
        dest = os.path.join(PUBLISH_RECURSOS, "Variables.xlsx")
        shutil.copy2(LOCAL_DICCIONARIO, dest)
        url = cfg.join_url(PUBLISH_BASE_URL, "Variables", "Variables.xlsx", suffix=PUBLISH_URL_SUFFIX)
        print(f"✓ Diccionario copiado. URL Estática:\n{url}\n")
    else:
        print("❌ No se encontró el diccionario de variables (configure SISBEN_DICTIONARY_PATH)")

def procesar_informes():
    df_dim = pd.read_csv(DIM_CSV, dtype=str)
    
    # Crear un mapeo normalizado de los nombres de los municipios para cruzar con los nombres de los PDFs
    def normalize(text):
        if pd.isna(text): return ""
        text = str(text)
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        return text.lower().strip().replace(" ", "")

    nombres_pdfs = {}
    if LOCAL_INFORMES and os.path.exists(LOCAL_INFORMES):
        for f in os.listdir(LOCAL_INFORMES):
            if f.endswith(".pdf"):
                norm_name = normalize(f.replace(".pdf", ""))
                nombres_pdfs[norm_name] = os.path.join(LOCAL_INFORMES, f)
    
    # Lista para almacenar las URLs de informes
    urls_informes = []
    
    for idx, row in df_dim.iterrows():
        cod = row['cod_mpio']
        nom = row['nom_mpio']
        
        # Omitimos el general 00000
        if cod == '00000':
            urls_informes.append("")
            continue
            
        norm_dim_name = normalize(nom)
        
        # Casos especiales de nombres si es necesario (ej: Santafé -> Santa Fe)
        if norm_dim_name == "santafe_de_antioquia": norm_dim_name = "santafedeantioquia"
        if norm_dim_name == "medellin": norm_dim_name = "distritoespecialdeciencia,tecnologiaeinnovaciondemedellin"
        if norm_dim_name == "turbo": norm_dim_name = "distritoportuario,logistico,industrial,turisticoycomercialdeturbo"
        if norm_dim_name == "carolina": norm_dim_name = "carolinadelprincipe"
        if norm_dim_name == "retiro": norm_dim_name = "elretiro"
        if norm_dim_name == "laceja": norm_dim_name = "lacejadeltambo"
        if norm_dim_name == "penol": norm_dim_name = "elpenol"
        
        pdf_origen = nombres_pdfs.get(norm_dim_name)
        
        if pdf_origen:
            # Nuevo nombre estandarizado: informe_05001_MEDELLIN.pdf
            nuevo_nombre = f"informe_{cod}_{nom.replace(' ', '_')}.pdf"
            pdf_destino = os.path.join(PUBLISH_INFORMES, nuevo_nombre)
            
            shutil.copy2(pdf_origen, pdf_destino)
            url = cfg.join_url(PUBLISH_BASE_URL, "Informes_Municipales", nuevo_nombre, suffix=PUBLISH_URL_SUFFIX)
            urls_informes.append(url)
        else:
            print(f"⚠️ No se encontró PDF local para: {nom} ({norm_dim_name})")
            urls_informes.append("")
            
    # Asignar nueva columna al CSV
    df_dim['Url_Informe'] = urls_informes
    import csv
    df_dim.to_csv(DIM_CSV, index=False, quoting=csv.QUOTE_ALL)
    print("✓ Informes copiados y dim_descargas_municipios.csv actualizado con columna Url_Informe")

if __name__ == "__main__":
    setup_directories()
    procesar_diccionario()
    procesar_informes()
