import os
import sys
import glob
import pandas as pd
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sisben_config as cfg  # noqa: E402

cfg.load_dotenv()

# ─── RUTAS LOCALES (configurables; ver .env.example) ──────────────
PUBLISH_DIR = cfg.env("SISBEN_PUBLISH_DIR", str(cfg.output_dir() / "publicacion_local"))
DIR_CSVS = os.path.join(PUBLISH_DIR, "Data_Municipios", "Ultimo_Anio")
DIR_INFORMES = os.path.join(PUBLISH_DIR, "Informes_Municipales")

OUTPUT_DIM_CSV  = cfg.env("SISBEN_DIM_CSV", str(cfg.output_dir() / "dim_descargas_municipios.csv"))

# ─── URLS DE PUBLICACIÓN (opcionales) ─────────────────────────────
# Sin SISBEN_PUBLISH_BASE_URL, la dimensión guarda rutas relativas a la carpeta de publicación.
PUBLISH_BASE_URL = cfg.env("SISBEN_PUBLISH_BASE_URL")
PUBLISH_URL_SUFFIX = cfg.env("SISBEN_PUBLISH_URL_SUFFIX", "")
URL_VARIABLES = cfg.join_url(PUBLISH_BASE_URL, "Variables", "Variables.xlsx", suffix=PUBLISH_URL_SUFFIX)

# Plantilla opcional para la imagen de bandera o escudo de cada municipio, por ejemplo
# "https://<servidor-propio>/escudos/{cod_mpio}.png". Úsela solo con imágenes cuya licencia
# permita reutilizarlas y acredite la fuente. Sin plantilla, la columna queda vacía.
FLAG_URL_TEMPLATE = cfg.env("SISBEN_FLAG_URL_TEMPLATE", "")

def generar_dim():
    archivos = glob.glob(os.path.join(DIR_CSVS, "mpio_*.csv"))
    datos_dim = []
    
    for ruta in archivos:
        nombre_archivo = os.path.basename(ruta)
        # Expected format: mpio_05001_MEDELLIN_ultimo_anio.csv
        partes = nombre_archivo.replace("mpio_", "").replace("_ultimo_anio.csv", "").split("_", 1)
        if len(partes) == 2:
            cod = partes[0]
            nom = partes[1]
        else:
            # Ignorar los archivos viejos que no tienen el nombre del municipio (ej. mpio_05001_ultimo_anio.csv)
            continue
            
        nombre_informe = f"informe_{cod}_{nom}.pdf"
            
        url_csv = cfg.join_url(PUBLISH_BASE_URL, "Data_Municipios", "Ultimo_Anio", nombre_archivo, suffix=PUBLISH_URL_SUFFIX)
        url_informe = cfg.join_url(PUBLISH_BASE_URL, "Informes_Municipales", nombre_informe, suffix=PUBLISH_URL_SUFFIX)
        url_bandera_escudo = FLAG_URL_TEMPLATE.format(cod_mpio=cod) if FLAG_URL_TEMPLATE else ""
        
        datos_dim.append({
            "cod_mpio": cod, 
            "nom_mpio": nom.replace("_", " "), 
            "Url_Descarga": url_csv,
            "Url_Informe": url_informe,
            "Url_Descarga_Variables": URL_VARIABLES,
            "Bandera_escudo": url_bandera_escudo
        })
        
    df_dim = pd.DataFrame(datos_dim).sort_values("cod_mpio")
    
    try:
        df_dim.to_csv(OUTPUT_DIM_CSV, index=False, quoting=csv.QUOTE_ALL)
        print(f"[EXITO] {OUTPUT_DIM_CSV} regenerado con {len(df_dim)} filas")
    except PermissionError:
        print(f"[ERROR] El archivo {OUTPUT_DIM_CSV} esta abierto en otro programa (Power BI o Excel). Por favor cierralo e intenta de nuevo.")

if __name__ == "__main__":
    generar_dim()
