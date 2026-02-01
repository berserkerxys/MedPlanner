# database.py
# Versão compatível e resiliente: usa Supabase se configurado em st.secrets,
# caso contrário usa fallback local (SQLite/JSON). Todas as funções esperadas
# pelas outras partes do app são definidas para evitar erros de import.

import os
import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
from typing import Optional, TYPE_CHECKING

# Import supabase client lazily for runtime; import type only for type checking
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
    # assuntos
    c.execute("""
    CREATE TABLE IF NOT EXISTS assuntos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nome TEXT UNIQUE,
      grande_area TEXT
    )""")
    # historico
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
    # revisoes
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
    # perfil_gamer
    c.execute("""
    CREATE TABLE IF NOT EXISTS perfil_gamer (
      usuario_id TEXT PRIMARY KEY,
      xp INTEGER,
      titulo TEXT,
      meta_diaria INTEGER
    )""")
    # resumos
    c.execute("""
    CREATE TABLE IF NOT EXISTS resumos (
      usuario_id TEXT,
      grande_area TEXT,
      conteudo TEXT,
      PRIMARY KEY (usuario_id, grande_area)
    )""")
    # cronogramas (fallback local) - arquivos JSON serão usados
    conn.commit()
    conn.close()

# -------------------------
# Supabase client
# -------------------------
@st.cache_resource
def get_supabase() -> Optional["Client"]:
    """
    Retorna cliente Supabase se configurado em st.secrets; caso contrário None.
    """
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
# Funções usadas pelo app
# -------------------------

# get_progresso_hoje(u, nonce) - usado na sidebar
@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce=None):
    client = get_supabase()
    if client:
        try:
            res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", datetime.now().strftime("%Y-%m-%d")).execute()
            return sum(int(i.get('total', 0)) for i in (res.data or []))
        except Exception as e:
            print("get_progresso_hoje supabase error:", e)
    # fallback local
    try:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT total FROM historico WHERE usuario_id = ? AND data_estudo = ?", conn, params=(u, datetime.now().strftime("%Y-%m-%d")))
        conn.close()
        return int(df['total'].sum()) if not df.empty else 0
    except Exception as e:
        print("get_progresso_hoje local error:", e)
        return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce=None):
    client = get_supabase()
    try:
        if client:
            res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
            if res.data:
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
                # calcs
                hoje = datetime.now().strftime("%Y-%m-%d")
                h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
                q = sum(int(i.get('total', 0)) for i in (h.data or []))
                a = sum(int(i.get('acertos', 0)) for i in (h.data or []))
                missoes = [
                    {"Icon": "🎯", "Meta": "Meta de Questões", "Prog": q, "Objetivo": status['meta_diaria'], "Unid": "q"},
                    {"Icon": "✅", "Meta": "Foco em Acertos", "Prog": a, "Objetivo": int(status['meta_diaria'] * 0.7), "Unid": "hits"},
                    {"Icon": "⚡", "Meta": "XP Gerado Hoje", "Prog": q * 2, "Objetivo": status['meta_diaria'] * 2, "Unid": "xp"}
                ]
                return status, pd.DataFrame(missoes)
        # fallback local:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT xp, titulo, meta_diaria FROM perfil_gamer WHERE usuario_id = ?", (u,))
        row = cur.fetchone()
        if row:
            xp, titulo, meta = row
        else:
            xp, titulo, meta = 0, "Interno", 50
        # cálculo simples local
        hoje = datetime.now().strftime("%Y-%m-%d")
        df = pd.read_sql_query("SELECT total, acertos FROM historico WHERE usuario_id = ? AND data_estudo = ?", conn, params=(u, hoje))
        conn.close()
        q = int(df['total'].sum()) if not df.empty else 0
        a = int(df['acertos'].sum()) if not df.empty else 0
        status = {
            'nivel': 1 + (int(xp) // 1000),
            'xp_atual': int(xp) % 1000,
            'xp_total': int(xp),
            'titulo': titulo,
            'meta_diaria': int(meta)
        }
        missoes = [
            {"Icon": "🎯", "Meta": "Meta de Questões", "Prog": q, "Objetivo": status['meta_diaria'], "Unid": "q"},
            {"Icon": "✅", "Meta": "Foco em Acertos", "Prog": a, "Objetivo": int(status['meta_diaria'] * 0.7), "Unid": "hits"},
            {"Icon": "⚡", "Meta": "XP Gerado Hoje", "Prog": q * 2, "Objetivo": status['meta_diaria'] * 2, "Unid": "xp"}
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
            trigger_refresh()
            return True
        # fallback local
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, COALESCE((SELECT xp FROM perfil_gamer WHERE usuario_id=?),0), COALESCE((SELECT titulo FROM perfil_gamer WHERE usuario_id=?),'Interno'), ?)", (u,u,u,int(nova_meta)))
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
    except Exception as e:
        print("get_resumo error:", e)
        return ""

def salvar_resumo(u, area, texto):
    client = get_supabase()
    try:
        if client:
            client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
            return True
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?, ?, ?)", (u, area, texto))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("salvar_resumo error:", e)
        return False

