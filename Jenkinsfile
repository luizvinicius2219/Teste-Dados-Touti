pipeline {
    agent any

    environment {
        PLANILHAS_FOLDER = './planilhas'
    }

    stages {
        stage('Checkout do código') {
            steps {
                echo 'Fazendo checkout do repositório...'
                checkout scm
            }
        }

        stage('Instalar dependências') {
            steps {
                echo 'Instalando dependências do projeto...'
                sh '''
                    set -e
                    python3 --version
                    pip3 --version

                    # Cria ambiente virtual (venv) isolado
                    python3 -m venv venv
                    . venv/bin/activate

                    # Atualiza pip dentro do venv
                    pip install --upgrade pip

                    # Instala dependências do projeto
                    pip install --no-cache-dir --default-timeout=100 --retries=5 -r requirements.txt
                '''
            }
        }

        stage('Executar script Python') {
            steps {
                echo 'Executando importação de planilhas...'
                sh '''
                    set -e
                    # Carrega variáveis do .env
                    export $(grep -v "^#" .env | xargs)

                    # Ativa o ambiente virtual e executa o script
                    . venv/bin/activate
                    python src/import_planilhas_mysql.py
                '''
            }
        }
    }

    post {
        success {
            echo 'Importação concluída com sucesso!'
        }
        failure {
            echo 'Erro durante a execução. Verifique os logs no console do Jenkins.'
        }
    }
}
