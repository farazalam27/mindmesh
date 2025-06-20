# Outputs for MindMesh Terraform Infrastructure

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

# EKS Outputs
output "cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_iam_role_name" {
  description = "IAM role name associated with EKS cluster"
  value       = module.eks.cluster_iam_role_name
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN associated with EKS cluster"
  value       = module.eks.cluster_iam_role_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_primary_security_group_id" {
  description = "Cluster security group that was created by Amazon EKS for the cluster"
  value       = module.eks.cluster_primary_security_group_id
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC Provider if enabled"
  value       = module.eks.oidc_provider_arn
}

# Node Group Outputs
output "eks_managed_node_groups" {
  description = "Map of attribute maps for all EKS managed node groups created"
  value       = module.eks.eks_managed_node_groups
}

output "eks_managed_node_groups_autoscaling_group_names" {
  description = "List of the autoscaling group names created by EKS managed node groups"
  value       = module.eks.eks_managed_node_groups_autoscaling_group_names
}

# RDS Outputs
output "db_instance_address" {
  description = "RDS instance hostname"
  value       = aws_db_instance.postgres.address
}

output "db_instance_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.postgres.arn
}

output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "db_instance_hosted_zone_id" {
  description = "RDS instance hosted zone ID"
  value       = aws_db_instance.postgres.hosted_zone_id
}

output "db_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.postgres.id
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.postgres.port
}

output "db_subnet_group_id" {
  description = "RDS subnet group ID"
  value       = aws_db_subnet_group.postgres.id
}

output "db_parameter_group_id" {
  description = "RDS parameter group ID"
  value       = aws_db_instance.postgres.parameter_group_name
}

# ElastiCache Outputs
output "redis_cluster_id" {
  description = "ElastiCache Redis cluster ID"
  value       = aws_elasticache_replication_group.redis.id
}

output "redis_cluster_arn" {
  description = "ElastiCache Redis cluster ARN"
  value       = aws_elasticache_replication_group.redis.arn
}

output "redis_primary_endpoint_address" {
  description = "Address of the endpoint for the primary node in the replication group"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint_address" {
  description = "Address of the endpoint for the reader node in the replication group"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_configuration_endpoint_address" {
  description = "Address of the replication group configuration endpoint when cluster mode is enabled"
  value       = try(aws_elasticache_replication_group.redis.configuration_endpoint_address, null)
}

output "redis_port" {
  description = "Port number on which each of the cache nodes will accept connections"
  value       = aws_elasticache_replication_group.redis.port
}

# S3 Outputs
output "s3_bucket_id" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.app_data.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.app_data.arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = aws_s3_bucket.app_data.bucket_domain_name
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.app_data.bucket_regional_domain_name
}

# CloudWatch Outputs
output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app_logs.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app_logs.arn
}

# Route53 Outputs
output "route53_zone_arn" {
  description = "Zone ARN of Route53 zone"
  value       = var.create_route53_zone ? aws_route53_zone.main[0].arn : null
}

output "route53_zone_id" {
  description = "Zone ID of Route53 zone"
  value       = var.create_route53_zone ? aws_route53_zone.main[0].zone_id : null
}

output "route53_zone_name_servers" {
  description = "Name servers of Route53 zone"
  value       = var.create_route53_zone ? aws_route53_zone.main[0].name_servers : null
}

# ACM Certificate Outputs
output "acm_certificate_arn" {
  description = "ARN of the certificate"
  value       = var.create_acm_certificate ? aws_acm_certificate.main[0].arn : null
}

output "acm_certificate_domain_name" {
  description = "Domain name for which the certificate is issued"
  value       = var.create_acm_certificate ? aws_acm_certificate.main[0].domain_name : null
}

output "acm_certificate_domain_validation_options" {
  description = "Set of domain validation objects which can be used to complete certificate validation"
  value       = var.create_acm_certificate ? aws_acm_certificate.main[0].domain_validation_options : null
}

# Security Group Outputs
output "postgres_security_group_id" {
  description = "ID of the PostgreSQL security group"
  value       = aws_security_group.postgres.id
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis.id
}

# IAM Outputs
output "eks_admin_role_arn" {
  description = "ARN of the EKS admin role"
  value       = aws_iam_role.eks_admin.arn
}

output "rds_monitoring_role_arn" {
  description = "ARN of the RDS monitoring role"
  value       = aws_iam_role.rds_monitoring.arn
}

# Kubectl Configuration
output "kubectl_config" {
  description = "kubectl config as generated by the module"
  value = {
    cluster_name                         = module.eks.cluster_id
    cluster_endpoint                     = module.eks.cluster_endpoint
    cluster_certificate_authority_data   = module.eks.cluster_certificate_authority_data
    cluster_region                       = var.aws_region
  }
}

# Connection Strings (sensitive)
output "postgres_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${var.db_name}"
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://:${var.redis_auth_token}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:${aws_elasticache_replication_group.redis.port}"
  sensitive   = true
}

# Environment Configuration
output "environment_config" {
  description = "Environment configuration for applications"
  value = {
    AWS_REGION                = var.aws_region
    ENVIRONMENT              = var.environment
    CLUSTER_NAME             = local.cluster_name
    
    # Database
    POSTGRES_HOST            = aws_db_instance.postgres.address
    POSTGRES_PORT            = aws_db_instance.postgres.port
    POSTGRES_DB              = var.db_name
    
    # Redis
    REDIS_HOST               = aws_elasticache_replication_group.redis.primary_endpoint_address
    REDIS_PORT               = aws_elasticache_replication_group.redis.port
    
    # S3
    S3_BUCKET                = aws_s3_bucket.app_data.id
    
    # CloudWatch
    LOG_GROUP                = aws_cloudwatch_log_group.app_logs.name
  }
}

# Tags
output "common_tags" {
  description = "Common tags applied to resources"
  value       = local.common_tags
}