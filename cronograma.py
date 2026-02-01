# Novo arquivo: cronograma.py
# UI para criar cronograma em blocos a partir de aulas_medcof.DADOS_LIMPOS
import streamlit as st
from aulas_medcof import DADOS_LIMPOS
from hashlib import md5

def _item_key(idx, nome):
    h = md5(f"{idx}:{nome}".encode("utf-8")).hexdigest()[:10]
    return f"cron_{idx}_{h}"

def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def render_cronograma(conn_ignored=None):
    st.header("🗂️ Cronograma por Blocos")
    u = st.session_state.get("username", None)

    # Controles superiores
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        block_size = st.number_input("Tamanho do bloco (itens por bloco):", min_value=1, max_value=50, value=8, step=1, key="cron_block_size")
    with c2:
        show_only_incomplete = st.checkbox("Mostrar só blocos completos/incompletos?", value=False, key="cron_filter_incomplete")
    with c3:
        search = st.text_input("🔎 Buscar por assunto (texto):", value="", key="cron_search")

    # Áreas disponíves (extraídas de DADOS_LIMPOS)
    areas = sorted(list({a for _, a in DADOS_LIMPOS if a}))
    sel_areas = st.multiselect("Filtrar por Grande Área:", options=areas, default=areas, key="cron_sel_areas")

    # Inicializa estado em session_state
    if "cron_checked" not in st.session_state:
        st.session_state.cron_checked = {}
        for idx, (nome, area) in enumerate(DADOS_LIMPOS):
            st.session_state.cron_checked[_item_key(idx, nome)] = False

    # Filtra itens conforme controles
    items = [(idx, nome, area) for idx, (nome, area) in enumerate(DADOS_LIMPOS)
             if (not sel_areas or area in sel_areas) and (search.lower() in nome.lower())]

    # Agrupa em blocos
    blocks = list(_chunk(items, block_size))

    # Ações globais
    a1, a2, a3 = st.columns([1,1,1])
    with a1:
        if st.button("Marcar todos visíveis", use_container_width=True):
            for (idx, nome, area) in items:
                st.session_state.cron_checked[_item_key(idx, nome)] = True
            st.toast("Todos os itens visíveis foram marcados.")
    with a2:
        if st.button("Desmarcar todos visíveis", use_container_width=True):
            for (idx, nome, area) in items:
                st.session_state.cron_checked[_item_key(idx, nome)] = False
            st.toast("Todos os itens visíveis foram desmarcados.")
    with a3:
        if st.button("Salvar checklist (persistir)", use_container_width=True):
            if not u:
                st.warning("Para salvar o checklist você precisa estar logado.")
            else:
                # Persistência: chamar função do database.py se disponível
                try:
                    from database import salvar_cronograma_status
                    payload = st.session_state.cron_checked
                    if salvar_cronograma_status(u, payload):
                        st.toast("Checklist salvo com sucesso!")
                    else:
                        st.error("Erro ao salvar checklist no banco.")
                except Exception as e:
                    st.warning("Persistência não configurada. Veja instruções para adicionar suporte ao DB.")

    st.divider()

    # Renderiza blocos
    for bi, bloco in enumerate(blocks, start=1):
        total = len(bloco)
        checked = sum(1 for (idx, nome, area) in bloco if st.session_state.cron_checked.get(_item_key(idx, nome), False))

        # Filtra se desejado
        if show_only_incomplete and checked == total:
            continue

        with st.expander(f"📦 BLOCO {bi} — {checked}/{total} estudados", expanded=False):
            st.progress(checked / total if total > 0 else 0)
            # Ações do bloco
            b1, b2 = st.columns([1,1])
            with b1:
                if st.button(f"Marcar BLOCO {bi} como concluído", key=f"mark_block_{bi}"):
                    for (idx, nome, area) in bloco:
                        st.session_state.cron_checked[_item_key(idx, nome)] = True
                    st.experimental_rerun()
            with b2:
                if st.button(f"Desmarcar BLOCO {bi}", key=f"unmark_block_{bi}"):
                    for (idx, nome, area) in bloco:
                        st.session_state.cron_checked[_item_key(idx, nome)] = False
                    st.experimental_rerun()

            # Lista de itens do bloco
            for (idx, nome, area) in bloco:
                key = _item_key(idx, nome)
                col_a, col_b = st.columns([6,1])
                with col_a:
                    # Checkbox ligado ao session_state para persistência local
                    st.checkbox(f"{nome}  —  {area}", value=st.session_state.cron_checked.get(key, False), key=key)
                with col_b:
                    if st.button("Registrar estudo", key=f"reg_{key}"):
                        st.toast("Para registrar estudos use o painel lateral 'Registar' ou a funcionalidade de Simulado.")
            st.divider()

    # Resumo
    total_all = len(items)
    total_checked = sum(1 for (idx, nome, area) in items if st.session_state.cron_checked.get(_item_key(idx, nome), False))
    st.caption(f"Visível: {total_all} itens — Marcados: {total_checked}")