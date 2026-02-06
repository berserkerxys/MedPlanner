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
    from supabase import Client
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

# --- 3. CONEXÃO ---
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
        c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
        c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
        try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
        except: pass
        try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
        except: pass
        try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
        except: pass
        conn.commit(); conn.close()
        return True
    except Exception: return False

# --- 4. FUNÇÕES DE DADOS (CADERNO, STATUS, ETC) ---
def get_caderno_erros(u, area):
    client = get_supabase()
    try:
        if client:
            res = client.table("resumos").select("conteudo").eq("usuario_id", u).eq("grande_area", area).execute()
            return res.data[0]['conteudo'] if res.data else ""
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT conteudo FROM resumos WHERE usuario_id=? AND grande_area=?", (u, area)).fetchone()
            return row[0] if row else ""
    except: return ""

def salvar_caderno_erros(u, area, texto):
    client = get_supabase(); texto = texto or ""
    try:
        if client: client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn: conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto))
        return True
    except: return False

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

def update_dados_pessoais(u, email, nascimento_str):
    client = get_supabase()
    try:
        if client: client.table("usuarios").update({"email": email, "data_nascimento": nascimento_str}).eq("username", u).execute()
        else: _ensure_local_db(); sqlite3.connect(DB_NAME).execute("UPDATE usuarios SET email=?, data_nascimento=? WHERE username=?", (email, nascimento_str, u)).commit()
        return True
    except: return False

def get_cronograma_status(usuario_id):
    client = get_supabase(); dados_raw = {}
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
    processado = {}
    for k, v in dados_raw.items():
        if isinstance(v, bool): processado[k] = {"feito": v, "prioridade": "Normal", "acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0}
        else:
            if "acertos_pre" not in v: v["acertos_pre"] = 0
            if "total_pre" not in v: v["total_pre"] = 0
            if "acertos_pos" not in v: v["acertos_pos"] = v.get("acertos", 0)
            if "total_pos" not in v: v["total_pos"] = v.get("total", 0)
            processado[k] = v
    return processado

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    estado_limpo = {k: v for k, v in estado_dict.items() if v}
    json_str = json.dumps(estado_limpo, ensure_ascii=False)
    try:
        if client: client.table("cronogramas").upsert({"usuario_id": usuario_id, "estado_json": estado_limpo}).execute()
        else: _ensure_local_db(); sqlite3.connect(DB_NAME).execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?, ?)", (usuario_id, json_str)).commit()
        trigger_refresh(); return True
    except: return False

