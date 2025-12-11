# Deployment Guide

## Enterprise PDF Translation Service Deployment

This guide covers deployment options for the PDF Translation Service with real-time streaming capabilities in various environments.

## Production Optimizations (v2.0)

### Performance Features
- **Real-Time Streaming**: Server-Sent Events for live translation feedback
- **Optimized Logging**: Minimal production logging for EC2 deployment
- **Background Processing**: Non-blocking S3 uploads and document generation
- **Memory Optimization**: Efficient handling of concurrent users and large documents
- **Retry Logic**: Fixed duplicate processing issues with proper retry loop handling

## Prerequisites

### System Requirements
- **Python**: 3.11 or higher
- **Memory**: Minimum 2GB RAM (4GB recommended for production)
- **Storage**: 10GB available space (more for S3 file caching)
- **Network**: Stable internet connection for AWS Bedrock API calls

### AWS Requirements
- **AWS Account** with Bedrock access enabled
- **IAM Permissions** for Bedrock Runtime and S3
- **S3 Bucket** for file storage (optional but recommended)
- **AWS CLI** configured with appropriate credentials

### Required AWS IAM Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

---

## Local Development Deployment

### 1. Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd pdf-translation-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. AWS Configuration
```bash
# Configure AWS CLI
aws configure
# Enter your AWS Access Key ID, Secret Access Key, Region, and Output format

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1

# Create S3 bucket (optional)
aws s3 mb s3://your-bucket-name
```

### 3. Environment Variables
```bash
# Create .env file
cat > .env << EOF
BUCKET_NAME=pnb-poc-docs
MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
AWS_DEFAULT_REGION=us-east-1
EOF

# Load environment variables
export $(cat .env | xargs)
```

### 4. Run Development Server
```bash
# Start the service
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Access the web interface
open http://localhost:8000
```

---

## Docker Deployment

### 1. Build Docker Image
```bash
# Build the container
docker build -t pdf-translator .

# Verify image
docker images | grep pdf-translator
```

### 2. Run Docker Container
```bash
# Run with environment variables
docker run -d \
  --name pdf-translator \
  -p 8000:8000 \
  -e BUCKET_NAME="pnb-poc-docs" \
  -e MODEL_ID="global.anthropic.claude-opus-4-5-20251101-v1:0" \
  -e AWS_ACCESS_KEY_ID="your-access-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret-key" \
  -e AWS_DEFAULT_REGION="us-east-1" \
  pdf-translator

# Check container status
docker ps
docker logs pdf-translator

# Test the service
curl http://localhost:8000/health
```

### 3. Docker Compose (Recommended)
```yaml
# docker-compose.yml
version: '3.8'

services:
  pdf-translator:
    build: .
    ports:
      - "8000:8000"
    environment:
      - BUCKET_NAME=pnb-poc-docs
      - MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_DEFAULT_REGION=us-east-1
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
# Deploy with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Scale service (if needed)
docker-compose up -d --scale pdf-translator=3
```

---

## Cloud Deployment

### AWS ECS Deployment

#### 1. Create ECS Task Definition
```json
{
  "family": "pdf-translator",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/pdf-translator-task-role",
  "containerDefinitions": [
    {
      "name": "pdf-translator",
      "image": "your-account.dkr.ecr.region.amazonaws.com/pdf-translator:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "BUCKET_NAME",
          "value": "pnb-poc-docs"
        },
        {
          "name": "MODEL_ID",
          "value": "global.anthropic.claude-opus-4-5-20251101-v1:0"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/pdf-translator",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

#### 2. Deploy to ECS
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com

docker build -t pdf-translator .
docker tag pdf-translator:latest your-account.dkr.ecr.us-east-1.amazonaws.com/pdf-translator:latest
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/pdf-translator:latest

# Create ECS service
aws ecs create-service \
  --cluster your-cluster \
  --service-name pdf-translator \
  --task-definition pdf-translator:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

### AWS Lambda Deployment (Serverless)

#### 1. Create Lambda Function
```python
# lambda_handler.py
import json
import base64
from app import app
from mangum import Mangum

handler = Mangum(app)

def lambda_handler(event, context):
    return handler(event, context)
```

#### 2. Package for Lambda
```bash
# Install dependencies in package directory
pip install -r requirements.txt -t package/
cp app.py pdf_generator.py docx_generator.py lambda_handler.py package/

# Create deployment package
cd package
zip -r ../deployment-package.zip .
cd ..

# Deploy to Lambda
aws lambda create-function \
  --function-name pdf-translator \
  --runtime python3.11 \
  --role arn:aws:iam::account:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://deployment-package.zip \
  --timeout 300 \
  --memory-size 2048 \
  --environment Variables='{BUCKET_NAME=pnb-poc-docs,MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0}'
