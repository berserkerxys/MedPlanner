import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import os

# --- CONFIGURAÇÃO DA CONEXÃO FIREBASE (PARA DADOS DO USUÁRIO) ---
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            key_dict = dict(st.secrets["firebase"])
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        elif os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Erro Firebase Init: {e}")

def get_db():
    try:
        return firestore.client()
    except:
        return None

def get_connection():
    return None

# ==========================================
# 📚 MÓDULO VIDEOTECA NATIVA (LENDO DO ARQUIVO)
# ==========================================

def listar_conteudo_videoteca():
    """
    Lê a VIDEOTECA_GLOBAL diretamente do arquivo biblioteca_conteudo.py.
    Isso torna a exibição instantânea e independente do banco de dados.
    """
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL:
            return pd.DataFrame()

        # Converte a lista de listas em DataFrame
        # Estrutura no arquivo: [area, assunto, tipo, subtipo, titulo, link, msg_id]
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=[
            'grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id'
        ])
        
        # Garante que o 'id' (message_id) seja tratado como string ou ID único
        df['message_id'] = df['id']
        return df
    except ImportError:
        st.error("Erro: Ficheiro 'biblioteca_conteudo.py' não encontrado.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar biblioteca nativa: {e}")
        return pd.DataFrame()

def pesquisar_global(termo):
    """Pesquisa no DataFrame gerado a partir do arquivo nativo"""
    df = listar_conteudo_videoteca()
    if df.empty: return df
    
    # Filtro simples em múltiplas colunas
    mask = (
        df['titulo'].str.contains(termo, case=False, na=False) | 
        df['assunto'].str.contains(termo, case=False, na=False) |
        df['grande_area'].str.contains(termo, case=False, na=False)
    )
    return df[mask]

# ==========================================
# 🔐 SEGURANÇA & PERFIL (FIREBASE)
# ==========================================

def verificar_login(u, p):
    db = get_db()
    if not db: return False, "Sem Conexão"
    users = list(db.collection('usuarios').where('username', '==', u).stream())
    for doc in users:
        d = doc.to_dict()
        if bcrypt.checkpw(p.encode('utf-8'), d['password_hash'].encode('utf-8')):
            return True, d['nome']
    return False, None

def criar_usuario(u, p, n):
    db = get_db()
    if list(db.collection('usuarios').where('username', '==', u).stream()):
        return False, "Utilizador já existe."
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.collection('usuarios').document(u).set({'username': u, 'nome': n, 'password_hash': hashed})
    db.collection('perfil_gamer').document(u).set({'usuario_id': u, 'nivel': 1, 'xp': 0, 'titulo': 'Calouro'})
    return True, "Criado com sucesso!"

# ==========================================
# 📊 PROGRESSO E HISTÓRICO (FIREBASE)
# ==========================================

def get_dados_graficos(u):
    db = get_db()
    # Puxa histórico privado
    hist_ref = db.collection('historico').where('usuario_id', '==', u).stream()
    hist_data = [d.to_dict() for d in hist_ref]
    if not hist_data: return pd.DataFrame()
    
    # Para o gráfico, precisamos do nome da área. Como a videoteca é nativa,
    # vamos usar uma lógica simplificada ou salvar a área direto no histórico.
    # Aqui, para garantir compatibilidade, pegamos os assuntos que estão na nuvem
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    
    clean = []
    for h in hist_data:
        aid = h.get('assunto_id')
        a_info = assuntos.get(str(aid), {'nome': 'Outros', 'grande_area': 'Outros'})
        clean.append({
            'data': h.get('data_estudo'),
            'acertos': h.get('acertos', 0), 'total': h.get('total', 0),
            'percentual': h.get('percentual', (h.get('acertos', 0) / h.get('total', 1) * 100)),
            'area': a_info['grande_area']
        })
    return pd.DataFrame(clean)

def get_progresso_hoje(u):
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

def get_status_gamer(u):
    db = get_db()
    doc = db.collection('perfil_gamer').document(u).get()
    if not doc.exists: return None, pd.DataFrame()
    d = doc.to_dict()
    xp = d.get('xp', 0)
    nivel = 1 + (xp // 1000)
    p = {'nivel': nivel, 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': 'Estrategista', 'xp_proximo': 1000}
    return p, pd.DataFrame()

# ==========================================
# 📝 REGISTROS (VINCULANDO TEMAS À NUVEM)
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d")
    
    # Busca ou cria o assunto na nuvem para manter o histórico agrupado
    docs = list(db.collection('assuntos').where('nome', '==', assunto).limit(1).stream())
    if docs:
        aid = docs[0].id
    else:
        # Se veio da videoteca nativa e não está no banco, cria agora
        # Tentamos descobrir a área pela videoteca nativa
        lib = listar_conteudo_videoteca()
        area = "Geral"
        if not lib.empty and assunto in lib['assunto'].values:
            area = lib[lib['assunto'] == assunto]['grande_area'].iloc[0]
            
        new_ref = db.collection('assuntos').add({'nome': assunto, 'grande_area': area})
        aid = new_ref[1].id

    db.collection('historico').add({
        'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt, 
        'acertos': acertos, 'total': total, 'percentual': (acertos/total*100)
    })
    
    # Adiciona XP
    ref_p = db.collection('perfil_gamer').document(u)
    p_doc = ref_p.get()
    if p_doc.exists: ref_p.update({'xp': p_doc.to_dict().get('xp', 0) + (total * 2)})
    
    return "✅ Registado com Sucesso!"

# ==========================================
# ⚙️ FUNÇÕES DE MANUTENÇÃO (OBRIGATÓRIAS)
# ==========================================

def inicializar_db():
    """Não precisa mais de Seed para vídeos, apenas garante temas base se desejar"""
    pass

def exportar_videoteca_para_arquivo():
    """Esta função agora é feita pelo sync.py do Telegram, mantemos o stub aqui"""
    pass

def excluir_conteudo(id):
    """
    Nota: Como a biblioteca é nativa (arquivo .py), você deve excluir no 
    Telegram e rodar o sync.py ou editar o arquivo .py manualmente.
    Excluir aqui não afetará o arquivo estático.
    """
    st.warning("Para excluir, remova do grupo Telegram e rode o sync.py.")

def sincronizar_videoteca_completa():
    return "Biblioteca Nativa Ativa! Use o sync.py localmente para atualizar o arquivo."

def concluir_revisao(rid, ac, tot):
    get_db().collection('revisoes').document(rid).update({'status': 'Concluido'})
    return "✅ OK!"

def listar_revisoes_completas(u):
    db = get_db()
    docs = db.collection('revisoes').where('usuario_id', '==', u).stream()
    # Cache de assuntos da nuvem
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    data = []
    for doc in docs:
        d = doc.to_dict()
        a = assuntos.get(d['assunto_id'], {'nome': '?', 'grande_area': '?'})
        data.append({'id': doc.id, 'assunto': a['nome'], 'grande_area': a['grande_area'], **d})
    return pd.DataFrame(data)