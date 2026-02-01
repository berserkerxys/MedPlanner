import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client

# --- CONFIGURAÇÃO DE LIGAÇÃO (SUPABASE) ---

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa a ligação única com o Supabase."""
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception as e:
        return None

# ==========================================
# 📚 MÓDULO 1: VIDEOTECA NATIVA (MEMÓRIA PERMANENTE)
# ==========================================

@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return pd.DataFrame()
        return pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=None)
def get_mapa_areas():
    df = listar_conteudo_videoteca()
    if df.empty: return {}
    return df.set_index(df['assunto'].str.strip().str.lower())['grande_area'].to_dict()

def get_area_por_assunto(nome_assunto):
    mapa = get_mapa_areas()
    return mapa.get(str(nome_assunto).strip().lower(), "Geral")

@st.cache_data(ttl=None)
def get_lista_assuntos_nativa():
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral - Livre", "Simulado - Geral"]
    return sorted(df['assunto'].unique().tolist())

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA E PERFIL
# ==========================================

def verificar_login(u, p):
    client = get_supabase()
    if not client: return False, "Sistema Offline"
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            user = res.data[0]
            stored = user['password_hash']
            if isinstance(stored, str): stored = stored.encode('utf-8')
            if bcrypt.checkpw(p.encode('utf-8'), stored):
                if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
                return True, user['nome']
        return False, "Dados de acesso incorretos"
    except Exception:
        return False, "Erro no servidor"

def criar_usuario(u, p, n):
    client = get_supabase()
    if not client: return False, "Sem ligação"
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": hashed}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "nivel": 1, "xp": 0, "titulo": "Calouro"}).execute()
        return True, "Conta criada com sucesso!"
    except Exception:
        return False, "Usuário já existe"

def update_perfil_nome(u, novo_nome):
    client = get_supabase()
    try:
        client.table("usuarios").update({"nome": novo_nome}).eq("username", u).execute()
        return True
    except: return False

# ==========================================
# 📊 MÓDULO 3: GAMIFICAÇÃO E MISSÕES (CORRIGIDO)
# ==========================================

def trigger_refresh():
    if 'data_nonce' in st.session_state:
        st.session_state.data_nonce += 1

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
    """Calcula Missões Diárias e Semanais com precisão."""
    client = get_supabase()
    if not client: return None, pd.DataFrame()
    
    try:
        # 1. Perfil
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        d = res.data[0]
        xp = d['xp']
        nivel = 1 + (xp // 1000)
        
        status = {
            'nivel': nivel, 
            'xp_atual': xp % 1000, 
            'xp_total': xp, 
            'titulo': d['titulo'], 
            'xp_proximo': 1000
        }

        # 2. Dados Históricos para Missões
        hoje = datetime.now().strftime("%Y-%m-%d")
        hist_hoje = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        
        q_hoje = sum([int(i['total']) for i in hist_hoje.data]) if hist_hoje.data else 0
        a_hoje = sum([int(i['acertos']) for i in hist_hoje.data]) if hist_hoje.data else 0
        
        # Missões formatadas para DataFrame
        missoes_data = [
            {"Icon": "🎯", "Missão": "Meta Diária de Questões", "Progresso": q_hoje, "Meta": 50, "Unid": "q"},
            {"Icon": "🔥", "Missão": "Precisão (Acertos)", "Progresso": a_hoje, "Meta": 30, "Unid": "ac"},
            {"Icon": "⚡", "Missão": "XP do Dia", "Progresso": q_hoje * 2, "Meta": 100, "Unid": "xp"}
        ]
        
        return status, pd.DataFrame(missoes_data)
    except:
        return None, pd.DataFrame()

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
        df['percentual'] = (df['acertos'].astype(float) / df['total'].astype(float) * 100).round(1)
        df['data'] = pd.to_datetime(df['data_estudo'])
        return df.sort_values('data')
    except: return pd.DataFrame()

# ==========================================
# 📝 MÓDULO 4: REGISTOS E AGENDA
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None, area_forçada=None, agendar_srs=True):
    client = get_supabase()
    dt_obj = data_personalizada if data_personalizada else datetime.now().date()
    dt_str = dt_obj.strftime("%Y-%m-%d")
    area = area_forçada if area_forçada else get_area_por_assunto(assunto)
    try:
        client.table("historico").insert({"usuario_id": u, "assunto_nome": assunto, "area_manual": area, "data_estudo": dt_str, "acertos": int(acertos), "total": int(total)}).execute()
        if agendar_srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt_obj + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": u, "assunto_nome": assunto, "grande_area": area, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"}).execute()
        update_xp(u, int(total * 2))
        trigger_refresh()
        return "✅ Registado!"
    except Exception as e: return f"Erro: {e}"

def registrar_simulado(u, dados, data_personalizada=None):
    client = get_supabase()
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    tq = 0
    inserts = []
    for area, v in dados.items():
        if v['total'] > 0:
            tq += v['total']
            inserts.append({"usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt_str, "acertos": int(v['acertos']), "total": int(v['total'])})
    try:
        if inserts: client.table("historico").insert(inserts).execute()
        update_xp(u, int(tq * 2.5))
        trigger_refresh()
        return f"✅ Simulado ({tq}q)!"
    except: return "Erro"

def update_xp(u, qtd):
    client = get_supabase()
    try:
        res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res.data:
            nxp = res.data[0]['xp'] + qtd
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
    except: pass

@st.cache_data(ttl=300)
def listar_revisoes_completas(u, nonce):
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
        registrar_estudo(u=rev['usuario_id'], assunto=rev['assunto_nome'], acertos=acertos, total=total, area_forçada=rev.get('grande_area'), agendar_srs=False)
        ciclo = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        dias, prox = ciclo.get(rev['tipo'], (None, None))
        if prox:
            dt_prox = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'], "grande_area": rev.get('grande_area'), "data_agendada": dt_prox, "tipo": prox, "status": "Pendente"}).execute()
        trigger_refresh()
        return "✅ Feito!"
    except: return "Erro"

# --- COMPATIBILIDADE ---
def get_db(): return True
def get_connection(): return None
def sincronizar_videoteca_completa(): return "OK"