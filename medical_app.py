import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client, Client
import datetime

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
st.set_page_config(
    page_title="Gestión Médica - Dr. Moraga",
    page_icon="👨‍⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: bold; color: #2C3E50; }
    .metric-label { font-size: 14px; color: #7F8C8D; text-transform: uppercase; }
    h1, h2, h3 { color: #2E86C1; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONEXIÓN & DATOS
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

@st.cache_data(ttl=600)
def load_data():
    # 1. Cargar Transacciones Individuales
    response_tx = supabase.table("transactions")\
        .select("*", count="exact")\
        .order("payment_date", desc=True)\
        .range(0, 10000)\
        .execute()
    
    # 2. Cargar Vista de Eventos (Cirugías Agrupadas)
    response_events = supabase.table("surgical_events_summary")\
        .select("*")\
        .order("payment_date", desc=True)\
        .range(0, 5000)\
        .execute()
        
    df_tx = pd.DataFrame(response_tx.data)
    df_events = pd.DataFrame(response_events.data)
    
    if df_tx.empty: return df_tx, df_events

    # Procesamiento Transacciones
    df_tx['payment_date'] = pd.to_datetime(df_tx['payment_date'], errors='coerce')
    df_tx['event_date'] = pd.to_datetime(df_tx['event_date'], errors='coerce')
    df_tx['net_amount'] = pd.to_numeric(df_tx['net_amount'], errors='coerce').fillna(0)
    
    if df_tx['payment_date'].isna().any():
        df_tx['payment_date'] = df_tx['payment_date'].fillna(pd.Timestamp.now())

    df_tx['Mes'] = df_tx['payment_date'].dt.strftime('%Y-%m')
    df_tx['Año'] = df_tx['payment_date'].dt.year.astype(int)
    
    df_tx['Origen_Label'] = df_tx['source'].map({
        'CAS_A': 'Alemana Ambulatorio',
        'CAS_H': 'Alemana Hospitalario',
        'AMCA': 'AMCA (Sociedad/Privado)'
    }).fillna(df_tx['source'])

    # Procesamiento Eventos
    if not df_events.empty:
        df_events['payment_date'] = pd.to_datetime(df_events['payment_date'], errors='coerce')
        df_events['surgery_date'] = pd.to_datetime(df_events['surgery_date'], errors='coerce')
        df_events['total_paid'] = pd.to_numeric(df_events['total_paid'], errors='coerce').fillna(0)
        df_events['Mes'] = df_events['payment_date'].dt.strftime('%Y-%m')
        df_events['Año'] = df_events['payment_date'].dt.year.astype(int)

    return df_tx, df_events

df, df_events = load_data()

# ==============================================================================
# SIDEBAR & FILTROS
# ==============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3774/3774299.png", width=80)
    st.title("Filtros")
    
    if not df.empty:
        years = sorted(df['Año'].unique(), reverse=True)
        selected_year = st.selectbox("📅 Año Fiscal", years, index=0, format_func=lambda x: str(x))
        
        months_available = sorted(df[df['Año'] == selected_year]['Mes'].unique(), reverse=True)
        selected_months = st.multiselect("📆 Meses (Opcional)", months_available, default=[])
        
        sources = df['Origen_Label'].unique()
        selected_sources = st.multiselect("🏥 Institución", sources, default=sources)
        
        # Filtro Principal
        df_filtered = df[(df['Año'] == selected_year) & (df['Origen_Label'].isin(selected_sources))]
        
        # Filtro Eventos
        if not df_events.empty:
            df_events_filtered = df_events[df_events['Año'] == selected_year]
        else:
            df_events_filtered = pd.DataFrame()

        if selected_months:
            df_filtered = df_filtered[df_filtered['Mes'].isin(selected_months)]
            if not df_events_filtered.empty:
                df_events_filtered = df_events_filtered[df_events_filtered['Mes'].isin(selected_months)]
    else:
        st.warning("No hay datos disponibles.")
        st.stop()
    
    st.markdown("---")
    st.info(f"Registros: {len(df)}")

# ==============================================================================
# DASHBOARD
# ==============================================================================
st.title(f"Resumen Financiero {selected_year}")

# TABS
tab1, tab2, tab3 = st.tabs(["📊 Resumen General", "🏥 Auditoría de Cirugías", "🔎 Buscador Detallado"])

# --- TAB 1: GENERAL ---
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    total_ingreso = df_filtered['net_amount'].sum()
    total_tx = len(df_filtered)
    
    def metric_card(label, value, prefix="$"):
        return f"""<div class="metric-container"><div class="metric-label">{label}</div><div class="metric-value">{prefix} {value}</div></div>"""

    with col1: st.markdown(metric_card("Ingreso Total", f"{total_ingreso:,.0f}".replace(",", "."), "$"), unsafe_allow_html=True)
    with col2: st.markdown(metric_card("Transacciones", f"{total_tx}", "#"), unsafe_allow_html=True)
    
    st.markdown("---")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        chart_mensual = alt.Chart(df_filtered).mark_bar().encode(
            x=alt.X('Mes:O', title='Mes'),
            y=alt.Y('sum(net_amount):Q', title='Monto ($)', axis=alt.Axis(format="$,.0f")),
            color='Origen_Label:N',
            tooltip=['Mes', 'Origen_Label', alt.Tooltip('sum(net_amount)', format="$,.0f")]
        ).properties(height=350)
        st.altair_chart(chart_mensual, use_container_width=True)
    
    with c2:
        # Top prestaciones
        if 'description' in df_filtered.columns:
            top_proc = df_filtered.groupby('description')['net_amount'].sum().reset_index().sort_values('net_amount', ascending=False).head(8)
            chart_top = alt.Chart(top_proc).mark_bar().encode(
                x=alt.X('net_amount:Q', title=None, axis=alt.Axis(format="$,.0f")),
                y=alt.Y('description:N', sort='-x', title=None),
                color=alt.value('#2E86C1'),
                tooltip=['description', alt.Tooltip('net_amount', format="$,.0f")]
            ).properties(height=350, title="Top Prestaciones")
            st.altair_chart(chart_top, use_container_width=True)

# --- TAB 2: AUDITORÍA DE CIRUGÍAS (VISTA AGRUPADA) ---
with tab2:
    st.markdown("### 🧬 Visor de Eventos Quirúrgicos")
    st.markdown("Aquí se agrupan todos los códigos asociados a una misma **Cuenta (Hospitalario)** u **Orden de Pago (Ambulatorio)**.")
    
    if not df_events_filtered.empty:
        # Ordenamos por monto total para ver las cirugías más importantes primero
        df_events_filtered = df_events_filtered.sort_values('total_paid', ascending=False)
        
        st.dataframe(
            df_events_filtered,
            column_config={
                "event_id": "N° Cuenta / OP",
                "payment_date": st.column_config.DateColumn("F. Pago", format="DD/MM/YYYY"),
                "surgery_date": st.column_config.DateColumn("F. Cirugía", format="DD/MM/YYYY"),
                "patient_name": "Paciente",
                "total_paid": st.column_config.NumberColumn("Total Evento", format="$%d"),
                "total_procedures": st.column_config.NumberColumn("# Ítems"),
                "descriptions_summary": "Detalle Completo (Kit)",
                "codes_list": "Códigos"
            },
            hide_index=True,
            use_container_width=True,
            height=600
        )
    else:
        st.info("No se encontraron eventos agrupados para este periodo.")

# --- TAB 3: BUSCADOR DETALLADO ---
with tab3:
    st.subheader("🔍 Buscador de Transacciones Individuales")
    text_search = st.text_input("Buscar:", placeholder="Paciente, Código, Glosa...")
    
    if text_search:
        mask = (
            df['raw_patient_name'].astype(str).str.contains(text_search, case=False, na=False) |
            df['description'].astype(str).str.contains(text_search, case=False, na=False) |
            (df['procedure_code'].astype(str).str.contains(text_search, case=False, na=False))
        )
        st.dataframe(df[mask][['payment_date', 'raw_patient_name', 'procedure_code', 'description', 'net_amount']], use_container_width=True)
    else:
        st.dataframe(df_filtered[['payment_date', 'raw_patient_name', 'procedure_code', 'description', 'net_amount']].head(50), use_container_width=True)
