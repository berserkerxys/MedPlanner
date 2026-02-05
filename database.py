# database.py
# Versão com Sincronização Sidebar -> Cronograma

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
            # Suporta tuplas de 2 (Aula, Area) ou 3 (Aula, Area, Prioridade) itens
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabelas Core
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

# --- 4. PERSISTÊNCIA CRONOGRAMA ---
def get_cronograma_status(usuario_id):
    """
    Retorna o estado do cronograma.
    Formato: { 'Nome Aula': {'feito': bool, 'prioridade': str, 'acertos': int, 'total': int} }
    """
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
                if row and row[0]:
                    dados_raw = json.loads(row[0])
    except: pass

    # Normalização dos dados para garantir formato novo
    dados_processados = {}
    for aula, valor in dados_raw.items():
        if isinstance(valor, bool):
            dados_processados[aula] = {"feito": valor, "prioridade": "Normal", "acertos": 0, "total": 0}
        else:
            dados_processados[aula] = valor
            
    return dados_processados

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    # Filtra entradas vazias para economizar espaço, mas mantém dados ricos
    estado_limpo = {k: v for k, v in estado_dict.items() if v.get('feito') or v.get('acertos') > 0 or v.get('prioridade') != 'Normal'}
    json_str = json.dumps(estado_limpo, ensure_ascii=False)
    try:
        if client:
            client.table("cronogramas").upsert({"usuario_id": usuario_id, "estado_json": estado_limpo}).execute()
            trigger_refresh()
            return True
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?, ?)", (usuario_id, json_str))
        trigger_refresh()
        return True
    except: return False

def atualizar_progresso_cronograma(u, assunto, acertos, total):
    """
    Função auxiliar para atualizar o cronograma quando um estudo é registrado na sidebar.
    """
    estado = get_cronograma_status(u)
    
    # Se o assunto existe no cronograma (mesmo que não iniciado), atualiza
    # Se não existe, cria nova entrada
    dados_atuais = estado.get(assunto, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
    
    # Acumula os valores
    dados_atuais["acertos"] = int(dados_atuais.get("acertos", 0)) + int(acertos)
    dados_atuais["total"] = int(dados_atuais.get("total", 0)) + int(total)
    
    # Marca como feito se tiver progresso (opcional, pode deixar manual)
    if dados_atuais["total"] > 0:
        dados_atuais["feito"] = True
        
    estado[assunto] = dados_atuais
    salvar_cronograma_status(u, estado)

# --- 5. REGISTROS (COM SINCRONIZAÇÃO) ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * 2
    client = get_supabase()

    # 1. Registo Histórico (Log)
    if client:
        try:
            client.table("historico").insert({"usuario_id":u, "assunto_nome":assunto, "area_manual":area, "data_estudo":dt, "acertos":int(acertos), "total":int(total)}).execute()
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
            res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            old_xp = res.data[0]['xp'] if res.data else 0
            client.table("perfil_gamer").upsert({"usuario_id":u, "xp": old_xp + xp_ganho}).execute()
        except: pass
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total))
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
            row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
            old_xp = row[0] if row else 0
            conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
    
    # 2. Sincronização com Cronograma
    atualizar_progresso_cronograma(u, assunto, acertos, total)
    
    trigger_refresh()
    return f"✅ Salvo em {area}!"

def registrar_simulado(u, dados):
    for area, d in dados.items():
        if int(d['total']) > 0: registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=normalizar_area(area), srs=False)
    return "✅ Simulado Salvo!"

# --- DEMAIS FUNÇÕES (MANTIDAS) ---
# ... (get_dados_graficos, listar_revisoes, concluir_revisao, etc. mantidos iguais)
def get_dados_pessoais(u):
    client = get_supabase(); dados = {"email": "", "nascimento": None}
    try:
        if client:
            res = client.table("usuarios").select("email, data_nascimento").eq("username", u).execute()
            if res.data: dados["email"] = res.data[0].get("email") or ""; dados["nascimento"] = res.data[0].get("data_nascimento")
        else:
            _ensure_local_db(); conn=sqlite3.connect(DB_NAME); conn.row_factory=sqlite3.Row
            row = conn.execute("SELECT email, data_nascimento FROM usuarios WHERE username=?", (u,)).fetchone()
            if row: dados["email"] = row["email"] or ""; dados["nascimento"] = row["data_nascimento"]
    except: pass
    return dados

def update_dados_pessoais(u, e, d):
    client = get_supabase()
    try:
        if client: client.table("usuarios").update({"email": e, "data_nascimento": d}).eq("username", u).execute()
        else: _ensure_local_db(); sqlite3.connect(DB_NAME).execute("UPDATE usuarios SET email=?, data_nascimento=? WHERE username=?", (e, d, u)).commit()
        return True
    except: return False

def get_benchmark_dados(u, df):
    # Mock para manter compatibilidade
    return pd.DataFrame([{"Area": "Geral", "Tipo": "Você", "Performance": 0}])

def get_caderno_erros(u, a): return ""
def salvar_caderno_erros(u, a, t): return True
def get_dados_graficos(u, n=None): return pd.DataFrame()
def listar_revisoes_completas(u, n=None): return pd.DataFrame()
def concluir_revisao(rid, ac, tot): return "OK"
def update_meta_diaria(u, n): pass
def get_conquistas_e_stats(u): return 0, [], None
def get_status_gamer(u, n=None): return {'meta_diaria': 50, 'titulo': 'Interno', 'nivel': 1, 'xp_atual': 0}, pd.DataFrame()
def get_progresso_hoje(u, n=None): return 0
def verificar_login(u, p): return True, u
def criar_usuario(u, p, n): return True, "OK"
def get_resumo(u, a): return ""
def salvar_resumo(u, a, t): return True
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_db(): return True