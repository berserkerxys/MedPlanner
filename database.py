# database.py
# Versão Integrada: Lê aulas_medcof.py (Tuplas) + Videoteca + Banco de Dados

import os
import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional, TYPE_CHECKING

# Import supabase client lazily
if TYPE_CHECKING:
    from supabase import Client  # type: ignore

try:
    from supabase import create_client
except Exception:
    create_client = None

# Nome do Banco Local (Fallback)
DB_NAME = "medplanner_local.db"

# -------------------------
# CACHE DE DADOS EXTERNOS (MEDCOF)
# -------------------------
@st.cache_data
def _carregar_dados_medcof():
    """
    Importa aulas_medcof.py e retorna:
    1. Lista de apenas os nomes das aulas (para o selectbox)
    2. Dicionário {Nome: Área} (para preencher a área automaticamente)
    """
    lista_aulas = []
    mapa_areas = {}
    
    try:
        import aulas_medcof
        # Procura por listas no arquivo (ex: DADOS_LIMPOS)
        for name in dir(aulas_medcof):
            if name.startswith("_"): continue
            val = getattr(aulas_medcof, name)
            
            if isinstance(val, list):
                for item in val:
                    # Suporte para tuplas ("Aula", "Area") - Estrutura MedCof
                    if isinstance(item, tuple) and len(item) >= 2:
                        aula, area = item[0], item[1]
                        lista_aulas.append(aula)
                        mapa_areas[aula] = area
                    # Suporte para strings simples
                    elif isinstance(item, str):
                        lista_aulas.append(item)
                    # Suporte para dicionários
                    elif isinstance(item, dict):
                        t = item.get('titulo') or item.get('assunto') or item.get('tema')
                        a = item.get('grande_area') or item.get('area')
                        if t:
                            lista_aulas.append(t)
                            if a: mapa_areas[t] = a
                            
    except ImportError:
        pass # Arquivo não encontrado, segue o fluxo
    except Exception as e:
        print(f"Erro ao ler aulas_medcof: {e}")
        
    return sorted(list(set(lista_aulas))), mapa_areas

# -------------------------
# HELPERS DE BANCO DE DADOS
# -------------------------
def _ensure_local_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS assuntos (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, grande_area TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT)")
    conn.commit()
    conn.close()

@st.cache_resource
def get_supabase() -> Optional["Client"]:
    try:
        if "supabase" in st.secrets and create_client:
            return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        return None
    except:
        return None

def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# -------------------------
# LISTAGEM E VIDEOTECA
# -------------------------
def get_lista_assuntos_nativa():
    """Combina MedCof + Videoteca + Banco para o SelectBox"""
    # 1. Carrega do MedCof
    aulas_medcof, _ = _carregar_dados_medcof()
    
    # 2. Carrega da Videoteca
    aulas_video = []
    df = listar_conteudo_videoteca()
    if not df.empty:
        if 'assunto' in df.columns: aulas_video.extend(df['assunto'].dropna().tolist())
        if 'titulo' in df.columns: aulas_video.extend(df['titulo'].dropna().tolist())
        
    # 3. Combina e remove duplicatas
    todos = set(aulas_medcof + aulas_video)
    
    if not todos:
        return ["Banco Geral"]
        
    return sorted(list(todos))

def get_area_por_assunto(assunto):
    """Retorna a Grande Área (ex: Cirurgia) baseada no nome do assunto."""
    # 1. Tenta no mapa do MedCof
    _, mapa = _carregar_dados_medcof()
    if assunto in mapa:
        return mapa[assunto]
        
    # 2. Tenta na Videoteca
    df = listar_conteudo_videoteca()
    if not df.empty and 'grande_area' in df.columns:
        # Busca exata
        match = df[df['assunto'] == assunto] if 'assunto' in df.columns else pd.DataFrame()
        if not match.empty: return match.iloc[0]['grande_area']
        
        match_t = df[df['titulo'] == assunto] if 'titulo' in df.columns else pd.DataFrame()
        if not match_t.empty: return match_t.iloc[0]['grande_area']

    return "Geral" # Fallback

@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    # Tenta Supabase
    client = get_supabase()
    if client:
        try:
            res = client.table("videoteca").select("*").execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    
    # Tenta arquivo python local (biblioteca_conteudo.py)
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        return pd.DataFrame(VIDEOTECA_GLOBAL, columns=['grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id_conteudo'])
    except: pass

    # Tenta JSON exportado
    if os.path.exists("videoteca_export.json"):
        return pd.read_json("videoteca_export.json")
        
    return pd.DataFrame()

def pesquisar_global(termo):
    df = listar_conteudo_videoteca()
    if df.empty: return df
    mask = pd.Series([False]*len(df))
    for col in ['titulo', 'assunto']:
        if col in df.columns:
            mask |= df[col].astype(str).str.contains(termo, case=False, na=False)
    return df[mask]

