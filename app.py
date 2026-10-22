import os
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
    page=st.radio("NAVEGACIÓN",["Overview","Explorar datos","Distribuciones","Acerca del proyecto"])
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
    st.markdown("- Conexión a MySQL mediante variables de entorno.\n- Indicadores y filtros dinámicos.\n- Gráficos interactivos de barras y anillos.\n- Explorador de datos y exportación CSV.")
    st.info("Los gráficos describen la muestra cargada; no prueban causalidad ni garantizan representar a toda la población.")
    st.write("Tablas detectadas:",", ".join(tables))
