import streamlit as st
import pandas as pd

def render_historico(conn):
    st.subheader("📜 Histórico Detalhado")
    try:
        df = pd.read_sql("""
            SELECT h.data_estudo, a.nome, a.grande_area, h.acertos, h.total, h.percentual 
            FROM historico h JOIN assuntos a ON h.assunto_id = a.id ORDER BY h.id DESC
        """, conn)
        
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "percentual": st.column_config.ProgressColumn("Nota", format="%.1f%%", min_value=0, max_value=100),
            "data_estudo": st.column_config.DateColumn("Data")
        })
    except:
        st.write("Sem dados.")