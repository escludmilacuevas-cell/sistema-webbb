# Procrastinación Analytics

Dashboard web interactivo conectado a MySQL local.

## Windows: instalar y ejecutar
Abrí CMD y ejecutá:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Luego iniciá la web:

```bat
py -m streamlit run app.py
```

Abrí `http://localhost:8501` si el navegador no se abre automáticamente.

