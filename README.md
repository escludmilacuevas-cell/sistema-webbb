# Procrastinación Analytics

Dashboard web interactivo conectado a tu MySQL local.

## Windows: instalar y ejecutar
Abrí CMD dentro de esta carpeta y ejecutá:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

En `.env`, completá tu contraseña y el nombre de la base. En la captura se ve `procrastinacion` como base y `participantes` como tabla principal.

Luego iniciá la web:

```bat
py -m streamlit run app.py
```

Abrí `http://localhost:8501` si el navegador no se abre automáticamente.

## Incluye
- Frontend oscuro estilo analytics.
- Overview con indicadores.
- Filtros de edad y variables categóricas detectadas.
- Gráficos interactivos y cálculo de porcentajes.
- Exploración y descarga CSV.
- Inspección de columnas para adaptarse a la tabla instalada.

No compartas el archivo `.env` ni subas tu contraseña a GitHub.
