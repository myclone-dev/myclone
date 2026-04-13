#!/bin/bash

# LocalStack initialization script
# This script runs when LocalStack is ready and sets up the S3 bucket

echo "Waiting for LocalStack to be ready..."
sleep 5

echo "Creating S3 bucket: ${USER_DATA_BUCKET}"
awslocal s3 mb s3://${USER_DATA_BUCKET}

echo "Listing S3 buckets:"
awslocal s3 ls

echo "LocalStack initialization complete!"
