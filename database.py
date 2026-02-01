# database.py
# Versão com Dados Pessoais (Email/Nascimento) e Migração Automática

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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabelas Core
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
    
    # MIGRAÇÃO: Adiciona colunas novas se não existirem (SQLite não suporta IF NOT EXISTS em ADD COLUMN facilmente, então usamos try/except)
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    except: pass
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
    except: pass
    
    conn.commit()
    conn.close()

# --- 4. GESTÃO DE DADOS PESSOAIS (NOVO) ---
def get_dados_pessoais(u):
    """Retorna dicionário com email e nascimento."""
    client = get_supabase()
    dados = {"email": "", "nascimento": None}
    
    try:
        if client:
            res = client.table("usuarios").select("email, data_nascimento").eq("username", u).execute()
            if res.data:
                d = res.data[0]
                dados["email"] = d.get("email") or ""
                dados["nascimento"] = d.get("data_nascimento")
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                # Usa row_factory para facilitar
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT email, data_nascimento FROM usuarios WHERE username=?", (u,))
                row = cur.fetchone()
                if row:
                    dados["email"] = row["email"] or ""
                    dados["nascimento"] = row["data_nascimento"]
    except: pass
    return dados

def update_dados_pessoais(u, email, nascimento_str):
    """Salva email e data de nascimento (formato YYYY-MM-DD)."""
    client = get_supabase()
    try:
        if client:
            client.table("usuarios").update({"email": email, "data_nascimento": nascimento_str}).eq("username", u).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("UPDATE usuarios SET email=?, data_nascimento=? WHERE username=?", (email, nascimento_str, u))
        return True
    except: return False

# --- 5. PERSISTÊNCIA CRONOGRAMA ---
def get_cronograma_status(usuario_id):
    client = get_supabase()
    try:
        if client:
            res = client.table("cronogramas").select("estado_json").eq("usuario_id", usuario_id).execute()
            if res.data:
                dados = res.data[0].get("estado_json")
                return dados if isinstance(dados, dict) else json.loads(dados)
            return {}
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("SELECT estado_json FROM cronogramas WHERE usuario_id=?", (usuario_id,))
            row = cur.fetchone()
            if row and row[0]: return json.loads(row[0])
        return {}
    except: return {}

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    estado_limpo = {k: v for k, v in estado_dict.items() if v}
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

# --- 6. REGISTROS ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * 2
    client = get_supabase()

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
    trigger_refresh()
    return f"✅ Salvo em {area}!"

def registrar_simulado(u, dados):
    for area, d in dados.items():
        if int(d['total']) > 0: registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=normalizar_area(area), srs=False)
    return "✅ Simulado Salvo!"

# --- 7. PERFORMANCE ---
def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    if client:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn: df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        if 'area_manual' in df.columns: df['area'] = df['area_manual'].apply(normalizar_area)
        else: df['area'] = "Geral"
        df['total'] = df['total'].astype(int); df['acertos'] = df['acertos'].astype(int)
    return df

# --- 8. SRS E AUTH ---
def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    if client:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    _ensure_local_db()
    with sqlite3.connect(DB_NAME) as conn: return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

def concluir_revisao(rid, ac, tot):
    srs_map = {"1 Semana": ("1 Mês", 30), "1 Mês": ("2 Meses", 60), "2 Meses": ("4 Meses", 120)}
    client = get_supabase()
    
    # Lógica unificada para evitar repetição (abstração simples)
    if client:
        r = client.table("revisoes").select("*").eq("id", rid).execute()
        if not r.data: return "Erro"
        rev = r.data[0]
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
    else:
        _ensure_local_db()
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM revisoes WHERE id=?", (rid,))
        rev = cur.fetchone()
        cur.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
        conn.commit()

    if rev:
        registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev['grande_area'], srs=False)
        tipo = rev['tipo']
        if tipo in srs_map:
            prox, dias = srs_map[tipo]
            dt = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            
            if client:
                client.table("revisoes").insert({"usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'], "grande_area": rev['grande_area'], "data_agendada": dt, "tipo": prox, "status": "Pendente"}).execute()
            else:
                cur.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (rev['usuario_id'], rev['assunto_nome'], rev['grande_area'], dt, prox, "Pendente"))
                conn.commit()
            return f"✅ Próxima em {dias}d ({prox})"
        return "✅ Ciclo Finalizado!"
    return "Erro"

def update_meta_diaria(u, nova):
    client = get_supabase()
    if client:
        try: client.table("perfil_gamer").update({"meta_diaria": int(nova)}).eq("usuario_id", u).execute()
        except: pass
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT OR IGNORE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, 0, 'Interno', ?)", (u, nova))
            conn.execute("UPDATE perfil_gamer SET meta_diaria=? WHERE usuario_id=?", (nova, u))
    trigger_refresh()

def get_conquistas_e_stats(u):
    # (Mantido igual à versão anterior, apenas recalculando para contexto)
    client = get_supabase()
    total_q = 0
    if client:
        try:
            h = client.table("historico").select("total").eq("usuario_id", u).execute()
            total_q = sum(x['total'] for x in h.data)
        except: pass
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT sum(total) FROM historico WHERE usuario_id=?", (u,)).fetchone()
            total_q = row[0] if row and row[0] else 0

    tiers = [
        {"nome": "Interno Iniciante", "meta": 100, "icon": "🏥"},
        {"nome": "Residente R1", "meta": 2000, "icon": "🩺"},
        {"nome": "Residente R3", "meta": 10000, "icon": "🧠"},
        {"nome": "Staff", "meta": 15000, "icon": "🎓"},
        {"nome": "A Lenda (Aprovado)", "meta": 20000, "icon": "🏆"},
    ]
    conq = [{"nome": t["nome"], "meta": t["meta"], "icon": t["icon"], "desbloqueado": total_q >= t["meta"]} for t in tiers]
    prox = next((t for t in tiers if total_q < t['meta']), None)
    return total_q, conq, prox

def get_status_gamer(u, nonce=None):
    client, xp, meta = get_supabase(), 0, 50
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    if client:
        try:
            res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
            if res.data: xp, meta = res.data[0].get('xp', 0), res.data[0].get('meta_diaria', 50)
            h = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
            q, a = sum(x['total'] for x in h.data), sum(x['acertos'] for x in h.data)
        except: q, a = 0, 0
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
            if row: xp, meta = row
            h_row = conn.execute("SELECT sum(total), sum(acertos) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, hoje)).fetchone()
            q, a = (h_row[0] or 0), (h_row[1] or 0)
    
    # Título dinâmico
    titulo = "Interno"
    q_total, _, _ = get_conquistas_e_stats(u)
    if q_total > 2000: titulo = "Residente R1"
    if q_total > 10000: titulo = "Residente R3"
    if q_total > 15000: titulo = "Staff"
    if q_total > 20000: titulo = "Chefe"

    status = {'nivel': 1 + (xp // 1000), 'xp_atual': xp % 1000, 'xp_total': xp, 'meta_diaria': meta, 'titulo': titulo}
    df_m = pd.DataFrame([{"Icon": "🎯", "Meta": "Questões", "Prog": q, "Objetivo": meta, "Unid": "q"}])
    return status, df_m

def get_progresso_hoje(u, nonce=None):
    _, df_m = get_status_gamer(u, nonce)
    return df_m.iloc[0]['Prog'] if not df_m.empty else 0

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
        return True, "Criado!"
    return False, "Erro"

def get_resumo(u, area): return ""
def salvar_resumo(u, area, texto): return True
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(termo): return pd.DataFrame()
def get_db(): return True