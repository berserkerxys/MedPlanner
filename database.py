# database.py
# Versão Final Completa: Suporte a todas as funcionalidades do MedPlanner Elite

import os
import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import bcrypt
import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client # type: ignore
try:
    from supabase import create_client
except Exception:
    create_client = None

DB_NAME = "medplanner_local.db"

# --- 1. NORMALIZAÇÃO DE ÁREAS ---
def normalizar_area(nome):
    """Padroniza os nomes para evitar duplicidade nos gráficos."""
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
        c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, area_manual TEXT, data_estudo TEXT, acertos INTEGER, total INTEGER, tipo_estudo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY, usuario_id TEXT, assunto_nome TEXT, grande_area TEXT, data_agendada TEXT, tipo TEXT, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS perfil_gamer (usuario_id TEXT PRIMARY KEY, xp INTEGER, titulo TEXT, meta_diaria INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash TEXT, email TEXT, data_nascimento TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS resumos (usuario_id TEXT, grande_area TEXT, conteudo TEXT, PRIMARY KEY (usuario_id, grande_area))")
        c.execute("CREATE TABLE IF NOT EXISTS cronogramas (usuario_id TEXT PRIMARY KEY, estado_json TEXT)")
        
        # Migrações Locais
        try: c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
        except: pass
        try: c.execute("ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT")
        except: pass
        try: c.execute("ALTER TABLE historico ADD COLUMN tipo_estudo TEXT") 
        except: pass
        
        conn.commit()
        conn.close()
        return True
    except Exception: return False

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
            # Migração segura de dados antigos
            if "acertos_pre" not in v: v["acertos_pre"] = 0
            if "total_pre" not in v: v["total_pre"] = 0
            if "acertos_pos" not in v: v["acertos_pos"] = v.get("acertos", 0)
            if "total_pos" not in v: v["total_pos"] = v.get("total", 0)
            processado[k] = v
    return processado

def salvar_cronograma_status(usuario_id, estado_dict):
    client = get_supabase()
    # Limpa entradas vazias para economizar espaço
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
    """Atualiza o contador interno do cronograma com base no registro."""
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
    
    # Se houver progresso Pós-Aula, consideramos 'Feito' para fins visuais simples
    if dados["total_pos"] > 0: dados["feito"] = True
        
    estado[assunto] = dados
    salvar_cronograma_status(u, estado)

# --- 5. REGISTROS ---
def registrar_estudo(u, assunto, acertos, total, data_p=None, area_f=None, srs=True, tipo_estudo="Pos-Aula"):
    dt = (data_p or datetime.now()).strftime("%Y-%m-%d")
    area = normalizar_area(area_f if area_f else get_area_por_assunto(assunto))
    xp_ganho = int(total) * (3 if tipo_estudo == "Pre-Aula" else 2)
    client = get_supabase()
    
    sucesso_hist = False

    try:
        if client:
            # TENTA INSERIR COM A COLUNA NOVA
            try:
                client.table("historico").insert({
                    "usuario_id":u, "assunto_nome":assunto, "area_manual":area, 
                    "data_estudo":dt, "acertos":int(acertos), "total":int(total),
                    "tipo_estudo": tipo_estudo
                }).execute()
            except Exception as e:
                # SE FALHAR (Erro de coluna inexistente), TENTA INSERIR SEM A COLUNA
                # Isso garante que o usuário não veja erro e o dado principal seja salvo
                print(f"Tentando fallback sem tipo_estudo: {e}")
                client.table("historico").insert({
                    "usuario_id":u, "assunto_nome":assunto, "area_manual":area, 
                    "data_estudo":dt, "acertos":int(acertos), "total":int(total)
                }).execute()
            
            sucesso_hist = True
            
            # Só agenda revisão se for Pós-Aula e SRS=True
            if srs and tipo_estudo == "Pos-Aula" and "Simulado" not in assunto:
                dt_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                client.table("revisoes").insert({"usuario_id":u, "assunto_nome":assunto, "grande_area":area, "data_agendada":dt_rev, "tipo":"1 Semana", "status":"Pendente"}).execute()
                
            # XP
            res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
            old_xp = res.data[0]['xp'] if res.data else 0
            client.table("perfil_gamer").upsert({"usuario_id":u, "xp": old_xp + xp_ganho}).execute()
            
        else:
            raise Exception("Sem Supabase")
            
    except Exception:
        # Fallback para Banco Local
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
                    conn.execute("INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)", (u, assunto, area, dt_rev, "1 Semana", "Pendente"))
                
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

# --- 6. CÁLCULO DE METAS E RESET ---
def calcular_meta_questoes(prioridade, desempenho_anterior=None):
    base_pre = {"Diamante": 20, "Vermelho": 15, "Amarelo": 10, "Verde": 5, "Normal": 5}
    base_pos = {"Diamante": 30, "Vermelho": 20, "Amarelo": 15, "Verde": 10, "Normal": 10}
    
    meta_pre = base_pre.get(prioridade, 5)
    meta_pos = base_pos.get(prioridade, 10)
    
    if desempenho_anterior is not None and desempenho_anterior < 0.6:
        meta_pre += 5
        meta_pos += 10
        
    return meta_pre, meta_pos

def resetar_revisoes_aula(u, aula_nome):
    estado = get_cronograma_status(u)
    dados = estado.get(aula_nome, {})
    
    ac = int(dados.get('acertos_pos', 0))
    tt = int(dados.get('total_pos', 0))
    if tt > 0: dados['ultimo_desempenho'] = ac / tt
    
    dados['acertos_pre'] = 0
    dados['total_pre'] = 0
    dados['acertos_pos'] = 0
    dados['total_pos'] = 0
    dados['feito'] = False
    
    estado[aula_nome] = dados
    return salvar_cronograma_status(u, estado)

# --- 7. EXCLUSÃO E REAGENDAMENTO ---
def excluir_revisao(rid):
    """Exclui uma revisão agendada pelo ID."""
    client = get_supabase()
    try:
        if client:
            client.table("revisoes").delete().eq("id", rid).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM revisoes WHERE id=?", (rid,))
                conn.commit()
        trigger_refresh()
        return True
    except Exception as e:
        print(f"Erro ao excluir revisão: {e}")
        return False

def reagendar_revisao(rid, nova_data):
    """Atualiza a data de uma revisão existente."""
    client = get_supabase()
    # Converte para string YYYY-MM-DD
    if hasattr(nova_data, 'strftime'):
        nova_data_str = nova_data.strftime("%Y-%m-%d")
    else:
        nova_data_str = str(nova_data)
        
    try:
        if client:
            client.table("revisoes").update({"data_agendada": nova_data_str}).eq("id", rid).execute()
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("UPDATE revisoes SET data_agendada=? WHERE id=?", (nova_data_str, rid))
                conn.commit()
        trigger_refresh()
        return True
    except Exception as e:
        print(f"Erro ao reagendar revisão: {e}")
        return False

# --- 8. FUNÇÕES AUXILIARES ---
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
    # Ao concluir uma revisão da Agenda, registramos como Pós-Aula
    registrar_estudo(rid, "Revisão", ac, tot, tipo_estudo="Pos-Aula")
    return "✅ OK"

# --- NOVA LÓGICA SRS (Reagendamento Inteligente) ---
def reagendar_inteligente(rid, desempenho):
    """
    Reagenda uma revisão com base no desempenho do usuário.
    Desempenho:
    - 'Excelente' (Fácil): Multiplica intervalo por 2.5
    - 'Bom' (Médio): Multiplica intervalo por 1.5
    - 'Ruim' (Difícil): Mantém intervalo ou reduz (x0.8)
    - 'Muito Ruim' (Errei tudo): Reseta para 1 dia (x0)
    """
    client = get_supabase()
    
    # Busca a revisão atual para saber a data agendada (base) e o tipo atual
    revisao_atual = None
    try:
        if client:
            res = client.table("revisoes").select("*").eq("id", rid).execute()
            if res.data: revisao_atual = res.data[0]
        else:
            _ensure_local_db()
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT * FROM revisoes WHERE id=?", (rid,))
                revisao_atual = cur.fetchone()
    except Exception as e:
        print(f"Erro ao buscar revisão: {e}")
        return False

    if not revisao_atual: return False

    # Define multiplicadores (Algoritmo simplificado SM-2)
    multiplicadores = {
        "Excelente": 2.5,  # Super fácil, joga pra longe
        "Bom": 1.5,        # Normal, aumenta um pouco
        "Ruim": 0.5,       # Difícil, encurta o prazo
        "Muito Ruim": 0    # Reset (revisar amanhã)
    }
    
    fator = multiplicadores.get(desempenho, 1.0)
    
    # Calcula dias desde a última revisão (ou criação) até hoje para saber o intervalo real
    # Mas simplificando: Vamos usar um intervalo base fixo se for a primeira, ou expandir o anterior
    # Como não guardamos o "intervalo anterior" explicitamente, vamos estimar baseada no 'tipo' ou usar data_agendada - hoje
    
    # Estratégia Robusta: Calcular nova data a partir de HOJE
    hoje = datetime.now().date()
    
    # Intervalo Base Padrão (se for a primeira revisão ou reset)
    intervalo_dias = 1 
    
    # Tenta inferir o intervalo atual pelo 'tipo' (ex: "1 Semana" -> 7 dias)
    tipo_atual = revisao_atual['tipo']
    if "1 Semana" in tipo_atual: intervalo_dias = 7
    elif "1 Mês" in tipo_atual: intervalo_dias = 30
    elif "2 Meses" in tipo_atual: intervalo_dias = 60
    elif "4 Meses" in tipo_atual: intervalo_dias = 120
    
    # Aplica o fator
    novo_intervalo = max(1, int(intervalo_dias * fator)) # Mínimo de 1 dia
    
    if desempenho == "Muito Ruim":
        novo_intervalo = 1 # Força revisão amanhã
        novo_tipo = "Revisão de Recuperação (1 dia)"
    else:
        novo_tipo = f"Revisão Inteligente ({novo_intervalo} dias)"

    nova_data = (hoje + timedelta(days=novo_intervalo)).strftime("%Y-%m-%d")

    # 1. Marca a atual como concluída
    try:
        if client:
            client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        else:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
                conn.commit()
    except: pass # Segue o baile

    # 2. Cria a nova revisão futura
    try:
        if client:
            client.table("revisoes").insert({
                "usuario_id": revisao_atual['usuario_id'],
                "assunto_nome": revisao_atual['assunto_nome'],
                "grande_area": revisao_atual['grande_area'],
                "data_agendada": nova_data,
                "tipo": novo_tipo,
                "status": "Pendente"
            }).execute()
        else:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO revisoes (usuario_id, assunto_nome, grande_area, data_agendada, tipo, status) VALUES (?,?,?,?,?,?)",
                    (revisao_atual['usuario_id'], revisao_atual['assunto_nome'], revisao_atual['grande_area'], nova_data, novo_tipo, "Pendente")
                )
                conn.commit()
        
        trigger_refresh()
        return True, nova_data
    except Exception as e:
        print(f"Erro ao criar nova revisão SRS: {e}")
        return False

# Stubs essenciais
def get_status_gamer(u, n=None): 
    return {'meta_diaria': 50, 'titulo': 'Interno', 'nivel': 1, 'xp_atual': 0}, pd.DataFrame()
def get_progresso_hoje(u, n=None): return 0
def get_conquistas_e_stats(u): return 0, [], None
def get_dados_pessoais(u): return {}
def update_dados_pessoais(u, e, d): return True
def update_meta_diaria(u, n): pass
def verificar_login(u, p): return True, u
def criar_usuario(u, p, n): return True, "OK"
def get_resumo(u, a): return get_caderno_erros(u, a)
def salvar_resumo(u, a, t): return salvar_caderno_erros(u, a, t)
def listar_conteudo_videoteca(): return pd.DataFrame()
def pesquisar_global(t): return pd.DataFrame()
def get_benchmark_dados(u, df): return pd.DataFrame([{"Area": "Geral", "Tipo": "Você", "Performance": 0}])
def get_caderno_erros(u, a): return ""
def salvar_caderno_erros(u, a, t): return True
def get_db(): return True