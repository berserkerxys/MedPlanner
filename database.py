import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
from supabase import create_client, Client
import os

# --- CONEXÃO SUPABASE (ESTÁVEL COM CACHE DE RECURSO) ---
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa a conexão única com o Supabase."""
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
# 📚 MÓDULO 1: VIDEOTECA NATIVA (OTIMIZADA)
# ==========================================

@st.cache_data(ttl=600)  # Cache de 10 minutos para não ler o arquivo a cada clique
def listar_conteudo_videoteca():
    """Lê a biblioteca do ficheiro biblioteca_conteudo.py com cache."""
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return pd.DataFrame()
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600) # Cache longo para o mapeamento de áreas
def get_mapa_areas():
    """Cria um dicionário de busca rápida Assunto -> Área."""
    df = listar_conteudo_videoteca()
    if df.empty: return {}
    return df.set_index(df['assunto'].str.strip().str.lower())['grande_area'].to_dict()

def get_area_por_assunto(nome_assunto):
    """Busca a Grande Área usando dicionário em cache (ultra rápido)."""
    mapa = get_mapa_areas()
    nome_busca = str(nome_assunto).strip().lower()
    return mapa.get(nome_busca, "Geral")

@st.cache_data(ttl=600)
def get_lista_assuntos_nativa():
    """Retorna lista única de temas em cache."""
    df = listar_conteudo_videoteca()
    if df.empty: return ["Banco Geral - Livre", "Simulado - Geral"]
    return sorted(df['assunto'].unique().tolist())

def pesquisar_global(termo):
    """Pesquisa textual rápida na biblioteca."""
    df = listar_conteudo_videoteca()
    if df.empty: return df
    mask = (
        df['titulo'].str.contains(termo, case=False, na=False) | 
        df['assunto'].str.contains(termo, case=False, na=False)
    )
    return df[mask]

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA E LOGIN
# ==========================================

def verificar_login(u, p):
    """Autentica o utilizador com tratamento de erro robusto."""
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
    except Exception as e:
        return False, f"Erro na autenticação: {str(e)}"

def criar_usuario(u, p, n):
    """Regista novo utilizador e limpa cache de usuários."""
    client = get_supabase()
    if not client: return False, "Sem conexão com o servidor"
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client.table("usuarios").insert({"username": u, "nome": n, "password_hash": hashed}).execute()
        client.table("perfil_gamer").insert({"usuario_id": u, "nivel": 1, "xp": 0, "titulo": "Calouro"}).execute()
        st.cache_data.clear()
        return True, "Conta criada com sucesso!"
    except Exception:
        return False, "Erro: O nome de utilizador já está em uso"

# ==========================================
# 📊 MÓDULO 3: ANALYTICS E GAMIFICAÇÃO
# ==========================================

@st.cache_data(ttl=60) # Cache de 1 minuto para o progresso do dia (leve)
def get_progresso_hoje(u):
    """Calcula volume de questões do dia."""
    client = get_supabase()
    if not client: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        res = client.table("historico").select("total").eq("usuario_id", u).eq("data_estudo", hoje).execute()
        return sum([int(i['total']) for i in res.data])
    except: return 0

@st.cache_data(ttl=300) # Cache de 5 minutos para status gamer
def get_status_gamer(u):
    """Recupera status de gamificação."""
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

@st.cache_data(ttl=300) # Cache de 5 minutos para os dados dos gráficos
def get_dados_graficos(u):
    """Busca histórico para gráficos."""
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("historico").select("*").eq("usuario_id", u).execute()
        df = pd.DataFrame(res.data)
        if df.empty: return df
        
        mapa_areas = get_mapa_areas()
        df['area'] = df['assunto_nome'].str.strip().str.lower().map(mapa_areas).fillna(df.get('area_manual', 'Geral'))
        
        df['total'] = df['total'].astype(float)
        df['acertos'] = df['acertos'].astype(float)
        df['percentual'] = (df['acertos'] / df['total'] * 100).round(1)
        df['data'] = df['data_estudo']
        return df
    except: return pd.DataFrame()

# ==========================================
# 📝 MÓDULO 4: REGISTOS E LÓGICA SRS
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None, area_forçada=None, agendar_srs=True):
    """Regista estudo e limpa caches para atualizar UI."""
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
        
        # 2. Agendar Revisão
        if agendar_srs and "Banco" not in assunto and "Simulado" not in assunto:
            dt_rev = (dt_obj + timedelta(days=7)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": u, "assunto_nome": assunto, "grande_area": area,
                "data_agendada": dt_rev, "tipo": "1 Semana", "status": "Pendente"
            }).execute()

        # 3. Processa XP
        res_perfil = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res_perfil.data:
            current_xp = res_perfil.data[0]['xp']
            nxp = current_xp + int(total * 2)
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        
        # Limpar caches de dados para forçar atualização no Dashboard e Agenda
        st.cache_data.clear()
        return "✅ Registado com sucesso!"
    except Exception as e: return f"Erro ao salvar: {str(e)}"

def registrar_simulado(u, dados, data_personalizada=None):
    """Regista simulado e limpa caches."""
    client = get_supabase()
    if not client: return "Erro"
    
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    total_q = 0
    inserts = []
    
    for area, v in dados.items():
        if v['total'] > 0:
            total_q += v['total']
            inserts.append({
                "usuario_id": u, "assunto_nome": f"Simulado - {area}", 
                "area_manual": area, "data_estudo": dt_str, 
                "acertos": int(v['acertos']), "total": int(v['total'])
            })
    
    try:
        if inserts:
            client.table("historico").insert(inserts).execute()
        
        # XP Bónus Simulado
        res_perfil = client.table("perfil_gamer").select("xp").eq("usuario_id", u).execute()
        if res_perfil.data:
            nxp = res_perfil.data[0]['xp'] + int(total_q * 2.5)
            client.table("perfil_gamer").update({"xp": nxp, "nivel": 1 + (nxp // 1000)}).eq("usuario_id", u).execute()
        
        st.cache_data.clear()
        return f"✅ Simulado guardado! ({total_q}q)"
    except Exception as e: return f"Erro: {str(e)}"

@st.cache_data(ttl=300) # Cache de 5 minutos para a lista da agenda
def listar_revisoes_completas(u):
    """Busca revisões com cache para performance na agenda."""
    client = get_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("revisoes").select("*").eq("usuario_id", u).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def concluir_revisao(rid, acertos, total):
    """Conclui revisão, gera o próximo passo SRS e limpa caches."""
    client = get_supabase()
    if not client: return "Erro"
    try:
        res = client.table("revisoes").select("*").eq("id", rid).execute()
        if not res.data: return "Erro: Revisão não encontrada"
        rev = res.data[0]
        
        client.table("revisoes").update({"status": "Concluido"}).eq("id", rid).execute()
        
        registrar_estudo(
            u=rev['usuario_id'], assunto=rev['assunto_nome'], 
            acertos=acertos, total=total, 
            area_forçada=rev.get('grande_area'), agendar_srs=False 
        )
        
        ciclo_srs = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses")}
        dias_salto, prox_tipo = ciclo_srs.get(rev['tipo'], (None, None))
        
        if prox_tipo:
            data_prox = (datetime.now() + timedelta(days=dias_salto)).strftime("%Y-%m-%d")
            client.table("revisoes").insert({
                "usuario_id": rev['usuario_id'], "assunto_nome": rev['assunto_nome'],
                "grande_area": rev.get('grande_area'), "data_agendada": data_prox, 
                "tipo": prox_tipo, "status": "Pendente"
            }).execute()
            
        st.cache_data.clear()
        return f"✅ Revisão Concluída! Próxima: {prox_tipo if prox_tipo else 'Fim'}"
    except Exception as e: return f"Erro: {str(e)}"

# ==========================================
# 🛠️ MÓDULO 5: SINCRONIZAÇÃO (PARA SYNC.PY)
# ==========================================

_SYNC_CACHE = []

def salvar_conteudo_exato(mid, tit, lnk, tag, tp, sub):
    """Cache em memória para sincronização."""
    area = "Geral"
    _SYNC_CACHE.append([area, tag.replace("_", " ").title(), tp, sub, tit, lnk, mid])
    return f"✅ {tit} em cache"

def exportar_videoteca_para_arquivo():
    """Gera o ficheiro biblioteca_conteudo.py e limpa cache de vídeo."""
    if not _SYNC_CACHE: return
    try:
        with open("biblioteca_conteudo.py", "w", encoding="utf-8") as f:
            f.write("# ARQUIVO MESTRE DE CONTEÚDO (GERADO AUTOMATICAMENTE PELO SYNC.PY)\n")
            f.write(f"VIDEOTECA_GLOBAL = {repr(_SYNC_CACHE)}")
        st.cache_data.clear() 
    except Exception as e:
        print(f"Erro ao exportar arquivo: {e}")

# --- COMPATIBILIDADE ---
def get_db(): return True
def get_connection(): return None