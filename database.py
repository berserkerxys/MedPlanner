# database.py
# Versão Mestra Final: Contém TODAS as funções necessárias para o MedPlanner

import os
import json
import sqlite3
import re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional

DB_NAME = "medplanner_local.db"

# --- 1. CONEXÃO E CACHE ---
@st.cache_resource
def get_db_connection():
    """Mantém a conexão aberta para evitar IO excessivo."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# --- 2. INICIALIZAÇÃO ---
def _ensure_local_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # CRIAÇÃO DAS TABELAS (GARANTIA)
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
    
    # Migrações rápidas (para garantir colunas novas em bancos velhos)
    try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    except: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
    except: pass
    try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
    except: pass
    
    conn.commit()

# --- DADOS ESTÁTICOS ---
@st.cache_data(ttl=3600)
def _carregar_dados_medcof():
    """Cache das aulas para não ler o arquivo aulas_medcof.py a todo momento."""
    lista, mapa = [], {}
    try:
        import aulas_medcof
        for item in aulas_medcof.DADOS_LIMPOS:
            aula, area = item[0], item[1]
            lista.append(aula)
            mapa[aula] = area
    except: pass
    return sorted(list(set(lista))), mapa

def get_lista_assuntos_nativa():
    aulas, _ = _carregar_dados_medcof()
    return aulas if aulas else ["Banco Geral"]

def normalizar_area(n):
    return str(n).strip() if n else "Geral"

def get_area_por_assunto(assunto):
    _, mapa = _carregar_dados_medcof()
    return mapa.get(assunto, "Geral")

# --- 3. FUNÇÕES DE CADERNO DE ERROS ---
def get_caderno_erros(u, area):
    _ensure_local_db() # Garante que a tabela existe antes de ler
    conn = get_db_connection()
    row = conn.execute("SELECT conteudo FROM resumos WHERE usuario_id=? AND grande_area=?", (u, area)).fetchone()
    return row['conteudo'] if row else ""

def salvar_caderno_erros(u, area, texto):
    _ensure_local_db()
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto or ""))
    conn.commit()
    return True

def get_resumo(u, a): return get_caderno_erros(u, a)
def salvar_resumo(u, a, t): return salvar_caderno_erros(u, a, t)

# --- 4. FUNÇÕES DE CRONOGRAMA ---
def get_cronograma_status(u):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (u,)).fetchone()
    return json.loads(row['estado_json']) if row else {}

def salvar_cronograma_status(u, d):
    _ensure_local_db()
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?,?)", (u, json.dumps(d)))
    conn.commit()
    trigger_refresh()
    return True

def calcular_meta_questoes(prioridade, desempenho_anterior=None):
    base = {"Diamante": 20, "Vermelho": 15, "Amarelo": 10, "Verde": 5}
    m = base.get(prioridade, 10)
    return m, m + 10

def resetar_revisoes_aula(u, aula):
    estado = get_cronograma_status(u)
    if aula in estado:
        estado[aula].update({"acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0, "feito": False})
        salvar_cronograma_status(u, estado)
    return True

# --- 5. FUNÇÕES DE PERFORMANCE E DASHBOARD ---
@st.cache_data(ttl=60)
def get_dados_graficos(u, nonce=None):
    _ensure_local_db()
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
        if not df.empty:
            df['data'] = pd.to_datetime(df['data_estudo'])
            df['area'] = df['area_manual']
        return df
    except Exception:
        return pd.DataFrame()

def get_status_gamer(u, nonce=None):
    _ensure_local_db() # Garante tabela antes de ler
    conn = get_db_connection()
    
    # Tenta buscar, se der erro assume 0
    try:
        row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
        xp = int(row['xp']) if row and row['xp'] is not None else 0
        meta = int(row['meta_diaria']) if row and row['meta_diaria'] is not None else 50
    except:
        xp, meta = 0, 50

    return {"nivel": 1+(xp//1000), "xp_atual": xp, "meta_diaria": meta, "titulo": "Interno"}, pd.DataFrame()

def get_benchmark_dados(u, df_user):
    return pd.DataFrame([{"Area": "Geral", "Tipo": "Você", "Performance": 70}, {"Area": "Geral", "Tipo": "Comunidade", "Performance": 65}])

def get_progresso_hoje(u, n=None):
    _ensure_local_db()
    conn = get_db_connection()
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        r = conn.execute("SELECT SUM(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
        return r[0] if r and r[0] else 0
    except: return 0

# --- 6. GESTÃO DE USUÁRIO ---
def verificar_login(u, p):
    _ensure_local_db()
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (u,)).fetchone()
        if row and bcrypt.checkpw(p.encode(), row['password_hash'].encode()):
            return True, row['nome']
    except: pass
    return False, "Erro"

def criar_usuario(u, p, n):
    _ensure_local_db()
    conn = get_db_connection()
    pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
    try:
        conn.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (u, n, pw))
        # Inicializa o perfil gamer junto para evitar erro de tabela vazia
        conn.execute("INSERT OR IGNORE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, 0, 'Interno', 50)", (u,))
        conn.commit()
        return True, "OK"
    except: return False, "Erro"

def get_dados_pessoais(u):
    _ensure_local_db()
    conn = get_db_connection()
    try:
        r = conn.execute("SELECT email, data_nascimento FROM usuarios WHERE username=?", (u,)).fetchone()
        return {"email": r['email'] if r else "", "nascimento": r['data_nascimento'] if r else None}
    except: return {"email": "", "nascimento": None}

def update_dados_pessoais(u, e, n):
    _ensure_local_db()
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET email=?, data_nascimento=? WHERE username=?", (e, n, u))
    conn.commit()
    return True

def resetar_conta_usuario(u):
    _ensure_local_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM historico WHERE usuario_id=?", (u,))
    conn.execute("DELETE FROM revisoes WHERE usuario_id=?", (u,))
    conn.execute("DELETE FROM cronogramas WHERE usuario_id=?", (u,))
    conn.execute("UPDATE perfil_gamer SET xp=0 WHERE usuario_id=?", (u,))
    conn.commit()
    trigger_refresh()
    return True

def registrar_estudo(u, a, ac, t, **kwargs):
    _ensure_local_db()
    conn = get_db_connection()
    dt = datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO historico (usuario_id, assunto_nome, acertos, total, data_estudo) VALUES (?,?,?,?,?)", (u, a, ac, t, dt))
    
    # Atualiza XP também
    xp_ganho = int(t) * 2
    conn.execute("INSERT INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50) ON CONFLICT(usuario_id) DO UPDATE SET xp = xp + ?", (u, xp_ganho, xp_ganho))
    
    conn.commit()
    trigger_refresh()
    return "Salvo"

def update_meta_diaria(u, m):
    _ensure_local_db()
    conn = get_db_connection()
    # Upsert seguro
    conn.execute("INSERT INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, 0, 'Interno', ?) ON CONFLICT(usuario_id) DO UPDATE SET meta_diaria = ?", (u, m, m))
    conn.commit()
    return True

def get_conquistas_e_stats(u): return 0, [], None

# --- SUPABASE STUBS (MANTIDOS PARA COMPATIBILIDADE) ---
# Se não estiver usando Supabase, estas funções evitam erros de importação
def get_supabase(): return None