# -------------------------
# FUNCIONALIDADES GAMER & PROGRESSO
# -------------------------
@st.cache_data(ttl=60)
def get_progresso_hoje(u, nonce=None):
    hoje = datetime.now().strftime("%Y-%m-%d")
    client = get_supabase()
    
    # Supabase
    if client:
        try:
            res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            return sum(item['total'] for item in res.data)
        except: pass
        
    # Local
    try:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        res = conn.execute("SELECT sum(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
        conn.close()
        return res[0] if res[0] else 0
    except: return 0

@st.cache_data(ttl=60)
def get_status_gamer(u, nonce=None):
    client = get_supabase()
    xp, titulo, meta = 0, "Interno", 50
    
    # Busca Perfil
    if client:
        try:
            res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
            if res.data:
                d = res.data[0]
                xp, titulo, meta = d.get('xp', 0), d.get('titulo', 'Interno'), d.get('meta_diaria', 50)
        except: pass
    else:
        try:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT xp, titulo, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                if row: xp, titulo, meta = row
        except: pass
        
    # Busca Stats Hoje
    q_hoje, a_hoje = 0, 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    if client:
        try:
            h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            if h.data:
                q_hoje = sum(x['total'] for x in h.data)
                a_hoje = sum(x['acertos'] for x in h.data)
        except: pass
    else:
        try:
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT sum(total), sum(acertos) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
                if row and row[0]: q_hoje, a_hoje = row
        except: pass

    status = {
        'nivel': 1 + (xp // 1000),
        'xp_atual': xp % 1000,
        'xp_total': xp,
        'titulo': titulo,
        'meta_diaria': meta
    }
    
    missoes = [
        {"Icon": "🎯", "Meta": "Questões", "Prog": q_hoje, "Objetivo": meta, "Unid": "q"},
        {"Icon": "✅", "Meta": "Acertos", "Prog": a_hoje, "Objetivo": int(meta * 0.7), "Unid": "hits"},
        {"Icon": "⚡", "Meta": "XP Hoje", "Prog": q_hoje * 2, "Objetivo": meta * 2, "Unid": "xp"}
    ]
    return status, pd.DataFrame(missoes)

def update_meta_diaria(u, nova):
    client = get_supabase()
    if client:
        client.table("perfil_gamer").update({"meta_diaria": int(nova)}).eq("usuario_id", u).execute()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT OR IGNORE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, 0, 'Interno', ?)", (u, nova))
            conn.execute("UPDATE perfil_gamer SET meta_diaria=? WHERE usuario_id=?", (nova, u))
    trigger_refresh()

# -------------------------
# REGISTROS DE ESTUDO
# -------------------------
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    # Usa a função inteligente para descobrir a área se não informada
    area = area_f if area_f else get_area_por_assunto(assunto)
    xp_ganho = int(total) * 2
    
    client = get_supabase()
    
    if client:
        try:
            # Histórico
            client.table("historico").insert({
                "usuario_id": u, "assunto_nome": assunto, "area_manual": area, 
                "data_estudo": dt, "acertos": int(acertos), "total": int(total)
            }).execute()
            
            # SRS (Revisão Agendada)
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({
                    "usuario_id": u, "assunto_nome": assunto, "grande_area": area, 
                    "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
                }).execute()
                
            # XP
            curr = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            curr_xp = curr.data[0]['xp'] if curr.data else 0
            client.table("perfil_gamer").upsert({"usuario_id": u, "xp": curr_xp + xp_ganho}).execute()
            
            trigger_refresh()
            return f"✅ Registrado em {area}!"
        except Exception as e:
            return f"Erro Sync: {e}"
    else:
        # Local
        try:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", 
                             (u, assunto, area, dt, acertos, total))
                
                if srs and "Simulado" not in assunto:
                    dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                                 (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
                
                # XP
                row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                old_xp = row[0] if row else 0
                conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
            
            trigger_refresh()
            return f"✅ Registrado em {area}!"
        except Exception as e:
            return f"Erro Local: {e}"

def registrar_simulado(u, dados):
    total_q = sum(int(d['total']) for d in dados.values())
    if total_q == 0: return "Sem dados"
    
    # Salva cada área como um registro
    for area, d in dados.items():
        if int(d['total']) > 0:
            registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=area, srs=False)
            
    return f"✅ Simulado ({total_q}q) salvo!"

# -------------------------
# RESUMOS
# -------------------------
def get_resumo(u, area):
    client = get_supabase()
    if client:
        res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
        return res.data[0]['conteudo'] if res.data else ""
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT conteudo FROM resumos WHERE usuario_id=? AND grande_area=?", (u, area)).fetchone()
            return row[0] if row else ""

def salvar_resumo(u, area, texto):
    client = get_supabase()
    if client:
        client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto))
    return True

# -------------------------
# AUTH
# -------------------------
def verificar_login(u, p):
    client = get_supabase()
    if client:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data and bcrypt.checkpw(p.encode(), res.data[0]['password_hash'].encode()):
            return True, res.data[0]['nome']
    return False, "Erro Login"

def criar_usuario(u, p, n):
    client = get_supabase()
    if client:
        pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": pw}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0}).execute()
        return True, "Criado"
    return False, "Erro Config"

# -------------------------
# STUBS
# -------------------------
def get_db(): return True
def get_dados_graficos(u, nonce=None): 
    # Implementação básica para gráficos funcionarem
    client = get_supabase()
    if client:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    else:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
        conn.close()
    
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        df['percentual'] = (df['acertos'] / df['total'] * 100).fillna(0)
    return df

def listar_revisoes_completas(u):
    client = get_supabase()
    if client:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    if client:
        # Pega dados da revisão antiga
        rev = client.table("revisoes").select("*").eq("id", rid).execute()
        if rev.data:
            r = rev.data[0]
            # Marca concluída
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
            # Registra novo estudo
            registrar_estudo(r['usuario_id'], r['assunto_nome'], ac, tot, area_f=r['grande_area'], srs=False)
            return "✅ Feito"
    return "Erro"