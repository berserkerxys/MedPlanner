import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client
import os

# --- CONEXÃO SUPABASE (ESTÁVEL COM CACHE) ---
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa a conexão única com o Supabase usando os secrets do Streamlit Cloud."""
    try:
        if "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        return None
    except Exception as e:
        st.error(f"Erro de conexão Supabase: {e}")
        return None

# ==========================================
# 📚 MÓDULO 1: VIDEOTECA NATIVA (.PY)
# ==========================================

def listar_conteudo_videoteca():
    """Lê a biblioteca do ficheiro biblioteca_conteudo.py instantaneamente."""
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return pd.DataFrame()
        # Colunas: [grande_area, assunto, tipo, subtipo, titulo, link, id]
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
        return df
    except Exception:
        return pd.DataFrame()

def get_area_por_assunto(nome_assunto):
    """Busca a Grande Área no ficheiro nativo para classificar o estudo."""
    df = listar_conteudo_videoteca()
    if df.empty: return "Geral"
    nome_busca = str(nome_assunto).strip().lower()
    match = df[df['assunto'].str.strip().str.lower() == nome_busca]
    if not match.empty:
        return match.iloc[0]['grande_area']
    return "Geral"

def get_lista_assuntos_nativa():
    """Retorna lista única de temas para os menus de seleção no App."""
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral - Livre", "Simulado - Geral"]
    return sorted(df['assunto'].unique().tolist())

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA E LOGIN
# ==========================================

def verificar_login(u, p):
    """Autentica o utilizador comparando o hash da senha no Supabase."""
    client = get_supabase()
    if not client: return False, "Sistema Offline (Erro de Conexão)"
    try:
        res = client.table("usuarios").select("password_hash, nome").eq("username", u).execute()
        if res.data:
            user = res.data[0]
            stored = user['password_hash']
            if isinstance(stored, str): stored = stored.encode('utf-8')
            if bcrypt.checkpw(p.encode('utf-8'), stored):
                return True, user['nome']
        return False, "Utilizador ou senha incorretos"
    except Exception:
        return False, "Erro de comunicação com o servidor de segurança"

def criar_usuario(u, p, n):
    """Regista novo utilizador e inicializa perfil gamificado no Supabase."""
    client = get_supabase()
    if not client: return False, "Sem conexão com o servidor"
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": hashed}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "nivel": 1, "xp": 0, "titulo": "Calouro"}).execute()
        return True, "Conta criada com sucesso!"
    except Exception:
        return False, "Erro: O nome de utilizador já está em uso"

# ==========================================
# 📊 MÓDULO 3: ANALYTICS E GAMIFICAÇÃO
# ==========================================

def get_progresso_hoje(u):
    """Calcula o volume total de questões resolvidas hoje."""
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data])
    except: return 0

def get_status_gamer(u):
    """Recupera nível, título e XP atual para o Dashboard."""
    client = get_supabase()
    if not client: return None, pd.DataFrame()
    try:
        res = client.table("perfil_gamer").select("*").eq("usuario_id", u).execute()
        if not res.data: return None, pd.DataFrame()
        d = res.data[0]
        xp = d['xp']
        nivel = 1 + (xp // 1000)
        return {
            'nivel': nivel, 
            'xp_atual': xp % 1000, 
            'xp_total': xp, 
            'titulo': d['titulo'], 
            'xp_proximo': 1000
        }, pd.DataFrame()
    except: return None, pd.DataFrame()

def get_dados_graficos(u):
    """Busca histórico completo para geração de gráficos Plotly."""
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        
        lib = listar_conteudo_videoteca()
        area_map = lib.set_index('assunto')['grande_area'].to_dict() if not lib.empty else {}
        df['area'] = df['assunto_nome'].map(area_map).fillna(df.get('area_manual', 'Geral'))
        
        df['percentual'] = (df['acertos'].astype(float) / df['total'].astype(float) * 100).round(1)
        df['data'] = df['data_estudo']
        return df
    except: return pd.DataFrame()

# ==========================================
# 📝 MÓDULO 4: REGISTOS E LÓGICA SRS (AGENDA)
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None, area_forçada=None, agendar_srs=True):
    """
    Regista o estudo no histórico.
    agendar_srs=True: Cria a revisão de 7 dias (usado para novas aulas).
    agendar_srs=False: Não cria nova revisão de 7 dias (usado ao concluir uma revisão do ciclo).
    """
    client = get_supabase()
    if not client: return "Erro: Banco offline"
    
    dt_obj = data_personalizada if data_personalizada else datetime.now().date()
    dt_str = dt_obj.strftime("%Y-%m-%d")
    area = area_forçada if area_forçada else get_area_por_assunto(assunto)

    try:
        # 1. Salvar no Histórico
        client.table("historico").insert({
            "usuario_id": u, "assunto_nome": assunto, "area_manual": area,
            "data_estudo": dt_str, "acertos": int(acertos), "total": int(total)
        }).execute()
        
        # 2. Agendar Revisão Inicial de 7 dias (Apenas se for Estudo Novo)
        if agendar_srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt_obj + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": u, "assunto_nome": assunto, "grande_area": area,
                "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
            }).execute()

        # 3. Processa XP
        status, _ = get_status_gamer(u)
        if status:
            nxp = status['xp_total'] + int(total * 2)
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        
        return "✅ Registado com sucesso!"
    except Exception as e: return f"Erro ao salvar: {str(e)}"

def registrar_simulado(u, dados, data_personalizada=None):
    """Regista o total e acertos de um simulado multi-área no Supabase."""
    client = get_supabase()
    if not client: return "Erro"
    
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    total_questoes_simulado = 0
    
    try:
        for area, v in dados.items():
            if v['total'] > 0:
                total_questoes_simulado += v['total']
                client.table("historico").insert({
                    "usuario_id": u, 
                    "assunto_nome": f"Simulado - {area}", 
                    "area_manual": area, 
                    "data_estudo": dt_str, 
                    "acertos": int(v['acertos']), 
                    "total": int(v['total'])
                }).execute()
        
        status, _ = get_status_gamer(u)
        if status:
            nxp = status['xp_total'] + int(total_questoes_simulado * 2.5)
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        
        return f"✅ Simulado guardado! Total: {total_questoes_simulado}q."
    except Exception as e: return f"Erro ao salvar simulado: {str(e)}"

def listar_revisoes_completas(u):
    """Busca todas as revisões do utilizador."""
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def concluir_revisao(rid, acertos, total):
    """
    Finaliza a revisão atual (X) e agenda a próxima do ciclo SRS (Y).
    Garante que a revisão X saia da lista de pendentes.
    """
    client = get_supabase()
    if not client: return "Erro"
    try:
        # 1. Pega os dados da revisão atual
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        if not res.data: return "Erro: Revisão não encontrada"
        rev = res.data[0]
        
        # 2. Marca a revisão atual como 'Concluido'
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        
        # 3. Regista desempenho histórico (agendar_srs=False evita duplicar a revisão de 1 semana)
        registrar_estudo(
            u=rev['usuario_id'], 
            assunto=rev['assunto_nome'], 
            acertos=acertos, 
            total=total, 
            area_forçada=rev.get('grande_area'),
            agendar_srs=False 
        )
        
        # 4. Lógica SRS Progressiva (Cria o PRÓXIMO passo)
        ciclo_srs = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        dias_salto, prox_tipo = ciclo_srs.get(rev['tipo'], (None, None))
        
        if prox_tipo:
            data_prox = (datetime.now() + timedelta(days=dias_salto)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": rev['usuario_id'], 
                "assunto_nome": rev['assunto_nome'],
                "grande_area": rev.get('grande_area'), 
                "data_agendada": data_prox, 
                "tipo": prox_tipo, 
                "status": "Pendente"
            }).execute()
            
        return f"✅ Revisão Concluída! Próxima: {prox_tipo if prox_tipo else 'Ciclo Finalizado'}"
    except Exception as e: return f"Erro no processo SRS: {str(e)}"

# ==========================================
# 🛠️ MÓDULO 5: SINCRONIZAÇÃO (PARA SYNC.PY)
# ==========================================

_SYNC_CACHE = []

def salvar_conteudo_exato(mid, tit, lnk, tag, tp, sub):
    """Cache em memória para o script de Telegram."""
    area = "Geral"
    _SYNC_CACHE.append([area, tag.replace("_", " ").title(), tp, sub, tit, lnk, mid])
    return f"✅ {tit} em cache"

def exportar_videoteca_para_arquivo():
    """Gera o ficheiro biblioteca_conteudo.py."""
    if not _SYNC_CACHE: return
    try:
        with open("biblioteca_conteudo.py", "w", encoding="utf-8") as f:
            f.write("# ARQUIVO MESTRE DE CONTEÚDO (GERADO AUTOMATICAMENTE PELO SYNC.PY)\n")
            f.write(f"VIDEOTECA_GLOBAL = {repr(_SYNC_CACHE)}")
    except Exception as e:
        print(f"Erro ao exportar arquivo: {e}")

# --- COMPATIBILIDADE ---
def get_db(): return True
def get_connection(): return None