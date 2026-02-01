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
    try: return firestore.client()
    except: return None

# Compatibilidade
def get_connection(): return None

# ==========================================
# ⚙️ INICIALIZAÇÃO & SEED
# ==========================================
def inicializar_db():
    db = get_db()
    if db: seed_universal(db)

def seed_universal(db):
    """Garante que existam temas base para as seleções"""
    try:
        # Verifica se 'assuntos' está vazio
        docs = list(db.collection('assuntos').limit(1).stream())
        if not docs:
            temas = [
                ('Apendicite Aguda', 'Cirurgia'), ('Abdome Agudo', 'Cirurgia'),
                ('Diabetes Mellitus', 'Clínica Médica'), ('Hipertensão Arterial', 'Clínica Médica'),
                ('Pré-Natal', 'G.O.'), ('Hemorragias da Gestação', 'G.O.'),
                ('Imunizações', 'Pediatria'), ('Puericultura', 'Pediatria'),
                ('Princípios do SUS', 'Preventiva'), ('Epidemiologia', 'Preventiva'),
                ('Banco Geral - Livre', 'Banco Geral')
            ]
            batch = db.batch()
            for n, a in temas:
                batch.set(db.collection('assuntos').document(), {'nome': n, 'grande_area': a})
            batch.commit()
    except: pass

# ==========================================
# 🔐 SEGURANÇA
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
        return False, "Usuário já existe"
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.collection('usuarios').document(u).set({'username': u, 'nome': n, 'password_hash': hashed})
    db.collection('perfil_gamer').document(u).set({'usuario_id': u, 'nivel': 1, 'xp': 0, 'titulo': 'Calouro'})
    return True, "Criado com sucesso!"

# ==========================================
# 📊 ANALYTICS & GAMIFICAÇÃO
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
            'acertos': h.get('acertos', 0),
            'total': h.get('total', 0),
            'percentual': (h.get('acertos', 0) / h.get('total', 1) * 100),
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
    titulos = [(10, "Estudante"), (30, "Interno"), (60, "Residente"), (100, "Especialista")]
    titulo = next((t for n, t in titulos if nivel <= n), "Mestre")
    p = {'nivel': nivel, 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': titulo, 'xp_proximo': 1000}
    return p, pd.DataFrame() # Missões podem ser adicionadas depois

def adicionar_xp(u, qtd):
    db = get_db()
    ref = db.collection('perfil_gamer').document(u)
    doc = ref.get()
    if doc.exists:
        ref.update({'xp': doc.to_dict().get('xp', 0) + qtd})

# ==========================================
# 📝 REGISTROS
# ==========================================
def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db()
    dt = data_personalizada.strftime("%Y-%m-%d")
    docs = list(db.collection('assuntos').where('nome', '==', assunto).limit(1).stream())
    if not docs: return "Erro: Tema não encontrado."
    aid = docs[0].id
    
    db.collection('historico').add({
        'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
        'acertos': acertos, 'total': total
    })
    
    if "Banco" not in assunto:
        db.collection('revisoes').add({
            'usuario_id': u, 'assunto_id': aid, 'data_agendada': (data_personalizada + timedelta(days=7)).strftime("%Y-%m-%d"),
            'tipo': '1 Semana', 'status': 'Pendente'
        })
    adicionar_xp(u, int(total * 2))
    return "✅ Estudo Registrado!"

def registrar_simulado(u, dados, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d")
    batch = db.batch()
    t_questoes = 0
    for area, v in dados.items():
        if v['total'] > 0:
            t_questoes += v['total']
            # Busca ID da área de simulado
            nome_sim = f"Simulado - {area}"
            docs = list(db.collection('assuntos').where('nome', '==', nome_sim).limit(1).stream())
            if docs: aid = docs[0].id
            else: 
                ref = db.collection('assuntos').add({'nome': nome_sim, 'grande_area': area})
                aid = ref[1].id
            
            ref_h = db.collection('historico').document()
            batch.set(ref_h, {
                'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
                'acertos': v['acertos'], 'total': v['total']
            })
    batch.commit()
    adicionar_xp(u, int(t_questoes * 2.5))
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

def concluir_revisao(rid, acertos, total):
    db = get_db()
    ref = db.collection('revisoes').document(rid)
    ref.update({'status': 'Concluido'})
    # Logica de SRS pode ser expandida aqui
    return "✅ Revisão Concluída!"

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

def pesquisar_global(t): return listar_conteudo_videoteca()
def excluir_conteudo(id): pass

inicializar_db()