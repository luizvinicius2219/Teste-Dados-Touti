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
                // roda pip3 e python no mesmo shell
                sh '''
                    python3 --version
                    pip3 --version
                    pip3 install --no-cache-dir --default-timeout=100 --retries=5 -r requirements.txt
                '''
            }
        }

        stage('Executar script Python') {
            steps {
                echo 'Executando importação de planilhas...'
                // carregar variáveis do .env e rodar Python no mesmo shell
                sh '''
                    export $(grep -v "^#" .env | xargs)
                    python3 src/import_planilhas_mysql.py
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
