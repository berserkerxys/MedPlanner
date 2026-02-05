# database.py
import os
import json
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

# --- 1. NORMALIZAÇÃO ---
def normalizar_area(nome):
    if not nome: return "Geral"
    n_upper = str(nome).strip().upper()
    mapeamento = {
        "G.O": "Ginecologia e Obstetrícia", "G.O.": "Ginecologia e Obstetrícia", "GO": "Ginecologia e Obstetrícia",
        "GINECO": "Ginecologia e Obstetrícia", "GINECOLOGIA": "Ginecologia e Obstetrícia",
        "OBSTETRICIA": "Ginecologia e Obstetrícia", "OBSTETRÍCIA": "Ginecologia e Obstetrícia",
        "GINECOLOGIA E OBSTETRICIA": "Ginecologia e Obstetrícia", "GINECOLOGIA E OBSTETRÍCIA": "Ginecologia e Obstetrícia",
        "PED": "Pediatria", "PEDIATRIA": "Pediatria",
        "CM": "Clínica Médica", "CLINICA": "Clínica Médica", "CLÍNICA": "Clínica Médica", 
        "CLINICA MEDICA": "Clínica Médica", "CLÍNICA MÉDICA": "Clínica Médica",
        "CIRURGIA": "Cirurgia", "CIRURGIA GERAL": "Cirurgia",
        "PREVENTIVA": "Preventiva", "MEDICINA PREVENTIVA": "Preventiva"
    }
    return mapeamento.get(n_upper, str(nome).strip())

# --- 2. INTEGRAÇÃO MEDCOF ---
@st.cache_data
def _carregar_dados_medcof():
    lista_aulas, mapa_areas = [], {}
    try:
        import aulas_medcof
        dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        for item in dados:
            if isinstance(item, tuple) and len(item) >= 2:
                aula, area = str(item[0]).strip(), str(item[1]).strip()
                lista_aulas.append(aula)
                mapa_areas[aula] = normalizar_area(area)
    except: pass
    return sorted(list(set(lista_aulas))), mapa_areas

def get_lista_assuntos_nativa():
    aulas, _ = _carregar_dados_medcof()
    return aulas if aulas else ["Banco Geral"]

def get_area_por_assunto(assunto):
    _, mapa = _carregar_dados_medcof()
    return mapa.get(assunto, "Geral")

# --- 3. CONEXÃO E UTILS ---
@st.cache_resource
def get_supabase() -> Optional["Client"]:
    try:
        if "supabase" in st.secrets:
            return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: pass
    return None

def trigger_refresh():
    if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
    st.session_state.data_nonce += 1

def _ensure_local_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
        c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
        
        # Migrações
        try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
        except: pass
        try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
        except: pass
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro DB Local: {e}")
        return False

# --- 4. PERSISTÊNCIA CRONOGRAMA ---
def get_cronograma_status(usuario_id):
    client = get_supabase()
    dados_raw = {}
    try:
        if client:
            res = client.table("cronogramas").select("estado_json").eq("usuario_id", usuario_id).execute()
            if res.data:
                d = res.data[0].get("estado_json")
                dados_raw = d if isinstance(d, dict) else json.loads(d)
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (usuario_id,)).fetchone()
                if row and row[0]: dados_raw = json.loads(row[0])
    except: pass

    # Normalização de compatibilidade
    processado = {}
    for k, v in dados_raw.items():
        if isinstance(v, bool): processado[k] = {"feito": v, "prioridade": "Normal", "acertos": 0, "total": 0}
        else: processado[k] = v
    return processado

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    json_str = json.dumps(estado_dict, ensure_ascii=False)
    try:
        if client:
            client.table("cronogramas").upsert({"usuario_id": usuario_id, "estado_json": estado_dict}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?, ?)", (usuario_id, json_str))
        trigger_refresh()
        return True
    except: return False

