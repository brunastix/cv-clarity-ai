import streamlit as st
from google import genai
from google.genai import types


st.title("Diagnóstico de conexión con Gemini")
st.write(
    "Esta pantalla consulta el catálogo de modelos. "
    "No envía currículums ni genera contenido."
)

api_key = st.text_input(
    "Pegá tu Gemini API Key",
    type="password",
)

if st.button("Consultar modelos"):
    if not api_key.strip():
        st.warning("Ingresá la clave en el campo de arriba.")
    else:
        try:
            with st.spinner("Consultando el catálogo de Google..."):
                with genai.Client(
                    api_key=api_key.strip(),
                    http_options=types.HttpOptions(timeout=30000),
                ) as client:
                    rows = []

                    for model in client.models.list():
                        actions = model.supported_actions or []

                        if "generateContent" in actions:
                            rows.append({
                                "Identificador": model.name,
                                "Nombre": model.display_name or "",
                            })

            if rows:
                st.success("Google devolvió estos modelos:")
                st.dataframe(rows, use_container_width=True)
                st.caption(
                    "Aparecer en el catálogo no garantiza cuota "
                    "ni disponibilidad. Después probaremos uno."
                )
            else:
                st.warning(
                    "No se encontraron modelos con generateContent."
                )

        except Exception as exc:
            code = getattr(exc, "code", None)
            st.error(
                f"No se pudo consultar el catálogo. "
                f"Código: {code or 'sin código'}. "
                f"Tipo: {type(exc).__name__}."
            )
