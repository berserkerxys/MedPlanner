import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception:
        return None

# ==========================================
# 📚 VIDEOTECA (CACHE PERMANENTE)
# ==========================================

@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        return pd.DataFrame(VIDEOTECA_GLOBAL, columns=['grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'])
    except: return pd.DataFrame()

@st.cache_data(ttl=None)
def get_mapa_areas():
    df = listar_conteudo_videoteca()
    if df.empty: return {}
    return df.set_index(df['assunto'].str.strip().str.lower())['grande_area'].to_dict()

def get_area_por_assunto(assunto):
    mapa = get_mapa_areas()
    return mapa.get(str(assunto).strip().lower(), "Geral")

@st.cache_data(ttl=None)
def get_lista_assuntos_nativa():
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral", "Simulado"]
    return sorted(df['assunto'].unique().tolist())

def pesquisar_global(termo):
    df = listar_conteudo_videoteca()
    if df.empty: return df
    mask = df['titulo'].str.contains(termo, case=False, na=False) | df['assunto'].str.contains(termo, case=False, na=False)
    return df[mask]

# ==========================================
# 📊 ANALYTICS E MISSÕES
# ==========================================

def trigger_refresh():
    if 'data_nonce' in st.session_state: st.session_state.data_nonce += 1

@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce):
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data])
    except: return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce):
    client = get_supabase()
    if not client: return None, pd.DataFrame()
    try:
        # 1. Perfil
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        d = res.data[0]
        xp = d['xp']
        status = {'nivel': 1 + (xp // 1000), 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': d['titulo'], 'xp_proximo': 1000}

        # 2. Missões do Dia
        hoje = datetime.now().strftime("%Y-%m-%d")
        h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        q = sum([int(i['total']) for i in h.data]) if h.data else 0
        a = sum([int(i['acertos']) for i in h.data]) if h.data else 0
        
        missoes = [
            {"Icon": "🎯", "Meta": "Questões", "Prog": q, "Objetivo": 50, "Cor": "#2563eb"},
            {"Icon": "✅", "Meta": "Acertos", "Prog": a, "Objetivo": 35, "Cor": "#059669"},
            {"Icon": "🔥", "Meta": "XP Diário", "Prog": q * 2, "Objetivo": 100, "Cor": "#d97706"}
        ]
        return status, pd.DataFrame(missoes)
    except: return None, pd.DataFrame()

@st.cache_data(ttl=300)
def get_dados_graficos(u, nonce):
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        mapa = get_mapa_areas()
        df['area'] = df['assunto_nome'].str.strip().str.lower().map(mapa).fillna(df.get('area_manual', 'Geral'))
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
        df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
        df['data'] = pd.to_datetime(df['data_estudo'])
        return df.sort_values('data')
    except: return pd.DataFrame()

# ==========================================
# 📝 REGISTOS E SEGURANÇA
# ==========================================

def verificar_login(u, p):
    client = get_supabase()
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            if bcrypt.checkpw(p.encode('utf-8'), res.data[0]['password_hash'].encode('utf-8')):
                return True, res.data[0]['nome']
        return False, "Dados Incorretos"
    except: return False, "Erro Servidor"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        h = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": h}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0, "titulo": "Interno"}).execute()
        return True, "Criado!"
    except: return False, "Usuário já existe"

def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    client = get_supabase()
    dt = data_p if data_p else datetime.now().date()
    area = area_f if area_f else get_area_por_assunto(assunto)
    try:
        client.table("historico").insert({"usuario_id": u, "assunto_nome": assunto, "area_manual": area, "data_estudo": dt.strftime("%Y-%m-%d"), "acertos": int(acertos), "total": int(total)}).execute()
        if srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": u, "assunto_nome": assunto, "grande_area": area, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"}).execute()
        
        # XP
        res_xp = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res_xp.data:
            new_xp = res_xp.data[0]['xp'] + (int(total) * 2)
            client.table("perfil_gamer").update({"xp": new_xp}).eq("usuario_id", u).execute()
        
        trigger_refresh()
        return "✅ Registrado!"
    except: return "Erro"

def registrar_simulado(u, dados, data_p=None):
    client = get_supabase()
    dt = data_p.strftime("%Y-%m-%d") if data_p else datetime.now().strftime("%Y-%m-%d")
    tq = 0
    inserts = []
    for area, v in dados.items():
        if v['total'] > 0:
            tq += v['total']
            inserts.append({"usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt, "acertos": int(v['acertos']), "total": int(v['total'])})
    try:
        if inserts: client.table("historico").insert(inserts).execute()
        trigger_refresh()
        return f"✅ Simulado salvo!"
    except: return "Erro"

def listar_revisoes_completas(u, n):
    client = get_supabase()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def concluir_revisao(rid, acertos, total):
    client = get_supabase()
    try:
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        rev = res.data[0]
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        registrar_estudo(rev['usuario_id'], rev['assunto_nome'], acertos, total, area_f=rev.get('grande_area'), srs=False)
        ciclo = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        d, prox = ciclo.get(rev['tipo'], (None, None))
        if prox:
            dt_p = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'], "grande_area": rev.get('grande_area'), "data_agendada": dt_p, "tipo": prox, "status": "Pendente"}).execute()
        trigger_refresh()
        return "✅ Feito!"
    except: return "Erro"

def get_db(): return True