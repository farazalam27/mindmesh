# Variables for MindMesh Terraform Infrastructure

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "mindmesh"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnets" {
  description = "Private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

# EKS Configuration
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.27"
}

variable "node_instance_types" {
  description = "EC2 instance types for EKS nodes"
  type        = list(string)
  default     = ["t3.medium", "t3.large"]
}

variable "spot_instance_types" {
  description = "EC2 instance types for EKS spot nodes"
  type        = list(string)
  default     = ["t3.medium", "t3.large", "t3.xlarge"]
}

variable "node_group_min_size" {
  description = "Minimum number of nodes in the node group"
  type        = number
  default     = 2
}

variable "node_group_max_size" {
  description = "Maximum number of nodes in the node group"
  type        = number
  default     = 10
}

variable "node_group_desired_size" {
  description = "Desired number of nodes in the node group"
  type        = number
  default     = 3
}

# RDS Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS instance"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS instance"
  type        = number
  default     = 1000
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "mindmesh"
}

variable "db_username" {
  description = "Username for the database"
  type        = string
  default     = "mindmesh_user"
}

variable "db_password" {
  description = "Password for the database"
  type        = string
  sensitive   = true
}

variable "db_backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 2
}

variable "redis_auth_token" {
  description = "Auth token for Redis"
  type        = string
  sensitive   = true
}

# Domain and SSL Configuration
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "mindmesh.com"
}

variable "create_route53_zone" {
  description = "Whether to create Route53 hosted zone"
  type        = bool
  default     = false
}

variable "create_acm_certificate" {
  description = "Whether to create ACM certificate"
  type        = bool
  default     = false
}

# Logging Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# AWS Auth Configuration
variable "aws_auth_users" {
  description = "List of IAM users to add to aws-auth configmap"
  type = list(object({
    userarn  = string
    username = string
    groups   = list(string)
  }))
  default = []
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Monitoring Configuration
variable "enable_cloudwatch_monitoring" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "enable_prometheus_monitoring" {
  description = "Enable Prometheus monitoring"
  type        = bool
  default     = true
}

# Security Configuration
variable "enable_guardduty" {
  description = "Enable AWS GuardDuty"
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Enable AWS Security Hub"
  type        = bool
  default     = true
}

# Backup Configuration
variable "enable_backup" {
  description = "Enable AWS Backup"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Backup retention period in days"
  type        = number
  default     = 30
}

# Cost Optimization
variable "enable_spot_instances" {
  description = "Enable spot instances for cost optimization"
  type        = bool
  default     = true
}

variable "enable_scheduled_scaling" {
  description = "Enable scheduled scaling for cost optimization"
  type        = bool
  default     = true
}