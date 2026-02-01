# Arquivo: styles.py
import streamlit as st

def aplicar_estilo():
    st.markdown("""
    <style>
        /* Fundo geral */
        .stApp { background-color: #f4f6f9; }
        
        /* Cards brancos */
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            border: 1px solid #eef2f5;
        }

        /* Sidebar Customizada */
        [data-testid="stSidebar"] { background-color: #1e2a36; }
        
        /* Títulos e Textos da Sidebar (Brancos) */
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] .stMarkdown {
            color: #ecf0f1 !important;
        }
        
        /* Inputs da Sidebar (Texto Escuro) */
        [data-testid="stSidebar"] input { color: #2c3e50 !important; }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div { color: #2c3e50 !important; }
        [data-testid="stSidebar"] svg { fill: #ecf0f1 !important; }

        /* Ajuste de Fontes */
        h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
        
        /* Divisores */
        hr { margin: 1.5em 0; }
    </style>
    """, unsafe_allow_html=True)