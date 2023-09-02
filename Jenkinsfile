pipeline {
    agent any
    
    stages {
        stage('Test') {
            steps {
                script {
                    // Run docker-compose up
                    sh "cd docker_stuff && docker-compose up"
                }
            }
        }
    }
}
