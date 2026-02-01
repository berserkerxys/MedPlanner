import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import json
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
            # st.success("Firebase conectado localmente!")
    except Exception as e:
        st.error(f"Erro ao inicializar Firebase: {e}")

def get_db():
    try:
        return firestore.client()
    except:
        return None

# ==========================================
# ⚙️ MÓDULO 1: INICIALIZAÇÃO & SEED
# ==========================================

def inicializar_db():
    """No Firebase, garante apenas que os dados base existam"""
    db = get_db()
    if db:
        seed_universal(db)

def seed_universal(db):
    """Popula dados padrão (Edital e Videoteca) se a coleção estiver vazia"""
    try:
        docs = list(db.collection('assuntos').limit(1).stream())
        
        if not docs:
            # Tenta importar do arquivo local se existir
            try:
                from aulas_medcof import DADOS_LIMPOS
            except ImportError:
                DADOS_LIMPOS = []

            if not DADOS_LIMPOS:
                DADOS_LIMPOS = [
                    ('Banco Geral - Livre', 'Banco Geral'), 
                    ('Simulado - Geral', 'Simulado'),
                    ('Abdome Agudo Hemorragico', 'G.O.'), 
                    ('Apendicite Aguda', 'Cirurgia')
                ]
            
            batch = db.batch()
            for nome, area in DADOS_LIMPOS:
                doc_ref = db.collection('assuntos').document()
                batch.set(doc_ref, {'nome': nome, 'grande_area': area})
            batch.commit()
            
            # Seed Videoteca (Exemplo ou Importação)
            try:
                from biblioteca_conteudo import VIDEOTECA_GLOBAL
            except ImportError:
                VIDEOTECA_GLOBAL = []
                
            if VIDEOTECA_GLOBAL:
                # Recupera IDs para vincular
                assuntos_ref = db.collection('assuntos').stream()
                assuntos_map = {d.to_dict()['nome']: d.id for d in assuntos_ref}
                
                batch_vid = db.batch()
                for area, ass_nome, tipo, subtipo, titulo, link, msg_id in VIDEOTECA_GLOBAL:
                    if ass_nome in assuntos_map:
                        doc_vid = db.collection('conteudos').document()
                        batch_vid.set(doc_vid, {
                            'assunto_id': assuntos_map[ass_nome],
                            'tipo': tipo,
                            'subtipo': subtipo,
                            'titulo': titulo,
                            'link': link,
                            'message_id': msg_id
                        })
                batch_vid.commit()

    except Exception as e:
        print(f"Erro no Seed: {e}")

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA
# ==========================================

def verificar_login(u, p):
    db = get_db()
    if not db: return False, "Erro Conexão"
    
    users_ref = db.collection('usuarios').where('username', '==', u).limit(1).stream()
    for doc in users_ref:
        user_data = doc.to_dict()
        stored_hash = user_data['password_hash']
        if isinstance(stored_hash, str): stored_hash = stored_hash.encode('utf-8')
        
        if bcrypt.checkpw(p.encode('utf-8'), stored_hash):
            return True, user_data['nome']
    return False, None

def criar_usuario(u, p, n):
    db = get_db()
    if list(db.collection('usuarios').where('username', '==', u).stream()):
        return False, "Usuário já existe."
    
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    batch = db.batch()
    user_ref = db.collection('usuarios').document(u)
    batch.set(user_ref, {'username': u, 'nome': n, 'password_hash': hashed})
    
    perf_ref = db.collection('perfil_gamer').document(u)
    batch.set(perf_ref, {
        'usuario_id': u, 'nivel': 1, 'xp_atual': 0, 'xp_total': 0, 'titulo': 'Calouro Desesperado'
    })
    batch.commit()
    return True, "Criado com sucesso!"

# ==========================================
# 🎮 MÓDULO 3: GAMIFICAÇÃO
# ==========================================

def calcular_info_nivel(nivel):
    xp_prox = int(1000 * (1 + (nivel * 0.1)))
    titulos = [(10, "Calouro"), (30, "Interno"), (60, "Residente"), (100, "Chefe")]
    titulo = next((t for n, t in titulos if nivel <= n), "Lenda")
    return titulo, xp_prox

