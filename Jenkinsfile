pipeline {
    agent any

    stages {
        stage('Preparation') {
            steps {
                sh 'docker image ls'
                sh 'docker system prune -a --volumes -f' 
                
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
                    sh 'cd docker_stuff && docker-compose down'
                    sh 'docker system prune -a --volumes -f' // Remove all unused Docker data again
                    sh 'sudo rm -r /var/lib/jenkins/workspace/nostpy-build-containers-docker-compose-up/*'
                    sh 'docker image ls'
                }
            }
        }
    }
}
