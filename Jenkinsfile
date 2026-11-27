pipeline {
    agent { label 'mtg-build' }
    options {
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }
    triggers { pollSCM('H/5 * * * *') }
    parameters {
        string(name: 'DEPLOY_HOST', defaultValue: '10.77.0.11', description: 'IP или DNS второй VM')
        string(name: 'DEPLOY_USER', defaultValue: 'student', description: 'SSH пользователь второй VM')
    }
    environment {
        COMPOSE_PROJECT_NAME = "mtg-check-${BUILD_NUMBER}"
        TEST_IMAGE_TAG = "jenkins-${BUILD_NUMBER}"
    }
    stages {
        stage('Check') {
            steps {
                sh 'docker compose -p "$COMPOSE_PROJECT_NAME" -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests'
            }
            post {
                always {
                    sh 'docker compose -p "$COMPOSE_PROJECT_NAME" -f docker-compose.test.yml down --volumes --remove-orphans'
                }
            }
        }
        stage('Build') {
            steps {
                sh 'docker build --target runtime -t "mtg-shop:$GIT_COMMIT" .'
                sh 'docker save -o image.tar "mtg-shop:$GIT_COMMIT"'
            }
        }
        stage('Deploy') {
            steps {
                withCredentials([
                    file(credentialsId: 'mtg-ssh-key', variable: 'SSH_PRIVATE_KEY'),
                    file(credentialsId: 'mtg-known-hosts', variable: 'SSH_KNOWN_HOSTS'),
                    file(credentialsId: 'mtg-deploy-env', variable: 'DEPLOY_ENV')
                ]) {
                    sh 'bash scripts/deploy.sh'
                }
            }
        }
    }
    post { always { sh 'rm -f image.tar' } }
}
