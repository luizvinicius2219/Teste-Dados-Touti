# ---------------------------------------------------------
# Script para importar planilhas (Excel/CSV) para o MySQL
# ---------------------------------------------------------
# Autor: [Luiz Vinicius Santana da Silva]
# Descrição:
# Este script percorre uma pasta com planilhas (.xlsx, .xls, .csv),
# lê cada arquivo e grava seu conteúdo em tabelas no banco de dados MySQL.
# Caso exista uma coluna chamada "codigo", o script cria uma tabela
# separada para cada valor distinto dessa coluna.
#
# Boas práticas aplicadas:
#  - Uso de dotenv para variáveis sensíveis (.env)
#  - Sanitização de nomes de tabelas
#  - Tratamento de exceções robusto em operações de I/O e banco
#  - Logs claros e informativos
#  - Modularização do código em funções
# ---------------------------------------------------------

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# ---------------------------------------------------------
# Carrega variáveis de ambiente (.env)
# ---------------------------------------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
print("Procurando .env em:", dotenv_path)
load_dotenv(dotenv_path)

# Debug: imprime variáveis carregadas (exceto senha)
print("DEBUG ENV:", os.getenv('DB_USER'), os.getenv('DB_HOST'), os.getenv('DB_NAME'))

# ---------------------------------------------------------
# Lê as variáveis de ambiente
# ---------------------------------------------------------
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', 3306))  # valor padrão 3306
DB_NAME = os.getenv('DB_NAME')
FOLDER = os.getenv('PLANILHAS_FOLDER', './planilhas')  # pasta padrão

# Cria string de conexão para o MySQL usando SQLAlchemy + PyMySQL
CONN_STR = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"


# ---------------------------------------------------------
# Função: sanitize_table_name
# Descrição: cria nomes válidos para tabelas SQL
# ---------------------------------------------------------
def sanitize_table_name(name: str) -> str:
    name = name.strip().lower()  # remove espaços e converte para minúsculas
    name = re.sub(r'[^a-z0-9_]', '_', name)  # substitui caracteres inválidos
    if re.match(r'^[0-9]', name):
        name = 't_' + name  # evita nome de tabela começando com número
    return name[:64]  # limite de 64 caracteres (MySQL)


# ---------------------------------------------------------
# Função: read_file_to_dfs
# Descrição: lê um arquivo Excel ou CSV e retorna dicionário de DataFrames
# ---------------------------------------------------------
def read_file_to_dfs(path):
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    # --- Caso seja Excel (.xls / .xlsx) ---
    if ext in ['.xls', '.xlsx']:
        xls = pd.ExcelFile(path)
        dfs = {}
        for sheet in xls.sheet_names:
            try:
                dfs[sheet] = xls.parse(sheet)  # lê cada aba como DataFrame
            except Exception as e:
                print(f"Erro lendo {path} sheet {sheet}: {e}")
        return dfs

    # --- Caso seja CSV ---
    elif ext == '.csv':
        try:
            # Conta total de linhas para comparar com as que foram lidas
            total_lines = sum(1 for _ in open(path, encoding='utf-8', errors='ignore'))

            df = pd.read_csv(
                path,
                dtype=str,              # lê tudo como string para evitar erros de tipo
                sep=None,               # autodetecta o separador
                engine='python',        # engine mais tolerante a erros
                on_bad_lines='skip'     # ignora linhas malformadas
            )

            # Calcula linhas ignoradas
            read_lines = len(df)
            skipped = total_lines - read_lines - 1  # -1 por causa do cabeçalho
            if skipped > 0:
                print(f"{skipped} linhas foram skipadas por erro de formatação no CSV.")

            return {'csv': df}

        except Exception as e:
            print(f"Erro CSV {path}: {e}")
            return {}

    else:
        # Extensão não suportada
        return {}


# ---------------------------------------------------------
# Função: ensure_db_connection
# Descrição: testa se a conexão com o banco está ativa
# ---------------------------------------------------------
def ensure_db_connection(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # comando simples de verificação
        print("Conexão ok")
        return True
    except SQLAlchemyError as e:
        print("Erro na conexão:", e)
        return False


# ---------------------------------------------------------
# Função: write_df_to_table
# Descrição: grava um DataFrame em uma tabela MySQL
# ---------------------------------------------------------
def write_df_to_table(engine, df: pd.DataFrame, table_name: str, if_exists='append', chunksize=5000):
    try:
        # to_sql faz o insert em lotes, com método multi para performance
        df.to_sql(name=table_name, con=engine, if_exists=if_exists, index=False, chunksize=chunksize, method='multi')
        print(f"Gravado {len(df)} linhas na tabela `{table_name}`")
    except Exception as e:
        print(f"Erro gravando tabela {table_name}: {e}")


# ---------------------------------------------------------
# Função principal
# ---------------------------------------------------------
def main():
    # Cria engine SQLAlchemy com pool de conexões
    engine = create_engine(CONN_STR, pool_pre_ping=True)

    # Verifica se o banco está acessível
    if not ensure_db_connection(engine):
        return

    # Lista todos os arquivos válidos na pasta
    files = [os.path.join(FOLDER, f) for f in os.listdir(FOLDER)
             if os.path.isfile(os.path.join(FOLDER, f))
             and os.path.splitext(f)[1].lower() in ('.xlsx', '.xls', '.csv')]

    if not files:
        print("Nenhum arquivo encontrado em:", FOLDER)
        return

    # Loop principal — percorre todos os arquivos
    for file_path in files:
        print(f"\n Processando: {file_path}")
        dfs = read_file_to_dfs(file_path)
        base_filename = os.path.splitext(os.path.basename(file_path))[0]

        # Para cada aba (ou arquivo CSV)
        for sheet_name, df in dfs.items():
            if df is None or df.empty:
                continue

            # Remove colunas completamente vazias
            df = df.dropna(axis=1, how='all')

            # Verifica se existe uma coluna chamada "codigo"
            codigo_cols = [c for c in df.columns if str(c).strip().lower() == 'codigo']
            if codigo_cols:
                codigo_col = codigo_cols[0]

                # Normaliza valores nulos e converte para string
                df[codigo_col] = df[codigo_col].astype(str).fillna('sem_codigo')

                # Cria uma tabela para cada código único
                for codigo_val, sub_df in df.groupby(codigo_col):
                    table_name_raw = f"{base_filename}_{sheet_name}_{codigo_val}"
                    table_name = sanitize_table_name(table_name_raw)
                    write_df_to_table(engine, sub_df, table_name)

            else:
                # Caso não exista a coluna "codigo", cria uma única tabela
                table_name_raw = f"{base_filename}_{sheet_name}"
                table_name = sanitize_table_name(table_name_raw)
                write_df_to_table(engine, df, table_name)

    # Fecha a engine de conexão
    engine.dispose()
    print("\n Fim do processamento.")


# ---------------------------------------------------------
# Execução direta do script
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
