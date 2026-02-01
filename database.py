import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client
import sqlite3
import json
import os

# -------------------------
# Config local (SQLite) used by ingestao_manual.py
# -------------------------
DB_NAME = "medplanner_local.db"

def inicializar_db():
    """
    Cria o banco sqlite local básico usado para importação manual (ingestao_manual).
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela de assuntos (nome único)
    c.execute("""
    CREATE TABLE IF NOT EXISTS assuntos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nome TEXT UNIQUE,
      grande_area TEXT
    )
    """)
    conn.commit()
    conn.close()

# -------------------------
# Supabase client (prod)
# -------------------------
@st.cache_resource
def get_supabase() -> Client:
    """
    Retorna um cliente Supabase se as credenciais estiverem em st.secrets.
    Caso contrário, retorna None (app pode operar em modo local dependendo das funções).
    """
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception as e:
        print("Erro ao criar cliente Supabase:", e)
        return None

# -------------------------
# Utilidades de cache / refresh
# -------------------------
def trigger_refresh():
    if 'data_nonce' not in st.session_state:
        st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

# -------------------------
# GAMIFICAÇÃO & MISSÕES
# -------------------------
@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce=None):
    client = get_supabase()
    if not client: 
        # fallback: 0 se não há supabase
        return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data]) if res.data else 0
    except Exception as e:
        print("Erro get_progresso_hoje:", e)
        return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce=None):
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
        
        # Cálculo de Missões em Tempo Real
        hoje = datetime.now().strftime("%Y-%m-%d")
        h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        q = sum([int(i['total']) for i in h.data]) if h.data else 0
        a = sum([int(i['acertos']) for i in h.data]) if h.data else 0
        
        missoes = [
            {"Icon": "🎯", "Meta": "Meta de Questões", "Prog": q, "Objetivo": meta, "Unid": "q"},
            {"Icon": "✅", "Meta": "Foco em Acertos", "Prog": a, "Objetivo": int(meta * 0.7), "Unid": "hits"},
            {"Icon": "⚡", "Meta": "XP Gerado Hoje", "Prog": q * 2, "Objetivo": meta * 2, "Unid": "xp"}
        ]
        return status, pd.DataFrame(missoes)
    except Exception as e:
        print("Erro get_status_gamer:", e)
        return None, pd.DataFrame()

def update_meta_diaria(u, nova_meta):
    client = get_supabase()
    try:
        client.table("perfil_gamer").update({"meta_diaria": int(nova_meta)}).eq("usuario_id", u).execute()
        trigger_refresh()
        return True
    except Exception as e:
        print("Erro update_meta_diaria:", e)
        return False

# -------------------------
# SISTEMA DE RESUMOS
# -------------------------
def get_resumo(u, area):
    client = get_supabase()
    try:
        res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
        return res.data[0]['conteudo'] if res.data else ""
    except Exception as e:
        # fallback: vazio
        print("Erro get_resumo:", e)
        return ""

def salvar_resumo(u, area, texto):
    client = get_supabase()
    try:
        client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
        return True
    except Exception as e:
        print("Erro salvar_resumo:", e)
        return False

# -------------------------
# VIDEOTECA / BIBLIOTECA
# -------------------------
@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    """
    Tenta obter a lista de conteúdo da videoteca do Supabase.
    Caso não haja conexão, tenta carregar um arquivo local 'videoteca_export.json' (opcional).
    Retorna um pandas.DataFrame com colunas mínimas: titulo, assunto, grande_area, link (quando disponíveis).
    """
    client = get_supabase()
    if client:
        try:
            res = client.table("videoteca").select("*").execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            # normaliza nomes de colunas esperadas
            return df
        except Exception as e:
            print("Erro listar_conteudo_videoteca (supabase):", e)
            return pd.DataFrame()
    else:
        # fallback: tenta arquivo local
        path = "videoteca_export.json"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return pd.DataFrame(data)
            except Exception as e:
                print("Erro ler videoteca local:", e)
                return pd.DataFrame()
        return pd.DataFrame()

# -------------------------
# UTILITÁRIAS DE LISTAS / PESQUISA
# -------------------------
def get_area_por_assunto(assunto):
    df = listar_conteudo_videoteca()
    if df.empty: return "Geral"
    # tenta mapear pela coluna 'assunto' ou 'titulo' dependendo do esquema
    if 'assunto' in df.columns:
        match = df[df['assunto'] == assunto]
        return match.iloc[0]['grande_area'] if not match.empty and 'grande_area' in df.columns else "Geral"
    # fallback: procura por assunto no título
    match = df[df['titulo'] == assunto] if 'titulo' in df.columns else pd.DataFrame()
    return match.iloc[0]['grande_area'] if not match.empty and 'grande_area' in df.columns else "Geral"

def get_lista_assuntos_nativa():
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral"]
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
    """
    Registra um estudo no histórico e cria uma revisão automática (SRS) para 7 dias depois.
    """
    client = get_supabase()
    dt = data_p if data_p else datetime.now().date()
    area = area_f if area_f else get_area_por_assunto(assunto)
    try:
        if not client:
            # fallback local: insere em sqlite (tabela 'historico' local)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT,
                assunto_nome TEXT,
                area_manual TEXT,
                data_estudo TEXT,
                acertos INTEGER,
                total INTEGER
            )
            """)
            c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                      (u, assunto, area, dt.strftime("%Y-%m-%d"), int(acertos), int(total)))
            conn.commit()
            conn.close()
        else:
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
    except Exception as e:
        print("Erro registrar_estudo:", e)
        return "Erro"

