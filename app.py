import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
from fpdf import FPDF
import os

# --- CONFIGURACIÓN DE ZONA HORARIA VENEZUELA (UTC-4) ---
TZ_VE = pytz.timezone("America/Caracas")

def ahora_ve():
    return datetime.now(TZ_VE)

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Control de Obra | S&SA, C.A.", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3.2em;
        font-weight: 700;
        background-color: #1B4F72;
        color: white;
        border: none;
        transition: 0.2s;
    }
    .stButton>button:hover {
        background-color: #154360;
        color: #EBF5FB;
    }
    .header-box {
        background-color: white;
        padding: 1.2rem;
        border-radius: 12px;
        border-left: 6px solid #1B4F72;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("DB_Nomina_SYSA")

try:
    sh = init_connection()
except Exception as e:
    st.error("⚠️ Error de conexión con Google Sheets. Verifica tus credenciales en Streamlit Secrets.")
    st.stop()

def load_data(sheet_name):
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def append_row(sheet_name, row_values):
    ws = sh.worksheet(sheet_name)
    ws.append_row(row_values)

def limpiar_texto_pdf(texto):
    """Evita errores de codificación en FPDF con tildes o caracteres especiales."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")

# --- ENCABEZADO CORPORATIVO ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo_sysa.png"):
        st.image("logo_sysa.png", width=130)
with col_title:
    st.markdown("""
        <div class="header-box">
            <h2 style="margin:0; color:#1B4F72;">SERVICIOS Y SUMINISTROS ARO, C.A.</h2>
            <p style="margin:0; color:#5D6D7E; font-weight:600;">RIF: J-40858539-1  |  Sistema de Control de Asistencia y Nómina de Obra</p>
        </div>
    """, unsafe_allow_html=True)

# --- NAVEGACIÓN PRINCIPAL ---
menu = st.radio(
    "Seleccione Módulo:",
    [
        "⏱️ Control Diario (Entrada / Salida)",
        "📅 Semanas y Reporte de Pago",
        "👷 Trabajadores y Datos Bancarios",
        "💼 Cargos y Tabulador"
    ],
    horizontal=True
)
st.divider()

# Cargar tablas base desde Google Sheets
df_cargos = load_data("cargos")
df_trabajadores = load_data("trabajadores")
df_semanas = load_data("semanas")
df_asistencia = load_data("asistencia")

# ==============================================================================
# MÓDULO 1: CONTROL DIARIO (ENTRADA / SALIDA)
# ==============================================================================
if menu == "⏱️ Control Diario (Entrada / Salida)":
    if df_semanas.empty or df_trabajadores.empty or df_cargos.empty:
        st.warning("Para comenzar, asegúrate de haber creado al menos un **Cargo**, un **Trabajador** y una **Semana de Nómina**.")
    else:
        semanas_abiertas = df_semanas[df_semanas["estado"] == "Abierta"]
        if semanas_abiertas.empty:
            st.warning("No hay semanas abiertas. Ve al módulo de **Semanas y Reporte de Pago** para crear o abrir una.")
        else:
            semana_sel = st.selectbox("📌 Semana Activa:", semanas_abiertas["nombre_semana"].tolist())
            id_semana_act = semanas_abiertas[semanas_abiertas["nombre_semana"] == semana_sel]["id_semana"].values[0]
            
            dt_ve = ahora_ve()
            fecha_hoy = str(dt_ve.date())

            tab_in, tab_out, tab_lista = st.tabs(["🟢 Registrar ENTRADA", "🔴 Registrar SALIDA", "📋 Lista del Día"])

            # --- PESTAÑA ENTRADA ---
            with tab_in:
                st.subheader(f"Ingreso de Personal ({fecha_hoy})")
                df_trabajadores["label"] = (
                    df_trabajadores["cedula"].astype(str) + " - " +
                    df_trabajadores["nombre"] + " " + df_trabajadores["apellido"]
                )
                trab_sel = st.selectbox("Seleccionar Trabajador:", df_trabajadores["label"].tolist())
                cedula_sel = trab_sel.split(" - ")[0].strip()

                hora_actual = dt_ve.time().replace(second=0, microsecond=0)
                hora_in = st.time_input("Hora de Entrada (puedes editarla si entró más temprano):", value=hora_actual)

                if st.button("✅ GUARDAR ENTRADA"):
                    ya_entro = False
                    if not df_asistencia.empty:
                        filtro = df_asistencia[
                            (df_asistencia["fecha"].astype(str) == fecha_hoy) &
                            (df_asistencia["cedula"].astype(str) == str(cedula_sel)) &
                            (df_asistencia["hora_salida"].astype(str) == "")
                        ]
                        if not filtro.empty:
                            ya_entro = True

                    if ya_entro:
                        st.error("Este trabajador ya tiene una entrada abierta hoy sin registrar salida.")
                    else:
                        nuevo_id = f"REG-{dt_ve.strftime('%Y%m%d%H%M%S')}"
                        append_row("asistencia", [
                            nuevo_id, id_semana_act, fecha_hoy, str(cedula_sel),
                            hora_in.strftime("%H:%M"), "", 0, 0, 0
                        ])
                        st.success(f"Entrada registrada a las **{hora_in.strftime('%H:%M')}** para {trab_sel}")
                        st.rerun()

            # --- PESTAÑA SALIDA ---
            with tab_out:
                st.subheader(f"Salida de Personal en Obra ({fecha_hoy})")
                if df_asistencia.empty:
                    st.info("Aún no hay personal registrado el día de hoy.")
                else:
                    en_obra = df_asistencia[
                        (df_asistencia["fecha"].astype(str) == fecha_hoy) &
                        (df_asistencia["hora_salida"].astype(str) == "")
                    ].copy()

                    if en_obra.empty:
                        st.info("Todo el personal registrado hoy ya marcó su salida.")
                    else:
                        en_obra["cedula_str"] = en_obra["cedula"].astype(str)
                        df_trabajadores["cedula_str"] = df_trabajadores["cedula"].astype(str)
                        en_obra = en_obra.merge(df_trabajadores, on="cedula_str", how="left")
                        en_obra["opcion"] = (
                            en_obra["cedula_str"] + " - " +
                            en_obra["nombre"] + " " + en_obra["apellido"] +
                            " (Entró: " + en_obra["hora_entrada"].astype(str) + ")"
                        )

                        salida_sel = st.selectbox("Personal pendiente por salir:", en_obra["opcion"].tolist())
                        reg_row = en_obra[en_obra["opcion"] == salida_sel].iloc[0]

                        hora_actual_out = ahora_ve().time().replace(second=0, microsecond=0)
                        hora_out = st.time_input("Hora de Salida (por defecto la actual, editable):", value=hora_actual_out)

                        if st.button("🚪 REGISTRAR SALIDA Y CALCULAR PAGO"):
                            fmt = "%H:%M"
                            t_in = datetime.strptime(str(reg_row["hora_entrada"]), fmt)
                            t_out = datetime.strptime(hora_out.strftime(fmt), fmt)
                            diff_horas = (t_out - t_in).total_seconds() / 3600.0

                            if diff_horas <= 0:
                                st.error("La hora de salida debe ser posterior a la hora de entrada.")
                            else:
                                h_normales = min(diff_horas, 8.0)
                                h_extras = max(0.0, diff_horas - 8.0)

                                cargo_match = df_cargos[df_cargos["id_cargo"] == reg_row["id_cargo"]]
                                if cargo_match.empty:
                                    st.error("No se encontró el salario asociado al cargo de este trabajador.")
                                else:
                                    salario_mes = float(cargo_match["salario_mensual"].values[0])
                                    valor_hora = salario_mes / 30.0 / 8.0
                                    pago_dia = round((h_normales * valor_hora) + (h_extras * valor_hora * 1.5), 2)

                                    ws = sh.worksheet("asistencia")
                                    cell = ws.find(reg_row["id_registro"])
                                    ws.update_cell(cell.row, 6, hora_out.strftime(fmt))
                                    ws.update_cell(cell.row, 7, round(h_normales, 2))
                                    ws.update_cell(cell.row, 8, round(h_extras, 2))
                                    ws.update_cell(cell.row, 9, pago_dia)

                                    st.success(
                                        f"Salida guardada ({hora_out.strftime(fmt)}). "
                                        f"Normales: **{h_normales:.2f}h** | Extras (1.5x): **{h_extras:.2f}h** | "
                                        f"Monto Día: **{pago_dia:,.2f}**"
                                    )
                                    st.rerun()

            # --- LISTA DEL DÍA ---
            with tab_lista:
                if not df_asistencia.empty:
                    hoy_df = df_asistencia[df_asistencia["fecha"].astype(str) == fecha_hoy].copy()
                    if not hoy_df.empty:
                        hoy_df["cedula_str"] = hoy_df["cedula"].astype(str)
                        df_trabajadores["cedula_str"] = df_trabajadores["cedula"].astype(str)
                        hoy_df = hoy_df.merge(df_trabajadores[["cedula_str", "nombre", "apellido"]], on="cedula_str", how="left")
                        cols_hoy = ["cedula_str", "nombre", "apellido", "hora_entrada", "hora_salida", "horas_normales", "horas_extras", "monto_pago"]
                        st.dataframe(hoy_df[cols_hoy], use_container_width=True)
                    else:
                        st.info("Sin registros de asistencia para la fecha de hoy.")

# ==============================================================================
# MÓDULO 2: SEMANAS Y REPORTE IMPRIMIBLE PARA ADMINISTRACIÓN
# ==============================================================================
elif menu == "📅 Semanas y Reporte de Pago":
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("➕ Crear Semana de Nómina")
        nom_sem = st.text_input("Nombre (Ej: Semana 46 - Nov 2026)")
        f_ini = st.date_input("Fecha Inicio", value=ahora_ve().date())
        f_fin = st.date_input("Fecha Fin", value=ahora_ve().date())
        if st.button("Crear Semana"):
            if nom_sem.strip():
                id_s = f"SEM-{ahora_ve().strftime('%Y%m%d%H%M%S')}"
                append_row("semanas", [id_s, nom_sem.strip(), str(f_ini), str(f_fin), "Abierta"])
                st.success("Semana creada exitosamente.")
                st.rerun()
            else:
                st.error("Escribe un nombre para identificar la semana.")

    with col2:
        st.subheader("🖨️ Nómina Consolidada para Administración")
        if not df_semanas.empty:
            sem_rep = st.selectbox("Selecciona la Semana a Imprimir:", df_semanas["nombre_semana"].tolist())
            id_sem_rep = df_semanas[df_semanas["nombre_semana"] == sem_rep]["id_semana"].values[0]

            if not df_asistencia.empty:
                asist_sem = df_asistencia[df_asistencia["id_semana"] == id_sem_rep].copy()
                if not asist_sem.empty:
                    asist_sem["cedula"] = asist_sem["cedula"].astype(str)
                    asist_sem["horas_normales"] = pd.to_numeric(asist_sem["horas_normales"], errors="coerce").fillna(0)
                    asist_sem["horas_extras"] = pd.to_numeric(asist_sem["horas_extras"], errors="coerce").fillna(0)
                    asist_sem["monto_pago"] = pd.to_numeric(asist_sem["monto_pago"], errors="coerce").fillna(0)

                    resumen = asist_sem.groupby("cedula", as_index=False).agg({
                        "horas_normales": "sum",
                        "horas_extras": "sum",
                        "monto_pago": "sum"
                    })

                    df_trabajadores["cedula"] = df_trabajadores["cedula"].astype(str)
                    nomina_final = resumen.merge(df_trabajadores, on="cedula", how="left")
                    nomina_final = nomina_final.merge(df_cargos, on="id_cargo", how="left")

                    cols_ver = [
                        "cedula", "nombre", "apellido", "descripcion",
                        "horas_normales", "horas_extras", "monto_pago",
                        "banco", "tipo_cuenta", "numero_cuenta",
                        "titular_nombre", "titular_cedula"
                    ]
                    st.dataframe(nomina_final[cols_ver], use_container_width=True)
                    st.metric("TOTAL GENERAL A PAGAR EN NÓMINA:", f"{nomina_final['monto_pago'].sum():,.2f}")

                    # Generar PDF listo para imprimir en horizontal (A4 Landscape)
                    def generar_pdf(df_pdf, titulo_semana):
                        pdf = FPDF(orientation="L", unit="mm", format="A4")
                        pdf.add_page()
                        if os.path.exists("logo_sysa.png"):
                            pdf.image("logo_sysa.png", x=10, y=8, w=25)
                        pdf.set_font("Arial", "B", 14)
                        pdf.cell(0, 8, limpiar_texto_pdf("SERVICIOS Y SUMINISTROS ARO, C.A."), ln=True, align="C")
                        pdf.set_font("Arial", "", 10)
                        pdf.cell(0, 6, limpiar_texto_pdf(f"RIF: J-40858539-1  |  RELACION DE PAGO DE NOMINA: {titulo_semana}"), ln=True, align="C")
                        pdf.ln(8)

                        headers = ["CI Trab.", "Trabajador", "Cargo", "H.N", "H.E", "Total Pagar", "Banco", "Tipo", "Nro. Cuenta", "Titular Cuenta", "CI Titular"]
                        widths = [19, 36, 25, 12, 12, 23, 28, 17, 40, 42, 21]
                        pdf.set_font("Arial", "B", 7.5)
                        pdf.set_fill_color(27, 79, 114)
                        pdf.set_text_color(255, 255, 255)
                        for h, w in zip(headers, widths):
                            pdf.cell(w, 8, limpiar_texto_pdf(h), border=1, align="C", fill=True)
                        pdf.ln()

                        pdf.set_font("Arial", "", 7.5)
                        pdf.set_text_color(0, 0, 0)
                        for _, r in df_pdf.iterrows():
                            nombre_comp = f"{r['nombre']} {r['apellido']}"[:20]
                            vals = [
                                str(r["cedula"]),
                                nombre_comp,
                                str(r["descripcion"])[:14],
                                f"{r['horas_normales']:.1f}",
                                f"{r['horas_extras']:.1f}",
                                f"{r['monto_pago']:,.2f}",
                                str(r["banco"])[:16],
                                str(r["tipo_cuenta"])[:10],
                                str(r["numero_cuenta"]).replace("'", ""),
                                str(r["titular_nombre"])[:22],
                                str(r["titular_cedula"])
                            ]
                            for v, w in zip(vals, widths):
                                pdf.cell(w, 7, limpiar_texto_pdf(v), border=1, align="C")
                            pdf.ln()

                        pdf.set_font("Arial", "B", 9.5)
                        pdf.cell(sum(widths[:5]), 9, "TOTAL NOMINA SEMANAL:", border=1, align="R")
                        pdf.cell(widths[5], 9, f"{df_pdf['monto_pago'].sum():,.2f}", border=1, align="C")
                        pdf.ln(14)

                        # Espacio para firmas
                        pdf.set_font("Arial", "", 8)
                        pdf.cell(90, 6, "_______________________________", align="C")
                        pdf.cell(90, 6, "_______________________________", align="C")
                        pdf.cell(90, 6, "_______________________________", ln=True, align="C")
                        pdf.cell(90, 5, "Elaborado por (Residente / Control)", align="C")
                        pdf.cell(90, 5, "Aprobado por (Direccion)", align="C")
                        pdf.cell(90, 5, "Pagado por (Administracion)", ln=True, align="C")

                        return bytes(pdf.output())

                    pdf_bytes = generar_pdf(nomina_final, sem_rep)
                    st.download_button(
                        label="📄 DESCARGAR NÓMINA EN PDF (IMPRIMIR / ENVIAR A ADMINISTRADORA)",
                        data=pdf_bytes,
                        file_name=f"Nomina_SYSA_{sem_rep.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.info("No hay registros de asistencia cargados en esta semana.")

# ==============================================================================
# MÓDULO 3: TRABAJADORES Y DATOS BANCARIOS
# ==============================================================================
elif menu == "👷 Trabajadores y Datos Bancarios":
    col_f, col_t = st.columns([1, 2])
    with col_f:
        st.subheader("Registrar Trabajador")
        if df_cargos.empty:
            st.warning("Crea primero los cargos en la pestaña 'Cargos y Tabulador'.")
        else:
            ced = st.text_input("Cédula del Trabajador")
            nom = st.text_input("Nombres del Trabajador")
            ape = st.text_input("Apellidos del Trabajador")
            cargo_nom = st.selectbox("Cargo", df_cargos["descripcion"].tolist())
            id_cargo_sel = df_cargos[df_cargos["descripcion"] == cargo_nom]["id_cargo"].values[0]

            st.markdown("---")
            st.markdown("**💳 Datos Bancarios para Pago**")
            banco = st.selectbox("Banco", [
                "Banco de Venezuela", "Banesco", "Mercantil", "Provincial",
                "BNC", "Bancamiga", "Exterior", "Tesoro", "Bicentenario", "Otro"
            ])
            tipo_cta = st.selectbox("Tipo de Cuenta", ["Corriente", "Ahorro", "Pago Móvil"])
            num_cta = st.text_input("Número de Cuenta (20 dígitos) o Teléfono Pago Móvil")

            es_mismo_titular = st.checkbox("La cuenta está a nombre del mismo trabajador", value=True)

            if es_mismo_titular:
                titular_nom = f"{nom} {ape}".strip()
                titular_ced = ced.strip()
                if titular_nom or titular_ced:
                    st.info(f"Titular asignado: **{titular_nom}** | CI: **{titular_ced}**")
            else:
                st.caption("Ingrese los datos de la persona dueña de la cuenta (ej. esposa, familiar):")
                titular_nom = st.text_input("Nombre Completo del Titular de la Cuenta")
                titular_ced = st.text_input("Cédula del Titular de la Cuenta")

            if st.button("💾 Guardar Trabajador"):
                if ced and nom and ape and titular_nom and titular_ced and num_cta:
                    append_row("trabajadores", [
                        ced.strip(), nom.strip(), ape.strip(), id_cargo_sel,
                        banco, tipo_cta, f"'{num_cta.strip()}",
                        titular_nom.strip(), titular_ced.strip()
                    ])
                    st.success("Trabajador y datos bancarios guardados correctamente.")
                    st.rerun()
                else:
                    st.error("Por favor completa todos los campos del trabajador y del titular bancario.")

    with col_t:
        st.subheader("Directorio de Personal y Cuentas Bancarias")
        st.dataframe(df_trabajadores, use_container_width=True)

# ==============================================================================
# MÓDULO 4: CARGOS Y SALARIOS MENSUALES
# ==============================================================================
elif menu == "💼 Cargos y Tabulador":
    col_c1, col_c2 = st.columns([1, 2])
    with col_c1:
        st.subheader("Nuevo Cargo")
        desc_c = st.text_input("Descripción del Cargo (Ej: Albañil, Ayudante, Maestro)")
        sal_m = st.number_input("Salario Mensual Base", min_value=0.0, step=10.0)
        if sal_m > 0:
            v_hora = sal_m / 30.0 / 8.0
            st.info(f"Valor Hora Normal: **{v_hora:.4f}** | Hora Extra (1.5x): **{v_hora*1.5:.4f}**")
        if st.button("Guardar Cargo"):
            if desc_c and sal_m > 0:
                id_c = f"CRG-{len(df_cargos)+1:03d}"
                append_row("cargos", [id_c, desc_c.strip(), sal_m])
                st.success("Cargo agregado correctamente.")
                st.rerun()
            else:
                st.error("Ingresa la descripción del cargo y un salario mayor a cero.")

    with col_c2:
        st.subheader("Tabulador de Cargos Registrados")
        st.dataframe(df_cargos, use_container_width=True)