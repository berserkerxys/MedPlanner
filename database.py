# database.py
# Versão Corrigida: Restaura listar_conteudo_videoteca para o Dashboard
# Mantém Sidebar estrita (apenas aulas_medcof.py)

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

# Nome do Banco Local
DB_NAME = "medplanner_local.db"

# -------------------------
# LEITURA ESTRITA DO MEDCOF (PARA SIDEBAR)
# -------------------------
@st.cache_data
def _carregar_dados_medcof_estrito():
    """
    Lê EXCLUSIVAMENTE o arquivo aulas_medcof.py.
    Retorna:
      - lista_aulas: Lista de strings para o SelectBox.
      - mapa_areas: Dicionário { 'Nome da Aula': 'Grande Área' } para preenchimento automático.
    """
    lista_aulas = []
    mapa_areas = {}
    
    try:
        import aulas_medcof
        
        # 1. Tenta pegar a variável DADOS_LIMPOS (padrão esperado)
        dados = getattr(aulas_medcof, 'DADOS_LIMPOS', None)
        
        # 2. Se não achar, varre o arquivo procurando qualquer lista grande
        if not dados:
            for name in dir(aulas_medcof):
                if name.startswith("_"): continue
                val = getattr(aulas_medcof, name)
                if isinstance(val, list) and len(val) > 2: 
                    dados = val
                    break
        
        # 3. Processa os dados encontrados
        if dados:
            for item in dados:
                # Se for tupla ("Aula", "Area")
                if isinstance(item, tuple) and len(item) >= 2:
                    aula = str(item[0]).strip()
                    area = str(item[1]).strip()
                    lista_aulas.append(aula)
                    mapa_areas[aula] = area
                # Se for string simples
                elif isinstance(item, str):
                    lista_aulas.append(item.strip())
                # Se for dicionário
                elif isinstance(item, dict):
                    t = item.get('titulo') or item.get('assunto')
                    a = item.get('grande_area') or item.get('area')
                    if t:
                        lista_aulas.append(str(t))
                        if a: mapa_areas[str(t)] = str(a)
                        
    except ImportError:
        print("Aviso: Arquivo aulas_medcof.py não encontrado ou com erro de importação.")
        return ["Erro: aulas_medcof.py não encontrado"], {}
    except Exception as e:
        print(f"Erro ao processar aulas_medcof.py: {e}")
        return [f"Erro ao ler aulas: {e}"], {}

    if not lista_aulas:
        return ["Aviso: Nenhuma aula encontrada em aulas_medcof.py"], {}

    # Remove duplicatas mantendo a ordem e classifica
    return sorted(list(set(lista_aulas))), mapa_areas

# -------------------------
# FUNÇÕES PRINCIPAIS (INTERFACING)
# -------------------------

def get_lista_assuntos_nativa():
    """
    Usada pela Sidebar.
    Retorna APENAS as aulas encontradas nos blocos do aulas_medcof.py.
    """
    aulas, _ = _carregar_dados_medcof_estrito()
    return aulas

def get_area_por_assunto(assunto):
    """
    Tenta descobrir a área usando o mapeamento do medcof.
    Se não achar, retorna 'Geral'.
    """
    _, mapa = _carregar_dados_medcof_estrito()
    return mapa.get(assunto, "Geral")

# -------------------------
# VIDEOTECA (NECESSÁRIO PARA DASHBOARD)
# -------------------------
@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    """
    Retorna DataFrame da videoteca.
    Usado pelo Dashboard e Videoteca, mas NÃO pela Sidebar.
    """
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
        try:
            return pd.read_json("videoteca_export.json")
        except: pass
        
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
# DATABASE & SUPABASE HELPERS
# -------------------------
def _ensure_local_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
    except: pass
    return None

