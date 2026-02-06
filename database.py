# database.py
# Versão Mestra Final: Contém TODAS as funções necessárias para o MedPlanner

import os
import json
import sqlite3
import re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
import random
from typing import Optional, TYPE_CHECKING

# Configuração condicional do Supabase
if TYPE_CHECKING:
    from supabase import Client # type: ignore
try:
    from supabase import create_client
except Exception:
    create_client = None

DB_NAME = "medplanner_local.db"

# ==============================================================================
# 1. FUNÇÕES DE NORMALIZAÇÃO E DADOS ESTÁTICOS
# ==============================================================================

def normalizar_area(nome):
    """Padroniza os nomes das áreas para evitar duplicidade."""
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

# ==============================================================================
# 2. CONEXÃO COM BANCO DE DADOS (SUPABASE E LOCAL)
# ==============================================================================

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
    """Garante que o banco local SQLite exista e tenha todas as tabelas/colunas."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Criação de Tabelas
        c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
        c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
        
        # Migrações (Adição de colunas novas em bancos existentes)
        try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
        except: pass
        try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
        except: pass
        try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
        except: pass
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao inicializar DB Local: {e}")
        return False

# ==============================================================================
# 3. GESTÃO DE DADOS PESSOAIS (PERFIL)
# ==============================================================================

def get_dados_pessoais(u):
    """Retorna email e data de nascimento do usuário."""
    client = get_supabase()
    dados = {"email": "", "nascimento": None}
    try:
        if client:
            res = client.table("usuarios").select("email, data_nascimento").eq("username", u).execute()
            if res.data:
                dados["email"] = res.data[0].get("email") or ""
                dados["nascimento"] = res.data[0].get("data_nascimento")
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT email, data_nascimento FROM usuarios WHERE username=?", (u,)).fetchone()
                if row:
                    dados["email"] = row["email"] or ""
                    dados["nascimento"] = row["data_nascimento"]
    except: pass
    return dados

def update_dados_pessoais(u, email, nascimento_str):
    """Atualiza email e data de nascimento."""
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

def resetar_conta_usuario(u):
    """Zera todo o progresso do usuário (histórico, xp, cronograma), mantendo o login."""
    client = get_supabase()
    try:
        if client:
            client.table("historico").delete().eq("usuario_id", u).execute()
            client.table("revisoes").delete().eq("usuario_id", u).execute()
            client.table("cronogramas").delete().eq("usuario_id", u).execute()
            client.table("resumos").delete().eq("usuario_id", u).execute()
            client.table("perfil_gamer").update({"xp": 0, "titulo": "Interno"}).eq("usuario_id", u).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM historico WHERE usuario_id=?", (u,))
                conn.execute("DELETE FROM revisoes WHERE usuario_id=?", (u,))
                conn.execute("DELETE FROM cronogramas WHERE usuario_id=?", (u,))
                conn.execute("DELETE FROM resumos WHERE usuario_id=?", (u,))
                conn.execute("UPDATE perfil_gamer SET xp=0, titulo='Interno' WHERE usuario_id=?", (u,))
        trigger_refresh()
        return True
    except Exception as e:
        print(f"Erro no reset: {e}")
        return False

# ==============================================================================
# 4. CADERNO DE ERROS (ANTIGOS RESUMOS)
# ==============================================================================

def get_caderno_erros(u, area):
    """Busca anotações do caderno de erros."""
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
    """Salva anotações no caderno de erros."""
    client = get_supabase()
    if texto is None: texto = ""
    try:
        if client:
            client.table("resumos").upsert({"usuario_id": u, "grande_area": area, "conteudo": texto}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT OR REPLACE INTO resumos (usuario_id, grande_area, conteudo) VALUES (?,?,?)", (u, area, texto))
        return True
    except: return False

# Aliases para manter compatibilidade com códigos antigos que chamam 'get_resumo'
def get_resumo(u, a): return get_caderno_erros(u, a)
def salvar_resumo(u, a, t): return salvar_caderno_erros(u, a, t)

# ==============================================================================
# 5. PERSISTÊNCIA DO CRONOGRAMA (CHECKBOXES E METAS)
# ==============================================================================

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

    # Normalização de dados legados
    processado = {}
    for k, v in dados_raw.items():
        if isinstance(v, bool): 
            processado[k] = {
                "feito": v, "prioridade": "Normal", 
                "acertos_pre": 0, "total_pre": 0,
                "acertos_pos": 0, "total_pos": 0,
                "ultimo_desempenho": None
            }
        else: 
            # Garante que chaves novas existam
            if "acertos_pre" not in v: v["acertos_pre"] = 0
            if "total_pre" not in v: v["total_pre"] = 0
            if "acertos_pos" not in v: v["acertos_pos"] = v.get("acertos", 0)
            if "total_pos" not in v: v["total_pos"] = v.get("total", 0)
            processado[k] = v
    return processado

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    # Otimização: Salva apenas itens relevantes (feitos ou com progresso)
    estado_limpo = {k: v for k, v in estado_dict.items() if v.get('feito') or v.get('total_pos') > 0 or v.get('total_pre') > 0 or v.get('ultimo_desempenho') is not None}
    json_str = json.dumps(estado_limpo, ensure_ascii=False)
    
    try:
        if client:
            client.table("cronogramas").upsert({"usuario_id": usuario_id, "estado_json": estado_limpo}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT OR REPLACE INTO cronogramas (usuario_id, estado_json) VALUES (?, ?)", (usuario_id, json_str))
        trigger_refresh()
        return True
    except: return False

def atualizar_progresso_cronograma(u, assunto, acertos, total, tipo_estudo="Pos-Aula"):
    """Atualiza contadores do cronograma sem agendar revisão."""
    estado = get_cronograma_status(u)
    dados = estado.get(assunto, {
        "feito": False, "prioridade": "Normal", 
        "acertos_pre": 0, "total_pre": 0,
        "acertos_pos": 0, "total_pos": 0
    })
    
    if tipo_estudo == "Pre-Aula":
        dados["acertos_pre"] = int(dados.get("acertos_pre", 0)) + int(acertos)
        dados["total_pre"] = int(dados.get("total_pre", 0)) + int(total)
    else: 
        dados["acertos_pos"] = int(dados.get("acertos_pos", 0)) + int(acertos)
        dados["total_pos"] = int(dados.get("total_pos", 0)) + int(total)
    
    if dados["total_pos"] > 0: dados["feito"] = True
        
    estado[assunto] = dados
    salvar_cronograma_status(u, estado)

def resetar_revisoes_aula(u, aula_nome):
    """Zera contadores para novo ciclo."""
    estado = get_cronograma_status(u)
    dados = estado.get(aula_nome, {})
    
    ac = int(dados.get('acertos_pos', 0))
    tt = int(dados.get('total_pos', 0))
    if tt > 0: dados['ultimo_desempenho'] = ac / tt
    
    dados.update({'acertos_pre': 0, 'total_pre': 0, 'acertos_pos': 0, 'total_pos': 0, 'feito': False})
    estado[aula_nome] = dados
    return salvar_cronograma_status(u, estado)

def calcular_meta_questoes(prioridade, desempenho_anterior=None):
    """Calcula meta inteligente baseada em prioridade e histórico."""
    base_pre = {"Diamante": 20, "Vermelho": 15, "Amarelo": 10, "Verde": 5, "Normal": 5}
    base_pos = {"Diamante": 30, "Vermelho": 20, "Amarelo": 15, "Verde": 10, "Normal": 10}
    
    meta_pre = base_pre.get(prioridade, 5)
    meta_pos = base_pos.get(prioridade, 10)
    
    if desempenho_anterior is not None and desempenho_anterior < 0.6:
        meta_pre += 5
        meta_pos += 10
        
    return meta_pre, meta_pos

# ==============================================================================
# 6. REGISTROS DE ESTUDO (HISTÓRICO E XP)
# ==============================================================================

def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=False, tipo_estudo="Pos-Aula"):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * (3 if tipo_estudo == "Pre-Aula" else 2)
    client = get_supabase()
    sucesso_hist = False

    try:
        if client:
            try:
                client.table("historico").insert({
                    "usuario_id":u, "assunto_nome":assunto, "area_manual":area, 
                    "data_estudo":dt, "acertos":int(acertos), "total":int(total),
                    "tipo_estudo": tipo_estudo
                }).execute()
            except:
                # Fallback se coluna tipo_estudo não existir no Supabase
                client.table("historico").insert({
                    "usuario_id":u, "assunto_nome":assunto, "area_manual":area, 
                    "data_estudo":dt, "acertos":int(acertos), "total":int(total)
                }).execute()
            
            sucesso_hist = True
            
            # Agendamento SRS (Só se solicitado explicitamente)
            if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
            
            # Atualiza XP
            try:
                res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
                old_xp = int(res.data[0]['xp']) if res.data else 0
                client.table("perfil_gamer").upsert({"usuario_id":u, "xp": old_xp + xp_ganho}).execute()
            except: pass
            
        else:
            raise Exception("Sem Supabase")
            
    except Exception:
        # Fallback Local
        try:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                try:
                    conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total, tipo_estudo) VALUES (?,?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total, tipo_estudo))
                except:
                    conn.execute("INSERT INTO historico (usuario_id, assunto_nome, area_manual, data_estudo, acertos, total) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, acertos, total))
                
                sucesso_hist = True
                
                if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
                    dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt, "1 Semana", "Pendente"))
                
                row = conn.execute("SELECT xp FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
                old_xp = row[0] if row else 0
                conn.execute("INSERT OR REPLACE INTO perfil_gamer (usuario_id, xp, titulo, meta_diaria) VALUES (?, ?, 'Interno', 50)", (u, old_xp + xp_ganho))
        except: return "Erro ao salvar"

    if sucesso_hist:
        atualizar_progresso_cronograma(u, assunto, acertos, total, tipo_estudo)
    
    trigger_refresh()
    return f"✅ Salvo em {area}!"

def registrar_simulado(u, dados):
    for area, d in dados.items():
        if int(d['total']) > 0: registrar_estudo(u, f"Simulado - {area}", d['acertos'], d['total'], area_f=normalizar_area(area), srs=False, tipo_estudo="Simulado")
    return "✅ Simulado Salvo!"

# ==============================================================================
# 7. AGENDA E SRS (REVISÕES)
# ==============================================================================

def listar_revisoes_completas(u, n=None):
    client = get_supabase()
    try:
        if client:
            res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
            if res.data: return pd.DataFrame(res.data)
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn: return pd.read_sql_query("SELECT * FROM revisoes WHERE usuario_id=?", conn, params=(u,))
    except: return pd.DataFrame()

def concluir_revisao(rid, ac, tot):
    # Registra como Pós-Aula para contar no progresso
    registrar_estudo(rid, "Revisão", ac, tot, tipo_estudo="Pos-Aula")
    return "✅ OK"

def excluir_revisao(rid):
    client = get_supabase()
    try:
        if client: client.table("revisoes").delete().eq("id", rid).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM revisoes WHERE id=?", (rid,))
        trigger_refresh()
        return True
    except: return False

def reagendar_inteligente(rid, desempenho):
    """SRS Baseado em Desempenho (Muito Ruim, Ruim, Bom, Excelente)."""
    client = get_supabase()
    try:
        # Busca revisão atual
        revisao = None
        if client:
            res = client.table("revisoes").select("*").eq("id", rid).execute()
            if res.data: revisao = res.data[0]
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                revisao = conn.execute("SELECT * FROM revisoes WHERE id=?", (rid,)).fetchone()
        
        if not revisao: return False, ""

        # Marca atual como concluída
        if client: client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        else: 
            with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,)).commit()

        # Calcula nova data
        fator = {"Excelente": 2.5, "Bom": 1.5, "Ruim": 0.5, "Muito Ruim": 0}.get(desempenho, 1.0)
        
        # Tenta extrair intervalo anterior do texto 'tipo'
        intervalo = 7 # Default
        match = re.search(r'\((\d+)\s*dias?\)', revisao['tipo'])
        if match: intervalo = int(match.group(1))
        elif "1 Mês" in revisao['tipo']: intervalo = 30
        
        novo_intervalo = max(1, int(intervalo * fator))
        if desempenho == "Muito Ruim": novo_intervalo = 1
        
        nova_data = (datetime.now() + timedelta(days=novo_intervalo)).strftime("%Y-%m-%d")
        novo_tipo = f"SRS ({novo_intervalo} dias)"

        # Insere nova revisão
        if client:
            client.table("revisoes").insert({
                "usuario_id": revisao['usuario_id'], "assunto_nome": revisao['assunto_nome'],
                "grande_area": revisao['grande_area'], "data_agendada": nova_data,
                "tipo": novo_tipo, "status": "Pendente"
            }).execute()
        else:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                             (revisao['usuario_id'], revisao['assunto_nome'], revisao['grande_area'], nova_data, novo_tipo, "Pendente"))
        
        trigger_refresh()
        return True, nova_data
    except Exception as e:
        print(e)
        return False, ""

# ==============================================================================
# 8. PERFORMANCE E GAMIFICAÇÃO
# ==============================================================================

def get_dados_graficos(u, nonce=None):
    client = get_supabase(); df = pd.DataFrame()
    try:
        if client:
            res = client.table("historico").select("*").eq("usuario_id", u).execute()
            if res.data: df = pd.DataFrame(res.data)
        if df.empty:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn: df = pd.read_sql_query("SELECT * FROM historico WHERE usuario_id=?", conn, params=(u,))
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
            _ensure_local_db()
            r = sqlite3.connect(DB_NAME).execute("SELECT xp, meta_diaria FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
            if r: xp=r[0]; meta=r[1]
    except: pass
    
    # Progresso Hoje
    hoje = datetime.now().strftime("%Y-%m-%d")
    q_hoje = 0
    try:
        df_h = get_dados_graficos(u)
        if not df_h.empty: q_hoje = df_h[df_h['data_estudo'] == hoje]['total'].sum()
    except: pass

    # Título
    tit = "Interno"
    if xp > 2000: tit = "Residente R1"
    if xp > 10000: tit = "Residente R3"
    
    status = {'nivel': 1+(xp//1000), 'xp_atual': xp, 'xp_total': xp, 'meta_diaria': meta, 'titulo': tit}
    df_m = pd.DataFrame([{"Icon": "🎯", "Meta": "Questões", "Prog": int(q_hoje), "Objetivo": int(meta), "Unid": "q"}])
    return status, df_m

def get_progresso_hoje(u, nonce=None):
    _, df_m = get_status_gamer(u, nonce)
    return df_m.iloc[0]['Prog'] if not df_m.empty else 0

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
    tiers = [
        {"nome": "Interno Iniciante", "meta": 100, "icon": "🏥"},
        {"nome": "Residente R1", "meta": 2000, "icon": "🩺"},
        {"nome": "Chefe", "meta": 20000, "icon": "🏆"}
    ]
    conq = [{"nome": t["nome"], "meta": t["meta"], "icon": t["icon"], "desbloqueado": total>=t["meta"]} for t in tiers]
    prox = next((t for t in tiers if total < t['meta']), None)
    return total, conq, prox

def get_benchmark_dados(u, df_usuario):
    """Função que retorna os dados de benchmark."""
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    dados = []
    stats_user = {a: 0 for a in areas}

    if not df_usuario.empty:
        if 'area' not in df_usuario.columns:
            if 'area_manual' in df_usuario.columns: df_usuario['area'] = df_usuario['area_manual'].apply(normalizar_area)
            else: df_usuario['area'] = "Geral"
        
        grupo = df_usuario.groupby('area').agg({'acertos': 'sum', 'total': 'sum'})
        for area in areas:
            if area in grupo.index:
                ac, tt = grupo.loc[area, 'acertos'], grupo.loc[area, 'total']
                stats_user[area] = (ac / tt * 100) if tt > 0 else 0

    # Dados da Comunidade (Simulados para Demo)
    stats_comunidade = {"Cirurgia": 65, "Clínica Médica": 62, "Ginecologia e Obstetrícia": 70, "Pediatria": 72, "Preventiva": 75}

    for area in areas:
        dados.append({"Area": area, "Tipo": "Você", "Performance": stats_user[area]})
        dados.append({"Area": area, "Tipo": "Comunidade", "Performance": stats_comunidade[area]})
    
    return pd.DataFrame(dados)

# --- 9. AUTH ---
def verificar_login(u, p):
    client = get_supabase()
    if client:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data and bcrypt.checkpw(p.encode(), res.data[0]['password_hash'].encode()): return True, res.data[0]['nome']
    else:
        _ensure_local_db()
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (u,)).fetchone()
            if row and bcrypt.checkpw(p.encode(), row[0].encode()): return True, row[1]
    return False, "Credenciais inválidas"

def criar_usuario(u, p, n):
    client = get_supabase()
    try:
        pw = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        if client: client.table("usuarios").insert({"username": u, "nome": n, "password_hash": pw}).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn: conn.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (u, n, pw))
        return True, "OK"
    except Exception as e: return False, str(e)

# Aliases
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_db(): return True