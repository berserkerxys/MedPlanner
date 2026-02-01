# database.py
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client # type: ignore
try:
    from supabase import create_client
except Exception:
    create_client = None

DB_NAME = "medplanner_local.db"

# --- AUXILIARES E CONEXÃO ---
def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

@st.cache_resource
def get_supabase() -> Optional["Client"]:
    try:
        if "supabase" in st.secrets:
            return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: pass
    return None

def _ensure_local_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT)")
    conn.commit()
    conn.close()

# --- INTEGRAÇÃO MEDCOF (PARA SIDEBAR) ---
@st.cache_data
def _carregar_dados_medcof():
    lista_aulas, mapa_areas = [], {}
    try:
        import aulas_medcof # cite: 18
        dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        for item in dados:
            if isinstance(item, tuple) and len(item) >= 2:
                aula, area = str(item[0]).strip(), str(item[1]).strip()
                lista_aulas.append(aula)
                mapa_areas[aula] = area
    except: pass
    return sorted(list(set(lista_aulas))), mapa_areas

def get_lista_assuntos_nativa():
    aulas, _ = _carregar_dados_medcof()
    return aulas if aulas else ["Banco Geral"]

def get_area_por_assunto(assunto):
    _, mapa = _carregar_dados_medcof()
    return mapa.get(assunto, "Geral")

# --- REGISTROS E PERFORMANCE ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = area_f if area_f else get_area_por_assunto(assunto)
    xp_ganho = int(total) * 2
    client = get_supabase()

    if client:
        client.table("historico").insert({"usuario_id":u, "assunto_nome":assunto, "area_manual":area, "data_estudo":dt, "acertos":int(acertos), "total":int(total)}).execute()
        if srs:
            dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
        res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        old_xp = res.data[0]['xp'] if res.data else 0
        client.table("perfil_gamer").upsert({"usuario_id":u, "xp": old_xp + xp_ganho}).execute()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total))
    trigger_refresh()
    return f"✅ Gravado em {area}!"

@st.cache_data(ttl=60)
def get_status_gamer(u, nonce=None):
    client, xp, meta = get_supabase(), 0, 50
    hoje = datetime.now().strftime("%Y-%m-%d")
    if client:
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if res.data: xp, meta = res.data[0].get('xp', 0), res.data[0].get('meta_diaria', 50)
        h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        q, a = sum(x['total'] for x in h.data), sum(x['acertos'] for x in h.data)
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
            if row: xp, meta = row
            q, a = 0, 0 # Fallback simplificado
    status = {'nivel': 1 + (xp // 1000), 'xp_atual': xp % 1000, 'xp_total': xp, 'meta_diaria': meta, 'titulo': "Interno"}
    df_m = pd.DataFrame([{"Icon": "🎯", "Meta": "Questões", "Prog": q, "Objetivo": meta, "Unid": "q"}])
    return status, df_m

def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    if client:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn: df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        df['area'] = df['area_manual'].fillna("Geral")
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
    return df

# --- AUTH (RESTAURADA) ---
def verificar_login(u, p):
    client = get_supabase()
    if client:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data and bcrypt.checkpw(p.encode(), res.data[0]['password_hash'].encode()):
            return True, res.data[0]['nome']
    return False, "Usuário ou senha inválidos"

def criar_usuario(u, p, n):
    client = get_supabase()
    if client:
        pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": pw}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0}).execute()
        return True, "Conta criada com sucesso!"
    return False, "Erro ao conectar ao servidor"

# --- STUBS PARA COMPATIBILIDADE ---
def get_resumo(u, area): return ""
def salvar_resumo(u, area, texto): return True
def listar_conteudo_videoteca(): return pd.DataFrame()
def listar_revisoes_completas(u, n=None): return pd.DataFrame()
def registrar_simulado(u, d): return "✅"