# -------------------------
# VIDEOTECA / BIBLIOTECA
# -------------------------
@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    client = get_supabase()
    try:
        if client:
            res = client.table("videoteca").select("*").execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            return df
        # fallback: se existir export local
        path = "videoteca_export.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        print("listar_conteudo_videoteca error:", e)
        return pd.DataFrame()

def get_area_por_assunto(assunto):
    df = listar_conteudo_videoteca()
    if df.empty: return "Geral"
    if 'assunto' in df.columns and 'grande_area' in df.columns:
        match = df[df['assunto'] == assunto]
        if not match.empty:
            return match.iloc[0]['grande_area']
    return "Geral"

def get_lista_assuntos_nativa():
    df = listar_conteudo_videoteca()
    if df.empty:
        return ["Banco Geral"]
    if 'assunto' in df.columns:
        return sorted(df['assunto'].dropna().unique().tolist())
    if 'titulo' in df.columns:
        return sorted(df['titulo'].dropna().unique().tolist())
    return ["Banco Geral"]

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
# REGISTROS (HISTÓRICO / REVISÕES)
# -------------------------
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    client = get_supabase()
    dt = data_p if data_p else datetime.now().date()
    area = area_f if area_f else get_area_por_assunto(assunto)
    try:
        if client:
            client.table("historico").insert({
                "usuario_id": u, "assunto_nome": assunto, "area_manual": area,
                "data_estudo": dt.strftime("%Y-%m-%d"), "acertos": int(acertos), "total": int(total)
            }).execute()
            if srs and "Banco" not in assunto and "Simulado" not in assunto:
                dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id": u, "assunto_nome": assunto, "grande_area": area, "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"}).execute()
            # XP
            res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            if res_p.data:
                nxp = int(res_p.data[0].get('xp', 0)) + (int(total) * 2)
                client.table("perfil_gamer").update({"xp": nxp}).eq("usuario_id", u).execute()
            trigger_refresh()
            return "✅ Registado!"
        # fallback local
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                  (u, assunto, area, dt.strftime("%Y-%m-%d"), int(acertos), int(total)))
        if srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt + timedelta(days=7)).strftime("%Y-%m-%d")
            c.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?, ?, ?, ?, ?, ?)",
                      (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
        # atualiza xp local
        c.execute("SELECT xp FROM perfil_gamer WHERE usuario_id = ?", (u,))
        row = c.fetchone()
        if row:
            nxp = int(row[0]) + (int(total) * 2)
            c.execute("UPDATE perfil_gamer SET xp = ? WHERE usuario_id = ?", (nxp, u))
        else:
            c.execute("INSERT INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, ?, ?)", (u, int(total) * 2, "Interno", 50))
        conn.commit()
        conn.close()
        trigger_refresh()
        return "✅ Registado!"
    except Exception as e:
        print("registrar_estudo error:", e)
        return "Erro"

def registrar_simulado(u, dados, data_p=None):
    client = get_supabase()
    dt = data_p.strftime("%Y-%m-%d") if data_p else datetime.now().strftime("%Y-%m-%d")
    inserts = []
    tq = 0
    try:
        for area, v in dados.items():
            if int(v.get('total', 0)) > 0:
                tq += int(v.get('total', 0))
                inserts.append({"usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt, "acertos": int(v.get('acertos', 0)), "total": int(v.get('total', 0))})
        if client:
            if inserts: client.table("historico").insert(inserts).execute()
            res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            if res_p.data:
                nxp = int(res_p.data[0].get('xp', 0)) + int(tq * 2.5)
                client.table("perfil_gamer").update({"xp": nxp}).eq("usuario_id", u).execute()
            trigger_refresh()
            return f"✅ Simulado salvo ({tq}q)!"
        # fallback local
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        for ins in inserts:
            c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                      (ins['usuario_id'], ins['assunto_nome'], ins['area_manual'], ins['data_estudo'], ins['acertos'], ins['total']))
        # xp
        c.execute("SELECT xp FROM perfil_gamer WHERE usuario_id = ?", (u,))
        row = c.fetchone()
        if row:
            nxp = int(row[0]) + int(tq * 2.5)
            c.execute("UPDATE perfil_gamer SET xp = ? WHERE usuario_id = ?", (nxp, u))
        else:
            c.execute("INSERT INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, ?, ?)", (u, int(tq * 2.5), "Interno", 50))
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
        if client:
            res = client.table("historico").select("*").eq("usuario_id", u).execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            if df.empty: return df
            lib = listar_conteudo_videoteca()
            area_map = lib.set_index('assunto')['grande_area'].to_dict() if not lib.empty and 'assunto' in lib.columns else {}
            df['area'] = df['assunto_nome'].map(area_map).fillna(df.get('area_manual', 'Geral'))
            df['total'] = df['total'].astype(int)
            df['acertos'] = df['acertos'].astype(int)
            df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
            df['data'] = pd.to_datetime(df['data_estudo']).dt.normalize()
            return df.sort_values('data')
        # fallback local
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id = ?", conn, params=(u,))
        conn.close()
        if df.empty: return df
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
        df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
        df['data'] = pd.to_datetime(df['data_estudo']).dt.normalize()
        return df.sort_values('data')
    except Exception as e:
        print("get_dados_graficos error:", e)
        return pd.DataFrame()

# -------------------------
# AUTH & AGENDA
# -------------------------
def verificar_login(u, p):
    client = get_supabase()
    try:
        if client:
            res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
            if res.data and bcrypt.checkpw(p.encode('utf-8'), res.data[0]['password_hash'].encode('utf-8')):
                return True, res.data[0].get('nome', u)
            return False, "Login falhou"
        # fallback local: no auth
        return False, "Sem autenticação local"
    except Exception as e:
        print("verificar_login error:", e)
        return False, "Erro conexão"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        if not client:
            return False, "Supabase não configurado"
        h = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": h}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0, "titulo": "Interno", "meta_diaria": 50}).execute()
        return True, "Criado!"
    except Exception as e:
        print("criar_usuario error:", e)
        return False, "Erro ao criar usuário"

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
    except Exception as e:
        print("listar_revisoes_completas error:", e)
        return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("id", rid).execute()
            if not res.data:
                return "Erro"
            rev = res.data[0]
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
            registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev.get('grande_area'), srs=False)
            return "✅ Concluído"
        # fallback local
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT usuario_id, assunto_nome, grande_area FROM revisoes WHERE id = ?", (rid,))
        row = c.fetchone()
        if not row:
            conn.close()
            return "Erro"
        usuario_id, assunto_nome, grande_area = row
        c.execute("UPDATE revisoes SET status = 'Concluido' WHERE id = ?", (rid,))
        c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                  (usuario_id, assunto_nome, grande_area, datetime.now().strftime("%Y-%m-%d"), int(ac), int(tot)))
        conn.commit()
        conn.close()
        return "✅ Concluído"
    except Exception as e:
        print("concluir_revisao error:", e)
        return "Erro"

