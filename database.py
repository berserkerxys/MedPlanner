import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client

# --- CONFIGURAÇÃO DE LIGAÇÃO (SUPABASE) ---

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa a ligação única com o Supabase usando os Secrets do Streamlit."""
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception as e:
        st.error(f"Erro de ligação Supabase: {e}")
        return None

# ==========================================
# 📚 MÓDULO 1: VIDEOTECA NATIVA (MEMÓRIA PERMANENTE)
# ==========================================

@st.cache_data(ttl=None)
def listar_conteudo_videoteca():
    """Lê a biblioteca local. Cache permanente para evitar lentidão no site."""
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return pd.DataFrame()
        # Estrutura esperada: [grande_area, assunto, tipo, subtipo, titulo, link, id]
        return pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=None)
def get_mapa_areas():
    """Dicionário Assunto -> Área em memória para detecção instantânea na Sidebar."""
    df = listar_conteudo_videoteca()
    if df.empty: return {}
    return df.set_index(df['assunto'].str.strip().str.lower())['grande_area'].to_dict()

def get_area_por_assunto(nome_assunto):
    """Busca a Grande Área no mapa em cache (O(1) de performance)."""
    mapa = get_mapa_areas()
    return mapa.get(str(nome_assunto).strip().lower(), "Geral")

@st.cache_data(ttl=None)
def get_lista_assuntos_nativa():
    """Retorna a lista de temas para os menus do App."""
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral - Livre", "Simulado - Geral"]
    return sorted(df['assunto'].unique().tolist())

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA E AUTENTICAÇÃO
# ==========================================

def verificar_login(u, p):
    """Autentica o utilizador e inicializa o nonce de actualização de dados."""
    client = get_supabase()
    if not client: return False, "Sistema Offline"
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            user = res.data[0]
            stored = user['password_hash']
            if isinstance(stored, str): stored = stored.encode('utf-8')
            if bcrypt.checkpw(p.encode('utf-8'), stored):
                # Inicializa o nonce para o cache dinâmico do utilizador
                if 'data_nonce' not in st.session_state: 
                    st.session_state.data_nonce = 0
                return True, user['nome']
        return False, "Dados de acesso incorrectos"
    except Exception:
        return False, "Erro no servidor de autenticação"

def criar_usuario(u, p, n):
    """Cria novo utilizador e perfil de gamificação."""
    client = get_supabase()
    if not client: return False, "Sem ligação"
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": hashed}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "nivel": 1, "xp": 0, "titulo": "Calouro"}).execute()
        return True, "Conta criada com sucesso!"
    except Exception:
        return False, "O nome de utilizador já existe"

# ==========================================
# 📊 MÓDULO 3: ANALYTICS E GAMIFICAÇÃO (CACHE DINÂMICO)
# ==========================================

def trigger_refresh():
    """Incrementa o nonce para forçar a actualização da Agenda/Dashboard sem travar o site."""
    if 'data_nonce' in st.session_state:
        st.session_state.data_nonce += 1

@st.cache_data(ttl=300)
def get_progresso_hoje(u, nonce):
    """Calcula o volume de questões feitas hoje (Cacheado pelo Nonce)."""
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data])
    except: return 0

@st.cache_data(ttl=300)
def get_status_gamer(u, nonce):
    """Recupera XP, Nível e calcula Missões Diárias."""
    client = get_supabase()
    if not client: return None, pd.DataFrame()
    
    try:
        # 1. Recuperar Perfil Principal
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        
        d = res.data[0]
        xp = d['xp']
        nivel = 1 + (xp // 1000)
        
        status = {
            'nivel': nivel, 
            'xp_atual': xp % 1000, 
            'xp_total': xp, 
            'titulo': d['titulo'], 
            'xp_proximo': 1000
        }

        # 2. Calcular Missões Diárias com base no Histórico
        hoje = datetime.now().strftime("%Y-%m-%d")
        hist_hoje = client.table("historico").select("total, acertos").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        
        q_hoje = sum([int(i['total']) for i in hist_hoje.data]) if hist_hoje.data else 0
        a_hoje = sum([int(i['acertos']) for i in hist_hoje.data]) if hist_hoje.data else 0
        
        # Estrutura de missões
        missoes_data = [
            {"missao": "🎯 Meta de Questões", "progresso": min(q_hoje, 50), "meta": 50, "unid": "q"},
            {"missao": "🔥 Foco em Acertos", "progresso": min(a_hoje, 30), "meta": 30, "unid": "ac"},
            {"missao": "🎓 XP Diário (Questões x 2)", "progresso": min(q_hoje * 2, 100), "meta": 100, "unid": "xp"}
        ]
        
        df_missoes = pd.DataFrame(missoes_data)
        return status, df_missoes

    except Exception:
        return None, pd.DataFrame()

@st.cache_data(ttl=300)
def get_dados_graficos(u, nonce):
    """Histórico de desempenho para os gráficos Plotly."""
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        mapa = get_mapa_areas()
        df['area'] = df['assunto_nome'].str.strip().str.lower().map(mapa).fillna(df.get('area_manual', 'Geral'))
        df['percentual'] = (df['acertos'].astype(float) / df['total'].astype(float) * 100).round(1)
        df['data'] = df['data_estudo']
        return df
    except: return pd.DataFrame()

# ==========================================
# 📝 MÓDULO 4: REGISTOS E LÓGICA SRS (AGENDA)
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None, area_forçada=None, agendar_srs=True):
    """Regista estudo e gere o agendamento inicial (7 dias)."""
    client = get_supabase()
    if not client: return "Erro"
    
    dt_obj = data_personalizada if data_personalizada else datetime.now().date()
    dt_str = dt_obj.strftime("%Y-%m-%d")
    area = area_forçada if area_forçada else get_area_por_assunto(assunto)

    try:
        # 1. Salvar Histórico
        client.table("historico").insert({
            "usuario_id": u, "assunto_nome": assunto, "area_manual": area,
            "data_estudo": dt_str, "acertos": int(acertos), "total": int(total)
        }).execute()
        
        # 2. Agendar Revisão (Somente para novos estudos, não para conclusões de ciclo)
        if agendar_srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt_obj + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": u, "assunto_nome": assunto, "grande_area": area,
                "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
            }).execute()

        # 3. Gamificação (XP)
        update_xp(u, int(total * 2))
        trigger_refresh() # Actualiza dashboard e agenda
        return "✅ Registado!"
    except Exception as e: return f"Erro: {e}"

def registrar_simulado(u, dados, data_personalizada=None):
    """Regista o simulado garantindo que o TOTAL de questões seja salvo."""
    client = get_supabase()
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    tq = 0
    try:
        for area, v in dados.items():
            if v['total'] > 0:
                tq += v['total']
                client.table("historico").insert({
                    "usuario_id": u, "assunto_nome": f"Simulado - {area}", 
                    "area_manual": area, "data_estudo": dt_str, 
                    "acertos": int(v['acertos']), "total": int(v['total'])
                }).execute()
        update_xp(u, int(tq * 2.5))
        trigger_refresh()
        return f"✅ Simulado salvo ({tq}q)!"
    except Exception as e: return f"Erro: {e}"

def update_xp(u, qtd):
    """Actualiza o XP do utilizador directamente no banco."""
    client = get_supabase()
    try:
        res = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res.data:
            nxp = res.data[0]['xp'] + qtd
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
    except: pass

@st.cache_data(ttl=300)
def listar_revisoes_completas(u, nonce):
    """Busca revisões da agenda com cache optimizado pelo Nonce."""
    client = get_supabase()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def concluir_revisao(rid, acertos, total):
    """Finaliza revisão X e cria a revisão Y do ciclo progressivo."""
    client = get_supabase()
    try:
        # Pega dados da revisão actual
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        if not res.data: return "Erro"
        rev = res.data[0]
        
        # 1. Marca como concluído (X sai da lista de pendentes)
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        
        # 2. Salva no histórico SEM criar novo agendamento de 1 semana (loop fix)
        registrar_estudo(
            u=rev['usuario_id'], assunto=rev['assunto_nome'], 
            acertos=acertos, total=total, 
            area_forçada=rev.get('grande_area'), agendar_srs=False
        )
        
        # 3. Lógica SRS: Próximo Passo do Ciclo
        saltos = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        dias, prox_tipo = saltos.get(rev['tipo'], (None, None))
        
        if prox_tipo:
            dt_prox = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'],
                "grande_area": rev.get('grande_area'), "data_agendada": dt_prox, 
                "tipo": prox_tipo, "status": "Pendente"
            }).execute()
            
        trigger_refresh()
        return f"✅ Revisão concluída! Próxima: {prox_tipo if prox_tipo else 'Ciclo Finalizado'}"
    except Exception as e: return f"Erro: {e}"

# ==========================================
# 🛠️ MÓDULO 5: SINCRONIZAÇÃO (TELEGRAM/SYNC)
# ==========================================

_SYNC_CACHE = []

def salvar_conteudo_exato(mid, tit, lnk, tag, tp, sub):
    """Prepara o cache para sincronização do script de Telegram."""
    _SYNC_CACHE.append(["Geral", tag.replace("_", " ").title(), tp, sub, tit, lnk, mid])
    return f"✅ {tit}"

def exportar_videoteca_para_arquivo():
    """Gera fisicamente o ficheiro biblioteca_conteudo.py."""
    if not _SYNC_CACHE: return
    try:
        with open("biblioteca_conteudo.py", "w", encoding="utf-8") as f:
            f.write("# ARQUIVO MESTRE DE CONTEÚDO (AUTO GENERATED)\n")
            f.write(f"VIDEOTECA_GLOBAL = {repr(_SYNC_CACHE)}")
        # Limpa cache estático para recarregar novos vídeos
        listar_conteudo_videoteca.clear()
        get_mapa_areas.clear()
        get_lista_assuntos_nativa.clear()
    except Exception: pass

# --- STUBS DE COMPATIBILIDADE ---
def get_db(): return True
def get_connection(): return None
def sincronizar_videoteca_completa(): return "OK"