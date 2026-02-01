import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client
import os

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception: return None

# ==========================================
# 📚 VIDEOTECA NATIVA (LÊ DO ARQUIVO)
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
    return sorted(df['assunto'].unique().tolist()) if not df.empty else ["Banco Geral"]

def pesquisar_global(termo):
    df = listar_conteudo_videoteca()
    if df.empty: return df
    mask = df['titulo'].str.contains(termo, case=False, na=False) | df['assunto'].str.contains(termo, case=False, na=False)
    return df[mask]

# ==========================================
# 📊 GAMIFICAÇÃO E METAS
# ==========================================
def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce):
    """Calcula questões feitas hoje. Resolve o ImportError."""
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data]) if res.data else 0
    except: return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce):
    client = get_supabase()
    try:
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        d = res.data[0]
        xp = int(d.get('xp', 0))
        meta = int(d.get('meta_diaria', 50))
        
        status = {
            'nivel': 1 + (xp // 1000), 
            'xp_atual': xp % 1000, 
            'xp_total': xp, 
            'titulo': d.get('titulo', 'Residente'), 
            'meta_diaria': meta
        }
        
        hoje = datetime.now().strftime("%Y-%m-%d")
        h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        q = sum([int(i['total']) for i in h.data]) if h.data else 0
        a = sum([int(i['acertos']) for i in h.data]) if h.data else 0
        
        missoes = [
            {"Icon": "🎯", "Meta": "Meta Diária", "Prog": q, "Objetivo": meta, "Unid": "q"},
            {"Icon": "✅", "Meta": "Foco em Acertos", "Prog": a, "Objetivo": int(meta * 0.7), "Unid": "hits"},
            {"Icon": "🔥", "Meta": "XP Hoje", "Prog": q * 2, "Objetivo": meta * 2, "Unid": "xp"}
        ]
        return status, pd.DataFrame(missoes)
    except: return None, pd.DataFrame()

def update_meta_diaria(u, nova_meta):
    client = get_supabase()
    try:
        client.table("perfil_gamer").update({"meta_diaria": int(nova_meta)}).eq("usuario_id", u).execute()
        trigger_refresh()
        return True
    except: return False

# ==========================================
# 📝 REGISTROS (SIMULADOS E AULAS)
# ==========================================
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    client = get_supabase()
    dt = data_p if data_p else datetime.now().date()
    area = area_f if area_f else get_area_por_assunto(assunto)
    try:
        client.table("historico").insert({
            "usuario_id": u, "assunto_nome": assunto, "area_manual": area, 
            "data_estudo": dt.strftime("%Y-%m-%d"), "acertos": int(acertos), "total": int(total)
        }).execute()
        
        if srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": u, "assunto_nome": assunto, "grande_area": area, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"}).execute()
        
        res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res_p.data:
            nxp = int(res_p.data[0]['xp']) + (int(total) * 2)
            client.table("perfil_gamer").update({"xp": nxp}).eq("usuario_id", u).execute()
            
        trigger_refresh()
        return "✅ Registrado!"
    except: return "Erro"

def registrar_simulado(u, dados, data_p=None):
    """Registra simulado com Total e Acertos por área."""
    client = get_supabase()
    dt = data_p.strftime("%Y-%m-%d") if data_p else datetime.now().strftime("%Y-%m-%d")
    inserts = []
    tq = 0
    for area, v in dados.items():
        if int(v['total']) > 0:
            tq += int(v['total'])
            inserts.append({"usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt, "acertos": int(v['acertos']), "total": int(v['total'])})
    try:
        if inserts: client.table("historico").insert(inserts).execute()
        
        # XP Bônus
        res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res_p.data:
            nxp = int(res_p.data[0]['xp']) + int(tq * 2.5)
            client.table("perfil_gamer").update({"xp": nxp}).eq("usuario_id", u).execute()
            
        trigger_refresh()
        return f"✅ Simulado ({tq}q) salvo!"
    except: return "Erro"

@st.cache_data(ttl=300)
def get_dados_graficos(u, nonce):
    client = get_supabase()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        mapa = get_mapa_areas()
        df['area'] = df['assunto_nome'].str.strip().str.lower().map(mapa).fillna(df.get('area_manual', 'Geral'))
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
        df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
        df['data'] = pd.to_datetime(df['data_estudo']).dt.normalize()
        return df.sort_values('data')
    except: return pd.DataFrame()

# ==========================================
# 🔐 AUTH, AGENDA, RESUMOS
# ==========================================
def verificar_login(u, p):
    client = get_supabase()
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            if bcrypt.checkpw(p.encode('utf-8'), res.data[0]['password_hash'].encode('utf-8')):
                return True, res.data[0]['nome']
        return False, "Login falhou"
    except: return False, "Erro conexão"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        h = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": h}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0, "titulo": "Interno", "meta_diaria": 50}).execute()
        return True, "Criado!"
    except: return False, "Usuário existe"

def listar_revisoes_completas(u, n):
    client = get_supabase()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    try:
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        rev = res.data[0]
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev.get('grande_area'), srs=False)
        return "✅ Concluído"
    except: return "Erro"

def get_resumo(u, area):
    client = get_supabase()
    try:
        res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
        return res.data[0]['conteudo'] if res.data else ""
    except: return ""

def salvar_resumo(u, area, texto):
    client = get_supabase()
    try:
        client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
        return True
    except: return False

def deletar_resumo(rid): pass # Simplificado para evitar erro

# Compatibilidade
def excluir_conteudo(id): pass
def get_db(): return True