# database.py
import os, json, sqlite3, bcrypt
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

DB_NAME = "medplanner_local.db"

@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_local_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Tabela de histórico com area_manual
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, meta_diaria INTEGER)")
    # Tabela de revisões para a Agenda
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    conn.commit()

# --- FUNÇÕES ESSENCIAIS PARA O CRONOGRAMA ---

def get_cronograma_status(u):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (u,)).fetchone()
    return json.loads(row['estado_json']) if row else {}

def salvar_cronograma_status(u, d):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?,?)", (u, json.dumps(d)))
    conn.commit()
    return True

def calcular_meta_questoes(prioridade, desempenho_anterior=None):
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
    return "Salvo com sucesso!"

def registrar_simulado(u, dados):
    _ensure_local_db()
    conn = get_db_connection()
    dt = datetime.now().strftime("%Y-%m-%d")
    for area, valores in dados.items():
        if int(valores['total']) > 0:
            conn.execute(
                "INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)",
                (u, f"Simulado - {area}", area, dt, int(valores['acertos']), int(valores['total']), "Simulado")
            )
    conn.commit()
    return "✅ Simulado Salvo!"

def get_lista_assuntos_nativa():
    try:
        from aulas_medcof import DADOS_LIMPOS
        return sorted([x[0] for x in DADOS_LIMPOS])
    except: return ["Aula Geral"]

def get_area_por_assunto(assunto):
    try:
        from aulas_medcof import DADOS_LIMPOS
        for a, area, prio in DADOS_LIMPOS:
            if a == assunto: return area
    except: pass
    return "Geral"

# --- FUNÇÕES PARA AGENDA ---

def listar_revisoes_completas(u, nonce=None):
    _ensure_local_db()
    conn = get_db_connection()
    return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

def excluir_revisao(rid):
    conn = get_db_connection()
    conn.execute("DELETE FROM revisoes WHERE id=?", (rid,))
    conn.commit()

def reagendar_inteligente(rid, desempenho):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    rev = conn.execute("SELECT * FROM revisoes WHERE id=?", (rid,)).fetchone()
    if not rev: return
    
    conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
    fator = {"Excelente": 2.5, "Bom": 1.5, "Ruim": 0.5, "Muito Ruim": 0}.get(desempenho, 1.0)
    intervalo = 7 
    nova_data = (datetime.now() + timedelta(days=max(1, int(intervalo * fator)))).strftime("%Y-%m-%d")
    
    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                 (rev['usuario_id'], rev['assunto_nome'], rev['grande_area'], nova_data, "SRS", "Pendente"))
    conn.commit()

def concluir_revisao(rid, ac, tot):
    # Stub para compatibilidade
    return True

# --- LOGIN E PERFIL ---

def verificar_login(u, p):
    _ensure_local_db()
    conn = get_db_connection()
    row = conn.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (u,)).fetchone()
    if row and bcrypt.checkpw(p.encode(), row['password_hash'].encode()):
        return True, row['nome']
    return False, "Erro"

def criar_usuario(u, p, n):
    conn = get_db_connection()
    pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
    try:
        conn.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (u, n, pw))
        conn.commit()
        return True, "OK"
    except: return False, "Erro"

def get_status_gamer(u, n): return {"nivel": 1, "xp_atual": 0, "meta_diaria": 50, "titulo": "Interno"}, pd.DataFrame()
def get_dados_graficos(u, n): return pd.DataFrame()
def get_benchmark_dados(u, df): return pd.DataFrame()
def get_caderno_erros(u, a): return ""
def salvar_caderno_erros(u, a, t): return True