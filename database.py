import os
import json
import sqlite3
import re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional, TYPE_CHECKING

# Configuração condicional do Supabase (Opcional)
if TYPE_CHECKING:
    from supabase import Client
try:
    from supabase import create_client
except Exception:
    create_client = None

DB_NAME = "medplanner_local.db"

# ==============================================================================
# 1. CONEXÃO E CACHE DE RECURSOS
# ==============================================================================

@st.cache_resource
def get_db_connection():
    """Mantém uma única conexão aberta durante toda a sessão do servidor."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # Permite aceder às colunas pelo nome (ex: row['nome'])
    conn.row_factory = sqlite3.Row
    return conn

def trigger_refresh():
    """Invalida caches visuais forçando a mudança de um nonce na sessão."""
    if 'data_nonce' not in st.session_state: 
        st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# ==============================================================================
# 2. CACHE DE DADOS ESTÁTICOS (AULAS MEDCOF)
# ==============================================================================

@st.cache_data(ttl=3600) # Cache por 1 hora
def _carregar_dados_medcof():
    """Carrega a lista mestre de aulas e áreas de forma optimizada."""
    lista_aulas, mapa_areas = [], {}
    try:
        from aulas_medcof import DADOS_LIMPOS
        for item in DADOS_LIMPOS:
            if isinstance(item, tuple) and len(item) >= 2:
                aula, area = str(item[0]).strip(), str(item[1]).strip()
                lista_aulas.append(aula)
                mapa_areas[aula] = normalizar_area(area)
    except Exception as e:
        print(f"Aviso: Não foi possível carregar aulas_medcof: {e}")
    return sorted(list(set(lista_aulas))), mapa_areas

def normalizar_area(nome):
    if not nome: return "Geral"
    n_upper = str(nome).strip().upper()
    mapeamento = {
        "G.O": "Ginecologia e Obstetrícia", "GO": "Ginecologia e Obstetrícia",
        "PED": "Pediatria", "CM": "Clínica Médica", "CIRURGIA": "Cirurgia",
        "PREVENTIVA": "Preventiva"
    }
    return mapeamento.get(n_upper, str(nome).strip())

def get_lista_assuntos_nativa():
    aulas, _ = _carregar_dados_medcof()
    return aulas if aulas else ["Banco Geral"]

def get_area_por_assunto(assunto):
    _, mapa = _carregar_dados_medcof()
    return mapa.get(assunto, "Geral")

# ==============================================================================
# 3. INICIALIZAÇÃO E TABELAS
# ==============================================================================

def _ensure_local_db():
    """Garante a integridade das tabelas no arranque do site."""
    conn = get_db_connection()
    c = conn.cursor()
    
    tabelas = [
        "CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)",
        "CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)",
        "CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)",
        "CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)",
        "CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))",
        "CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)"
    ]
    
    for sql in tabelas:
        c.execute(sql)
    
    # Migrações rápidas (colunas novas)
    colunas_novas = [
        ("usuarios", "email", "TEXT"),
        ("usuarios", "data_nascimento", "TEXT"),
        ("historico", "tipo_estudo", "TEXT")
    ]
    for tab, col, tip in colunas_novas:
        try: c.execute(f"ALTER TABLE {tab} ADD COLUMN {col} {tip}")
        except: pass
        
    conn.commit()

# ==============================================================================
# 4. GESTÃO DE UTILIZADORES E SESSÃO
# ==============================================================================

def verificar_login(u, p):
    conn = get_db_connection()
    row = conn.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (u,)).fetchone()
    if row and bcrypt.checkpw(p.encode(), row['password_hash'].encode()):
        return True, row['nome']
    return False, "Credenciais Inválidas"

def criar_usuario(u, p, n):
    try:
        conn = get_db_connection()
        pw_hash = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        conn.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (u, n, pw_hash))
        conn.commit()
        return True, "OK"
    except Exception as e:
        return False, str(e)

# ==============================================================================
# 5. CRONOGRAMA E ESTADO
# ==============================================================================

def get_cronograma_status(u):
    conn = get_db_connection()
    row = conn.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (u,)).fetchone()
    if row and row['estado_json']:
        return json.loads(row['estado_json'])
    return {}

def salvar_cronograma_status(u, dados):
    conn = get_db_connection()
    json_str = json.dumps(dados, ensure_ascii=False)
    conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?, ?)", (u, json_str))
    conn.commit()
    return True

# ==============================================================================
# 6. HISTÓRICO E PERFORMANCE (Otimizado para Dashboard)
# ==============================================================================

def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=False, tipo_estudo="Pos-Aula"):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * (3 if tipo_estudo == "Pre-Aula" else 2)
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)",
        (u, assunto, area, dt, int(acertos), int(total), tipo_estudo)
    )
    
    # Gamificação
    row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
    old_xp = row['xp'] if row else 0
    conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
    
    # SRS (Agenda)
    if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
        dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
    
    conn.commit()
    trigger_refresh()
    return f"✅ Salvo em {area}!"

@st.cache_data(ttl=60) # Cache curto para reflectir mudanças rápidas no Dashboard
def get_dados_graficos(u, nonce=None):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        df['area'] = df['area_manual'].apply(normalizar_area)
    return df

def get_status_gamer(u, nonce=None):
    conn = get_db_connection()
    row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
    xp, meta = (row['xp'], row['meta_diaria']) if row else (0, 50)
    
    # Progresso Hoje
    hoje = datetime.now().strftime("%Y-%m-%d")
    r_h = conn.execute("SELECT SUM(total) as tot FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
    q_hoje = r_h['tot'] if r_h and r_h['tot'] else 0
    
    status = {'nivel': 1+(xp//1000), 'xp_atual': xp, 'meta_diaria': meta, 'titulo': "R1" if xp > 2000 else "Interno"}
    df_m = pd.DataFrame([{"Prog": q_hoje}])
    return status, df_m

# ==============================================================================
# 7. AGENDA, PERFIL E BENCHMARK
# ==============================================================================

def listar_revisoes_completas(u, nonce=None):
    conn = get_db_connection()
    return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

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

def get_benchmark_dados(u, df_user):
    # Simulação de dados de benchmark para performance
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    dados = []
    for a in areas:
        dados.append({"Area": a, "Tipo": "Você", "Performance": 60})
        dados.append({"Area": a, "Tipo": "Comunidade", "Performance": 65})
    return pd.DataFrame(dados)

def get_caderno_erros(u, area):
    conn = get_db_connection()
    row = conn.execute("SELECT conteudo FROM resumos WHERE usuario_id=? AND grande_area=?", (u, area)).fetchone()
    return row['conteudo'] if row else ""

def salvar_caderno_erros(u, area, texto):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto))
    conn.commit()
    return True

def get_progresso_hoje(u, n=None):
    _, df = get_status_gamer(u, n)
    return df.iloc[0]['Prog']

def update_meta_diaria(u, v):
    conn = get_db_connection()
    conn.execute("UPDATE perfil_gamer SET meta_diaria=? WHERE usuario_id=?", (v, u))
    conn.commit()
    trigger_refresh()

# Funções não utilizadas mas mantidas para compatibilidade de import
def get_dados_pessoais(u): return {"email": "", "nascimento": None}
def update_dados_pessoais(u, e, n): return True
def registrar_simulado(u, d): return True