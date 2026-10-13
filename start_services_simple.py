#!/usr/bin/env python3

import subprocess
import sys
import time
import os
import signal
from typing import List, Dict

class ServiceManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.services = {
            "ideas": {"port": 8001, "path": "ideas_service/main.py"},
            "voting": {"port": 8002, "path": "voting_service/main.py"},  
            "decision": {"port": 8003, "path": "decision_service/main.py"},
            "analytics": {"port": 8004, "path": "analytics_service/main.py"}
        }

    def start_infrastructure(self):
        """Start PostgreSQL and Redis using Docker Compose"""
        print("🚀 Starting infrastructure (PostgreSQL & Redis)...")
        try:
            result = subprocess.run([
                "docker-compose", "up", "-d", "postgres", "redis"
            ], check=True, capture_output=True, text=True)
            print("✅ Infrastructure started successfully")
            
            # Wait for services to be ready
            print("⏳ Waiting for database to be ready...")
            time.sleep(5)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start infrastructure: {e}")
            print(f"stderr: {e.stderr}")
            sys.exit(1)

    def check_service_health(self, service_name: str, port: int) -> bool:
        """Check if a service is healthy"""
        try:
            import requests
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def start_service(self, service_name: str, service_config: Dict) -> subprocess.Popen:
        """Start a single service"""
        print(f"🚀 Starting {service_name} service on port {service_config['port']}...")
        
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            f"{service_config['path'].replace('/', '.').replace('.py', '')}:app",
            "--host", "0.0.0.0",
            "--port", str(service_config['port']),
            "--reload"
        ], env=env)
        
        return process

    def wait_for_service(self, service_name: str, port: int, timeout: int = 30):
        """Wait for service to be ready"""
        print(f"⏳ Waiting for {service_name} service to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.check_service_health(service_name, port):
                print(f"✅ {service_name} service is ready")
                return True
            time.sleep(1)
        
        print(f"⚠️  {service_name} service health check failed, but continuing...")
        return False

    def start_all_services(self):
        """Start all services"""
        print("🚀 Starting MindMesh services...")
        
        for service_name, config in self.services.items():
            process = self.start_service(service_name, config)
            self.processes.append(process)
            time.sleep(2)  # Stagger startup
            
        # Wait for all services to be ready
        for service_name, config in self.services.items():
            self.wait_for_service(service_name, config['port'])

    def stop_all_services(self):
        """Stop all services"""
        print("\n🛑 Stopping all services...")
        
        for process in self.processes:
            if process.poll() is None:  # Process is still running
                process.terminate()
                
        # Wait for graceful shutdown
        time.sleep(2)
        
        # Force kill if necessary
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                
        print("✅ All services stopped")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n📡 Received signal {signum}")
        self.stop_all_services()
        sys.exit(0)

    def run(self):
        """Main execution"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Start infrastructure
            self.start_infrastructure()
            
            # Start all services
            self.start_all_services()
            
            print("\n🎉 All services started successfully!")
            print("📊 Service URLs:")
            for service_name, config in self.services.items():
                print(f"  • {service_name.capitalize()}: http://localhost:{config['port']}")
            
            print("\n🏥 Health check all services:")
            for service_name, config in self.services.items():
                health_url = f"http://localhost:{config['port']}/health"
                print(f"  • {health_url}")
            
            print("\n📖 API Documentation:")
            for service_name, config in self.services.items():
                docs_url = f"http://localhost:{config['port']}/docs"
                print(f"  • {service_name.capitalize()}: {docs_url}")
            
            print("\n🛑 Press Ctrl+C to stop all services")
            
            # Keep the script running
            while True:
                # Check if any process has died
                for i, process in enumerate(self.processes):
                    if process.poll() is not None:
                        service_name = list(self.services.keys())[i]
                        print(f"⚠️  {service_name} service has stopped unexpectedly")
                        
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            self.stop_all_services()
        except Exception as e:
            print(f"❌ Error: {e}")
            self.stop_all_services()
            sys.exit(1)

if __name__ == "__main__":
    print("🧠 MindMesh Service Manager")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("ideas_service"):
        print("❌ Please run this script from the mindmesh root directory")
        sys.exit(1)
    
    # Check if Docker is running
    try:
        subprocess.run(["docker", "version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ Docker is not running. Please start Docker first.")
        sys.exit(1)
    
    manager = ServiceManager()
    manager.run()