```

---

## Production Deployment Considerations

### 1. Security
```bash
# Use AWS Secrets Manager for sensitive data
aws secretsmanager create-secret \
  --name pdf-translator/config \
  --description "PDF Translator configuration" \
  --secret-string '{"BUCKET_NAME":"pnb-poc-docs","MODEL_ID":"global.anthropic.claude-opus-4-5-20251101-v1:0"}'

# Use IAM roles instead of access keys
# Implement VPC security groups
# Enable HTTPS with SSL certificates
```

### 2. Monitoring & Logging
```bash
# CloudWatch Logs
aws logs create-log-group --log-group-name /aws/ecs/pdf-translator

# CloudWatch Metrics
aws cloudwatch put-metric-alarm \
  --alarm-name pdf-translator-high-cpu \
  --alarm-description "High CPU usage" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### 3. Load Balancing
```yaml
# Application Load Balancer configuration
apiVersion: v1
kind: Service
metadata:
  name: pdf-translator-service
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 8000
  selector:
    app: pdf-translator
```

### 4. Auto Scaling
```bash
# ECS Auto Scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/your-cluster/pdf-translator \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --policy-name pdf-translator-scale-up \
  --service-namespace ecs \
  --resource-id service/your-cluster/pdf-translator \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

---

## Environment-Specific Configurations

### Development
```bash
# .env.development
BUCKET_NAME=pnb-poc-docs-dev
MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
LOG_LEVEL=DEBUG
AWS_DEFAULT_REGION=us-east-1
```

### Staging
```bash
# .env.staging
BUCKET_NAME=pnb-poc-docs-staging
MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
LOG_LEVEL=INFO
AWS_DEFAULT_REGION=us-east-1
```

### Production
```bash
# .env.production
BUCKET_NAME=pnb-poc-docs-prod
MODEL_ID=global.anthropic.claude-opus-4-5-20251101-v1:0
LOG_LEVEL=WARNING
AWS_DEFAULT_REGION=us-east-1
```

---

## Health Checks & Monitoring

### Application Health Checks
```bash
# Basic health check
curl -f http://localhost:8000/health

# Detailed S3 status
curl -f http://localhost:8000/s3-status

# Test S3 upload functionality
curl -X POST http://localhost:8000/test-s3
```

### Monitoring Script
```bash
#!/bin/bash
# monitor.sh

SERVICE_URL="http://localhost:8000"
LOG_FILE="/var/log/pdf-translator-monitor.log"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Health check
    if curl -f -s "$SERVICE_URL/health" > /dev/null; then
        echo "$TIMESTAMP - Service is healthy" >> $LOG_FILE
    else
        echo "$TIMESTAMP - Service health check failed" >> $LOG_FILE
        # Send alert (email, Slack, etc.)
    fi
    
    # S3 status check
    S3_STATUS=$(curl -s "$SERVICE_URL/s3-status" | jq -r '.status')
    echo "$TIMESTAMP - S3 Status: $S3_STATUS" >> $LOG_FILE
    
    sleep 300  # Check every 5 minutes
done
```

---

## Backup & Recovery

### S3 Backup Strategy
```bash
# Enable S3 versioning
aws s3api put-bucket-versioning \
  --bucket pnb-poc-docs \
  --versioning-configuration Status=Enabled

# Setup lifecycle policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket pnb-poc-docs \
  --lifecycle-configuration file://lifecycle-policy.json

# Cross-region replication
aws s3api put-bucket-replication \
  --bucket pnb-poc-docs \
  --replication-configuration file://replication-config.json
```

### Database Backup (if applicable)
```bash
# Backup application logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz /var/log/pdf-translator/

# Backup configuration
cp -r .kiro/steering/ backup/steering-$(date +%Y%m%d)/
```

---

## Troubleshooting

### Common Deployment Issues

1. **Container fails to start**
   ```bash
   # Check container logs
   docker logs pdf-translator
   
   # Verify environment variables
   docker exec pdf-translator env | grep -E "(BUCKET_NAME|MODEL_ID|AWS_)"
   ```

2. **AWS permissions issues**
   ```bash
   # Test AWS credentials
   aws sts get-caller-identity
   
   # Test Bedrock access
   aws bedrock list-foundation-models --region us-east-1
   
   # Test S3 access
   aws s3 ls s3://pnb-poc-docs/
   ```

3. **Performance issues**
   ```bash
   # Monitor resource usage
   docker stats pdf-translator
   
   # Check application metrics
   curl http://localhost:8000/health
   ```

### Performance Tuning
- Increase memory allocation for large documents
- Use SSD storage for temporary file processing
- Implement connection pooling for AWS services
- Consider using AWS Lambda for variable workloads
- Monitor and optimize Bedrock API call patterns