def get_status_gamer(u):
    db = get_db()
    doc = db.collection('perfil_gamer').document(u).get()
    
    if not doc.exists: return None, pd.DataFrame()
    data = doc.to_dict()
    
    titulo, xp_prox = calcular_info_nivel(data.get('nivel', 1))
    
    p = {
        "nivel": data.get('nivel', 1), 
        "xp_atual": data.get('xp_atual', 0), 
        "xp_total": data.get('xp_total', 0), 
        "titulo": titulo, 
        "xp_proximo": xp_prox
    }
    
    hoje = datetime.now().strftime("%Y-%m-%d")
    missoes_ref = db.collection('missoes_hoje').where('usuario_id', '==', u).where('data_missao', '==', hoje).stream()
    m_data = [d.to_dict() for d in missoes_ref]
    
    if not m_data:
        gerar_missoes_no_firebase(u, db, hoje)
        return get_status_gamer(u)
        
    return p, pd.DataFrame(m_data)

def gerar_missoes_no_firebase(u, db, hoje):
    templates = [
        {"desc": "Resolver 20 questões", "tipo": "questoes", "meta": 20, "xp": 100},
        {"desc": "Revisar 1 tema", "tipo": "revisao", "meta": 1, "xp": 150},
        {"desc": "Assistir 1 aula", "tipo": "video", "meta": 1, "xp": 200}
    ]
    batch = db.batch()
    for m in templates:
        ref = db.collection('missoes_hoje').document()
        batch.set(ref, {
            "usuario_id": u, "data_missao": hoje, "descricao": m['desc'],
            "tipo": m['tipo'], "meta_valor": m['meta'], "progresso_atual": 0,
            "xp_recompensa": m['xp'], "concluida": False
        })
    batch.commit()

def adicionar_xp(u, qtd):
    db = get_db()
    doc_ref = db.collection('perfil_gamer').document(u)
    
    @firestore.transactional
    def update_in_transaction(transaction, ref):
        snapshot = transaction.get(ref)
        if not snapshot.exists: return
        data = snapshot.to_dict()
        
        novo_xp = data.get('xp_atual', 0) + qtd
        novo_total = data.get('xp_total', 0) + qtd
        nivel = data.get('nivel', 1)
        
        _, meta = calcular_info_nivel(nivel)
        while novo_xp >= meta:
            novo_xp -= meta
            nivel += 1
            _, meta = calcular_info_nivel(nivel)
            
        transaction.update(ref, {'nivel': nivel, 'xp_atual': novo_xp, 'xp_total': novo_total})
        
    transaction = db.transaction()
    update_in_transaction(transaction, doc_ref)

def processar_progresso_missao(u, tipo_acao, qtd, area=None):
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    docs = db.collection('missoes_hoje').where('usuario_id', '==', u).where('data_missao', '==', hoje).where('concluida', '==', False).stream()
    
    msgs = []
    for doc in docs:
        m = doc.to_dict()
        if m['tipo'] == tipo_acao:
            novo_p = m['progresso_atual'] + qtd
            updates = {'progresso_atual': novo_p}
            
            if novo_p >= m['meta_valor']:
                updates['concluida'] = True
                adicionar_xp(u, m['xp_recompensa'])
                msgs.append(f"🏆 Missão Cumprida: {m['descricao']}")
            
            doc.reference.update(updates)
            
    return msgs

# ==========================================
# 📊 AUXILIARES DE DADOS
# ==========================================
def get_assuntos_dict():
    db = get_db()
    docs = db.collection('assuntos').stream()
    return {d.id: d.to_dict() for d in docs}

def get_assunto_id_by_name(nome):
    db = get_db()
    docs = list(db.collection('assuntos').where('nome', '==', nome).limit(1).stream())
    if docs:
        return docs[0].id, docs[0].to_dict().get('grande_area')
    
    area = "Geral"
    if "Simulado" in nome: 
        try: area = nome.split(" - ")[1]
        except: pass
    elif "Banco" in nome:
        area = "Banco Geral"
        
    ref = db.collection('assuntos').add({'nome': nome, 'grande_area': area})
    return ref[1].id, area

