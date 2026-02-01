import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import os

# --- CONFIGURAÇÃO DA CONEXÃO FIREBASE (SINGLETON) ---
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
    """Função de compatibilidade para evitar quebras em imports antigos."""
    return None

# ==========================================
# ⚙️ SINCRONIZAÇÃO EM MASSA (BIBLIOTECA)
# ==========================================

def sincronizar_videoteca_completa():
    """Importa todos os itens de biblioteca_conteudo.py em lotes de 400."""
    db = get_db()
    if not db: return "Erro: Sem conexão com Firebase."
    
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return "⚠️ Ficheiro de backup está vazio."

        # Mapa de assuntos para evitar duplicados
        assuntos_ref = db.collection('assuntos').stream()
        assuntos_map = {d.to_dict()['nome']: d.id for d in assuntos_ref}

        total_itens = len(VIDEOTECA_GLOBAL)
        chunk_size = 400
        
        for i in range(0, total_itens, chunk_size):
            batch = db.batch()
            chunk = VIDEOTECA_GLOBAL[i : i + chunk_size]
            
            for item in chunk:
                # Estrutura: [area, assunto, tipo, subtipo, titulo, link, msg_id]
                area, ass_nome, tipo, subtipo, titulo, link, msg_id = item
                
                if ass_nome not in assuntos_map:
                    new_ref = db.collection('assuntos').add({'nome': ass_nome, 'grande_area': area})
                    aid = new_ref[1].id
                    assuntos_map[ass_nome] = aid
                else:
                    aid = assuntos_map[ass_nome]

                doc_ref = db.collection('conteudos').document(str(msg_id))
                batch.set(doc_ref, {
                    'assunto_id': aid, 'tipo': tipo, 'subtipo': subtipo,
                    'titulo': titulo, 'link': link, 'message_id': msg_id,
                    'sync_at': firestore.SERVER_TIMESTAMP
                })
            batch.commit()
            
        return f"🎉 Sucesso! {total_itens} itens sincronizados."
    except ImportError:
        return "❌ Ficheiro biblioteca_conteudo.py não encontrado."
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# ==========================================
# 🔐 SEGURANÇA & GAMIFICAÇÃO
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

def get_status_gamer(u):
    db = get_db()
    doc = db.collection('perfil_gamer').document(u).get()
    if not doc.exists: return None, pd.DataFrame()
    d = doc.to_dict()
    xp = d.get('xp', 0)
    nivel = 1 + (xp // 1000)
    p = {'nivel': nivel, 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': 'Residente', 'xp_proximo': 1000}
    return p, pd.DataFrame()

def adicionar_xp(u, qtd):
    db = get_db()
    ref = db.collection('perfil_gamer').document(u)
    doc = ref.get()
    if doc.exists:
        ref.update({'xp': doc.to_dict().get('xp', 0) + qtd})

# ==========================================
# 📊 ANALYTICS
# ==========================================

def get_dados_graficos(u):
    db = get_db()
    hist_ref = db.collection('historico').where('usuario_id', '==', u).stream()
    hist_data = [d.to_dict() for d in hist_ref]
    if not hist_data: return pd.DataFrame()
    
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    clean = []
    for h in hist_data:
        aid = h.get('assunto_id')
        a_info = assuntos.get(str(aid), {'nome': 'Outros', 'grande_area': 'Outros'})
        clean.append({
            'data': h.get('data_estudo'),
            'acertos': h.get('acertos', 0), 'total': h.get('total', 0),
            'percentual': (h.get('acertos', 0) / h.get('total', 1) * 100),
            'area': a_info['grande_area']
        })
    return pd.DataFrame(clean)

def get_progresso_hoje(u):
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

# ==========================================
# 📝 REGISTROS
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d")
    docs = list(db.collection('assuntos').where('nome', '==', assunto).limit(1).stream())
    if not docs: return "Erro: Tema não encontrado."
    aid = docs[0].id
    db.collection('historico').add({'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt, 'acertos': acertos, 'total': total})
    adicionar_xp(u, int(total * 2))
    return "✅ Registado!"

def registrar_simulado(u, dados, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d"); batch = db.batch()
    t_q = 0
    for area, v in dados.items():
        if v['total'] > 0:
            t_q += v['total']
            docs = list(db.collection('assuntos').where('nome', '==', f"Simulado - {area}").limit(1).stream())
            aid = docs[0].id if docs else db.collection('assuntos').add({'nome': f"Simulado - {area}", 'grande_area': area})[1].id
            batch.set(db.collection('historico').document(), {'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt, 'acertos': v['acertos'], 'total': v['total']})
    batch.commit()
    adicionar_xp(u, int(t_q * 2.5))
    return "✅ Simulado Salvo!"

# ==========================================
# 📅 LISTAGENS
# ==========================================

def listar_revisoes_completas(u):
    db = get_db()
    docs = db.collection('revisoes').where('usuario_id', '==', u).stream()
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    data = []
    for doc in docs:
        d = doc.to_dict()
        a = assuntos.get(d['assunto_id'], {'nome': '?', 'grande_area': '?'})
        data.append({'id': doc.id, 'assunto': a['nome'], 'grande_area': a['grande_area'], **d})
    return pd.DataFrame(data)

def concluir_revisao(rid, ac, tot):
    get_db().collection('revisoes').document(rid).update({'status': 'Concluido'})
    return "✅ OK!"

def listar_conteudo_videoteca():
    db = get_db()
    docs = db.collection('conteudos').stream()
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    data = []
    for doc in docs:
        d = doc.to_dict()
        a = assuntos.get(d['assunto_id'], {'nome': '?', 'grande_area': '?'})
        data.append({'id': doc.id, 'assunto': a['nome'], 'grande_area': a['grande_area'], **d})
    return pd.DataFrame(data)

def pesquisar_global(t):
    df = listar_conteudo_videoteca()
    return df[df['titulo'].str.contains(t, case=False) | df['assunto'].str.contains(t, case=False)] if not df.empty else df

def excluir_conteudo(id): 
    get_db().collection('conteudos').document(id).delete()

# Inicialização Base
try:
    if get_db():
        docs = list(get_db().collection('assuntos').limit(1).stream())
        if not docs:
            batch = get_db().batch()
            for n, a in [('Banco Geral - Livre', 'Banco Geral'), ('Simulado - Geral', 'Simulado')]:
                batch.set(get_db().collection('assuntos').document(), {'nome': n, 'grande_area': a})
            batch.commit()
except: pass