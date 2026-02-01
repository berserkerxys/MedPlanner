import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import random
import re
import math
import bcrypt

# Tenta importar backups se existirem
try:
    from aulas_medcof import DADOS_LIMPOS
except ImportError:
    DADOS_LIMPOS = []

try:
    from biblioteca_conteudo import VIDEOTECA_GLOBAL
except ImportError:
    VIDEOTECA_GLOBAL = []

DB_NAME = 'dados_medcof.db'

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# ==========================================
# ⚙️ MÓDULO 1: INICIALIZAÇÃO
# ==========================================

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    
    # Tabelas Universais
    c.execute('''CREATE TABLE IF NOT EXISTS assuntos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        nome TEXT UNIQUE, 
        grande_area TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS conteudos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        assunto_id INTEGER, 
        tipo TEXT, subtipo TEXT, titulo TEXT, link TEXT, message_id INTEGER UNIQUE,
        FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inbox_telegram (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER UNIQUE,
                    titulo_original TEXT,
                    link_direto TEXT,
                    hashtag_detectada TEXT,
                    status TEXT DEFAULT 'Pendente'
                )''')

    # Tabelas de Usuário
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash BLOB)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        usuario_id TEXT, assunto_id INTEGER, 
        data_estudo DATE, acertos INTEGER, total INTEGER, percentual REAL, 
        FOREIGN KEY(usuario_id) REFERENCES usuarios(username), 
        FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS revisoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        usuario_id TEXT, assunto_id INTEGER, 
        data_agendada DATE, tipo TEXT, status TEXT DEFAULT 'Pendente', 
        FOREIGN KEY(usuario_id) REFERENCES usuarios(username), 
        FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS perfil_gamer (
        usuario_id TEXT PRIMARY KEY, 
        nivel INTEGER DEFAULT 1, xp_atual INTEGER DEFAULT 0, xp_total INTEGER DEFAULT 0, 
        titulo TEXT DEFAULT 'Calouro Desesperado', 
        FOREIGN KEY(usuario_id) REFERENCES usuarios(username))''')

    c.execute('''CREATE TABLE IF NOT EXISTS missoes_hoje (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        usuario_id TEXT, data_missao DATE, descricao TEXT, tipo TEXT, 
        meta_valor INTEGER, progresso_atual INTEGER DEFAULT 0, 
        xp_recompensa INTEGER, concluida BOOLEAN DEFAULT 0)''')

    conn.commit()
    seed_universal(conn)
    conn.close()
    padronizar_areas()

def seed_universal(conn):
    c = conn.cursor()
    # Edital
    c.execute("SELECT COUNT(*) FROM assuntos")
    if c.fetchone()[0] == 0:
        if DADOS_LIMPOS:
            c.executemany("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", DADOS_LIMPOS)
        else:
            temas = [('Banco Geral - Livre', 'Banco Geral'), ('Simulado - Geral', 'Simulado')]
            c.executemany("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", temas)
        conn.commit()

    # Videoteca (Backup)
    c.execute("SELECT COUNT(*) FROM conteudos")
    if c.fetchone()[0] == 0 and VIDEOTECA_GLOBAL:
        for item in VIDEOTECA_GLOBAL:
            try:
                area, assunto, tipo, subtipo, titulo, link, msg_id = item
                c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", (assunto, area))
                c.execute("SELECT id FROM assuntos WHERE nome = ?", (assunto,))
                res = c.fetchone()
                if res:
                    c.execute('''INSERT OR IGNORE INTO conteudos (assunto_id, tipo, subtipo, titulo, link, message_id) 
                                 VALUES (?, ?, ?, ?, ?, ?)''', (res[0], tipo, subtipo, titulo, link, msg_id))
            except: pass
        conn.commit()

def padronizar_areas():
    conn = get_connection()
    try:
        conn.execute("UPDATE assuntos SET grande_area = 'G.O.' WHERE grande_area LIKE 'Gineco%' OR grande_area = 'Ginecologia e Obstetrícia'")
        conn.commit()
    except: pass
    finally: conn.close()

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA
# ==========================================

def verificar_login(u, p):
    conn = get_connection(); c = conn.cursor()
    user = c.execute("SELECT password_hash, nome FROM usuarios WHERE username = ?", (u,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(p.encode('utf-8'), user[0]): return True, user[1]
    return False, None

def criar_usuario(u, p, n):
    conn = get_connection(); c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?, ?, ?)", (u, n, hashed))
        c.execute("INSERT INTO perfil_gamer (usuario_id) VALUES (?)", (u,))
        conn.commit(); return True, "Usuário criado!"
    except: return False, "Usuário já existe."
    finally: conn.close()

# ==========================================
# 🎮 MÓDULO 3: GAMIFICAÇÃO
# ==========================================

def calcular_info_nivel(nivel):
    xp_prox = int(1000 * (1 + (nivel * 0.1)))
    mult = 1.0 + (nivel * 0.05)
    titulos = [(10, "Calouro"), (30, "Interno"), (60, "Residente"), (100, "Chefe")]
    titulo = next((t for n, t in titulos if nivel <= n), "Lenda")
    return titulo, xp_prox, mult

def gerar_missoes_do_dia(u):
    conn = get_connection(); c = conn.cursor(); hoje = datetime.now().date()
    if c.execute("SELECT count(*) FROM missoes_hoje WHERE usuario_id = ? AND data_missao = ?", (u, hoje)).fetchone()[0] > 0:
        conn.close(); return

    nivel = c.execute("SELECT nivel FROM perfil_gamer WHERE usuario_id = ?", (u,)).fetchone()[0]
    _, _, mult = calcular_info_nivel(nivel)

    templates = [
        {"desc": "Resolver {X} questões de Cirurgia", "tipo": "questoes_area", "area": "Cirurgia", "base": 15, "xp": 150},
        {"desc": "Resolver {X} questões de Clínica", "tipo": "questoes_area", "area": "Clínica Médica", "base": 15, "xp": 150},
        {"desc": "Resolver {X} questões de Pediatria", "tipo": "questoes_area", "area": "Pediatria", "base": 15, "xp": 150},
        {"desc": "Resolver {X} questões de G.O.", "tipo": "questoes_area", "area": "G.O.", "base": 15, "xp": 150},
        {"desc": "Resolver {X} questões de Preventiva", "tipo": "questoes_area", "area": "Preventiva", "base": 15, "xp": 150},
        {"desc": "Meta Global: {X} questões hoje", "tipo": "questoes_total", "base": 40, "xp": 200},
        {"desc": "Assistir {X} Aulas na Videoteca", "tipo": "video", "base": 2, "xp": 300},
        {"desc": "Matar {X} temas de Revisão", "tipo": "revisao", "base": 5, "xp": 400},
    ]
    
    for m in random.sample(templates, 3):
        meta = int(m["base"] * mult); xp = int(m["xp"] * mult)
        c.execute('''INSERT INTO missoes_hoje (usuario_id, data_missao, descricao, tipo, meta_valor, xp_recompensa)
                     VALUES (?, ?, ?, ?, ?, ?)''', (u, hoje, m["desc"].replace("{X}", str(meta)), m["tipo"], meta, xp))
    conn.commit(); conn.close()

def get_status_gamer(u):
    # Gera se não existir
    try:
        gerar_missoes_do_dia(u)
    except: pass 
    
    conn = get_connection()
    row = conn.execute("SELECT nivel, xp_atual, xp_total, titulo FROM perfil_gamer WHERE usuario_id = ?", (u,)).fetchone()
    if not row: conn.close(); return None, None
    _, xp_prox, _ = calcular_info_nivel(row[0])
    p = {"nivel": row[0], "xp_atual": row[1], "xp_total": row[2], "titulo": row[3], "xp_proximo": xp_prox}
    m = pd.read_sql("SELECT * FROM missoes_hoje WHERE usuario_id = ? AND data_missao = ?", conn, params=(u, datetime.now().date()))
    conn.close(); return p, m

def adicionar_xp(u, qtd, conn):
    c = conn.cursor()
    res = c.execute("SELECT nivel, xp_atual, xp_total FROM perfil_gamer WHERE usuario_id=?", (u,)).fetchone()
    if not res: return
    n, xp, tot = res
    xp += qtd; tot += qtd; _, meta, _ = calcular_info_nivel(n)
    while xp >= meta: 
        xp -= meta; n += 1; _, meta, _ = calcular_info_nivel(n)
    tit, _, _ = calcular_info_nivel(n)
    c.execute("UPDATE perfil_gamer SET nivel=?, xp_atual=?, xp_total=?, titulo=? WHERE usuario_id=?", (n, xp, tot, tit, u))

def processar_progresso_missao(u, tipo_acao, quantidade, area=None):
    conn = get_connection(); c = conn.cursor(); hoje = datetime.now().date()
    ativas = c.execute("SELECT id, tipo, meta_valor, progresso_atual, xp_recompensa, descricao FROM missoes_hoje WHERE usuario_id = ? AND data_missao = ? AND concluida = 0", (u, hoje)).fetchall()
    msgs = []
    
    area_reg = area.lower().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace(".","") if area else ""
    
    for mid, mtipo, meta, prog, xp_rw, desc in ativas:
        match = False
        if mtipo == "questoes_total" and tipo_acao == "questoes":
            match = True
        elif mtipo == "questoes_area" and tipo_acao == "questoes" and area:
            desc_norm = desc.lower().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace(".","")
            keywords = ["cirurgia", "clinica", "pediatria", "go", "ginecologia", "preventiva"]
            for k in keywords:
                if k in area_reg and k in desc_norm:
                    match = True; break
        elif mtipo == "video" and tipo_acao == "video": match = True
        elif mtipo == "revisao" and tipo_acao == "revisao": match = True
            
        if match:
            novo_p = prog + quantidade
            if novo_p >= meta:
                c.execute("UPDATE missoes_hoje SET progresso_atual = ?, concluida = 1 WHERE id = ?", (meta, mid))
                adicionar_xp(u, xp_rw, conn); msgs.append(f"🏆 {desc}")
            else:
                c.execute("UPDATE missoes_hoje SET progresso_atual = ? WHERE id = ?", (novo_p, mid))
                
    conn.commit(); conn.close(); return msgs

# ==========================================
# 📅 MÓDULO 4: REGISTROS E SRS
# ==========================================

def registrar_estudo(u, assunto, acertos, total, data_personalizada=None):
    conn = get_connection(); c = conn.cursor()
    res = c.execute("SELECT id, grande_area FROM assuntos WHERE nome=?", (assunto,)).fetchone()
    if not res: 
        if "Banco Geral" in assunto:
            c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, 'Banco Geral')", (assunto,))
            res = c.execute("SELECT id, grande_area FROM assuntos WHERE nome=?", (assunto,)).fetchone()
        else: conn.close(); return "Erro: Assunto não encontrado."
    
    dt = data_personalizada if data_personalizada else datetime.now().date()
    c.execute("INSERT INTO historico (usuario_id, assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?,?)", 
              (u, res[0], dt, acertos, total, (acertos/total*100)))
    
    if "Banco" not in assunto and "Simulado" not in assunto:
        c.execute("INSERT INTO revisoes (usuario_id, assunto_id, data_agendada, tipo, status) VALUES (?,?,?,?, 'Pendente')", (u, res[0], dt + timedelta(days=7), "1 Semana"))
    
    adicionar_xp(u, int(total * 2), conn)
    conn.commit(); conn.close()
    
    # Processa missões
    msgs = processar_progresso_missao(u, "questoes", total, res[1])
    extra = f" | {' '.join(msgs)}" if msgs else ""
    return f"✅ Registrado!{extra}"

def registrar_simulado(u, dados, data_personalizada=None):
    conn = get_connection(); c = conn.cursor()
    dt = data_personalizada if data_personalizada else datetime.now().date()
    tq = 0
    for area, v in dados.items():
        if v['total'] > 0:
            tq += v['total']
            c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?,?)", (f"Simulado - {area}", area))
            aid = c.execute("SELECT id FROM assuntos WHERE nome=?", (f"Simulado - {area}",)).fetchone()[0]
            c.execute("INSERT INTO historico (usuario_id, assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?,?)", 
                      (u, aid, dt, v['acertos'], v['total'], (v['acertos']/v['total']*100)))
    adicionar_xp(u, int(tq*2.5), conn)
    conn.commit(); conn.close()
    processar_progresso_missao(u, "questoes", tq)
    return "✅ Simulado salvo!"

def concluir_revisao(rid, acertos, total):
    conn = get_connection(); c = conn.cursor()
    rev = c.execute("SELECT usuario_id, assunto_id, tipo FROM revisoes WHERE id=?", (rid,)).fetchone()
    if not rev: conn.close(); return "Erro."
    u, aid, tipo = rev; hoje = datetime.now().date()
    saltos = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses"), "2 Meses": (120, "4 Meses")}
    dias, prox = saltos.get(tipo, (0, None))
    c.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
    c.execute("INSERT INTO historico (usuario_id, assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?,?)", (u, aid, hoje, acertos, total, (acertos/total*100)))
    if prox:
        c.execute("INSERT INTO revisoes (usuario_id, assunto_id, data_agendada, tipo, status) VALUES (?,?,?,?, 'Pendente')", (u, aid, hoje + timedelta(days=dias), prox))
    adicionar_xp(u, 100, conn); conn.commit(); conn.close()
    processar_progresso_missao(u, "revisao", 1)
    return "✅ Reagendado!"

# --- UTILS ---
def listar_revisoes_completas(u):
    conn = get_connection(); df = pd.read_sql("SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id WHERE r.usuario_id = ?", conn, params=(u,)); conn.close(); return df
def listar_revisoes_pendentes(u):
    conn = get_connection(); df = pd.read_sql("SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id WHERE r.usuario_id = ? AND r.status='Pendente'", conn, params=(u,)); conn.close(); return df
def get_progresso_hoje(u):
    conn = get_connection(); r = conn.execute("SELECT SUM(total) FROM historico WHERE usuario_id=? AND data_estudo=?", (u, datetime.now().date())).fetchone(); conn.close(); return r[0] if r[0] else 0
def salvar_conteudo_exato(mid, tit, lnk, tag, tp, sub):
    conn = get_connection(); c = conn.cursor()
    try:
        tag_limpa = re.sub(r'(?<!^)(?=[A-Z])', ' ', tag.replace("#","").replace("_"," ").lower().strip()).strip()
        df = pd.read_sql("SELECT id, nome, grande_area FROM assuntos", conn)
        aid, area = None, None
        for _, r in df.iterrows():
            if r['nome'].replace(" ","").lower() == tag_limpa.replace(" ",""): aid, area = r['id'], r['grande_area']; break
        if not aid: return f"⚠️ Não mapeado: {tag}"
        if c.execute("SELECT id FROM conteudos WHERE message_id = ?", (mid,)).fetchone(): return "⏭️"
        t_final = tit
        if sub == "Curto": t_final += " (⏱️ Curto)"
        elif sub == "Longo": t_final += " (📽️ Longo)"
        elif sub == "Ficha": t_final = "📑 " + t_final
        c.execute("INSERT INTO conteudos (assunto_id, tipo, subtipo, titulo, link, message_id) VALUES (?,?,?,?,?,?)", (aid, tp, sub, t_final, lnk, mid))
        conn.commit(); return f"✅ Salvo em {area}"
    except Exception as e: return str(e)
    finally: conn.close()
def exportar_videoteca_para_arquivo():
    conn = get_connection(); df = pd.read_sql("SELECT a.grande_area, a.nome, c.tipo, c.subtipo, c.titulo, c.link, c.message_id FROM conteudos c JOIN assuntos a ON c.assunto_id = a.id", conn); conn.close()
    with open("biblioteca_conteudo.py", "w", encoding="utf-8") as f: f.write(f"VIDEOTECA_GLOBAL = {df.values.tolist()}")
def listar_conteudo_videoteca(): conn=get_connection(); df=pd.read_sql("SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link FROM conteudos c JOIN assuntos a ON c.assunto_id=a.id ORDER BY a.grande_area", conn); conn.close(); return df
def pesquisar_global(t): conn=get_connection(); tf=f"%{t.lower()}%"; df=pd.read_sql("SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link FROM conteudos c JOIN assuntos a ON c.assunto_id=a.id WHERE lower(c.titulo) LIKE ? OR lower(a.nome) LIKE ?", conn, params=(tf,tf)); conn.close(); return df
def excluir_conteudo(id): conn=get_connection(); conn.execute("DELETE FROM conteudos WHERE id=?",(id,)); conn.commit(); conn.close()
def atualizar_nome_assunto(id,n): conn=get_connection(); conn.execute("UPDATE assuntos SET nome=? WHERE id=?",(n,id)); conn.commit(); conn.close(); return True,"Ok"
def registrar_topico_do_sumario(g,n): conn=get_connection(); c=conn.cursor(); c.execute("INSERT OR IGNORE INTO assuntos (nome,grande_area) VALUES (?,?)",(n,g)); conn.commit(); conn.close()
def deletar_assunto(id): conn=get_connection(); conn.execute("DELETE FROM assuntos WHERE id=?",(id,)); conn.commit(); conn.close()
def salvar_config(k,v): conn=get_connection(); conn.execute("INSERT OR REPLACE INTO configuracoes VALUES (?,?)",(k,str(v))); conn.commit(); conn.close()
def ler_config(k): conn=get_connection(); r=conn.cursor().execute("SELECT valor FROM configuracoes WHERE chave=?",(k,)).fetchone(); conn.close(); return r[0] if r else None
def resetar_progresso(u): conn=get_connection(); conn.execute("DELETE FROM historico WHERE usuario_id=?",(u,)); conn.execute("DELETE FROM revisoes WHERE usuario_id=?",(u,)); conn.commit(); conn.close(); return "Limpo!"

inicializar_db()