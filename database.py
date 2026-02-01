import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import os

# --- CONFIGURAÇÃO FIREBASE (PARA DADOS DINÂMICOS DO UTILIZADOR) ---
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            # Configuração para o Streamlit Cloud via Secrets
            key_dict = dict(st.secrets["firebase"])
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        elif os.path.exists("firebase_key.json"):
            # Configuração para desenvolvimento local
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Erro ao inicializar Firebase: {e}")

def get_db():
    """Retorna o cliente Firestore."""
    try:
        return firestore.client()
    except:
        return None

# --- MÓDULO 1: VIDEOTECA NATIVA (LITURA DE FICHEIRO LOCAL) ---

def listar_conteudo_videoteca():
    """Lê a biblioteca estática diretamente do ficheiro biblioteca_conteudo.py."""
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL:
            return pd.DataFrame()
        
        # Estrutura esperada: [grande_area, assunto, tipo, subtipo, titulo, link, id]
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
        return df
    except ImportError:
        st.error("Erro: O ficheiro 'biblioteca_conteudo.py' não foi encontrado no repositório.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar a biblioteca nativa: {e}")
        return pd.DataFrame()

def get_lista_assuntos_nativa():
    """Gera uma lista única de temas baseada no catálogo de vídeos."""
    df = listar_conteudo_videoteca()
    if df.empty:
        return ["Banco Geral - Livre", "Simulado - Geral"]
    
    # Adiciona opções padrão e remove duplicados da biblioteca
    assuntos = sorted(df['assunto'].unique().tolist())
    if "Banco Geral - Livre" not in assuntos:
        assuntos.insert(0, "Banco Geral - Livre")
    return assuntos

def pesquisar_global(termo):
    """Realiza pesquisa textual na biblioteca nativa."""
    df = listar_conteudo_videoteca()
    if df.empty:
        return df
    mask = (
        df['titulo'].str.contains(termo, case=False, na=False) | 
        df['assunto'].str.contains(termo, case=False, na=False)
    )
    return df[mask]

# --- MÓDULO 2: SEGURANÇA E AUTENTICAÇÃO (FIREBASE) ---

def verificar_login(u, p):
    """Verifica credenciais no Firestore."""
    db = get_db()
    if not db: return False, "Erro de Conexão"
    
    users = list(db.collection('usuarios').where('username', '==', u).stream())
    for doc in users:
        d = doc.to_dict()
        stored_hash = d['password_hash']
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
            
        if bcrypt.checkpw(p.encode('utf-8'), stored_hash):
            return True, d['nome']
    return False, None

def criar_usuario(u, p, n):
    """Cria um novo utilizador e perfil no Firestore."""
    db = get_db()
    if not db: return False, "Erro de Conexão"
    
    # Verifica se já existe
    if list(db.collection('usuarios').where('username', '==', u).stream()):
        return False, "O nome de utilizador já existe."
    
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    batch = db.batch()
    # Dados de login
    batch.set(db.collection('usuarios').document(u), {
        'username': u, 'nome': n, 'password_hash': hashed
    })
    # Perfil gamificado
    batch.set(db.collection('perfil_gamer').document(u), {
        'usuario_id': u, 'nivel': 1, 'xp': 0, 'titulo': 'Calouro'
    })
    
    batch.commit()
    return True, "Utilizador criado com sucesso!"

# --- MÓDULO 3: PROGRESSO E GAMIFICAÇÃO (FIREBASE) ---

def get_progresso_hoje(u):
    """Calcula o total de questões resolvidas pelo utilizador no dia atual."""
    db = get_db()
    if not db: return 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

