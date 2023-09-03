pipeline {
    agent any

    stages {
        stage('Preparation') {
            steps {
                sh 'docker image ls'
                sh 'docker system prune -a --volumes -f' // Remove all unused Docker data
            }
        }

        stage('Run') {
            steps {
                sh 'cd docker_stuff && docker-compose up -d'
            }
        }
    }

    post {
        always {
            script {
                stage('Cleanup') {
                    sh 'docker compose down --remove-orphans'
                    sh 'docker system prune -a --volumes -f' // Remove all unused Docker data again
                    sh 'docker image ls'
                }
            }
        }
    }
}