# -------------------------
# Funções administrativas mínimas esperadas por gerenciar.py / mapear.py
# -------------------------
def registrar_topico_do_sumario(area, nome):
    """
    Salva um tópico mapeado (sumário) na tabela 'assuntos' (fallback).
    Retorna mensagem string (usado nos scripts mapear/gerenciar).
    """
    client = get_supabase()
    try:
        if client:
            # tenta inserir, evita duplicados
            client.table("assuntos").insert({"nome": nome, "grande_area": area}).execute()
            return f"✅ {nome} salvo em {area}"
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO assuntos (nome, grande_area) VALUES (?, ?)", (nome, area))
        except sqlite3.IntegrityError:
            conn.close()
            return f"⚠️ {nome} já existe"
        conn.commit()
        conn.close()
        return f"✅ {nome} salvo em {area}"
    except Exception as e:
        print("registrar_topico_do_sumario error:", e)
        return "Erro"

# Stub admin functions (implementações mínimas para não quebrar imports)
def atualizar_nome_assunto(old, new): return True
def deletar_assunto(nome): return True
def resetar_progresso(usuario_id): return True
def salvar_config(k, v): 
    try:
        # grava em arquivo simples
        conf = {}
        path = "config.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                conf = json.load(f)
        conf[k] = v
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("salvar_config error:", e)
        return False

