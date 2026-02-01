# database.py
# Versão Final: Correção de duplicidade de áreas e funções administrativas

import os
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

# --- NORMALIZAÇÃO INTELIGENTE (RESOLVE DUPLICIDADE) ---
def normalizar_area(nome):
    """
    Padroniza os nomes das áreas para evitar duplicidade nos gráficos.
    Ex: G.O -> Ginecologia e Obstetrícia
    """
    if not nome: return "Geral"
    
    n_upper = str(nome).strip().upper()
    
    mapeamento = {
        # GINECOLOGIA
        "G.O": "Ginecologia e Obstetrícia",
        "G.O.": "Ginecologia e Obstetrícia",
        "GO": "Ginecologia e Obstetrícia",
        "GINECO": "Ginecologia e Obstetrícia",
        "GINECOLOGIA": "Ginecologia e Obstetrícia",
        "OBSTETRICIA": "Ginecologia e Obstetrícia",
        "OBSTETRÍCIA": "Ginecologia e Obstetrícia",
        "GINECOLOGIA E OBSTETRICIA": "Ginecologia e Obstetrícia",
        "GINECOLOGIA E OBSTETRÍCIA": "Ginecologia e Obstetrícia",
        
        # PEDIATRIA
        "PED": "Pediatria",
        "PEDIATRIA": "Pediatria",
        
        # CLÍNICA
        "CM": "Clínica Médica",
        "CLINICA": "Clínica Médica",
        "CLÍNICA": "Clínica Médica",
        "CLINICA MEDICA": "Clínica Médica",
        "CLÍNICA MÉDICA": "Clínica Médica",
        
        # CIRURGIA
        "CIRURGIA": "Cirurgia",
        "CIRURGIA GERAL": "Cirurgia",
        
        # PREVENTIVA
        "PREVENTIVA": "Preventiva",
        "MEDICINA PREVENTIVA": "Preventiva"
    }
    
    return mapeamento.get(n_upper, str(nome).strip())

# --- INTEGRAÇÃO MEDCOF ---
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
                # Aplica normalização já na carga
                mapa_areas[aula] = normalizar_area(area)
    except: pass
    return sorted(list(set(lista_aulas))), mapa_areas

def get_lista_assuntos_nativa():
    aulas, _ = _carregar_dados_medcof()
    return aulas if aulas else ["Banco Geral"]

def get_area_por_assunto(assunto):
    _, mapa = _carregar_dados_medcof()
    return mapa.get(assunto, "Geral")

# --- CONEXÃO ---
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
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
    conn.commit()
    conn.close()

# --- REGISTROS ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    
    # Prioridade: Área informada > Área do MedCof > Geral -> NORMALIZADA
    area_crua = area_f if area_f else get_area_por_assunto(assunto)
    area = normalizar_area(area_crua)
    
    xp_ganho = int(total) * 2
    client = get_supabase()

    if client:
        try:
            client.table("historico").insert({
                "usuario_id":u, "assunto_nome":assunto, "area_manual":area, 
                "data_estudo":dt, "acertos":int(acertos), "total":int(total)
            }).execute()
            
            if srs and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({
                    "usuario_id":u, "assunto_nome":assunto, "grande_area":area, 
                    "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"
                }).execute()
                
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
        if int(d['total']) > 0: 
            # Normaliza a chave do dicionário também
            registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=normalizar_area(area), srs=False)
    return "✅ Simulado Salvo!"

# --- PERFORMANCE (GRÁFICOS) ---
def get_dados_graficos(u, nonce=None):
    client = get_supabase()
    if client:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn: 
            df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
    
    if not df.empty:
        df['data'] = pd.to_datetime(df['data_estudo'])
        
        # NORMALIZAÇÃO RETROATIVA para correção de dados antigos
        if 'area_manual' in df.columns:
            df['area'] = df['area_manual'].apply(normalizar_area)
        else:
            df['area'] = df['assunto_nome'].apply(get_area_por_assunto).apply(normalizar_area)
            
        df['total'] = df['total'].astype(int)
        df['acertos'] = df['acertos'].astype(int)
    return df

# --- AGENDA & REVISÕES ---
def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    if client:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    
    _ensure_local_db()
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))

def concluir_revisao(rid, ac, tot):
    client = get_supabase()
    if client:
        r = client.table("revisoes").select("*").eq("id", rid).execute()
        if r.data:
            rev = r.data[0]
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
            registrar_estudo(rev['usuario_id'], rev['assunto_nome'], ac, tot, area_f=rev['grande_area'], srs=False)
            return "✅ Revisão Concluída!"
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("SELECT usuario_id, assunto_nome, grande_area FROM revisoes WHERE id=?", (rid,))
            rev = cur.fetchone()
            if rev:
                cur.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
                conn.commit()
                # Registra o estudo sem agendar nova revisão (srs=False)
                registrar_estudo(rev[0], rev[1], ac, tot, area_f=rev[2], srs=False)
                return "✅ Revisão Concluída!"
    return "Erro"

# --- GAMIFICAÇÃO & UTILS ---
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
            
    status = {'nivel': 1 + (xp // 1000), 'xp_atual': xp % 1000, 'xp_total': xp, 'meta_diaria': meta, 'titulo': "Interno"}
    df_m = pd.DataFrame([{"Icon": "🎯", "Meta": "Questões", "Prog": q, "Objetivo": meta, "Unid": "q"}])
    return status, df_m

def get_progresso_hoje(u, nonce=None):
    _, df_m = get_status_gamer(u, nonce)
    return df_m.iloc[0]['Prog'] if not df_m.empty else 0

# --- AUTH & STUBS ---
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

def get_resumo(u, area): 
    # Implementação simplificada para evitar erro se tabela não existir
    return ""
def salvar_resumo(u, area, texto): return True
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(termo): return pd.DataFrame()
def get_db(): return True