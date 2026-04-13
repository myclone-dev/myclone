# LocalStack Deployment Guide

This guide explains how to set up and use LocalStack for local AWS S3 development using Docker Compose.

## Overview

LocalStack is a cloud service emulator that runs in a single container on your local machine. It provides a local testing environment for AWS services, specifically S3 in our case, without requiring actual AWS credentials or incurring costs.

## Architecture

Our LocalStack setup includes:
- **LocalStack Container**: Emulates AWS S3 service
- **Auto-initialization**: Automatically creates required S3 buckets on startup
- **Docker Compose Integration**: Runs alongside other application services
- **Environment Configuration**: Configurable bucket names and settings

## Prerequisites

- Docker and Docker Compose installed
- Project environment properly configured

## Configuration Files

### 1. Environment Configuration (`.env`)

Add these LocalStack-specific variables to your `.env` file:

```env
# LocalStack Configuration for Local AWS S3 Development
AWS_ENDPOINT_URL=http://myclone_localstack:4566
USER_DATA_BUCKET=myclone-user-data-local
AWS_DEFAULT_REGION=us-east-1
LOCALSTACK_HOSTNAME=myclone_localstack
```

### 2. Docker Compose Service

The LocalStack service is defined in `docker-compose.yml`:

```yaml
services:
  localstack:
    build:
      context: .
      dockerfile: docker/Dockerfile.localstack
    container_name: myclone_localstack
    ports:
      - "4566:4566"
    env_file:
      - .env
    volumes:
      - localstack_data:/var/lib/localstack
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 30s
      timeout: 10s
      retries: 5
```

### 3. Dockerfile Configuration

Located at `docker/Dockerfile.localstack`:

```dockerfile
FROM localstack/localstack:latest

ENV SERVICES=s3
ENV DEBUG=1
ENV DATA_DIR=/var/lib/localstack

COPY docker/localstack-init.sh /etc/localstack/init/ready.d/init-aws.sh
RUN chmod +x /etc/localstack/init/ready.d/init-aws.sh

EXPOSE 4566
```

### 4. Initialization Script

The `docker/localstack-init.sh` script automatically sets up S3 buckets:

```bash
#!/bin/bash
echo "Waiting for LocalStack to be ready..."
sleep 5

echo "Creating S3 bucket: ${USER_DATA_BUCKET}"
awslocal s3 mb s3://${USER_DATA_BUCKET}

echo "Listing S3 buckets:"
awslocal s3 ls

echo "LocalStack initialization complete!"
```

## Deployment

### Start All Services (Including LocalStack)

```bash
# Start all services in background
docker-compose up -d

# Or start with logs visible
docker-compose up
```

### Start Only LocalStack

```bash
# Start only LocalStack service
docker-compose up -d localstack
```

### Check LocalStack Status

```bash
# Check if LocalStack is healthy
docker-compose ps localstack

# View LocalStack logs
docker-compose logs localstack

# Check LocalStack health endpoint
curl http://localhost:4566/_localstack/health
```

## Usage

### Accessing LocalStack

- **From Host Machine**: `http://localhost:4566`
- **From Docker Containers**: `http://myclone_localstack:4566`
- **Health Check**: `http://localhost:4566/_localstack/health`

### S3 Operations

#### Using AWS CLI with LocalStack

```bash
# Install AWS CLI locally (if not already installed)
pip install awscli-local

# List buckets
awslocal s3 ls

# Upload a file
awslocal s3 cp myfile.txt s3://myclone-user-data-local/

# Download a file
awslocal s3 cp s3://myclone-user-data-local/myfile.txt ./downloaded-file.txt

# List objects in bucket
awslocal s3 ls s3://myclone-user-data-local/
```

#### From Application Code

Your application should use the environment variables from `.env`:

```python
import boto3
import os

# S3 client configured for LocalStack
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
    region_name=os.getenv('AWS_DEFAULT_REGION'),
    aws_access_key_id='test',  # LocalStack doesn't validate credentials
    aws_secret_access_key='test'
)

bucket_name = os.getenv('USER_DATA_BUCKET')
```

## Configuration Management

### Changing Bucket Name

To use a different S3 bucket name:

1. Update `.env`:
   ```env
   USER_DATA_BUCKET=my-custom-bucket-name
   ```

2. Restart LocalStack:
   ```bash
   docker-compose restart localstack
   ```

### Multiple Buckets

To create additional buckets, modify `docker/localstack-init.sh`:

```bash
# Add more bucket creation commands
awslocal s3 mb s3://${USER_DATA_BUCKET}
awslocal s3 mb s3://additional-bucket-name
awslocal s3 mb s3://another-bucket
```

## Troubleshooting

### Common Issues

1. **Port 4566 already in use**
   ```bash
   # Check what's using the port
   lsof -i :4566
   
   # Stop conflicting service or change port in docker-compose.yml
   ```

2. **LocalStack not ready**
   ```bash
   # Check LocalStack logs
   docker-compose logs localstack
   
   # Wait for initialization to complete
   curl http://localhost:4566/_localstack/health
   ```

3. **Bucket not created**
   ```bash
   # Check if initialization script ran
   docker-compose logs localstack | grep "Creating S3 bucket"
   
   # Manually create bucket
   awslocal s3 mb s3://myclone-user-data-local
   ```

### Debugging Commands

```bash
# Enter LocalStack container
docker-compose exec localstack bash

# Check LocalStack services
curl http://localhost:4566/_localstack/health

# View all environment variables
docker-compose exec localstack env

# Restart specific service
docker-compose restart localstack
```

## Data Persistence

LocalStack data is persisted using Docker volumes:

```bash
# View volume information
docker volume ls | grep localstack

# Backup LocalStack data
docker-compose stop localstack
docker run --rm -v myclone_localstack_data:/data -v $(pwd):/backup busybox tar czf /backup/localstack-backup.tar.gz -C /data .

# Restore LocalStack data
docker-compose stop localstack
docker run --rm -v myclone_localstack_data:/data -v $(pwd):/backup busybox tar xzf /backup/localstack-backup.tar.gz -C /data
docker-compose start localstack
```

## Integration with Other Services

### API Service Integration

The API service automatically connects to LocalStack when using the `.env` configuration:

```yaml
api:
  env_file:
    - .env  # LocalStack configuration is included here
  depends_on:
    - localstack       # LocalStack dependency is now included
```

### Development vs Production

- **Development**: Use LocalStack with appropriate `.env` variables
- **Production**: Use real AWS S3 with appropriate credentials

Switch between environments by changing the environment variables in your `.env` file.

## Security Notes

- LocalStack doesn't require real AWS credentials
- Data is stored locally and not sent to AWS
- Use dummy credentials like 'test'/'test' for AWS access keys
- Never commit real AWS credentials to version control

## Performance Considerations

- LocalStack uses more resources than real S3
- Good for testing but not for production workloads
- Consider using LocalStack Pro for better performance and additional services

## Next Steps

1. Start LocalStack with `docker-compose up -d`
2. Verify bucket creation with `awslocal s3 ls`
3. Test S3 operations from your application
4. Review logs for any issues: `docker-compose logs localstack`

For more advanced LocalStack features, refer to the [official LocalStack documentation](https://docs.localstack.cloud/).
