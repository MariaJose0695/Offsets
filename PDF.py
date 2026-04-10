import streamlit as st
import pdfplumber
import re
import pandas as pd
from io import BytesIO


st.title("Offsets Pendientes🔔⚠️")

file = st.file_uploader("Sube PDF Offset 📁 ⬆️", type=["pdf"])

if file:

    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            contenido = page.extract_text()
            if contenido:
                text += contenido + "\n"

    # --- FILTRAR LÍNEAS QUE NO SON OFFSETS ---
    lineas_validas = []
    for linea in text.split("\n"):
        if "Offset: Value" in linea:
            lineas_validas.append(linea)
    text = "\n".join(lineas_validas)

    # ---- BUSCAR REGISTROS ----
    pattern = r"\d{1,2}/\d{1,2}/\d{4}.*?Offset: Value \(-?\d+\.?\d*\s*->\s*-?\d+\.?\d*\).*?(?=\n|$)"
    registros = re.findall(pattern, text)

    # ---- BUSCAR REGISTROS (versión línea a línea, más robusta) ----
    rows = []

    # Dividimos por líneas (ya filtradas por "Offset: Value")
    lineas = [l.strip() for l in text.splitlines() if l.strip()]
    #st.write(f"🔎 Líneas con 'Offset: Value' encontradas: {len(lineas)}")
    #if len(lineas) > 10:
    #    st.write("Primeras 10 líneas (para debug):")
    #    st.write(lineas[:10])

    # Regex robusto por línea
    regex_linea = (
        r"(\d{1,2}/\d{1,2}/\d{4})\s+"            # Fecha
        r"(\d{1,2}:\d{2}:\d{2})\s*([AP]M)\s+"    # Hora + AM/PM
        r"([A-Za-z0-9\-_]+)\s+"                  # Entity (acepta letras, números, _, -)
        r"([A-Za-z0-9\-_]+)\s*"                  # Characteristic (X, Y, Z, Y-nom, Z_nom, etc)
        r".*?"                                   # cualquier texto intermedio (no codicioso)
        r"Offset\s*:\s*Value\s*"                 # literal Offset: Value (espacios tolerantes)
        r"\(\s*(-?\d+\.?\d*)\s*->\s*(-?\d+\.?\d*)\s*\)"  # old -> new
    )

    matched_count = 0
    for linea in lineas:
        m = re.search(regex_linea, linea, flags=re.IGNORECASE)
        if m:
            matched_count += 1
            fecha = m.group(1)
            hora = f"{m.group(2)} {m.group(3)}"
            entity = m.group(4)
            characteristic = m.group(5)
            old = float(m.group(6))
            new = float(m.group(7))

            # Intentamos capturar el usuario al final (si existe)
            # ej: "... Offset: Value (a -> b) CESAR"
            parts = linea.rsplit(")", 1)
            user = ""
            if len(parts) == 2:
                posible_user = parts[1].strip()
                if posible_user:
                    # el usuario normalmente es la última palabra o la última columna
                    user = posible_user.split()[-1]
            if not user:
                user = ""  # fallback vacío si no lo encontramos

            rows.append([fecha, hora, entity, characteristic, old, new, user])

    #st.write(f"✅ Líneas que matchearon correctamente: {matched_count}")


    # ---- DATAFRAME BASE ----
    df = pd.DataFrame(rows, columns=[
        "Fecha", "Hora", "Entity", "Characteristic", "Old", "New", "User"
    ])

    st.write("📄 Datos del PDF:")
    st.dataframe(df)

    # ---- CALCULAR PENDIENTE REAL POR ENTITY + CHARACTERISTIC ----
    df['Datetime'] = pd.to_datetime(df['Fecha'] + ' ' + df['Hora'], errors='coerce')
    df = df.sort_values(['Entity', 'Characteristic', 'Datetime']).reset_index(drop=True)
    
    pendiente_real = []
    
    # Agrupamos por Entity **y** por eje (Characteristic)
    for (ent, eje), group in df.groupby(['Entity', 'Characteristic']):
        group = group.sort_values('Datetime')
    
        old_inicial = group.iloc[0]['Old']
        new_final = group.iloc[-1]['New']
        fecha_final = group.iloc[-1]['Fecha']
        hora_final = group.iloc[-1]['Hora']
        diferencia = abs(old_inicial - new_final)
    
        pendiente_real.append({
            'Entity': ent,
            'Characteristic': eje,
            'Fecha_final': fecha_final,
            'Hora_final': hora_final,
            'Old_inicial': old_inicial,
            'New_final': new_final,
            'Diferencia_pendiente': diferencia
        })
    
    df_pendiente_real = pd.DataFrame(pendiente_real)

    st.subheader("❗ Offsets Pendientes de Regresar")
    st.dataframe(df_pendiente_real)

    # ---- EXPORTAR A EXCEL ----
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
        df_pendiente_real.to_excel(writer, index=False, sheet_name='Pendientes')

    st.download_button(
        label="📥 Descargar Excel",
        data=output.getvalue(),
        file_name="offsets_pendientes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
