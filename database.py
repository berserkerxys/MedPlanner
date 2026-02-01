# database.py
# Versão com integração automática ao aulas_medcof.py

import os
import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional, TYPE_CHECKING

# Import supabase client lazily for runtime
if TYPE_CHECKING:
    from supabase import Client  # type: ignore

try:
    from supabase import create_client
except Exception:
    create_client = None

# Local DB filename (usado pelo fallback)
DB_NAME = "medplanner_local.db"

# -------------------------
# Helpers
# -------------------------
def _ensure_local_db():
    """Cria tabelas locais mínimas se não existirem (fallback)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela assuntos
    c.execute("""
    CREATE TABLE IF NOT EXISTS assuntos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nome TEXT UNIQUE,
      grande_area TEXT
    )""")
    # Tabela historico
    c.execute("""
    CREATE TABLE IF NOT EXISTS historico (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usuario_id TEXT,
      assunto_nome TEXT,
      area_manual TEXT,
      data_estudo TEXT,
      acertos INTEGER,
      total INTEGER
    )""")
    # Tabela revisoes
    c.execute("""
    CREATE TABLE IF NOT EXISTS revisoes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usuario_id TEXT,
      assunto_nome TEXT,
      grande_area TEXT,
      data_agendada TEXT,
      tipo TEXT,
      status TEXT
    )""")
    # Tabela perfil_gamer
    c.execute("""
    CREATE TABLE IF NOT EXISTS perfil_gamer (
      usuario_id TEXT PRIMARY KEY,
      xp INTEGER,
      titulo TEXT,
      meta_diaria INTEGER
    )""")
    # Tabela resumos
    c.execute("""
    CREATE TABLE IF NOT EXISTS resumos (
      usuario_id TEXT,
      grande_area TEXT,
      conteudo TEXT,
      PRIMARY KEY (usuario_id, grande_area)
    )""")
    conn.commit()
    conn.close()

# -------------------------
# Supabase client
# -------------------------
@st.cache_resource
def get_supabase() -> Optional["Client"]:
    try:
        if "supabase" in st.secrets and create_client:
            url = st.secrets["supabase"].get("url")
            key = st.secrets["supabase"].get("key")
            if url and key:
                return create_client(url, key)
        return None
    except Exception as e:
        print("get_supabase error:", e)
        return None

# -------------------------
# Refresh util
# -------------------------
def trigger_refresh():
    if 'data_nonce' not in st.session_state:
        st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# -------------------------
# INTEGRAÇÃO DE CONTEÚDO (MEDCOF + VIDEOTECA)
# -------------------------
def get_lista_assuntos_nativa():
    """
    Retorna uma lista unificada de assuntos para o SelectBox.
    Tenta ler de:
    1. aulas_medcof.py (qualquer lista encontrada no arquivo)
    2. Videoteca Global (biblioteca_conteudo ou Supabase)
    """
    items = set()

    # 1. Tenta carregar do módulo aulas_medcof.py dinamicamente
    try:
        import aulas_medcof
        # Procura por todas as listas definidas no arquivo aulas_medcof
        for name in dir(aulas_medcof):
            if not name.startswith("_"): # Ignora variaveis internas
                val = getattr(aulas_medcof, name)
                if isinstance(val, list):
                    # Tenta extrair texto de cada item da lista
                    for i in val:
                        if isinstance(i, str):
                            items.add(i)
                        elif isinstance(i, dict):
                            # Tenta chaves comuns de objetos de aula
                            if 'titulo' in i: items.add(i['titulo'])
                            elif 'assunto' in i: items.add(i['assunto'])
                            elif 'tema' in i: items.add(i['tema'])
                            elif 'aula' in i: items.add(i['aula'])
    except ImportError:
        pass # Arquivo não existe ou erro de sintaxe, segue o baile
    except Exception as e:
        print(f"Erro ao processar aulas_medcof: {e}")

    # 2. Carrega da videoteca padrão (Supabase ou JSON local)
    try:
        df = listar_conteudo_videoteca()
        if not df.empty:
            if 'assunto' in df.columns:
                items.update(df['assunto'].dropna().unique().tolist())
            if 'titulo' in df.columns:
                items.update(df['titulo'].dropna().unique().tolist())
    except Exception as e:
        print(f"Erro ao processar videoteca: {e}")

    # 3. Fallback se tudo falhar
    if not items:
        return ["Banco Geral", "Sem Tópicos Encontrados"]
            
    return sorted(list(items))

@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    client = get_supabase()
    try:
        if client:
            res = client.table("videoteca").select("*").execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            return df
        # fallback: tenta ler de json local se existir
        path = "videoteca_export.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        # fallback 2: tenta ler de biblioteca_conteudo.py se existir
        try:
            from biblioteca_conteudo import VIDEOTECA_GLOBAL
            cols = ['grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id_conteudo']
            return pd.DataFrame(VIDEOTECA_GLOBAL, columns=cols)
        except ImportError:
            pass
            
        return pd.DataFrame()
    except Exception as e:
        print("listar_conteudo_videoteca error:", e)
        return pd.DataFrame()

def get_area_por_assunto(assunto):
    """Tenta descobrir a Grande Área baseada no nome do assunto."""
    # 1. Tenta na videoteca
    df = listar_conteudo_videoteca()
    if not df.empty:
        # Verifica coluna 'assunto'
        if 'assunto' in df.columns and 'grande_area' in df.columns:
            match = df[df['assunto'] == assunto]
            if not match.empty: return match.iloc[0]['grande_area']
        # Verifica coluna 'titulo'
        if 'titulo' in df.columns and 'grande_area' in df.columns:
            match = df[df['titulo'] == assunto]
            if not match.empty: return match.iloc[0]['grande_area']
            
    # 2. Se não achou, tenta mapeamento manual simples ou retorna Geral
    return "Geral"

def pesquisar_global(termo):
    df = listar_conteudo_videoteca()
    if df.empty: return df
    mask = pd.Series([False] * len(df))
    if 'titulo' in df.columns:
        mask = mask | df['titulo'].str.contains(termo, case=False, na=False)
    if 'assunto' in df.columns:
        mask = mask | df['assunto'].str.contains(termo, case=False, na=False)
    return df[mask]

# -------------------------
# Funções de Progresso e Gamer (Sidebar)
# -------------------------
@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce=None):
    client = get_supabase()
    hoje = datetime.now().strftime("%Y-%m-%d")
    if client:
        try:
            res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            return sum(int(i.get('total', 0)) for i in (res.data or []))
        except Exception:
            pass
    # fallback local
    try:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT total FROM historico WHERE usuario_id = ? AND data_estudo = ?", conn, params=(u, hoje))
        conn.close()
        return int(df['total'].sum()) if not df.empty else 0
    except Exception:
        return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce=None):
    client = get_supabase()
    try:
        # Tenta pegar perfil
        xp, titulo, meta = 0, "Interno", 50
        
        if client:
            res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
            if res.data:
                d = res.data[0]
                xp = int(d.get('xp', 0))
                meta = int(d.get('meta_diaria', 50))
                titulo = d.get('titulo', 'Residente')
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("SELECT xp, titulo, meta_diaria FROM perfil_gamer WHERE usuario_id = ?", (u,))
            row = cur.fetchone()
            conn.close()
            if row:
                xp, titulo, meta = row

        # Calcula progresso de hoje
        q_hoje, a_hoje = 0, 0
        hoje = datetime.now().strftime("%Y-%m-%d")
        
        if client:
            h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            if h.data:
                q_hoje = sum(int(i.get('total', 0)) for i in h.data)
                a_hoje = sum(int(i.get('acertos', 0)) for i in h.data)
        else:
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query("SELECT total, acertos FROM historico WHERE usuario_id = ? AND data_estudo = ?", conn, params=(u, hoje))
            conn.close()
            if not df.empty:
                q_hoje = int(df['total'].sum())
                a_hoje = int(df['acertos'].sum())

        status = {
            'nivel': 1 + (xp // 1000),
            'xp_atual': xp % 1000,
            'xp_total': xp,
            'titulo': titulo,
            'meta_diaria': meta
        }
        
        missoes = [
            {"Icon": "🎯", "Meta": "Meta de Questões", "Prog": q_hoje, "Objetivo": status['meta_diaria'], "Unid": "q"},
            {"Icon": "✅", "Meta": "Foco em Acertos", "Prog": a_hoje, "Objetivo": int(status['meta_diaria'] * 0.7), "Unid": "hits"},
            {"Icon": "⚡", "Meta": "XP Gerado Hoje", "Prog": q_hoje * 2, "Objetivo": status['meta_diaria'] * 2, "Unid": "xp"}
        ]
        return status, pd.DataFrame(missoes)
        
    except Exception as e:
        print("get_status_gamer error:", e)
        return None, pd.DataFrame()

def update_meta_diaria(u, nova_meta):
    client = get_supabase()
    try:
        if client:
            client.table("perfil_gamer").update({"meta_diaria": int(nova_meta)}).eq("usuario_id", u).execute()
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            # Upsert simplificado para SQLite
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, 0, 'Interno', ?)", (u, int(nova_meta)))
            c.execute("UPDATE perfil_gamer SET meta_diaria = ? WHERE usuario_id = ?", (int(nova_meta), u))
            conn.commit()
            conn.close()
            
        trigger_refresh()
        return True
    except Exception as e:
        print("update_meta_diaria error:", e)
        return False

# -------------------------
# SISTEMA DE RESUMOS
# -------------------------
def get_resumo(u, area):
    client = get_supabase()
    try:
        if client:
            res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
            return res.data[0]['conteudo'] if res.data else ""
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT conteudo FROM resumos WHERE usuario_id = ? AND grande_area = ?", (u, area))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""

def salvar_resumo(u, area, texto):
    client = get_supabase()
    try:
        if client:
            client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?, ?, ?)", (u, area, texto))
            conn.commit()
            conn.close()
        return True
    except Exception:
        return False

# -------------------------
# REGISTROS (HISTÓRICO / REVISÕES)
# -------------------------
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    client = get_supabase()
    dt = data_p if data_p else datetime.now().date()
    area = area_f if area_f else get_area_por_assunto(assunto)
    xp_ganho = int(total) * 2
    
    try:
        if client:
            client.table("historico").insert({
                "usuario_id": u, "assunto_nome": assunto, "area_manual": area,
                "data_estudo": dt.strftime("%Y-%m-%d"), "acertos": int(acertos), "total": int(total)
            }).execute()
            
            if srs and "Banco" not in assunto and "Simulado" not in assunto:
                dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id": u, "assunto_nome": assunto, "grande_area": area, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"}).execute()
            
            # Atualiza XP
            res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            current_xp = int(res_p.data[0].get('xp', 0)) if res_p.data else 0
            client.table("perfil_gamer").upsert({"usuario_id": u, "xp": current_xp + xp_ganho}).execute()
            
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                      (u, assunto, area, dt.strftime("%Y-%m-%d"), int(acertos), int(total)))
            
            if srs and "Banco" not in assunto and "Simulado" not in assunto:
                dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
                c.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?, ?, ?, ?, ?, ?)",
                      (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
            
            # XP
            c.execute("SELECT xp FROM perfil_gamer WHERE usuario_id = ?", (u,))
            row = c.fetchone()
            new_xp = (int(row[0]) + xp_ganho) if row else xp_ganho
            c.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, COALESCE((SELECT titulo FROM perfil_gamer WHERE usuario_id=?),'Interno'), COALESCE((SELECT meta_diaria FROM perfil_gamer WHERE usuario_id=?), 50))", (u, new_xp, u, u))
            conn.commit()
            conn.close()
            
        trigger_refresh()
        return "✅ Registado!"
    except Exception as e:
        print("registrar_estudo error:", e)
        return "Erro ao registrar"

def registrar_simulado(u, dados, data_p=None):
    client = get_supabase()
    dt = data_p.strftime("%Y-%m-%d") if data_p else datetime.now().strftime("%Y-%m-%d")
    inserts = []
    tq = 0
    
    # Prepara dados
    for area, v in dados.items():
        if int(v.get('total', 0)) > 0:
            tq += int(v.get('total', 0))
            inserts.append({
                "usuario_id": u, "assunto_nome": f"Simulado - {area}", 
                "area_manual": area, "data_estudo": dt, 
                "acertos": int(v.get('acertos', 0)), "total": int(v.get('total', 0))
            })
            
    if not inserts: return "Nada a salvar"

    try:
        xp_ganho = int(tq * 2.5)
        
        if client:
            client.table("historico").insert(inserts).execute()
            res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            current_xp = int(res_p.data[0].get('xp', 0)) if res_p.data else 0
            client.table("perfil_gamer").upsert({"usuario_id": u, "xp": current_xp + xp_ganho}).execute()
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            for ins in inserts:
                c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                          (ins['usuario_id'], ins['assunto_nome'], ins['area_manual'], ins['data_estudo'], ins['acertos'], ins['total']))
            # XP
            c.execute("SELECT xp FROM perfil_gamer WHERE usuario_id = ?", (u,))
            row = c.fetchone()
            new_xp = (int(row[0]) + xp_ganho) if row else xp_ganho
            c.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, COALESCE((SELECT titulo FROM perfil_gamer WHERE usuario_id=?),'Interno'), COALESCE((SELECT meta_diaria FROM perfil_gamer WHERE usuario_id=?), 50))", (u, new_xp, u, u))
            conn.commit()
            conn.close()

        trigger_refresh()
        return f"✅ Simulado salvo ({tq}q)!"
    except Exception as e:
        print("registrar_simulado error:", e)
        return "Erro"

@st.cache_data(ttl=300)
def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    try:
        df = pd.DataFrame()
        if client:
            res = client.table("historico").select("*").eq("usuario_id", u).execute()
            if res.data: df = pd.DataFrame(res.data)
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id = ?", conn, params=(u,))
            conn.close()
            
        if df.empty: return df
        
        # Processamento
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
        df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
        df['data'] = pd.to_datetime(df['data_estudo']).dt.normalize()
        
        # Tenta mapear áreas
        if 'area_manual' not in df.columns or df['area_manual'].isnull().all():
             df['area'] = df['assunto_nome'].apply(get_area_por_assunto)
        else:
             df['area'] = df['area_manual'].fillna("Geral")
             
        return df.sort_values('data')
    except Exception as e:
        print("get_dados_graficos error:", e)
        return pd.DataFrame()

# -------------------------
# AUTH E ADMINISTRAÇÃO
# -------------------------
def verificar_login(u, p):
    client = get_supabase()
    try:
        if client:
            res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
            if res.data and bcrypt.checkpw(p.encode('utf-8'), res.data[0]['password_hash'].encode('utf-8')):
                return True, res.data[0].get('nome', u)
            return False, "Login falhou"
        return False, "Sem autenticação local (configure Supabase)"
    except Exception:
        return False, "Erro conexão"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        if not client: return False, "Supabase offline"
        h = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": h}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0, "titulo": "Interno", "meta_diaria": 50}).execute()
        return True, "Criado!"
    except Exception:
        return False, "Erro ao criar"

def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
            return pd.DataFrame(res.data) if res.data else pd.DataFrame()
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id = ?", conn, params=(u,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    # Lógica simplificada: marca como concluído e cria histórico
    client = get_supabase()
    try:
        u_id, assunto, area = None, None, None
        
        # 1. Busca dados da revisão
        if client:
            res = client.table("revisoes").select("*").eq("id", rid).execute()
            if res.data:
                r = res.data[0]
                u_id, assunto, area = r['usuario_id'], r['assunto_nome'], r['grande_area']
                client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        else:
            _ensure_local_db()
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("SELECT usuario_id, assunto_nome, grande_area FROM revisoes WHERE id=?", (rid,))
            row = cur.fetchone()
            if row:
                u_id, assunto, area = row
                cur.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
                conn.commit()
            conn.close()

        # 2. Registra o estudo
        if u_id:
            registrar_estudo(u_id, assunto, ac, tot, area_f=area, srs=False)
            return "✅ Concluído"
        return "Erro: Revisão não encontrada"
    except Exception as e:
        print("concluir_revisao error:", e)
        return "Erro"

# Stubs para compatibilidade
def get_db(): return True
def registrar_topico_do_sumario(area, nome): return "OK"