# ==========================================
# 📅 REGISTROS
# ==========================================
def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db()
    aid, area = get_assunto_id_by_name(assunto)
    if not aid: return "Erro ao catalogar assunto."
    
    dt = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    
    db.collection('historico').add({
        'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
        'acertos': acertos, 'total': total, 'percentual': (acertos/total*100)
    })
    
    if "Banco" not in assunto and "Simulado" not in assunto:
        data_rev = (datetime.strptime(dt, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        db.collection('revisoes').add({
            'usuario_id': u, 'assunto_id': aid, 'data_agendada': data_rev,
            'tipo': '1 Semana', 'status': 'Pendente'
        })
    
    adicionar_xp(u, int(total*2))
    msgs = processar_progresso_missao(u, 'questoes', total)
    return f"✅ Registrado na Nuvem! {' '.join(msgs)}"

def registrar_simulado(u, dados, data_personalizada=None):
    db = get_db()
    dt = data_personalizada.strftime("%Y-%m-%d") if data_personalizada else datetime.now().strftime("%Y-%m-%d")
    tq = 0
    batch = db.batch()
    
    for area, v in dados.items():
        if v['total'] > 0:
            tq += v['total']
            nome = f"Simulado - {area}"
            aid, _ = get_assunto_id_by_name(nome)
            
            ref = db.collection('historico').document()
            batch.set(ref, {
                'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt,
                'acertos': v['acertos'], 'total': v['total'], 'percentual': (v['acertos']/v['total']*100)
            })
            
    batch.commit()
    adicionar_xp(u, int(tq*2.5))
    msgs = processar_progresso_missao(u, 'questoes', tq)
    return f"✅ Simulado Salvo! {' '.join(msgs)}"

def concluir_revisao(rid, acertos, total):
    db = get_db()
    rev_ref = db.collection('revisoes').document(rid)
    doc = rev_ref.get()
    if not doc.exists: return "Erro."
    
    d = doc.to_dict()
    aid = d['assunto_id']
    u = d['usuario_id']
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    rev_ref.update({'status': 'Concluido'})
    
    db.collection('historico').add({
        'usuario_id': u, 'assunto_id': aid, 'data_estudo': hoje,
        'acertos': acertos, 'total': total, 'percentual': (acertos/total*100)
    })
    
    # Ciclo SRS (1 Sem -> 1 Mês -> 2 Meses -> 4 Meses)
    ciclo = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses"), "2 Meses": (120, "4 Meses")}
    dias, prox = ciclo.get(d['tipo'], (0, None))
    
    msg = "Revisão Concluída!"
    if prox:
        nova_data = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        db.collection('revisoes').add({
            'usuario_id': u, 'assunto_id': aid, 'data_agendada': nova_data,
            'tipo': prox, 'status': 'Pendente'
        })
        msg += f" Próxima em {dias} dias ({prox})."
        
    adicionar_xp(u, 100)
    msgs = processar_progresso_missao(u, 'revisao', 1)
    return f"{msg} {' '.join(msgs)}"

# ==========================================
# 📊 LEITURA
# ==========================================
def listar_revisoes_completas(u):
    db = get_db()
    revs = list(db.collection('revisoes').where('usuario_id', '==', u).stream())
    if not revs: return pd.DataFrame()
    
    assuntos = get_assuntos_dict()
    data = []
    for r in revs:
        rd = r.to_dict()
        ad = assuntos.get(rd['assunto_id'], {'nome': 'Desconhecido', 'grande_area': 'Outros'})
        data.append({
            'id': r.id, 'assunto': ad['nome'], 'grande_area': ad['grande_area'],
            'data_agendada': rd['data_agendada'], 'tipo': rd['tipo'], 'status': rd['status']
        })
    return pd.DataFrame(data)

def listar_conteudo_videoteca():
    db = get_db()
    conts = list(db.collection('conteudos').stream())
    assuntos = get_assuntos_dict()
    data = []
    for c in conts:
        cd = c.to_dict()
        ad = assuntos.get(cd.get('assunto_id'), {'nome': '?', 'grande_area': 'Outros'})
        data.append({'id': c.id, 'assunto': ad['nome'], 'grande_area': ad['grande_area'], **cd})
    return pd.DataFrame(data)

def get_progresso_hoje(u):
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('historico').where('usuario_id', '==', u).where('data_estudo', '==', hoje).stream()
    return sum([d.to_dict().get('total', 0) for d in docs])

# Placeholders para evitar erro de import
def pesquisar_global(t): return listar_conteudo_videoteca()
def salvar_config(k,v): pass
def ler_config(k): return None
def excluir_conteudo(id): 
    try: get_db().collection('conteudos').document(id).delete()
    except: pass
def atualizar_nome_assunto(id,n): pass
def deletar_assunto(id): pass
def registrar_topico_do_sumario(g, n): pass
def resetar_progresso(u): pass 

inicializar_db()