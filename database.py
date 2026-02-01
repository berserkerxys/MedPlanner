import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client
import os

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa a conexão com o Supabase usando os secrets."""
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# ==========================================
# 📚 MÓDULO 1: VIDEOTECA NATIVA (.PY)
# ==========================================

def listar_conteudo_videoteca():
    """Lê a biblioteca do ficheiro biblioteca_conteudo.py."""
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return pd.DataFrame()
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
        return df
    except Exception:
        return pd.DataFrame()

def get_lista_assuntos_nativa():
    """Gera lista de temas para o selectbox do app."""
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral - Livre", "Simulado - Geral"]
    return sorted(df['assunto'].unique().tolist())

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA (SUPABASE)
# ==========================================

def verificar_login(u, p):
    client = get_supabase()
    if not client: return False, "Erro de Conexão"
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            user = res.data[0]
            stored = user['password_hash']
            if isinstance(stored, str): stored = stored.encode('utf-8')
            if bcrypt.checkpw(p.encode('utf-8'), stored):
                return True, user['nome']
        return False, "Dados incorretos"
    except Exception:
        return False, "Erro no servidor de autenticação"

def criar_usuario(u, p, n):
    client = get_supabase()
    if not client: return False, "Erro de Conexão"
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": hashed}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "nivel": 1, "xp": 0, "titulo": "Calouro"}).execute()
        return True, "Conta criada!"
    except Exception:
        return False, "Erro: Utilizador já existe"

# ==========================================
# 📊 MÓDULO 3: PROGRESSO E DASHBOARD
# ==========================================

def get_progresso_hoje(u):
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data])
    except: return 0

def get_status_gamer(u):
    client = get_supabase()
    if not client: return None, pd.DataFrame()
    try:
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        d = res.data[0]
        xp = d['xp']
        nivel = d['nivel']
        status = {'nivel': nivel, 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': d['titulo'], 'xp_proximo': 1000}
        return status, pd.DataFrame()
    except: return None, pd.DataFrame()

def get_dados_graficos(u):
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        lib = listar_conteudo_videoteca()
        if not lib.empty:
            area_map = lib.set_index('assunto')['grande_area'].to_dict()
            df['area'] = df['assunto_nome'].map(area_map).fillna(df.get('area_manual', 'Geral'))
        else:
            df['area'] = df.get('area_manual', 'Geral')
        df['percentual'] = (df['acertos'].astype(float) / df['total'].astype(float) * 100).round(1)
        df['data'] = df['data_estudo']
        return df
    except: return pd.DataFrame()

# ==========================================
# 📝 MÓDULO 4: REGISTOS E AGENDA
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    client = get_supabase()
    if not client: return "Erro"
    dt = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    try:
        # 1. Salvar Histórico
        client.table("historico").insert({
            "usuario_id": u, "assunto_nome": assunto, "data_estudo": dt, "acertos": acertos, "total": total
        }).execute()
        
        # 2. Agendar Revisão (7 dias depois) se não for banco/simulado
        if "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (data_personalizada + timedelta(days=7)).strftime("%Y-%m-%d") if data_personalizada else (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": u, "assunto_nome": assunto, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
            }).execute()

        # 3. Atualizar XP
        status, _ = get_status_gamer(u)
        nxp = status['xp_total'] + (total * 2)
        client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        return "✅ Registado!"
    except Exception as e: return f"Erro ao salvar: {e}"

def registrar_simulado(u, dados, data_personalizada=None):
    client = get_supabase()
    if not client: return "Erro"
    dt = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    tq = 0
    try:
        for area, v in dados.items():
            if v['total'] > 0:
                tq += v['total']
                client.table("historico").insert({
                    "usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt, "acertos": v['acertos'], "total": v['total']
                }).execute()
        status, _ = get_status_gamer(u)
        nxp = status['xp_total'] + int(tq * 2.5)
        client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        return "✅ Simulado salvo!"
    except: return "Erro ao salvar"

def listar_revisoes_completas(u):
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        # Adiciona a grande área da biblioteca nativa para o visual
        lib = listar_conteudo_videoteca()
        if not lib.empty:
            area_map = lib.set_index('assunto')['grande_area'].to_dict()
            df['grande_area'] = df['assunto_nome'].map(area_map).fillna('Geral')
        else:
            df['grande_area'] = 'Geral'
        return df
    except: return pd.DataFrame()

def concluir_revisao(rid, acertos, total):
    client = get_supabase()
    if not client: return "Erro"
    try:
        # Busca dados da revisão atual
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        if not res.data: return "Revisão não encontrada"
        rev = res.data[0]
        
        # Marca como concluído
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        
        # Regista o desempenho no histórico
        registrar_estudo(rev['usuario_id'], rev['assunto_nome'], acertos, total)
        
        # Lógica de Reagendamento SRS (Simples)
        saltos = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        dias, prox_tipo = saltos.get(rev['tipo'], (None, None))
        
        if prox_tipo:
            dt_prox = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'],
                "data_agendada": dt_prox, "tipo": prox_tipo, "status": "Pendente"
            }).execute()
            
        return "✅ Revisão Concluída!"
    except Exception as e: return f"Erro: {e}"

# --- COMPATIBILIDADE ---
def get_db(): return True
def get_connection(): return None
def sincronizar_videoteca_completa(): return "Modo Nativo Ativo"
def pesquisar_global(t):
    df = listar_conteudo_videoteca()
    if df.empty: return df
    return df[df['titulo'].str.contains(t, case=False, na=False) | df['assunto'].str.contains(t, case=False, na=False)]