def atualizar_progresso_cronograma(u, assunto, acertos, total):
    """Sincroniza registro da Sidebar com o Cronograma."""
    estado = get_cronograma_status(u)
    dados = estado.get(assunto, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
    
    # Soma aos valores existentes
    dados["acertos"] = int(dados.get("acertos", 0)) + int(acertos)
    dados["total"] = int(dados.get("total", 0)) + int(total)
    
    # Marca como feito se tiver progresso
    if dados["total"] > 0: dados["feito"] = True
        
    estado[assunto] = dados
    salvar_cronograma_status(u, estado)

# --- 5. REGISTROS (CORRIGIDO) ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * 2
    client = get_supabase()
    
    sucesso_hist = False
    sucesso_rev = False

    try:
        # 1. Tenta Supabase
        if client:
            client.table("historico").insert({"usuario_id":u, "assunto_nome":assunto, "area_manual":area, "data_estudo":dt, "acertos":int(acertos), "total":int(total)}).execute()
            sucesso_hist = True
            
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
                sucesso_rev = True
                
            # XP
            res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            old_xp = res.data[0]['xp'] if res.data else 0
            client.table("perfil_gamer").upsert({"usuario_id":u, "xp": old_xp + xp_ganho}).execute()
            
        else:
            raise Exception("Sem cliente Supabase") # Força fallback
            
    except Exception as e:
        print(f"Erro Supabase (Fallback Local): {e}")
        # 2. Fallback SQLite
        try:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total))
                sucesso_hist = True
                
                if srs and "Simulado" not in assunto:
                    dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
                    sucesso_rev = True
                
                row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                old_xp = row[0] if row else 0
                conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
        except Exception as e2:
            print(f"Erro SQLite: {e2}")
            return f"❌ Erro ao salvar: {e2}"

    # 3. Sincroniza Cronograma
    if sucesso_hist:
        atualizar_progresso_cronograma(u, assunto, acertos, total)
    
    trigger_refresh()
    return f"✅ Salvo em {area}!"

def registrar_simulado(u, dados):
    for area, d in dados.items():
        if int(d['total']) > 0: registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=normalizar_area(area), srs=False)
    return "✅ Simulado Salvo!"

# --- 6. LEITURA DE DADOS (CORRIGIDO PARA DASHBOARD) ---
def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    df = pd.DataFrame()
    try:
        if client:
            res = client.table("historico").select("*").eq("usuario_id", u).execute()
            if res.data: df = pd.DataFrame(res.data)
        
        # Se falhou ou vazio no Supabase, tenta local
        if df.empty:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    except Exception as e:
        print(f"Erro get_dados: {e}")

    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        if 'area_manual' in df.columns: df['area'] = df['area_manual'].apply(normalizar_area)
        else: df['area'] = "Geral"
        df['total'] = df['total'].astype(int); df['acertos'] = df['acertos'].astype(int)
    
    return df

def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    df = pd.DataFrame()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
            if res.data: df = pd.DataFrame(res.data)
        
        if df.empty:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                df = pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))
    except: pass
    return df

# --- DEMAIS STUBS ---
def concluir_revisao(rid, ac, tot): return "OK"
def get_status_gamer(u, n=None): return {'meta_diaria': 50, 'titulo': 'Interno', 'nivel': 1, 'xp_atual': 0}, pd.DataFrame()
def get_progresso_hoje(u, n=None): return 0
def get_conquistas_e_stats(u): return 0, [], None
def get_dados_pessoais(u): return {}
def update_dados_pessoais(u, e, d): return True
def update_meta_diaria(u, n): pass
def verificar_login(u, p): return True, u
def criar_usuario(u, p, n): return True, "OK"
def get_resumo(u, a): return ""
def salvar_resumo(u, a, t): return True
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_benchmark_dados(u, df): return pd.DataFrame([{"Area": "Geral", "Tipo": "Você", "Performance": 0}])
def get_caderno_erros(u, a): return ""
def salvar_caderno_erros(u, a, t): return True
def get_db(): return True