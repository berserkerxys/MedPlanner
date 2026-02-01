import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import json
import os

# --- CONEXÃO FIREBASE ---
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            # Nuvem
            key_dict = dict(st.secrets["firebase"])
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        elif os.path.exists("firebase_key.json"):
            # Local
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred)
    except Exception as e:
        # Silencioso para não quebrar a UI, o app.py checa get_db()
        print(f"Erro Firebase Init: {e}")

def get_db():
    try:
        return firestore.client()
    except:
        return None

# ==========================================
# ⚙️ SEED
# ==========================================
def inicializar_db():
    db = get_db()
    if db: seed_universal(db)

def seed_universal(db):
    try:
        if not list(db.collection('assuntos').limit(1).stream()):
            temas = [
                ('Abdome Agudo', 'Cirurgia'), ('Diabetes', 'Clínica Médica'), 
                ('Pré-Natal', 'G.O.'), ('Imunizações', 'Pediatria'), 
                ('SUS', 'Preventiva')
            ]
            batch = db.batch()
            for n, a in temas:
                doc = db.collection('assuntos').document()
                batch.set(doc, {'nome': n, 'grande_area': a})
            batch.commit()
    except: pass

# ==========================================
# 🔐 LOGIN
# ==========================================
def verificar_login(u, p):
    db = get_db()
    if not db: return False, "Sem Conexão"
    
    users = list(db.collection('usuarios').where('username', '==', u).stream())
    for doc in users:
        d = doc.to_dict()
        stored = d['password_hash']
        if isinstance(stored, str): stored = stored.encode('utf-8')
        if bcrypt.checkpw(p.encode('utf-8'), stored): return True, d['nome']
    return False, None

def criar_usuario(u, p, n):
    db = get_db()
    if list(db.collection('usuarios').where('username', '==', u).stream()):
        return False, "Usuário já existe"
    
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    batch = db.batch()
    
    batch.set(db.collection('usuarios').document(u), {'username': u, 'nome': n, 'password_hash': hashed})
    batch.set(db.collection('perfil_gamer').document(u), {'usuario_id': u, 'nivel': 1, 'xp': 0, 'titulo': 'Calouro'})
    
    batch.commit()
    return True, "Criado!"

# ==========================================
# 🎮 & 📊 ANALYTICS
# ==========================================
def get_progresso_hoje(u):
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

def get_status_gamer(u):
    db = get_db()
    doc = db.collection('perfil_gamer').document(u).get()
    if not doc.exists: return None, None
    d = doc.to_dict()
    
    # Nível simplificado
    xp = d.get('xp', 0)
    nivel = 1 + (xp // 1000)
    prox = nivel * 1000
    
    p = {'nivel': nivel, 'xp_atual': xp, 'xp_total': xp, 'titulo': d.get('titulo', 'Calouro'), 'xp_proximo': prox}
    return p, pd.DataFrame() # Missões vazias por enquanto para evitar erro

def adicionar_xp(u, qtd):
    db = get_db()
    ref = db.collection('perfil_gamer').document(u)
    doc = ref.get()
    if doc.exists:
        xp_antigo = doc.to_dict().get('xp', 0)
        ref.update({'xp': xp_antigo + qtd})

# ==========================================
# 📝 REGISTRO
# ==========================================
def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db()
    dt = data_personalizada.strftime("%Y-%m-%d")
    
    # Busca/Cria Assunto
    docs = list(db.collection('assuntos').where('nome', '==', assunto).stream())
    if docs: aid = docs[0].id
    else: aid = db.collection('assuntos').add({'nome': assunto, 'grande_area': 'Geral'})[1].id
    
    db.collection('historico').add({
        'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
        'acertos': acertos, 'total': total, 'percentual': (acertos/total*100)
    })
    
    if "Banco" not in assunto:
        dt_rev = (data_personalizada + timedelta(days=7)).strftime("%Y-%m-%d")
        db.collection('revisoes').add({
            'usuario_id': u, 'assunto_id': aid, 'data_agendada': dt_rev,
            'tipo': '1 Semana', 'status': 'Pendente'
        })
        
    adicionar_xp(u, int(total * 2))
    return "✅ Salvo!"

def registrar_simulado(u, dados, data_personalizada=None):
    db = get_db()
    dt = data_personalizada.strftime("%Y-%m-%d")
    batch = db.batch()
    
    tq = 0
    for area, v in dados.items():
        if v['total'] > 0:
            tq += v['total']
            nome = f"Simulado - {area}"
            # Busca simples
            docs = list(db.collection('assuntos').where('nome', '==', nome).stream())
            if docs: aid = docs[0].id
            else: aid = db.collection('assuntos').add({'nome': nome, 'grande_area': area})[1].id
            
            ref = db.collection('historico').document()
            batch.set(ref, {
                'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
                'acertos': v['acertos'], 'total': v['total'], 'percentual': (v['acertos']/v['total']*100)
            })
            
    batch.commit()
    adicionar_xp(u, int(tq * 2.5))
    return "✅ Simulado Salvo!"

# ==========================================
# 📅 AGENDA E VIDEOS
# ==========================================
def listar_revisoes_completas(u):
    db = get_db()
    revs = list(db.collection('revisoes').where('usuario_id', '==', u).stream())
    if not revs: return pd.DataFrame()
    
    # Cache assuntos
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    
    data = []
    for r in revs:
        rd = r.to_dict()
        ad = assuntos.get(rd['assunto_id'], {'nome': '?', 'grande_area': 'Outros'})
        data.append({
            'id': r.id, 'assunto': ad['nome'], 'grande_area': ad['grande_area'],
            'data_agendada': rd['data_agendada'], 'tipo': rd['tipo'], 'status': rd['status']
        })
    return pd.DataFrame(data)

def concluir_revisao(rid, a, t):
    db = get_db()
    ref = db.collection('revisoes').document(rid)
    ref.update({'status': 'Concluido'})
    # (Adicione lógica SRS aqui se quiser)
    return "✅ Feito!"

def listar_conteudo_videoteca():
    db = get_db()
    docs = db.collection('conteudos').stream()
    data = []
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    for doc in docs:
        d = doc.to_dict()
        ad = assuntos.get(d['assunto_id'], {'nome': '?', 'grande_area': 'Outros'})
        data.append({'id': doc.id, 'assunto': ad['nome'], 'grande_area': ad['grande_area'], **d})
    return pd.DataFrame(data)

# Placeholders para compatibilidade
def pesquisar_global(t): return listar_conteudo_videoteca()
def excluir_conteudo(id): pass

inicializar_db()