def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True, tipo_estudo="Pos-Aula"):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * (3 if tipo_estudo == "Pre-Aula" else 2)
    client = get_supabase(); sucesso_hist = False
    try:
        if client:
            client.table("historico").insert({"usuario_id":u, "assunto_nome":assunto, "area_manual":area, "data_estudo":dt, "acertos":int(acertos), "total":int(total), "tipo_estudo": tipo_estudo}).execute()
            sucesso_hist = True
            if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
            curr = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            ox = curr.data[0]['xp'] if curr.data else 0
            client.table("perfil_gamer").upsert({"usuario_id":u, "xp": ox + xp_ganho}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total, tipo_estudo))
                sucesso_hist = True
                if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
                    dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, "1 Semana", "Pendente"))
                r = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                ox = r[0] if r else 0
                conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, ox + xp_ganho))
    except Exception as e: print(f"Erro Reg: {e}"); return "Erro"
    
    if sucesso_hist:
        # Atualiza cronograma
        estado = get_cronograma_status(u)
        d = estado.get(assunto, {"feito": False, "prioridade": "Normal", "acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0})
        if tipo_estudo == "Pre-Aula":
            d["acertos_pre"] = int(d.get("acertos_pre",0)) + int(acertos)
            d["total_pre"] = int(d.get("total_pre",0)) + int(total)
        else:
            d["acertos_pos"] = int(d.get("acertos_pos",0)) + int(acertos)
            d["total_pos"] = int(d.get("total_pos",0)) + int(total)
        if d["total_pos"] > 0: d["feito"] = True
        estado[assunto] = d
        salvar_cronograma_status(u, estado)
        
    trigger_refresh()
    return f"✅ Salvo!"

def get_dados_graficos(u, nonce=None):
    client = get_supabase(); df = pd.DataFrame()
    try:
        if client:
            res = client.table("historico").select("*").eq("usuario_id", u).execute()
            if res.data: df = pd.DataFrame(res.data)
        if df.empty:
            _ensure_local_db(); conn = sqlite3.connect(DB_NAME); df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    except: pass
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        if 'area_manual' in df.columns: df['area'] = df['area_manual'].apply(normalizar_area)
        else: df['area'] = "Geral"
        df['total'] = df['total'].astype(int); df['acertos'] = df['acertos'].astype(int)
    return df

def get_status_gamer(u, nonce=None):
    client = get_supabase(); xp=0; meta=50
    try:
        if client:
            r = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
            if r.data: xp=r.data[0].get('xp',0); meta=r.data[0].get('meta_diaria',50)
        else:
            _ensure_local_db(); r = sqlite3.connect(DB_NAME).execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
            if r: xp=r[0]; meta=r[1]
    except: pass
    
    # Busca total de questões HOJE
    hoje = datetime.now().strftime("%Y-%m-%d")
    q_hoje = 0
    try:
        df_h = get_dados_graficos(u)
        if not df_h.empty:
            q_hoje = df_h[df_h['data_estudo'] == hoje]['total'].sum()
    except: pass

    tit = "Interno"
    if xp > 2000: tit = "R1"
    status = {'nivel': 1+(xp//1000), 'xp_atual': xp, 'xp_total': xp, 'meta_diaria': meta, 'titulo': tit}
    df_m = pd.DataFrame([{"Icon": "🎯", "Meta": "Questões", "Prog": int(q_hoje), "Objetivo": int(meta), "Unid": "q"}])
    return status, df_m

def get_progresso_hoje(u, n=None):
    s, df = get_status_gamer(u, n)
    if not df.empty: return df.iloc[0]['Prog']
    return 0

def update_meta_diaria(u, nova):
    client = get_supabase()
    try:
        if client: client.table("perfil_gamer").update({"meta_diaria": int(nova)}).eq("usuario_id", u).execute()
        else: _ensure_local_db(); sqlite3.connect(DB_NAME).execute("UPDATE perfil_gamer SET meta_diaria=? WHERE usuario_id=?", (nova, u)).commit()
    except: pass
    trigger_refresh()

def get_conquistas_e_stats(u):
    df = get_dados_graficos(u)
    total = df['total'].sum() if not df.empty else 0
    tiers = [{"nome": "R1", "meta": 2000, "icon": "🩺", "desbloqueado": total>=2000}]
    return total, tiers, None

def calcular_meta_questoes(prio, anterior):
    base = {"Diamante": 20, "Vermelho": 15, "Amarelo": 10, "Verde": 5, "Normal": 5}
    m_pre = base.get(prio, 5); m_pos = m_pre + 10
    return m_pre, m_pos

def resetar_revisoes_aula(u, aula):
    stt = get_cronograma_status(u)
    d = stt.get(aula, {})
    ac = int(d.get('acertos_pos', 0)); tt = int(d.get('total_pos', 0))
    if tt > 0: d['ultimo_desempenho'] = ac/tt
    d.update({'acertos_pre':0, 'total_pre':0, 'acertos_pos':0, 'total_pos':0, 'feito':False})
    stt[aula] = d
    return salvar_cronograma_status(u, stt)

def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
            if res.data: return pd.DataFrame(res.data)
        _ensure_local_db(); return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", sqlite3.connect(DB_NAME), params=(u,))
    except: return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    registrar_estudo(rid, "Revisão", ac, tot, tipo_estudo="Pos-Aula")
    return "✅"

def excluir_revisao(rid):
    client = get_supabase()
    try:
        if client: client.table("revisoes").delete().eq("id", rid).execute()
        else: sqlite3.connect(DB_NAME).execute("DELETE FROM revisoes WHERE id=?", (rid,)).commit()
        trigger_refresh(); return True
    except: return False

def reagendar_inteligente(rid, desempenho):
    # Lógica simplificada de reagendamento
    client = get_supabase()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("id", rid).execute()
            rev = res.data[0]
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
            
            # Nova data (simplificada)
            dias = 1 if desempenho == "Muito Ruim" else 7
            dt = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({"usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'], "grande_area": rev['grande_area'], "data_agendada": dt, "tipo": "SRS", "status": "Pendente"}).execute()
        trigger_refresh()
        return True, ""
    except: return False, ""

def registrar_simulado(u, d): return "OK"
def verificar_login(u, p): return True, u
def criar_usuario(u, p, n): return True, "OK"
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_db(): return True