def registrar_simulado(u, dados, data_p=None):
    """
    Dados: dict area -> {'acertos': int, 'total': int}
    """
    client = get_supabase()
    dt = data_p.strftime("%Y-%m-%d") if data_p else datetime.now().strftime("%Y-%m-%d")
    inserts = []
    tq = 0
    for area, v in dados.items():
        if int(v.get('total', 0)) > 0:
            tq += int(v['total'])
            inserts.append({"usuario_id": u, "assunto_nome": f"Simulado - {area}", "area_manual": area, "data_estudo": dt, "acertos": int(v.get('acertos', 0)), "total": int(v.get('total', 0))})
    try:
        if not client:
            # fallback local: grava em sqlite
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT,
                assunto_nome TEXT,
                area_manual TEXT,
                data_estudo TEXT,
                acertos INTEGER,
                total INTEGER
            )
            """)
            for ins in inserts:
                c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                          (ins['usuario_id'], ins['assunto_nome'], ins['area_manual'], ins['data_estudo'], ins['acertos'], ins['total']))
            conn.commit()
            conn.close()
        else:
            if inserts:
                client.table("historico").insert(inserts).execute()
            
            # XP Bônus
            res_p = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            if res_p.data:
                nxp = int(res_p.data[0].get('xp', 0)) + int(tq * 2.5)
                client.table("perfil_gamer").update({"xp": nxp}).eq("usuario_id", u).execute()
        trigger_refresh()
        return f"✅ Simulado salvo ({tq}q)!"
    except Exception as e:
        print("Erro registrar_simulado:", e)
        return "Erro"

@st.cache_data(ttl=300)
def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    try:
        if not client:
            # fallback local: tenta ler sqlite historico
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id = ?", conn, params=(u,))
            conn.close()
            if df.empty: return df
            df['data'] = pd.to_datetime(df['data_estudo']).dt.normalize()
            df['acertos'] = df['acertos'].astype(int)
            df['total'] = df['total'].astype(int)
            df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
            return df.sort_values('data')
        
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
    except Exception as e:
        print("Erro get_dados_graficos:", e)
        return pd.DataFrame()

# -------------------------
# AUTH & AGENDA
# -------------------------
def verificar_login(u, p):
    client = get_supabase()
    try:
        if not client:
            return False, "Sem backend de autenticação"
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            if bcrypt.checkpw(p.encode('utf-8'), res.data[0]['password_hash'].encode('utf-8')):
                return True, res.data[0]['nome']
        return False, "Login falhou"
    except Exception as e:
        print("Erro verificar_login:", e)
        return False, "Erro conexão"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        if not client:
            return False, "Sem supabase configurado"
        h = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": h}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "xp": 0, "titulo": "Interno", "meta_diaria": 50}).execute()
        return True, "Criado!"
    except Exception as e:
        print("Erro criar_usuario:", e)
        return False, "Usuário existe ou erro"

def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    try:
        if not client:
            # fallback local
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id = ?", conn, params=(u,))
            conn.close()
            return df
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        print("Erro listar_revisoes_completas:", e)
        return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    try:
        if not client:
            # fallback local: atualiza sqlite revisoes e registra historico
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT usuario_id, assunto_nome, grande_area FROM revisoes WHERE id = ?", (rid,))
            row = c.fetchone()
            if not row:
                conn.close()
                return "Erro"
            usuario_id, assunto_nome, grande_area = row
            c.execute("UPDATE revisoes SET status = 'Concluido' WHERE id = ?", (rid,))
            # registra historico
            c.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?, ?, ?, ?, ?, ?)",
                      (usuario_id, assunto_nome, grande_area, datetime.now().strftime("%Y-%m-%d"), int(ac), int(tot)))
            conn.commit()
            conn.close()
            return "✅ Concluído"
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        rev = res.data[0]
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev.get('grande_area'), srs=False)
        return "✅ Concluído"
    except Exception as e:
        print("Erro concluir_revisao:", e)
        return "Erro"

# -------------------------
# CRONOGRAMA: persistência do checklist (JSON)
# -------------------------
def get_cronograma_status(usuario_id):
    """
    Retorna um dicionário (JSON) com o estado salvo do checklist do cronograma para o usuário.
    """
    client = get_supabase()
    try:
        if not client:
            # fallback local: arquivo JSON por usuário
            path = f"cronograma_{usuario_id}.json"
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        res = client.table("cronogramas").select("estado_json").eq("usuario_id", usuario_id).execute()
        if not res.data:
            return {}
        return res.data[0].get("estado_json") or {}
    except Exception as e:
        print("Erro get_cronograma_status:", e)
        return {}

def salvar_cronograma_status(usuario_id, estado_dict):
    """
    Salva (upsert) o estado do checklist do cronograma para o usuário.
    estado_dict deve ser um dicionário serializável em JSON.
    """
    client = get_supabase()
    try:
        if not client:
            # fallback local: salva em arquivo JSON
            path = f"cronograma_{usuario_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(estado_dict, f, ensure_ascii=False, indent=2)
            return True
        payload = {"usuario_id": usuario_id, "estado_json": estado_dict}
        # upsert: insere ou atualiza o registro com user_id
        client.table("cronogramas").upsert(payload, on_conflict="usuario_id").execute()
        trigger_refresh()
        return True
    except Exception as e:
        print("Erro salvar_cronograma_status:", e)
        return False

# -------------------------
# STUBS / UTILIDADES
# -------------------------
def get_db():
    """
    Retorno stub para compatibilidade com outras partes do projeto.
    """
    return True