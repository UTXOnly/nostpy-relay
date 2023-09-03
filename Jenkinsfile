pipeline {
    agent any
    
    stages {
        stage('Execute menu') {
            steps {
                script {
                    sh 'echo "1" | python3 menu.py'
                }
            }
        }
    }
}