def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# -------------------------
# REGISTROS DE ESTUDO
# -------------------------
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    # Usa mapeamento do medcof para preencher a área automaticamente
    area = area_f if area_f else get_area_por_assunto(assunto)
    xp_ganho = int(total) * 2
    
    client = get_supabase()
    
    # Payload comum
    hist_data = {
        "usuario_id": u, "assunto_nome": assunto, "area_manual": area, 
        "data_estudo": dt, "acertos": int(acertos), "total": int(total)
    }

    if client:
        try:
            client.table("historico").insert(hist_data).execute()
            
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({
                    "usuario_id": u, "assunto_nome": assunto, "grande_area": area, 
                    "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
                }).execute()
                
            # XP
            curr = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            old_xp = curr.data[0]['xp'] if curr.data else 0
            client.table("perfil_gamer").upsert({"usuario_id": u, "xp": old_xp + xp_ganho}).execute()
            
            trigger_refresh()
            return f"✅ Registrado: {assunto} ({area})"
        except Exception as e:
            return f"Erro Sync: {e}"
    else:
        # Local SQLite
        try:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", 
                             (u, assunto, area, dt, acertos, total))
                
                if srs and "Simulado" not in assunto:
                    dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                                 (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
                
                row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                old_xp = row[0] if row else 0
                conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
            
            trigger_refresh()
            return f"✅ Registrado: {assunto} ({area})"
        except Exception as e:
            return f"Erro Local: {e}"

def registrar_simulado(u, dados):
    total_q = sum(int(d['total']) for d in dados.values())
    if total_q == 0: return "Sem dados"
    for area, d in dados.items():
        if int(d['total']) > 0:
            registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=area, srs=False)
    return f"✅ Simulado ({total_q}q) salvo!"

# -------------------------
# GAMIFICAÇÃO (SIDEBAR)
# -------------------------
@st.cache_data(ttl=60)
def get_progresso_hoje(u, nonce=None):
    hoje = datetime.now().strftime("%Y-%m-%d")
    client = get_supabase()
    if client:
        try:
            res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            return sum(x['total'] for x in res.data)
        except: pass
    
    try:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT sum(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
            return row[0] if row and row[0] else 0
    except: return 0

@st.cache_data(ttl=60)
def get_status_gamer(u, nonce=None):
    client = get_supabase()
    xp, titulo, meta = 0, "Interno", 50
    
    # 1. Busca Perfil
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
        
    # 2. Busca Progresso do Dia
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
        'nivel': 1 + (xp // 1000), 'xp_atual': xp % 1000, 'xp_total': xp,
        'titulo': titulo, 'meta_diaria': meta
    }
    
    missoes = [
        {"Icon": "🎯", "Meta": "Questões", "Prog": q_hoje, "Objetivo": meta, "Unid": "q"},
        {"Icon": "✅", "Meta": "Acertos", "Prog": a_hoje, "Objetivo": int(meta * 0.7), "Unid": "hits"},
        {"Icon": "⚡", "Meta": "XP", "Prog": q_hoje * 2, "Objetivo": meta * 2, "Unid": "xp"}
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
# RESUMOS & AUTH & STUBS
# -------------------------
def get_resumo(u, area):
    client = get_supabase()
    if client:
        res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
        return res.data[0]['conteudo'] if res.data else ""
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

def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    df = pd.DataFrame()
    if client:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        if res.data: df = pd.DataFrame(res.data)
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        df['percentual'] = (df['acertos'] / df['total'] * 100).fillna(0)
        # Preenche área vazia com mapeamento do medcof
        if 'area_manual' in df.columns:
            mask = df['area_manual'].isnull() | (df['area_manual'] == "")
            df.loc[mask, 'area_manual'] = df.loc[mask, 'assunto_nome'].apply(get_area_por_assunto)
            df['area'] = df['area_manual']
    return df

def listar_revisoes_completas(u):
    client = get_supabase()
    if client:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    _ensure_local_db()
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    # Lógica simplificada de conclusão
    if client:
        r = client.table("revisoes").select("*").eq("id", rid).execute()
        if r.data:
            rev = r.data[0]
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
            registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev['grande_area'], srs=False)
            return "✅ Feito"
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            rev = conn.execute("SELECT usuario_id, assunto_nome, grande_area FROM revisoes WHERE id=?", (rid,)).fetchone()
            if rev:
                conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
                registrar_estudo(rev[0], rev[1], ac, tot, area_f=rev[2], srs=False)
                return "✅ Feito"
    return "Erro"

def get_db(): return True