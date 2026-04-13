# CI/CD Auto-Deployment Setup Guide

This guide explains how to set up automated deployment to EC2 when pushing to the `main` branch.

## Overview

The deployment workflow automatically:

1. ✅ Triggers on push to `main` branch
2. ✅ Connects to your EC2 instance via SSH
3. ✅ Pulls latest code from `main`
4. ✅ Builds the backend Docker image
5. ✅ Restarts the backend service (migrations run automatically via entrypoint.sh)
6. ✅ Verifies deployment health
7. ✅ Shows logs for debugging

**Note:** Database migrations are handled automatically by the Docker entrypoint script ([docker/entrypoint.sh](../../docker/entrypoint.sh)), so no separate migration step is needed in the CI/CD workflow.

## Required GitHub Secrets

You need to configure the following secrets in your GitHub repository:

### 1. `EC2_SSH_PRIVATE_KEY`

Your EC2 instance's SSH private key (`.pem` file content)

**How to get it:**

```bash
# If you have the .pem file locally
cat /path/to/your-key.pem
```

**Format:** Full content of the PEM file including:

```
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
...
-----END RSA PRIVATE KEY-----
```

### 2. `EC2_HOST`

Your EC2 instance's public IP address or DNS hostname

**Example:**

```
ec2-xx-xxx-xxx-xxx.compute-1.amazonaws.com
```

or

```
xx.xxx.xxx.xxx
```

**How to get it:**

- AWS Console → EC2 → Instances → Select your instance
- Copy the "Public IPv4 address" or "Public IPv4 DNS"

### 3. `EC2_USER`

SSH username for your EC2 instance

**Common values:**

- Ubuntu AMI: `ubuntu`
- Amazon Linux: `ec2-user`
- Other: depends on your AMI

**Example:**

```
ubuntu
```

### 4. `EC2_REPO_PATH`

Absolute path to your repository on the EC2 instance

**Example:**

```
/home/ubuntu/expert-clone
```

**How to get it:**

```bash
# SSH to your EC2 and run:
cd /path/to/your/repo
pwd
```

## How to Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each of the 4 secrets above

Example:

- **Name:** `EC2_SSH_PRIVATE_KEY`
- **Value:** [paste your PEM file content]

## EC2 Instance Requirements

Your EC2 instance must have:

### 1. Git Repository Setup

```bash
# Repository should be cloned on EC2
cd /home/ubuntu  # or your preferred directory
git clone https://github.com/myclone-dev/myclone.git
cd expert-clone
```

### 2. Docker & Docker Compose Installed

```bash
# Verify installation
docker --version
docker-compose --version
```

### 3. Repository Should Be on Main Branch

```bash
cd /path/to/your/repo
git checkout main
```

### 4. SSH Key Authentication for Git (Recommended)

To avoid password prompts during `git pull`:

```bash
# Generate SSH key on EC2
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add public key to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and add to GitHub: Settings → SSH and GPG keys → New SSH key

# Test connection
ssh -T git@github.com

# Update remote to use SSH (if using HTTPS)
git remote set-url origin git@github.com:myclone-dev/myclone.git
```

### 5. Environment Variables

Ensure `.env` file exists on EC2 with all required variables:

```bash
cd /path/to/your/repo
cat .env  # Verify it exists and has all required vars
```

### 6. GitHub Runner IP Whitelisting (if applicable)

If your EC2 has strict security groups, you may need to allow GitHub Actions IP ranges:

- See: https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#ip-addresses

Or use a self-hosted runner (recommended for production).

## Testing the Deployment

### 1. Test SSH Connection Locally First

```bash
# Test if you can SSH with your key
ssh -i /path/to/your-key.pem ubuntu@your-ec2-host

# Test deployment commands manually
cd /path/to/repo
git pull origin main
docker-compose build backend
docker-compose up -d backend
docker-compose logs -f backend
```

### 2. Make a Test Commit to Main

```bash
# Make a small change
echo "# Test deployment" >> README.md
git add README.md
git commit -m "test: trigger deployment"
git push origin main
```

### 3. Monitor GitHub Actions

- Go to your GitHub repository
- Click **Actions** tab
- Watch the "Auto Deploy to EC2" workflow run
- Check logs for any errors

## Workflow Features

### 🎯 Smart Triggering

- Only triggers on `main` branch pushes
- Ignores changes to:
  - Markdown files (`**.md`)
  - Claude workflow files
  - Test files (`tests/**`)

### 🔒 Security

- SSH key is stored securely in GitHub Secrets
- Key is temporarily written and immediately deleted
- No sensitive data exposed in logs

### 🏥 Health Checks

- Waits for backend to start
- Verifies container health status
- Shows logs automatically

### 📊 Error Handling

- Stops on first error (`set -e`)
- Shows detailed error logs on failure
- Clear success/failure indicators

## Troubleshooting

### Issue: "Permission denied (publickey)"

**Solution:**

- Verify `EC2_SSH_PRIVATE_KEY` is correct and complete
- Check `EC2_USER` matches your AMI (ubuntu, ec2-user, etc.)
- Ensure SSH key has correct permissions on EC2 (chmod 600)

### Issue: "docker-compose: command not found"

**Solution:**

```bash
# Install docker-compose on EC2
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Issue: Git pull fails with authentication error

**Solution:** Set up SSH key authentication for Git (see section 4 above)

### Issue: Container fails to start

**Solution:**

- Check `.env` file exists and has all required variables
- Review logs: `docker-compose logs backend`
- Verify database is accessible from EC2

### Issue: Deployment succeeds but app not accessible

**Solution:**

- Check security group allows inbound traffic on port 8001
- Verify `HOST_PORT` in `.env` or docker-compose.yml
- Check if backend is listening: `docker-compose exec backend curl localhost:8001/api/v1/health`

## Rolling Back a Failed Deployment

If deployment fails and app is broken:

```bash
# SSH to EC2
ssh -i your-key.pem ubuntu@your-ec2-host

# Navigate to repo
cd /path/to/repo

# Rollback to previous commit
git log --oneline -5  # Find previous working commit
git reset --hard <commit-hash>

# Rebuild and restart
docker-compose build backend
docker-compose up -d backend
docker-compose logs -f backend
```

## Advanced: Multiple Environments

To deploy to staging/production separately:

1. Create separate workflows:

   - `.github/workflows/deploy-staging.yml` (triggers on `staging` branch)
   - `.github/workflows/deploy-production.yml` (triggers on `main` branch)

2. Use different secrets:
   - `STAGING_EC2_HOST`, `PROD_EC2_HOST`
   - `STAGING_EC2_USER`, `PROD_EC2_USER`
   - etc.

## Monitoring Deployments

### View Deployment History

- GitHub repository → Actions tab
- Filter by workflow: "Auto Deploy to EC2"

### View Live Logs on EC2

```bash
ssh -i your-key.pem ubuntu@your-ec2-host
cd /path/to/repo
docker-compose logs -f backend
```

### Check Container Status

```bash
docker-compose ps
docker-compose exec backend curl localhost:8001/api/v1/health
```

## Next Steps

After setup is complete:

1. ✅ Test deployment with a dummy commit
2. ✅ Monitor logs for any issues
3. ✅ Set up error notifications (Slack, email, etc.)
4. ✅ Consider blue-green deployment for zero-downtime updates

---

**Need Help?** Check the workflow logs in GitHub Actions for detailed error messages.
