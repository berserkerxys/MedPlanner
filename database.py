import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import streamlit as st
import json
import os
import re

# --- CONEXÃO FIREBASE ---
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
# ⚙️ MÓDULO DE SINCRONIZAÇÃO (BIBLIOTECA -> CLOUD)
# ==========================================

def inicializar_db():
    db = get_db()
    if db:
        seed_universal(db)

def seed_universal(db):
    """
    Verifica se o banco está vazio e popula com os temas base 
    e o conteúdo do arquivo biblioteca_conteudo.py
    """
    try:
        # 1. Garante Temas Base (Edital)
        docs_assuntos = list(db.collection('assuntos').limit(1).stream())
        if not docs_assuntos:
            print("🌱 Criando assuntos base...")
            temas_iniciais = [
                ('Banco Geral - Livre', 'Banco Geral'),
                ('Simulado - Geral', 'Simulado')
            ]
            batch = db.batch()
            for n, a in temas_iniciais:
                batch.set(db.collection('assuntos').document(), {'nome': n, 'grande_area': a})
            batch.commit()

        # 2. Popula Videoteca a partir do backup biblioteca_conteudo.py
        docs_conteudo = list(db.collection('conteudos').limit(1).stream())
        if not docs_conteudo:
            importar_videoteca_do_backup()
            
    except Exception as e:
        print(f"Erro no Seed: {e}")

def importar_videoteca_do_backup():
    """Lê o arquivo master local e envia tudo para o Firebase"""
    db = get_db()
    try:
        from biblioteca_conteudo import VIDEOTECA_GLOBAL
        if not VIDEOTECA_GLOBAL: return "Backup vazio."

        print(f"📦 Importando {len(VIDEOTECA_GLOBAL)} itens para a nuvem...")
        
        # Mapeia assuntos atuais para evitar duplicados
        assuntos_ref = db.collection('assuntos').stream()
        assuntos_map = {d.to_dict()['nome']: d.id for d in assuntos_ref}

        for item in VIDEOTECA_GLOBAL:
            # Estrutura esperada: [area, assunto, tipo, subtipo, titulo, link, msg_id]
            area, assunto, tipo, subtipo, titulo, link, msg_id = item
            
            # Se o assunto não existe, cria
            if assunto not in assuntos_map:
                new_ass_ref = db.collection('assuntos').add({'nome': assunto, 'grande_area': area})
                aid = new_ass_ref[1].id
                assuntos_map[assunto] = aid
            else:
                aid = assuntos_map[assunto]

            # Adiciona o conteúdo
            db.collection('conteudos').document(str(msg_id)).set({
                'assunto_id': aid,
                'tipo': tipo,
                'subtipo': subtipo,
                'titulo': titulo,
                'link': link,
                'message_id': msg_id
            })
        return f"✅ {len(VIDEOTECA_GLOBAL)} itens sincronizados!"
    except ImportError:
        return "⚠️ Arquivo biblioteca_conteudo.py não encontrado."
    except Exception as e:
        return f"❌ Erro na importação: {e}"

# Função exigida pelo sync.py do Telegram
def salvar_conteudo_exato(mid, tit, lnk, tag, tp, sub):
    """
    Função usada pelo script de sincronização para salvar um item específico
    vindo do Telegram diretamente no Firestore.
    """
    db = get_db()
    try:
        # Tenta mapear a hashtag para um assunto existente
        # Ex: #Apendicite_Aguda -> Apendicite Aguda
        nome_assunto = tag.replace("_", " ").strip()
        
        # Busca assunto
        docs = list(db.collection('assuntos').where('nome', '==', nome_assunto).limit(1).stream())
        if docs:
            aid = docs[0].id
        else:
            # Cria se não existir (Área padrão: Outros, você pode ajustar depois)
            new_ref = db.collection('assuntos').add({'nome': nome_assunto, 'grande_area': 'Outros'})
            aid = new_ref[1].id

        # Salva o conteúdo usando o message_id como ID do documento para evitar duplicatas
        db.collection('conteudos').document(str(mid)).set({
            'assunto_id': aid,
            'tipo': tp,
            'subtipo': sub,
            'titulo': tit,
            'link': lnk,
            'message_id': mid
        })
        return "✅ Salvo na Nuvem"
    except Exception as e:
        return f"Erro: {e}"

def exportar_videoteca_para_arquivo():
    """
    Mantém o arquivo local sincronizado com a nuvem (backup reverso).
    """
    db = get_db()
    conts = db.collection('conteudos').stream()
    assuntos = {d.id: d.to_dict() for d in db.collection('assuntos').stream()}
    
    lista_final = []
    for c in conts:
        cd = c.to_dict()
        a = assuntos.get(cd.get('assunto_id'), {'grande_area': '?', 'nome': '?'})
        lista_final.append([
            a['grande_area'], a['nome'], cd['tipo'], cd['subtipo'], 
            cd['titulo'], cd['link'], cd['message_id']
        ])
    
    with open("biblioteca_conteudo.py", "w", encoding="utf-8") as f:
        f.write("# Backup Automático\n")
        f.write(f"VIDEOTECA_GLOBAL = {lista_final}")

# ==========================================
# 📊 OUTRAS FUNÇÕES (LOGIN, DASHBOARD, ETC)
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
    p = {'nivel': nivel, 'xp_atual': xp % 1000, 'xp_total': xp, 'titulo': 'Estudante', 'xp_proximo': 1000}
    return p, pd.DataFrame()

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d")
    docs = list(db.collection('assuntos').where('nome', '==', assunto).limit(1).stream())
    if not docs: return "Erro: Tema não encontrado."
    aid = docs[0].id
    db.collection('historico').add({'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt, 'acertos': acertos, 'total': total})
    return "✅ Estudo Registrado!"

def registrar_simulado(u, dados, data_personalizada=None):
    db = get_db(); dt = data_personalizada.strftime("%Y-%m-%d"); batch = db.batch()
    for area, v in dados.items():
        if v['total'] > 0:
            docs = list(db.collection('assuntos').where('nome', '==', f"Simulado - {area}").limit(1).stream())
            aid = docs[0].id if docs else db.collection('assuntos').add({'nome': f"Simulado - {area}", 'grande_area': area})[1].id
            batch.set(db.collection('historico').document(), {'usuario_id': u, 'assunto_id': aid, 'data_estudo': dt, 'acertos': v['acertos'], 'total': v['total']})
    batch.commit(); return "✅ Simulado Salvo!"

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
    if df.empty: return df
    return df[df['titulo'].str.contains(t, case=False) | df['assunto'].str.contains(t, case=False)]

def excluir_conteudo(id): 
    get_db().collection('conteudos').document(id).delete()

inicializar_db()