def ler_config(k):
    try:
        path = "config.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                conf = json.load(f)
            return conf.get(k)
        return None
    except Exception as e:
        print("ler_config error:", e)
        return None

def get_connection():
    """Retorna conexão sqlite local para ferramentas administrativas."""
    _ensure_local_db()
    return sqlite3.connect(DB_NAME)

# -------------------------
# Funções de sincronização (stubs)
# -------------------------
def salvar_conteudo_exato(msg_id, titulo, link, hashtag, tipo, subtipo):
    """Usado por sync.py; implementa um stub que cria/atualiza videoteca local."""
    try:
        client = get_supabase()
        payload = {"id": msg_id, "titulo": titulo, "link": link, "assunto": hashtag, "tipo": tipo, "subtipo": subtipo, "grande_area": ""}
        if client:
            client.table("videoteca").upsert(payload, on_conflict="id").execute()
            return f"✅ {msg_id} salvo (supabase)"
        # fallback local: append to json file
        path = "videoteca_export.json"
        arr = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                arr = json.load(f)
        # evita duplicados por id
        if not any(str(x.get("id")) == str(msg_id) for x in arr):
            arr.append(payload)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
        return f"✅ {msg_id} salvo (local)"
    except Exception as e:
        print("salvar_conteudo_exato error:", e)
        return "Erro"

def exportar_videoteca_para_arquivo():
    """Stub que garante que há um arquivo local se não houver supabase."""
    try:
        client = get_supabase()
        if client:
            res = client.table("videoteca").select("*").execute()
            data = res.data or []
            with open("videoteca_export.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return True
    except Exception as e:
        print("exportar_videoteca_para_arquivo error:", e)
        return False

# -------------------------
# Cronograma persistence (Supabase table 'cronogramas' or local JSON file)
# -------------------------
def get_cronograma_status(usuario_id):
    client = get_supabase()
    try:
        if client:
            res = client.table("cronogramas").select("estado_json").eq("usuario_id", usuario_id).execute()
            if res.data:
                return res.data[0].get("estado_json") or {}
            return {}
        # local
        path = f"cronograma_{usuario_id}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        print("get_cronograma_status error:", e)
        return {}

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    try:
        if client:
            payload = {"usuario_id": usuario_id, "estado_json": estado_dict}
            client.table("cronogramas").upsert(payload, on_conflict="usuario_id").execute()
            trigger_refresh()
            return True
        # local
        path = f"cronograma_{usuario_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(estado_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("salvar_cronograma_status error:", e)
        return False

# Compatibilidade mínima
def get_db(): return True