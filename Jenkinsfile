pipeline {
    agent {
        kubernetes {
            yaml """
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: docker
                    image: docker:latest
                    command:
                    - cat
                    tty: true
                    volumeMounts:
                    - mountPath: /var/run/docker.sock
                      name: docker-sock
                  - name: kubectl
                    image: bitnami/kubectl:latest
                    command:
                    - cat
                    tty: true
                  - name: node
                    image: node:18-alpine
                    command:
                    - cat
                    tty: true
                  - name: sonar
                    image: sonarsource/sonar-scanner-cli:latest
                    command:
                    - cat
                    tty: true
                  volumes:
                  - name: docker-sock
                    hostPath:
                      path: /var/run/docker.sock
            """
        }
    }

    environment {
        DOCKER_REGISTRY = 'your-registry.com'
        DOCKER_REPO = 'mindmesh'
        KUBECONFIG = credentials('kubeconfig')
        SONAR_TOKEN = credentials('sonar-token')
        SONAR_HOST_URL = 'https://sonarcloud.io'
        DOCKER_REGISTRY_CREDENTIALS = credentials('docker-registry-credentials')
        SLACK_WEBHOOK = credentials('slack-webhook')
        VERSION = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
                    env.GIT_BRANCH = sh(returnStdout: true, script: 'git rev-parse --abbrev-ref HEAD').trim()
                }
            }
        }

        stage('Install Dependencies') {
            parallel {
                stage('Ideas Service') {
                    steps {
                        container('node') {
                            dir('backend/ideas-service') {
                                sh 'npm ci'
                            }
                        }
                    }
                }
                stage('Voting Service') {
                    steps {
                        container('node') {
                            dir('backend/voting-service') {
                                sh 'npm ci'
                            }
                        }
                    }
                }
                stage('Analytics Service') {
                    steps {
                        container('node') {
                            dir('backend/analytics-service') {
                                sh 'npm ci'
                            }
                        }
                    }
                }
                stage('Decision Service') {
                    steps {
                        container('node') {
                            dir('backend/decision-service') {
                                sh 'npm ci'
                            }
                        }
                    }
                }
            }
        }

        stage('Lint & Format Check') {
            parallel {
                stage('Ideas Service Lint') {
                    steps {
                        container('node') {
                            dir('backend/ideas-service') {
                                sh 'npm run lint || true'
                                sh 'npm run format:check || true'
                            }
                        }
                    }
                }
                stage('Voting Service Lint') {
                    steps {
                        container('node') {
                            dir('backend/voting-service') {
                                sh 'npm run lint || true'
                                sh 'npm run format:check || true'
                            }
                        }
                    }
                }
                stage('Analytics Service Lint') {
                    steps {
                        container('node') {
                            dir('backend/analytics-service') {
                                sh 'npm run lint || true'
                                sh 'npm run format:check || true'
                            }
                        }
                    }
                }
                stage('Decision Service Lint') {
                    steps {
                        container('node') {
                            dir('backend/decision-service') {
                                sh 'npm run lint || true'
                                sh 'npm run format:check || true'
                            }
                        }
                    }
                }
            }
        }

        stage('Unit Tests') {
            parallel {
                stage('Ideas Service Tests') {
                    steps {
                        container('node') {
                            dir('backend/ideas-service') {
                                sh 'npm test -- --coverage --ci --watchAll=false'
                                publishTestResults testResultsPattern: 'coverage/lcov.info'
                            }
                        }
                    }
                }
                stage('Voting Service Tests') {
                    steps {
                        container('node') {
                            dir('backend/voting-service') {
                                sh 'npm test -- --coverage --ci --watchAll=false'
                                publishTestResults testResultsPattern: 'coverage/lcov.info'
                            }
                        }
                    }
                }
                stage('Analytics Service Tests') {
                    steps {
                        container('node') {
                            dir('backend/analytics-service') {
                                sh 'npm test -- --coverage --ci --watchAll=false'
                                publishTestResults testResultsPattern: 'coverage/lcov.info'
                            }
                        }
                    }
                }
                stage('Decision Service Tests') {
                    steps {
                        container('node') {
                            dir('backend/decision-service') {
                                sh 'npm test -- --coverage --ci --watchAll=false'
                                publishTestResults testResultsPattern: 'coverage/lcov.info'
                            }
                        }
                    }
                }
            }
        }

        stage('SonarQube Analysis') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                    changeRequest()
                }
            }
            steps {
                container('sonar') {
                    withSonarQubeEnv('SonarCloud') {
                        sh 'sonar-scanner'
                    }
                }
            }
        }

        stage('Quality Gate') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                    changeRequest()
                }
            }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Security Scan') {
            parallel {
                stage('Dependency Check') {
                    steps {
                        container('node') {
                            sh 'npm audit --audit-level moderate'
                        }
                    }
                }
                stage('Docker Image Scan') {
                    when {
                        anyOf {
                            branch 'main'
                            branch 'develop'
                        }
                    }
                    steps {
                        container('docker') {
                            script {
                                def services = ['ideas', 'voting', 'analytics', 'decision']
                                services.each { service ->
                                    sh """
                                        docker build -f infrastructure/docker/Dockerfile.${service} -t temp-${service}:scan .
                                        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \\
                                            aquasec/trivy image --exit-code 1 --severity HIGH,CRITICAL temp-${service}:scan || true
                                        docker rmi temp-${service}:scan
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Build Docker Images') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            parallel {
                stage('Build Ideas Service') {
                    steps {
                        container('docker') {
                            script {
                                def image = "${DOCKER_REGISTRY}/${DOCKER_REPO}/ideas-service:${VERSION}"
                                sh "docker build -f infrastructure/docker/Dockerfile.ideas -t ${image} ."
                                sh "docker tag ${image} ${DOCKER_REGISTRY}/${DOCKER_REPO}/ideas-service:latest"
                            }
                        }
                    }
                }
                stage('Build Voting Service') {
                    steps {
                        container('docker') {
                            script {
                                def image = "${DOCKER_REGISTRY}/${DOCKER_REPO}/voting-service:${VERSION}"
                                sh "docker build -f infrastructure/docker/Dockerfile.voting -t ${image} ."
                                sh "docker tag ${image} ${DOCKER_REGISTRY}/${DOCKER_REPO}/voting-service:latest"
                            }
                        }
                    }
                }
                stage('Build Analytics Service') {
                    steps {
                        container('docker') {
                            script {
                                def image = "${DOCKER_REGISTRY}/${DOCKER_REPO}/analytics-service:${VERSION}"
                                sh "docker build -f infrastructure/docker/Dockerfile.analytics -t ${image} ."
                                sh "docker tag ${image} ${DOCKER_REGISTRY}/${DOCKER_REPO}/analytics-service:latest"
                            }
                        }
                    }
                }
                stage('Build Decision Service') {
                    steps {
                        container('docker') {
                            script {
                                def image = "${DOCKER_REGISTRY}/${DOCKER_REPO}/decision-service:${VERSION}"
                                sh "docker build -f infrastructure/docker/Dockerfile.decision -t ${image} ."
                                sh "docker tag ${image} ${DOCKER_REGISTRY}/${DOCKER_REPO}/decision-service:latest"
                            }
                        }
                    }
                }
            }
        }

        stage('Push Images') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                container('docker') {
                    script {
                        docker.withRegistry("https://${DOCKER_REGISTRY}", "${DOCKER_REGISTRY_CREDENTIALS}") {
                            def services = ['ideas-service', 'voting-service', 'analytics-service', 'decision-service']
                            services.each { service ->
                                sh "docker push ${DOCKER_REGISTRY}/${DOCKER_REPO}/${service}:${VERSION}"
                                sh "docker push ${DOCKER_REGISTRY}/${DOCKER_REPO}/${service}:latest"
                            }
                        }
                    }
                }
            }
        }

        stage('Deploy to Staging') {
            when {
                branch 'develop'
            }
            steps {
                container('kubectl') {
                    script {
                        sh """
                            kubectl apply -f infrastructure/kubernetes/namespace.yaml
                            kubectl apply -f infrastructure/kubernetes/configmap.yaml -n mindmesh-staging
                            kubectl apply -f infrastructure/kubernetes/secrets.yaml -n mindmesh-staging
                            kubectl apply -f infrastructure/kubernetes/postgresql.yaml -n mindmesh-staging
                            kubectl apply -f infrastructure/kubernetes/redis.yaml -n mindmesh-staging
                            kubectl set image deployment/ideas-service ideas-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/ideas-service:${VERSION} -n mindmesh-staging
                            kubectl set image deployment/voting-service voting-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/voting-service:${VERSION} -n mindmesh-staging
                            kubectl set image deployment/analytics-service analytics-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/analytics-service:${VERSION} -n mindmesh-staging
                            kubectl set image deployment/decision-service decision-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/decision-service:${VERSION} -n mindmesh-staging
                            kubectl rollout status deployment/ideas-service -n mindmesh-staging --timeout=300s
                            kubectl rollout status deployment/voting-service -n mindmesh-staging --timeout=300s
                            kubectl rollout status deployment/analytics-service -n mindmesh-staging --timeout=300s
                            kubectl rollout status deployment/decision-service -n mindmesh-staging --timeout=300s
                        """
                    }
                }
            }
        }

        stage('Integration Tests') {
            when {
                branch 'develop'
            }
            steps {
                container('node') {
                    dir('tests/integration') {
                        sh 'npm ci'
                        sh 'npm run test:staging'
                    }
                }
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    input message: 'Deploy to Production?', ok: 'Deploy',
                          submitterParameter: 'APPROVER'
                }
                container('kubectl') {
                    script {
                        sh """
                            kubectl apply -f infrastructure/kubernetes/namespace.yaml
                            kubectl apply -f infrastructure/kubernetes/configmap.yaml -n mindmesh
                            kubectl apply -f infrastructure/kubernetes/secrets.yaml -n mindmesh
                            kubectl apply -f infrastructure/kubernetes/postgresql.yaml -n mindmesh
                            kubectl apply -f infrastructure/kubernetes/redis.yaml -n mindmesh
                            kubectl set image deployment/ideas-service ideas-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/ideas-service:${VERSION} -n mindmesh
                            kubectl set image deployment/voting-service voting-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/voting-service:${VERSION} -n mindmesh
                            kubectl set image deployment/analytics-service analytics-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/analytics-service:${VERSION} -n mindmesh
                            kubectl set image deployment/decision-service decision-service=${DOCKER_REGISTRY}/${DOCKER_REPO}/decision-service:${VERSION} -n mindmesh
                            kubectl rollout status deployment/ideas-service -n mindmesh --timeout=300s
                            kubectl rollout status deployment/voting-service -n mindmesh --timeout=300s
                            kubectl rollout status deployment/analytics-service -n mindmesh --timeout=300s
                            kubectl rollout status deployment/decision-service -n mindmesh --timeout=300s
                        """
                    }
                }
            }
        }

        stage('Post-Deployment Tests') {
            when {
                branch 'main'
            }
            steps {
                container('node') {
                    dir('tests/e2e') {
                        sh 'npm ci'
                        sh 'npm run test:production'
                    }
                }
            }
        }

        stage('Performance Tests') {
            when {
                branch 'main'
            }
            steps {
                container('node') {
                    dir('tests/performance') {
                        sh 'npm ci'
                        sh 'npm run test:production'
                    }
                }
            }
        }
    }

    post {
        always {
            publishTestResults testResultsPattern: '**/test-results.xml'
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: false,
                keepAll: true,
                reportDir: 'coverage',
                reportFiles: 'index.html',
                reportName: 'Coverage Report'
            ])
        }

        success {
            script {
                def message = """
                ✅ *MindMesh Deployment Successful*
                
                *Branch:* ${env.GIT_BRANCH}
                *Version:* ${VERSION}
                *Build:* ${env.BUILD_NUMBER}
                *Commit:* ${env.GIT_COMMIT.take(7)}
                
                *Deployed Services:*
                • Ideas Service
                • Voting Service  
                • Analytics Service
                • Decision Service
                
                *Environment:* ${env.GIT_BRANCH == 'main' ? 'Production' : 'Staging'}
                *Approved by:* ${env.APPROVER ?: 'Automated'}
                """
                
                sh "curl -X POST -H 'Content-type: application/json' --data '{\"text\":\"${message}\"}' ${SLACK_WEBHOOK}"
            }
        }

        failure {
            script {
                def message = """
                ❌ *MindMesh Deployment Failed*
                
                *Branch:* ${env.GIT_BRANCH}
                *Build:* ${env.BUILD_NUMBER}
                *Stage:* ${env.STAGE_NAME}
                *Commit:* ${env.GIT_COMMIT.take(7)}
                
                Please check the build logs for details.
                """
                
                sh "curl -X POST -H 'Content-type: application/json' --data '{\"text\":\"${message}\"}' ${SLACK_WEBHOOK}"
            }
        }

        cleanup {
            container('docker') {
                sh 'docker system prune -f'
            }
        }
    }
}