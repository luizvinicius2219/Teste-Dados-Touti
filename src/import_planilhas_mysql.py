import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# ==========================
# 1. Carregar variáveis do .env (dentro da mesma pasta do script)
# ==========================
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
print("Procurando .env em:", dotenv_path)
load_dotenv(dotenv_path)

print("DEBUG ENV:", os.getenv('DB_USER'), os.getenv('DB_HOST'), os.getenv('DB_NAME'))

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_NAME = os.getenv('DB_NAME')
FOLDER = os.getenv('PLANILHAS_FOLDER', './planilhas')

# String de conexão
CONN_STR = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# ==========================
# 2. Funções auxiliares
# ==========================
def sanitize_table_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    if re.match(r'^[0-9]', name):
        name = 't_' + name
    return name[:64]

def read_file_to_dfs(path):
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    # --- Excel ---
    if ext in ['.xls', '.xlsx']:
        xls = pd.ExcelFile(path)
        dfs = {}
        for sheet in xls.sheet_names:
            try:
                dfs[sheet] = xls.parse(sheet)
            except Exception as e:
                print(f"⚠️ Erro lendo {path} sheet {sheet}: {e}")
        return dfs

    # --- CSV ---
    elif ext == '.csv':
        try:
            # Conta quantas linhas totais há no arquivo
            total_lines = sum(1 for _ in open(path, encoding='utf-8', errors='ignore'))

            # Lê o CSV de forma robusta
            df = pd.read_csv(
                path,
                dtype=str,
                sep=None,           # Detecta o separador automaticamente
                engine='python',    # Parsing mais tolerante
                on_bad_lines='skip' # Ignora linhas quebradas
            )

            # Conta quantas linhas foram realmente lidas
            read_lines = len(df)
            skipped = total_lines - read_lines - 1  # -1 por causa do cabeçalho
            if skipped > 0:
                print(f"⚠️ {skipped} linhas foram ignoradas por erro de formatação no CSV.")

            return {'csv': df}

        except Exception as e:
            print(f"❌ Erro lendo CSV {path}: {e}")
            return {}

    else:
        return {}

def ensure_db_connection(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Conexão com o banco MySQL bem-sucedida!")
        return True
    except SQLAlchemyError as e:
        print("❌ Erro conectando ao banco:", e)
        return False

def write_df_to_table(engine, df: pd.DataFrame, table_name: str, if_exists='append', chunksize=5000):
    try:
        df.to_sql(name=table_name, con=engine, if_exists=if_exists, index=False, chunksize=chunksize, method='multi')
        print(f"✅ Gravado {len(df)} linhas na tabela `{table_name}`")
    except Exception as e:
        print(f"❌ Erro gravando tabela {table_name}: {e}")

# ==========================
# 3. Função principal
# ==========================
def main():
    engine = create_engine(CONN_STR, pool_pre_ping=True)
    if not ensure_db_connection(engine):
        return

    files = [os.path.join(FOLDER, f) for f in os.listdir(FOLDER)
             if os.path.isfile(os.path.join(FOLDER, f)) and os.path.splitext(f)[1].lower() in ('.xlsx','.xls','.csv')]

    if not files:
        print("⚠️ Nenhum arquivo encontrado em:", FOLDER)
        return

    for file_path in files:
        print(f"\n📄 Processando: {file_path}")
        dfs = read_file_to_dfs(file_path)
        base_filename = os.path.splitext(os.path.basename(file_path))[0]

        for sheet_name, df in dfs.items():
            if df is None or df.empty:
                continue
            df = df.dropna(axis=1, how='all')

            codigo_cols = [c for c in df.columns if str(c).strip().lower() == 'codigo']
            if codigo_cols:
                codigo_col = codigo_cols[0]
                df[codigo_col] = df[codigo_col].astype(str).fillna('sem_codigo')
                for codigo_val, sub_df in df.groupby(codigo_col):
                    table_name_raw = f"{base_filename}_{sheet_name}_{codigo_val}"
                    table_name = sanitize_table_name(table_name_raw)
                    write_df_to_table(engine, sub_df, table_name)
            else:
                table_name_raw = f"{base_filename}_{sheet_name}"
                table_name = sanitize_table_name(table_name_raw)
                write_df_to_table(engine, df, table_name)

    engine.dispose()
    print("\n✅ Fim do processamento.")

if __name__ == "__main__":
    main()
