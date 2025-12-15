import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client, Client
import datetime

# ==============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Gestión Médica - Dr. Moraga",
    page_icon="👨‍⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para un look médico profesional
st.markdown("""
<style>
    /* Tarjetas de Métricas */
    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #2C3E50;
    }
    .metric-label {
        font-size: 14px;
        color: #7F8C8D;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    /* Encabezados */
    h1, h2, h3 {
        color: #2E86C1;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXIÓN A SUPABASE
# ==============================================================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Error de conexión: {str(e)}")
        st.stop()

supabase = init_connection()

# ==============================================================================
# 3. CARGA Y PROCESAMIENTO DE DATOS
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    # Traemos todas las transacciones ordenadas por fecha
    # FIX: Aumentamos el rango a 7000 para traer todo el historial
    response = supabase.table("transactions")\
        .select("*", count="exact")\
        .order("payment_date", desc=True)\
        .range(0, 7000)\
        .execute()
        
    df = pd.DataFrame(response.data)
    
    if df.empty:
        return df

    # Conversión de tipos
    # errors='coerce' convertirá fechas inválidas a NaT.
    df['payment_date'] = pd.to_datetime(df['payment_date'], errors='coerce')
    df['event_date'] = pd.to_datetime(df['event_date'], errors='coerce')
    df['net_amount'] = pd.to_numeric(df['net_amount'], errors='coerce').fillna(0)
    
    # Manejo de fechas nulas para evitar errores
    if df['payment_date'].isna().any():
        df['payment_date'] = df['payment_date'].fillna(pd.Timestamp.now())

    # Columnas derivadas
    df['Mes'] = df['payment_date'].dt.strftime('%Y-%m')
    
    # Año como entero
    df['Año'] = df['payment_date'].dt.year.astype(int)
    
    df['Origen_Label'] = df['source'].map({
        'CAS_A': 'Alemana Ambulatorio',
        'CAS_H': 'Alemana Hospitalario',
        'AMCA': 'AMCA (Sociedad/Privado)'
    }).fillna(df['source'])
    
    # Limpieza de descripciones para gráficos
    df['Glosa_Corta'] = df['description'].fillna('Sin Descripción').apply(lambda x: str(x)[:30] + '...' if len(str(x)) > 30 else str(x))
    
    return df

df = load_data()

# ==============================================================================
# 4. BARRA LATERAL (FILTROS)
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3774/3774299.png", width=80)
    st.title("Filtros")
    
    if not df.empty:
        # Filtro Año
        years = sorted(df['Año'].unique(), reverse=True)
        # Seleccionamos el primer año disponible por defecto (el más reciente)
        default_idx = 0 
        selected_year = st.selectbox("📅 Año Fiscal", years, index=default_idx, format_func=lambda x: str(x))
        
        # Filtro Mes (Multiselect)
        months_available = sorted(df[df['Año'] == selected_year]['Mes'].unique(), reverse=True)
        selected_months = st.multiselect("📆 Meses (Opcional)", months_available, default=[])
        
        # Filtro Origen
        sources = df['Origen_Label'].unique()
        selected_sources = st.multiselect("🏥 Institución", sources, default=sources)
        
        # Aplicar Filtros
        df_filtered = df[
            (df['Año'] == selected_year) & 
            (df['Origen_Label'].isin(selected_sources))
        ]
        
        if selected_months:
            df_filtered = df_filtered[df_filtered['Mes'].isin(selected_months)]
    else:
        st.warning("No hay datos disponibles.")
        st.stop()

    st.markdown("---")
    st.caption("Última actualización: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))

# ==============================================================================
# 5. PÁGINA PRINCIPAL
# ==============================================================================

# --- HEADER Y KPIS ---
st.title(f"Resumen Financiero {selected_year}")

col1, col2, col3, col4 = st.columns(4)

total_ingreso = df_filtered['net_amount'].sum()
total_tx = len(df_filtered)
ticket_promedio = total_ingreso / total_tx if total_tx > 0 else 0
# Calcular mejor mes
ingreso_mensual = df_filtered.groupby('Mes')['net_amount'].sum()
mejor_mes = ingreso_mensual.idxmax() if not ingreso_mensual.empty else "-"
mejor_mes_monto = ingreso_mensual.max() if not ingreso_mensual.empty else 0

# Función auxiliar para renderizar tarjeta HTML
def metric_card(label, value, prefix="$"):
    return f"""
    <div class="metric-container">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{prefix} {value}</div>
    </div>
    """

with col1:
    st.markdown(metric_card("Ingreso Total Líquido", f"{total_ingreso:,.0f}".replace(",", "."), "$"), unsafe_allow_html=True)
with col2:
    st.markdown(metric_card("Procedimientos Pagados", f"{total_tx}", "#"), unsafe_allow_html=True)
with col3:
    st.markdown(metric_card("Valor Promedio x Prestación", f"{ticket_promedio:,.0f}".replace(",", "."), "$"), unsafe_allow_html=True)
with col4:
    st.markdown(metric_card(f"Mejor Mes ({mejor_mes})", f"{mejor_mes_monto:,.0f}".replace(",", "."), "$"), unsafe_allow_html=True)

st.markdown("---")

# --- GRÁFICOS PRINCIPALES ---
col_izq, col_der = st.columns([2, 1])

with col_izq:
    st.subheader("💰 Evolución de Ingresos Mensuales")
    
    chart_mensual = alt.Chart(df_filtered).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        x=alt.X('Mes:O', title='Mes'),
        y=alt.Y('sum(net_amount):Q', title='Monto Líquido ($)', axis=alt.Axis(format="$,.0f")), 
        color=alt.Color('Origen_Label:N', legend=alt.Legend(title="Origen", orient="top")),
        tooltip=[
            alt.Tooltip('Mes', title='Periodo'),
            alt.Tooltip('Origen_Label', title='Fuente'),
            alt.Tooltip('sum(net_amount)', title='Monto', format="$,.0f")
        ]
    ).properties(height=350)
    
    st.altair_chart(chart_mensual, use_container_width=True)

with col_der:
    st.subheader("🏥 Distribución por Origen")
    
    # Datos para el gráfico de torta
    pie_data = df_filtered.groupby('Origen_Label')['net_amount'].sum().reset_index()
    
    # Gráfico Base (Arco)
    base = alt.Chart(pie_data).encode(
        theta=alt.Theta("net_amount", stack=True)
    )

    # El Donut
    pie = base.mark_arc(innerRadius=60, outerRadius=120).encode(
        color=alt.Color("Origen_Label", legend=alt.Legend(title=None, orient="bottom")),
        order=alt.Order("net_amount", sort="descending"),
        tooltip=["Origen_Label", alt.Tooltip("net_amount", format="$,.0f")]
    )

    # Etiquetas de texto
    text = base.mark_text(radius=140).encode(
        text=alt.Text("net_amount", format="$,.0s"), 
        order=alt.Order("net_amount", sort="descending"),
        color=alt.value("black")  
    )

    st.altair_chart(pie + text, use_container_width=True)

# --- ANÁLISIS DE PROCEDIMIENTOS ---
st.subheader("🩺 Top 10 Prestaciones (Lo que más genera)")

top_procedimientos = df_filtered.groupby('description')['net_amount'].sum().reset_index()
top_procedimientos = top_procedimientos.sort_values('net_amount', ascending=False).head(10)

chart_top = alt.Chart(top_procedimientos).mark_bar().encode(
    x=alt.X('net_amount:Q', title='Ingresos Generados ($)', axis=alt.Axis(format="$,.0f")),
    y=alt.Y('description:N', sort='-x', title=None, axis=alt.Axis(labelLimit=300)), 
    color=alt.value('#2E86C1'),
    tooltip=[alt.Tooltip('description', title='Prestación'), alt.Tooltip('net_amount', format="$,.0f")]
).properties(height=400)

st.altair_chart(chart_top, use_container_width=True)

# ==============================================================================
# 6. SECCIÓN: BUSCADOR AVANZADO
# ==============================================================================
st.markdown("---")
st.subheader("🔍 Buscador de Detalle")

text_search = st.text_input("Buscar por Paciente, Glosa o Código:", placeholder="Ej: Perez, Manguito, 2104051...")

if text_search:
    # Filtrar en el DF cargado (más rápido que ir a SQL para búsquedas simples)
    mask = (
        df['raw_patient_name'].astype(str).str.contains(text_search, case=False, na=False) |
        df['description'].astype(str).str.contains(text_search, case=False, na=False)
    )
    df_results = df[mask]
    
    if not df_results.empty:
        st.success(f"Se encontraron **{len(df_results)}** registros.")
        
        st.dataframe(
            df_results[['payment_date', 'raw_patient_name', 'description', 'Origen_Label', 'net_amount']],
            column_config={
                "payment_date": st.column_config.DateColumn("Fecha Pago", format="DD/MM/YYYY"),
                "raw_patient_name": "Paciente",
                "description": "Detalle Prestación",
                "Origen_Label": "Fuente",
                "net_amount": st.column_config.NumberColumn("Monto", format="$%d")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No se encontraron resultados con ese término.")
else:
    # Mostrar últimos 10 movimientos por defecto
    st.markdown("##### Últimos 10 Pagos Recibidos")
    st.dataframe(
        df_filtered.head(10)[['payment_date', 'raw_patient_name', 'description', 'Origen_Label', 'net_amount']],
        use_container_width=True,
        hide_index=True
    )
