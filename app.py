import os
import re
from io import BytesIO
import pandas as pd
import plotly.express as px
import streamlit as st
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Procrastinación Analytics", page_icon="◈", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
.stApp{background:radial-gradient(ellipse at 15% 0%,#182849 0%,#0b1020 42%,#090e1a 100%);color:#edf3ff}
[data-testid="stSidebar"]{background:#0b1222;border-right:1px solid #202b40}
.block-container{padding-top:1.6rem;max-width:1500px}
h1,h2,h3{font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.03em}
.eyebrow{color:#8fa4c7;text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:700}
.sub{color:#9aabc7;margin-top:-.6rem}
.metric{background:linear-gradient(145deg,#19263e,#111a2c);border:1px solid #2a3954;border-radius:16px;padding:18px;min-height:120px}
.ml{color:#9baac4;font-size:.82rem;font-weight:600}.mv{font-size:2rem;font-weight:700;color:#f5f8ff;margin-top:7px}.mf{color:#67e8f9;font-size:.78rem;margin-top:7px}
</style>
""", unsafe_allow_html=True)

def db_connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST","localhost"),
        port=int(os.getenv("DB_PORT","3306")),
        user=os.getenv("DB_USER","root"),
        password=os.getenv("DB_PASSWORD",""),
        database=os.getenv("DB_NAME","procrastinacion"),
        connection_timeout=5,
    )

@st.cache_data(ttl=60)
def get_tables():
    con=db_connect()
    try:
        cur=con.cursor()
        cur.execute("SHOW TABLES")
        return [x[0] for x in cur.fetchall()]
    finally:
        con.close()

@st.cache_data(ttl=60)
def get_table(name):
    con=db_connect()
    try:
        return pd.read_sql(f"SELECT * FROM `{name}`",con)
    finally:
        con.close()

def find_col(columns, choices):
    lookup={str(c).lower():c for c in columns}
    for x in choices:
        if x.lower() in lookup: return lookup[x.lower()]
    for c in columns:
        if any(x.lower() in str(c).lower() for x in choices): return c
    return None


def normaliza(texto):
    return re.sub(r"[^a-z0-9]", "", str(texto).lower())

def detectar_columna_id(tabla):
    """Busca una columna identificadora en una tabla de catálogo."""
    for c in tabla.columns:
        n = normaliza(c)
        if n == "id" or n.endswith("id") or n.endswith("cod") or n.endswith("codigo"):
            return c
    # fallback: primera columna
    return tabla.columns[0] if len(tabla.columns) else None

def detectar_columna_nombre(tabla, id_col):
    """Busca el campo descriptivo para mostrar en lugar del código numérico."""
    if id_col is None:
        return None
    preferidas = ("nombre", "descripcion", "descrip", "detalle", "etiqueta", "categoria",
                  "genero", "educacion", "ocupacion", "estado", "rango", "label", "name", "tipo")
    candidatas = [c for c in tabla.columns if c != id_col]
    for palabra in preferidas:
        for c in candidatas:
            if palabra in normaliza(c):
                return c
    # Evitar columnas que parecen códigos y elegir una columna textual si existe
    for c in candidatas:
        if not (normaliza(c).endswith("id") or normaliza(c).endswith("cod") or normaliza(c).endswith("codigo")):
            return c
    return candidatas[0] if candidatas else None

@st.cache_data(ttl=60)
def cargar_etiquetas(tablas_disponibles):
    """Construye mapas ID -> nombre a partir de tablas de catálogo conocidas."""
    catalogos = {
        "genero": ("genero", "parti_gen", "id_genero"),
        "educacion": ("educacion", "parti_edu", "id_educacion"),
        "estado_laboral": ("estado laboral", "parti_esla", "id_estado_laboral"),
        "ocupacion": ("ocupacion", "parti_ocu", "id_ocupacion"),
        "rango_edad": ("rango etario", "parti_rang", "id_rango_edad"),
    }
    resultado = {}
    for tabla_nombre in tablas_disponibles:
        clave = normaliza(tabla_nombre)
        catalogo = next((v for k, v in catalogos.items() if normaliza(k) == clave), None)
        if not catalogo:
            continue
        try:
            t = get_table(tabla_nombre)
            id_col = detectar_columna_id(t)
            nombre_col = detectar_columna_nombre(t, id_col)
            if id_col is None or nombre_col is None:
                continue
            etiqueta = catalogo[0]
            resultado[etiqueta] = {
                "id_col": id_col,
                "nombre_col": nombre_col,
                "map": dict(zip(t[id_col].astype(str), t[nombre_col].fillna("Sin dato").astype(str))),
            }
        except Exception:
            continue
    return resultado

def aplicar_etiquetas(df_original, etiquetas):
    """Sustituye claves foráneas por sus nombres en la copia visible del dataframe."""
    salida = df_original.copy()
    reglas = [
        (("genero", "partigen", "idgenero", "gender", "sex"), "genero"),
        (("educacion", "partiedu", "ideducacion", "education"), "educacion"),
        (("estadolaboral", "partiesla", "idestadolaboral", "estlab", "employment"), "estado laboral"),
        (("ocupacion", "partiocu", "idocupacion", "occupation"), "ocupacion"),
        (("rangoedad", "partirang", "idrangoedad", "randad", "agerange"), "rango etario"),
    ]
    for c in salida.columns:
        nc = normaliza(c)
        for patrones, nombre_catalogo in reglas:
            if any(patron in nc for patron in patrones):
                catalog_key = next((k for k in etiquetas if normaliza(k) == normaliza(nombre_catalogo)), None)
                if catalog_key and catalog_key in etiquetas:
                    mapa = etiquetas[catalog_key]["map"]
                    salida[c] = salida[c].map(
                        lambda x: mapa.get(str(x), str(x)) if pd.notna(x) else "Sin dato"
                    )
                    break
    return salida


def style(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#dce7fb",margin=dict(l=10,r=10,t=45,b=10),
        xaxis=dict(gridcolor="#25324a"),yaxis=dict(gridcolor="#25324a"))
    return fig

def card(label,value,foot):
    st.markdown(f'<div class="metric"><div class="ml">{label}</div><div class="mv">{value}</div><div class="mf">{foot}</div></div>',unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="eyebrow">TP FINAL · DATA STUDIO</div>',unsafe_allow_html=True)
    st.title("◈ Procrastinación")
    page=st.radio("NAVEGACIÓN",["Overview","Consultas","Explorar datos","Distribuciones","Acerca del proyecto"])
    st.divider()
    if st.button("↻ Actualizar datos",use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown('<div class="eyebrow">OBSERVATORIO DE DATOS</div>',unsafe_allow_html=True)
st.title("Procrastination Analytics")
st.markdown('<div class="sub">Explorá los perfiles de la encuesta y sus distribuciones.</div>',unsafe_allow_html=True)

try:
    tables=get_tables()
    main=next((t for t in tables if t.lower()=="participantes"),None)
    if not main: main=next((t for t in tables if "particip" in t.lower() and "raw" not in t.lower()),None)
    if not main:
        st.error("No encontré la tabla principal de participantes. Tablas: "+", ".join(tables)); st.stop()
    df=get_table(main)
except Exception as e:
    st.error("No pude conectar con MySQL. Verificá el archivo .env y que MySQL esté iniciado.")
    st.code(str(e))
    st.info("Copiá .env.example como .env y completá usuario, contraseña y nombre de base.")
    st.stop()

# Convertir códigos de tablas catálogo a nombres legibles para toda la interfaz.
etiquetas = cargar_etiquetas(tuple(tables))
df = aplicar_etiquetas(df, etiquetas)

age=find_col(df.columns,["parti_age","edad","age"])
categoricals=[
    ("Género",find_col(df.columns,["parti_gen","id_genero","genero","gender","sex"])),
    ("Educación",find_col(df.columns,["parti_edu","id_educacion","educacion","education"])),
    ("Estado laboral",find_col(df.columns,["parti_esla","estado_laboral","estlab","employment"])),
    ("Ocupación",find_col(df.columns,["parti_ocu","ocupacion","occupation"])),
    ("Rango etario",find_col(df.columns,["parti_rang","rango_edad","randad","age_range"])),
]
filtered=df.copy()
with st.sidebar:
    st.markdown("**FILTROS**")
    if age:
        nums=pd.to_numeric(filtered[age],errors="coerce")
        vals=nums.dropna()
        if not vals.empty:
            lo,hi=int(vals.min()),int(vals.max())
            bounds=st.slider("Edad",(lo),(hi),(lo,hi))
            filtered=filtered[(pd.to_numeric(filtered[age],errors="coerce")>=bounds[0])&(pd.to_numeric(filtered[age],errors="coerce")<=bounds[1])]
    for label,col in categoricals:
        if col and filtered[col].nunique(dropna=True)<=30:
            opts=sorted(filtered[col].dropna().astype(str).unique().tolist())
            chosen=st.multiselect(label,opts,default=opts)
            if chosen: filtered=filtered[filtered[col].astype(str).isin(chosen)]

n=len(df); nf=len(filtered)
miss=100*filtered.isna().sum().sum()/max(filtered.size,1)
if page=="Overview":
    st.subheader("Resumen general")
    c=st.columns(4)
    with c[0]: card("PARTICIPANTES",f"{nf:,}",f"{(100*nf/n if n else 0):.1f}% del total")
    with c[1]: card("VARIABLES",str(df.shape[1]),"columnas disponibles")
    with c[2]:
        vals=pd.to_numeric(filtered[age],errors="coerce") if age else pd.Series(dtype=float)
        avg=f"{vals.mean():.1f}" if vals.notna().any() else "—"
        card("EDAD PROMEDIO",avg,"años · si está disponible")
    with c[3]: card("DATOS FALTANTES",f"{miss:.1f}%","en la selección filtrada")
    left,right=st.columns([1.15,1])
    with left:
        st.markdown("### Vista previa de participantes")
        st.dataframe(filtered.head(15),use_container_width=True,hide_index=True)
        st.caption(f"Mostrando hasta 15 de {nf:,} registros.")
    with right:
        st.markdown("### Calidad de datos")
        missing=filtered.isna().sum().sort_values(ascending=False).head(12)
        missing=missing[missing>0]
        if len(missing):
            fig=px.bar(x=missing.values,y=missing.index,orientation="h",labels={"x":"Valores faltantes","y":"Variable"})
            st.plotly_chart(style(fig),use_container_width=True)
        else: st.success("No hay valores faltantes en la selección.")
    st.markdown("### Distribuciones rápidas")
    avail=[(label,col) for label,col in categoricals if col and filtered[col].nunique(dropna=True)>1]
    if avail:
        cols=st.columns(min(3,len(avail)))
        for i,(label,col) in enumerate(avail[:3]):
            counts=filtered[col].fillna("Sin dato").astype(str).value_counts().reset_index()
            counts.columns=["Categoría","Cantidad"]
            with cols[i]:
                fig=px.pie(counts,names="Categoría",values="Cantidad",hole=.56,title=label)
                st.plotly_chart(style(fig),use_container_width=True)
    else: st.info("No identifiqué automáticamente categorías; usá Distribuciones para elegir una columna.")
elif page=="Consultas":
    st.subheader("Consultas por perfil de participantes")
    st.markdown("Combiná varios criterios y cruzá variables entre sí. Por ejemplo: participantes de cierto rango de edad, profesión y género, agrupados por una variable relacionada con procrastinación si existe en la base.")
    st.caption("Los resultados cuentan registros de la tabla de participantes; no se infiere quién procrastina si la base no incluye una variable o escala que lo mida.")

    query_df = df.copy()
    st.markdown("### 1. Elegí los filtros de esta consulta")
    q1, q2 = st.columns(2)
    with q1:
        if age:
            age_nums = pd.to_numeric(query_df[age], errors="coerce")
            age_values = age_nums.dropna()
            if not age_values.empty:
                age_min, age_max = int(age_values.min()), int(age_values.max())
                age_bounds = st.slider("Edad de los participantes", min_value=age_min, max_value=age_max,
                                       value=(age_min, age_max), key="consulta_edad")
                query_df = query_df[age_nums.between(age_bounds[0], age_bounds[1])]
        else:
            st.caption("No se detectó una columna de edad en la tabla principal.")
    with q2:
        if "parti_cod" in query_df.columns:
            st.caption("Se mantiene el identificador de cada participante para consultar sus registros.")

    filter_cols = [(label, col) for label, col in categoricals if col and col in query_df.columns]
    if filter_cols:
        filter_grid = st.columns(2)
        for idx, (label, col) in enumerate(filter_cols):
            opts = sorted(query_df[col].dropna().astype(str).unique().tolist())
            if 0 < len(opts) <= 100:
                with filter_grid[idx % 2]:
                    selected = st.multiselect(f"{label}", opts, default=[], key=f"consulta_filtro_{col}",
                                              help="Dejalo vacío para incluir todas las opciones.")
                if selected:
                    query_df = query_df[query_df[col].astype(str).isin(selected)]

    st.markdown("### 2. ¿Cómo querés clasificar los resultados?")
    # Offer useful dimensions, avoiding very high-cardinality identifiers where possible.
    groupable = [c for c in query_df.columns if query_df[c].nunique(dropna=True) <= 100]
    if not groupable:
        groupable = list(query_df.columns)
    g1, g2, g3 = st.columns([1, 1, 1])
    with g1:
        group1 = st.selectbox("Agrupar por", groupable, index=groupable.index(categoricals[3][1]) if len(categoricals) > 3 and categoricals[3][1] in groupable else 0, key="consulta_group1")
    with g2:
        other_options = ["(No cruzar) Open"] + [c for c in groupable if c != group1]
        group2_choice = st.selectbox("Cruzar también por", other_options, key="consulta_group2")
    with g3:
        chart_type = st.selectbox("Mostrar como", ["Tabla", "Barras", "Barras apiladas"], key="consulta_grafico")

    # Search for a likely procrastination score/category, but never assume one exists.
    procrast_cols = [c for c in query_df.columns if any(k in str(c).lower() for k in
                     ["procrast", "procras", "procr", "pss", "score", "puntaje", "escala"])]
    if procrast_cols:
        pcol = st.selectbox("Variable de procrastinación (si corresponde)", ["No usar como categoría"] + procrast_cols,
                            key="consulta_procrast_col", help="Elegí una columna real de tu base que mida procrastinación.")
        if pcol != "No usar como categoría":
            st.caption(f"Se usará **{pcol}** como categoría de resultado; revisá que represente una medida de procrastinación.")
    else:
        pcol = "No usar como categoría"
        st.info("No encontré una columna cuyo nombre indique claramente una medida de procrastinación. Podés cruzar edad, ocupación, educación y otras variables, pero para contar específicamente quiénes son procrastinadores necesitamos una columna/escala de la encuesta que lo mida.")

    run_query = st.button("🔎 Ejecutar consulta", type="primary", key="consulta_run")
    if run_query:
        st.session_state["consulta_ejecutada"] = True
        st.session_state["consulta_snapshot"] = query_df.copy()
        st.session_state["consulta_group1_saved"] = group1
        st.session_state["consulta_group2_saved"] = group2_choice
        st.session_state["consulta_chart_saved"] = chart_type
        st.session_state["consulta_pcol_saved"] = pcol

    if st.session_state.get("consulta_ejecutada", False):
        result_df = st.session_state.get("consulta_snapshot", query_df)
        group1 = st.session_state.get("consulta_group1_saved", group1)
        group2_choice = st.session_state.get("consulta_group2_saved", group2_choice)
        chart_type = st.session_state.get("consulta_chart_saved", chart_type)
        pcol = st.session_state.get("consulta_pcol_saved", pcol)
        if result_df.empty:
            st.warning("No hay participantes que coincidan con esos filtros. Probá ampliar la selección.")
        else:
            dimensions = [group1]
            if group2_choice != "(No cruzar) Open":
                dimensions.append(group2_choice)
            if pcol != "No usar como categoría" and pcol not in dimensions:
                dimensions.append(pcol)
            summary = (result_df.assign(**{c: result_df[c].fillna("Sin dato").astype(str) for c in dimensions})
                       .groupby(dimensions, dropna=False).size().reset_index(name="Participantes")
                       .sort_values("Participantes", ascending=False))
            summary["Porcentaje"] = (summary["Participantes"] / max(int(summary["Participantes"].sum()), 1) * 100).round(2)

            st.markdown("### 3. Resultado de la consulta")
            m1, m2, m3 = st.columns(3)
            with m1: card("PARTICIPANTES", f"{len(result_df):,}", "coinciden con los filtros")
            with m2: card("GRUPOS", f"{len(summary):,}", "combinaciones encontradas")
            with m3: card("FILTROS ACTIVOS", f"{sum(1 for label, col in filter_cols if col in result_df.columns and col in query_df.columns):,}", "variables disponibles para filtrar")

            if chart_type == "Barras":
                plot_data = summary.copy()
                plot_data["Grupo"] = plot_data[dimensions].astype(str).agg(" · ".join, axis=1)
                fig = px.bar(plot_data.head(40).sort_values("Participantes"), x="Participantes", y="Grupo",
                             orientation="h", text="Participantes", title="Cantidad de participantes por combinación")
                st.plotly_chart(style(fig), use_container_width=True)
            elif chart_type == "Barras apiladas" and len(dimensions) >= 2:
                fig = px.bar(summary, x=dimensions[0], y="Participantes", color=dimensions[1], barmode="stack",
                             title=f"Participantes por {dimensions[0]} y {dimensions[1]}")
                st.plotly_chart(style(fig), use_container_width=True)
            elif chart_type == "Barras apiladas":
                fig = px.bar(summary, x=dimensions[0], y="Participantes", title=f"Participantes por {dimensions[0]}")
                st.plotly_chart(style(fig), use_container_width=True)
            st.dataframe(summary, use_container_width=True, hide_index=True)

            st.markdown("### 4. Descargar resultados")
            d1, d2 = st.columns(2)
            with d1:
                st.download_button("⬇️ Descargar registros CSV", data=result_df.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="participantes_consulta.csv", mime="text/csv")
            with d2:
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    result_df.to_excel(writer, index=False, sheet_name="Participantes")
                    summary.to_excel(writer, index=False, sheet_name="Resumen")
                st.download_button("⬇️ Descargar Excel (datos + resumen)", data=excel_buffer.getvalue(),
                                   file_name="participantes_consulta.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Combiná los filtros, elegí una o dos variables para clasificar y apretá «Ejecutar consulta».")
elif page=="Explorar datos":
    st.subheader("Explorador de la base")
    st.write(f"Tabla: **{main}** · {n:,} registros · {df.shape[1]} columnas")
    st.dataframe(filtered,use_container_width=True,hide_index=True)
    st.download_button("Descargar selección CSV",filtered.to_csv(index=False).encode("utf-8-sig"),"participantes_filtrados.csv","text/csv")
    schema=pd.DataFrame({"Columna":df.columns.astype(str),"Tipo":[str(x) for x in df.dtypes],
        "No nulos":[int(df[c].notna().sum()) for c in df.columns],"Nulos":[int(df[c].isna().sum()) for c in df.columns],
        "Valores únicos":[int(df[c].nunique(dropna=True)) for c in df.columns]})
    st.markdown("### Diccionario de columnas")
    st.dataframe(schema,use_container_width=True,hide_index=True)
elif page=="Distribuciones":
    st.subheader("Distribuciones y porcentajes")
    possible=[c for c in filtered.columns if filtered[c].nunique(dropna=True)<=60]
    if possible:
        col=st.selectbox("Elegí una variable",possible)
        counts=filtered[col].fillna("Sin dato").astype(str).value_counts().rename_axis("Categoría").reset_index(name="Cantidad")
        counts["Porcentaje"]=(counts["Cantidad"]/max(counts["Cantidad"].sum(),1)*100).round(2)
        a,b=st.columns([1.2,1])
        with a:
            fig=px.bar(counts.sort_values("Cantidad"),x="Cantidad",y="Categoría",orientation="h",text="Cantidad",title=f"Distribución de {col}")
            st.plotly_chart(style(fig),use_container_width=True)
        with b:
            fig=px.pie(counts,names="Categoría",values="Cantidad",hole=.5,title="Participación porcentual")
            st.plotly_chart(style(fig),use_container_width=True)
        st.dataframe(counts,use_container_width=True,hide_index=True)
        st.caption("Los porcentajes se calculan sobre los registros filtrados.")
    else: st.info("No hay columnas categóricas para graficar.")
else:
    st.subheader("Acerca del proyecto")
    st.write("Dashboard exploratorio para el TP Final sobre procrastinación.")
    st.markdown("- Conexión a MySQL mediante variables de entorno.\n- Indicadores y filtros dinámicos.\n- Consultas personalizadas con gráficos.\n- Explorador de datos y exportación CSV/Excel.")
    st.info("Los gráficos describen la muestra cargada; no prueban causalidad ni garantizan representar a toda la población.")
    st.write("Tablas detectadas:",", ".join(tables))