def get_status_gamer(u):
    """Recupera o nível, XP e títulos do utilizador."""
    db = get_db()
    if not db: return None, pd.DataFrame()
    
    doc = db.collection('perfil_gamer').document(u).get()
    if not doc.exists: return None, pd.DataFrame()
    
    d = doc.to_dict()
    xp = d.get('xp', 0)
    nivel = 1 + (xp // 1000)
    
    # Títulos baseados em nível
    titulos = [(10, "Estudante"), (30, "Interno"), (60, "Residente"), (100, "Especialista")]
    titulo = next((t for n, t in titulos if nivel <= n), "Mestre")
    
    status = {
        'nivel': nivel,
        'xp_atual': xp % 1000,
        'xp_total': xp,
        'titulo': titulo,
        'xp_proximo': 1000
    }
    return status, pd.DataFrame() # Espaço reservado para futuras missões

def get_dados_graficos(u):
    """Recupera o histórico do Firebase para alimentar os gráficos do Dashboard."""
    db = get_db()
    if not db: return pd.DataFrame()
    
    hist_ref = db.collection('historico').where('usuario_id', '==', u).stream()
    hist_data = [d.to_dict() for d in hist_ref]
    if not hist_data: return pd.DataFrame()
    
    # Mapeamento de áreas vindo da biblioteca nativa para garantir consistência
    lib = listar_conteudo_videoteca()
    area_map = lib.set_index('assunto')['grande_area'].to_dict() if not lib.empty else {}

    clean = []
    for h in hist_data:
        assunto = h.get('assunto_nome', 'Outros')
        acertos = h.get('acertos', 0)
        total = h.get('total', 1)
        clean.append({
            'data': h.get('data_estudo'),
            'acertos': acertos,
            'total': total,
            'percentual': (acertos / total * 100),
            'area': area_map.get(assunto, h.get('area_manual', 'Outros'))
        })
    return pd.DataFrame(clean)

# --- MÓDULO 4: REGISTOS DE ATIVIDADE (FIREBASE) ---

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    """Regista uma sessão de estudo de um tema específico."""
    db = get_db()
    if not db: return "Erro: Sem conexão."
    
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    
    db.collection('historico').add({
        'usuario_id': u,
        'assunto_nome': assunto,
        'data_estudo': dt_str,
        'acertos': acertos,
        'total': total
    })
    
    # Ganho de XP (2 pontos por questão)
    ref_p = db.collection('perfil_gamer').document(u)
    p_doc = ref_p.get()
    if p_doc.exists:
        ref_p.update({'xp': p_doc.to_dict().get('xp', 0) + (total * 2)})
    
    return "✅ Estudo registado na nuvem!"

def registrar_simulado(u, dados, data_personalizada=None):
    """Regista o desempenho de várias áreas de um simulado de uma só vez."""
    db = get_db()
    if not db: return "Erro: Sem conexão."
    
    dt_str = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    batch = db.batch()
    total_questoes = 0
    
    for area, v in dados.items():
        if v['total'] > 0:
            total_questoes += v['total']
            ref = db.collection('historico').document()
            batch.set(ref, {
                'usuario_id': u,
                'assunto_nome': f"Simulado - {area}",
                'area_manual': area,
                'data_estudo': dt_str,
                'acertos': v['acertos'],
                'total': v['total']
            })
    
    batch.commit()
    
    # XP de Simulado (2.5 pontos por questão)
    ref_p = db.collection('perfil_gamer').document(u)
    p_doc = ref_p.get()
    if p_doc.exists:
        ref_p.update({'xp': p_doc.to_dict().get('xp', 0) + int(total_questoes * 2.5)})
        
    return "✅ Simulado completo guardado!"

# --- STUBS E COMPATIBILIDADE (PARA EVITAR ERROS DE IMPORTAÇÃO) ---

def sincronizar_videoteca_completa():
    return "O sistema está em modo nativo (.py). Não é necessário sincronizar a nuvem para vídeos."

def concluir_revisao(rid, ac, tot):
    return "✅ OK"

def listar_revisoes_completas(u):
    return pd.DataFrame()

def excluir_conteudo(id):
    pass

def get_connection():
    return None