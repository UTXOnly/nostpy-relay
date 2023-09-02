pipeline {
    agent any

    stages {
        stage('Preparation') {
            steps {
                sh 'docker system prune -af' // Remove all unused Docker data
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
                    sh 'docker system prune -af' // Remove all unused Docker data again
                }
            }
        }
    }
}
