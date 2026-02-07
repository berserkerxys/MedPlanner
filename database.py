# database.py
# Versão Consolidada: Inclui TODAS as funções para Sidebar, Cronograma, Dashboard e Agenda.

import os
import json
import sqlite3
import bcrypt
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

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
    """Garante a existência de todas as tabelas necessárias."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
    
    # Migrações rápidas
    try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
    except: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    except: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
    except: pass
    
    conn.commit()

# --- 3. FUNÇÕES DE CRONOGRAMA E REVISÃO ---

def get_cronograma_status(u):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (u,)).fetchone()
    return json.loads(row['estado_json']) if row else {}

def salvar_cronograma_status(u, d):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?,?)", (u, json.dumps(d)))
    conn.commit()
    trigger_refresh()
    return True

def calcular_meta_questoes(prioridade, desempenho_anterior=None):
    """Metas baseadas na prioridade do MedCof."""
    bases = {"Diamante": (20, 30), "Verde": (15, 25), "Amarelo": (10, 20), "Vermelho": (5, 10)}
    return bases.get(prioridade, (10, 15))

def registrar_estudo(u, a, ac, t, tipo_estudo="Pos-Aula", srs=False, area_f=None):
    _ensure_local_db()
    conn = get_db_connection()
    dt = datetime.now().strftime("%Y-%m-%d")
    area = area_f if area_f else get_area_por_assunto(a)
    
    conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)", 
                 (u, a, area, dt, int(ac), int(t), tipo_estudo))
    
    # Atualiza o cronograma automaticamente
    estado = get_cronograma_status(u)
    dados = estado.get(a, {"feito": False, "acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0})
    if tipo_estudo == "Pre-Aula":
        dados["acertos_pre"] += int(ac); dados["total_pre"] += int(t)
    else:
        dados["acertos_pos"] += int(ac); dados["total_pos"] += int(t)
        dados["feito"] = True
    
    estado[a] = dados
    salvar_cronograma_status(u, estado)
    
    # Agendamento de Revisão (SRS)
    if srs and tipo_estudo == "Pos-Aula":
        dt_rev = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", 
                     (u, a, area, dt_rev, "1 Semana", "Pendente"))
    
    conn.commit()
    trigger_refresh()
    return f"✅ Salvo em {area}!"

# --- 4. FUNÇÕES DE STATUS E PERFORMANCE (SIDEBAR/DASHBOARD) ---

def get_status_gamer(u, nonce=None):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
    
    xp = int(row['xp']) if row and row['xp'] is not None else 0
    meta = int(row['meta_diaria']) if row and row['meta_diaria'] is not None else 50
    
    status = {
        'nivel': 1 + (xp // 1000), 
        'xp_atual': xp, 
        'meta_diaria': meta, 
        'titulo': "Residente R1" if xp > 2000 else "Interno"
    }
    return status, pd.DataFrame()

def get_progresso_hoje(u, n=None):
    """Calcula o total de questões resolvidas hoje."""
    _ensure_local_db()
    conn = get_db_connection()
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        r = conn.execute("SELECT SUM(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
        return r[0] if r and r[0] else 0
    except:
        return 0

def get_area_por_assunto(assunto):
    try:
        from aulas_medcof import DADOS_LIMPOS
        for a, area, prio in DADOS_LIMPOS:
            if a == assunto: return area
    except: pass
    return "Geral"

def update_meta_diaria(u, m):
    _ensure_local_db()
    conn = get_db_connection()
    conn.execute("INSERT INTO perfil_gamer (usuario_id, xp, meta_diaria) VALUES (?, 0, ?) ON CONFLICT(usuario_id) DO UPDATE SET meta_diaria = ?", (u, m, m))
    conn.commit()
    return True

# --- 5. FUNÇÕES DE ACESSO ---

def verificar_login(u, p):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (u,)).fetchone()
    if row and bcrypt.checkpw(p.encode(), row['password_hash'].encode()):
        return True, row['nome']
    return False, "Erro"

def criar_usuario(u, p, n):
    _ensure_local_db()
    conn = get_db_connection()
    pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
    try:
        conn.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (u, n, pw))
        conn.commit()
        return True, "OK"
    except: return False, "Erro"

# --- 6. STUBS PARA COMPATIBILIDADE ---
def get_dados_graficos(u, n): return pd.DataFrame()
def get_benchmark_dados(u, df): return pd.DataFrame()
def get_caderno_erros(u, a): return ""
def salvar_caderno_erros(u, a, t): return True
def listar_revisoes_completas(u, n): return pd.DataFrame()
def reagendar_inteligente(id, d): pass
def excluir_revisao(id): pass
def registrar_simulado(u, d): pass
def get_lista_assuntos_nativa(): return []