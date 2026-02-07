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
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
    
    # Migrações rápidas
    try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    except: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
    except: pass
    try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
    except: pass
    conn.commit()

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
    conn = get_db_connection()
    row = conn.execute("SELECT conteudo FROM resumos WHERE usuario_id=? AND grande_area=?", (u, area)).fetchone()
    return row['conteudo'] if row else ""

def salvar_caderno_erros(u, area, texto):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto or ""))
    conn.commit()
    return True

def get_resumo(u, a): return get_caderno_erros(u, a)
def salvar_resumo(u, a, t): return salvar_caderno_erros(u, a, t)

# --- 4. FUNÇÕES DE CRONOGRAMA ---
def get_cronograma_status(u):
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
    base = {"Diamante": 20, "Vermelho": 15, "Amarelo": 10, "Verde": 5}
    m = base.get(prioridade, 10)
    return m, m + 10

def resetar_revisoes_aula(u, aula):
    estado = get_cronograma_status(u)
    if aula in estado:
        estado[aula].update({"acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0, "feito": False})
        salvar_cronograma_status(u, estado)
    return True

def atualizar_progresso_cronograma(u, assunto, acertos, total, tipo_estudo="Pos-Aula"):
    """Atualiza APENAS os números no cronograma."""
    estado = get_cronograma_status(u)
    dados = estado.get(assunto, {
        "feito": False, "prioridade": "Normal", 
        "acertos_pre": 0, "total_pre": 0,
        "acertos_pos": 0, "total_pos": 0
    })
    
    if tipo_estudo == "Pre-Aula":
        dados["acertos_pre"] = int(dados.get("acertos_pre", 0)) + int(acertos)
        dados["total_pre"] = int(dados.get("total_pre", 0)) + int(total)
    else: 
        dados["acertos_pos"] = int(dados.get("acertos_pos", 0)) + int(acertos)
        dados["total_pos"] = int(dados.get("total_pos", 0)) + int(total)
    
    if dados["total_pos"] > 0: dados["feito"] = True
        
    estado[assunto] = dados
    salvar_cronograma_status(u, estado)

# --- 5. FUNÇÕES DE PERFORMANCE E DASHBOARD ---
@st.cache_data(ttl=60)
def get_dados_graficos(u, nonce=None):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        df['area'] = df['area_manual']
    return df

def get_status_gamer(u, nonce=None):
    conn = get_db_connection()
    row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
    xp, meta = (row['xp'], row['meta_diaria']) if row else (0, 50)
    return {"nivel": 1+(xp//1000), "xp_atual": xp, "meta_diaria": meta, "titulo": "Interno"}, pd.DataFrame()

def get_benchmark_dados(u, df_user):
    # Mock para evitar erro de importação
    return pd.DataFrame([{"Area": "Geral", "Tipo": "Você", "Performance": 70}, {"Area": "Geral", "Tipo": "Comunidade", "Performance": 65}])

def get_progresso_hoje(u, n=None):
    conn = get_db_connection()
    hoje = datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT SUM(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
    return r[0] if r and r[0] else 0

# --- 6. GESTÃO DE USUÁRIO ---
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

def get_dados_pessoais(u):
    conn = get_db_connection()
    r = conn.execute("SELECT email, data_nascimento FROM usuarios WHERE username=?", (u,)).fetchone()
    return {"email": r['email'] if r else "", "nascimento": r['data_nascimento'] if r else None}

def update_dados_pessoais(u, e, n):
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET email=?, data_nascimento=? WHERE username=?", (e, n, u))
    conn.commit()
    return True

def resetar_conta_usuario(u):
    conn = get_db_connection()
    conn.execute("DELETE FROM historico WHERE usuario_id=?", (u,))
    conn.execute("DELETE FROM revisoes WHERE usuario_id=?", (u,))
    conn.execute("DELETE FROM cronogramas WHERE usuario_id=?", (u,))
    conn.execute("UPDATE perfil_gamer SET xp=0 WHERE usuario_id=?", (u,))
    conn.commit()
    trigger_refresh()
    return True

def registrar_estudo(u, a, ac, t, **kwargs):
    conn = get_db_connection()
    dt = datetime.now().strftime("%Y-%m-%d")
    
    # Extrai tipo_estudo e srs dos kwargs ou define padrão
    tipo_estudo = kwargs.get('tipo_estudo', 'Pos-Aula')
    srs = kwargs.get('srs', False)
    area_f = kwargs.get('area_f', None)

    # Garante normalização da área
    if not area_f:
        area_f = get_area_por_assunto(a)
    area = normalizar_area(area_f)
    
    # Insere no histórico
    conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)", 
                 (u, a, area, dt, int(ac), int(t), tipo_estudo))
    
    # Atualiza cronograma
    atualizar_progresso_cronograma(u, a, ac, t, tipo_estudo)

    # Agenda revisão se necessário
    if srs:
        dt_rev = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", 
                     (u, a, area, dt_rev, "1 Semana", "Pendente"))

    conn.commit()
    trigger_refresh()
    return f"✅ Salvo em {area}!"

def registrar_simulado(u, dados):
    """
    Registra um simulado completo, salvando cada área individualmente.
    dados: {'Area': {'acertos': 10, 'total': 20}, ...}
    """
    conn = get_db_connection()
    dt = datetime.now().strftime("%Y-%m-%d")
    
    for area, valores in dados.items():
        if int(valores['total']) > 0:
            conn.execute(
                "INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)",
                (u, f"Simulado - {area}", normalizar_area(area), dt, int(valores['acertos']), int(valores['total']), "Simulado")
            )
    
    conn.commit()
    trigger_refresh()
    return "✅ Simulado Salvo!"

def update_meta_diaria(u, m):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, meta_diaria) VALUES (?,?)", (u, m))
    conn.commit()
    return True

def get_conquistas_e_stats(u): return 0, [], None

def listar_revisoes_completas(u, nonce=None):
    conn = get_db_connection()
    return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

def concluir_revisao(rid, ac, tot):
    # Registra como Pós-Aula para contar no progresso
    registrar_estudo(rid, "Revisão", ac, tot, tipo_estudo="Pos-Aula")
    return "✅ OK"

def excluir_revisao(rid):
    conn = get_db_connection()
    conn.execute("DELETE FROM revisoes WHERE id=?", (rid,))
    conn.commit()
    trigger_refresh()

def reagendar_inteligente(rid, desempenho):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    rev = conn.execute("SELECT * FROM revisoes WHERE id=?", (rid,)).fetchone()
    if not rev: return
    
    conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
    fator = {"Excelente": 2.5, "Bom": 1.5, "Ruim": 0.5, "Muito Ruim": 0}.get(desempenho, 1.0)
    intervalo = 7 # Simplificado
    nova_data = (datetime.now() + timedelta(days=max(1, int(intervalo * fator)))).strftime("%Y-%m-%d")
    
    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                 (rev['usuario_id'], rev['assunto_nome'], rev['grande_area'], nova_data, "SRS", "Pendente"))
    conn.commit()
    trigger_refresh()

# Stubs para compatibilidade
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_db(): return True

# --- SUPABASE STUBS (MANTIDOS PARA COMPATIBILIDADE) ---
# Se não estiver usando Supabase, estas funções evitam erros de importação
def get_supabase(): return None