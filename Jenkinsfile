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

        stage('Instalar Python') {
            steps {
                echo 'Instalando Python e pip...'
                sh '''
                    apt-get update -y
                    apt-get install -y python3 python3-pip
                    python3 --version
                    pip3 --version
                '''
            }
        }

        stage('Instalar dependências') {
            steps {
                echo 'Instalando dependências do projeto...'
                sh 'pip3 install --no-cache-dir -r requirements.txt'
            }
        }

        stage('Carregar variáveis do .env') {
            steps {
                echo 'Carregando variáveis de ambiente do arquivo .env...'
                sh 'export $(grep -v "^#" .env | xargs)'
            }
        }

        stage('Executar script Python') {
            steps {
                echo ' Executando importação de planilhas...'
                sh 'python3 src/import_planilhas_mysql.py'
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
