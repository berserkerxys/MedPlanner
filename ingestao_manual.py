import sqlite3
from database import inicializar_db, DB_NAME
# Importa a lista de dados que acabamos de criar
from aulas_medcof import DADOS_LIMPOS

def importar_manual():
    # 1. Garante que o banco existe
    inicializar_db()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print("--- 📥 Iniciando Importação Manual (Zero Erro) ---")
    
    novos = 0
    ignorados = 0
    
    for aula, area in DADOS_LIMPOS:
        try:
            # Tenta inserir. Se já existir o nome exato, ignora (OR IGNORE)
            c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", 
                      (aula, area))
            
            if c.rowcount > 0:
                novos += 1
            else:
                ignorados += 1
        except Exception as e:
            print(f"Erro no item '{aula}': {e}")
            
    conn.commit()
    conn.close()
    
    print("\n✅ Concluído com Sucesso!")
    print(f"Novas aulas inseridas: {novos}")
    print(f"Aulas já existentes (ignoradas): {ignorados}")
    print(f"Total de aulas no sistema: {novos + ignorados}")
    print("\nAgora pode rodar: streamlit run app.py")

if __name__ == "__main__":
    importar_manual()