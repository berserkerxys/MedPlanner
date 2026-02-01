import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import json
import os

# --- CONEXÃO FIREBASE (SINGLETON) ---
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

# --- FUNÇÃO DE COMPATIBILIDADE (CORRIGE O ERRO DE IMPORTAÇÃO) ---
def get_connection():
    """Função dummy para satisfazer imports antigos do app.py"""
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
# 📊 ANALYTICS & DASHBOARD (FUNÇÕES OBRIGATÓRIAS)
# ==========================================

def get_dados_graficos(u):
    """
    Necessária para o dashboard.py.
    """
    db = get_db()
    hist_ref = db.collection('historico').where('usuario_id', '==', u).stream()
    hist_data = [d.to_dict() for d in hist_ref]
    
    if not hist_data: return pd.DataFrame()
    
    assuntos_ref = db.collection('assuntos').stream()
    assuntos_map = {d.id: d.to_dict() for d in assuntos_ref}
    
    clean_data = []
    for h in hist_data:
        aid = h.get('assunto_id')
        subject = assuntos_map.get(str(aid))
        
        area = "Outros"
        if subject:
            area = subject.get('grande_area', 'Outros')
            if "Gineco" in area: area = "G.O."
            
        clean_data.append({
            'data_estudo': h.get('data_estudo'),
            'acertos': h.get('acertos', 0),
            'total': h.get('total', 0),
            'percentual': h.get('percentual', 0),
            'grande_area': area
        })
        
    return pd.DataFrame(clean_data)

def get_progresso_hoje(u):
    """
    Necessária para o app.py (Barra Lateral).
    Conta quantas questões o usuário fez hoje.
    """
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

def get_status_gamer(u):
    """
    Necessária para o dashboard.py.
    """
    db = get_db()
    doc = db.collection('perfil_gamer').document(u).get()
    if not doc.exists: return None, None
    d = doc.to_dict()
    
    xp = d.get('xp', 0)
    nivel = 1 + (xp // 1000)
    prox = nivel * 1000
    
    p = {'nivel': nivel, 'xp_atual': xp, 'xp_total': xp, 'titulo': d.get('titulo', 'Calouro'), 'xp_proximo': prox}
    return p, pd.DataFrame() 

def adicionar_xp(u, qtd):
    db = get_db()
    doc_ref = db.collection('perfil_gamer').document(u)
    
    # Simples update para evitar complexidade de transação se não configurado
    try:
        doc = doc_ref.get()
        if doc.exists:
            curr = doc.to_dict()
            doc_ref.update({'xp': curr.get('xp', 0) + qtd})
    except: pass

# ==========================================
# 📝 REGISTRO (APP.PY)
# ==========================================
def get_assuntos_dict():
    db = get_db()
    docs = db.collection('assuntos').stream()
    return {d.id: d.to_dict() for d in docs}

def get_assunto_id_by_name(nome):
    db = get_db()
    docs = list(db.collection('assuntos').where('nome', '==', nome).limit(1).stream())
    if docs: return docs[0].id, docs[0].to_dict().get('grande_area')
    
    area = "Geral"
    if "Simulado" in nome: 
        try: area = nome.split(" - ")[1]
        except: pass
    elif "Banco" in nome: area = "Banco Geral"
        
    ref = db.collection('assuntos').add({'nome': nome, 'grande_area': area})
    return ref[1].id, area

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db()
    aid, area = get_assunto_id_by_name(assunto)
    dt = data_personalizada.strftime("%Y-%m-%d")
    
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
# 📅 AGENDA E VIDEOTECA
# ==========================================
def listar_revisoes_completas(u):
    db = get_db()
    revs = list(db.collection('revisoes').where('usuario_id', '==', u).stream())
    if not revs: return pd.DataFrame()
    
    assuntos = get_assuntos_dict()
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
    return "✅ Feito!"

def listar_conteudo_videoteca():
    db = get_db()
    docs = db.collection('conteudos').stream()
    data = []
    assuntos = get_assuntos_dict()
    for doc in docs:
        d = doc.to_dict()
        ad = assuntos.get(d['assunto_id'], {'nome': '?', 'grande_area': 'Outros'})
        data.append({'id': doc.id, 'assunto': ad['nome'], 'grande_area': ad['grande_area'], **d})
    return pd.DataFrame(data)

# Placeholders
def pesquisar_global(t): return listar_conteudo_videoteca()
def excluir_conteudo(id): pass

inicializar_db()