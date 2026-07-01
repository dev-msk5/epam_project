
---

# 🚀 AWS EC2 + SSM Deployment Guide

This guide will walk you through deploying our FastAPI Project Dashboard onto an AWS EC2 instance. We will use AWS Systems Manager (SSM) Parameter Store to securely manage our environment variables, and Docker Compose to run our application and database.

---

## Part 1: AWS Setup (The Cloud Infrastructure)

### Step 1: Create an S3 Bucket for Document Storage
Our application stores PDF and Word documents in Amazon S3.
1. Open the **AWS Console** and search for **S3**.
2. Click **Create bucket**.
3. **Bucket name**: Enter a unique name (e.g., `my-project-dashboard-storage-unique`). **Remember this name!**
4. **AWS Region**: Select `us-east-1` (or your preferred region).
5. Leave everything else as default, scroll to the bottom, and click **Create bucket**.

---

### Step 2: Create an IAM Instance Profile (Role) for EC2
We must give our EC2 instance permission to fetch configurations from SSM Parameter Store and upload files to S3 *without* hardcoding AWS access keys on the server.
1. Open the **AWS Console** and search for **IAM**.
2. Click **Roles** on the left menu, then click **Create role**.
3. Under *Trusted entity type*, select **AWS service**. Under *Service or use case*, select **EC2**. Click **Next**.
4. Search for and check the boxes next to these policies:
   * **`AmazonSSMManagedInstanceCore`** (Allows the SSM Agent to register and execute commands securely)
   * **`AmazonS3FullAccess`** (Allows your app to upload/download files to S3)
5. Click **Next**.
6. **Role name**: Enter `EC2-Dashboard-App-Role`.
7. Scroll down and click **Create role**.

---

### Step 3: Launch your EC2 Instance
1. Search for **EC2** in the AWS Console.
2. Click **Launch instance**.
3. **Name**: `project-dashboard-server`.
4. **Application and OS Image (AMI)**: Choose **Amazon Linux 2023** (This is free-tier eligible and default).
5. **Instance type**: Choose `t2.micro` (Free tier).
6. **Key pair**: Click **Create new key pair**.
   * Name it `dashboard-key`.
   * Keep type as `RSA` and private key format as `.pem`.
   * Click **Create key pair**. A file named `dashboard-key.pem` will automatically download to your computer. **Keep this file safe!**
7. **Network Settings (Security Group)**:
   * Check **Allow SSH traffic from** (select "Anywhere" or "My IP" for security).
   * Check **Allow HTTP traffic from the internet**.
8. Under **Advanced details** (scroll to the bottom):
   * **IAM instance profile**: Select the `EC2-Dashboard-App-Role` we created in Step 2.
9. Click **Launch instance**.

---

### Step 4: Assign an Elastic IP (Static IP)
By default, EC2 IP addresses change every time you reboot the server. We need a permanent IP address.
1. On the left sidebar of the EC2 Dashboard, click **Elastic IPs** (under *Network & Security*).
2. Click **Allocate Elastic IP address**, then click **Allocate** at the bottom.
3. Select your newly created Elastic IP from the list.
4. Click **Actions** -> **Associate Elastic IP address**.
5. **Instance**: Click the box and select your running `project-dashboard-server` instance.
6. Click **Associate**.

---

### Step 5: Edit Inbound Security Rules to Open Port 8000
Our FastAPI application runs on port `8000`. We need to tell AWS to let web traffic access this port.
1. In the EC2 console, go to **Instances** and click on your running instance.
2. Select the **Security** tab at the bottom, then click on your **Security Group** (e.g., `sg-0xxxxxxxx`).
3. Click **Edit inbound rules**.
4. Click **Add rule**:
   * **Type**: `Custom TCP`
   * **Port Range**: `8000`
   * **Source**: `Anywhere-IPv4` (`0.0.0.0/0`)
5. Click **Save rules**.

---

### Step 6: Fix the Docker IMDSv2 Hop Limit (Crucial!)
Because Docker containers run inside a virtual network, requests from inside a container to AWS metadata services count as an extra network "hop." AWS security blocks this by default. 
To fix this, run this AWS CLI command **on your local machine** (where your AWS CLI is configured with administrative permissions) or use the AWS CloudShell in your browser:

```bash
aws ec2 modify-instance-metadata-options \
    --instance-id <YOUR_EC2_INSTANCE_ID> \
    --http-put-response-hop-limit 2 \
    --http-endpoint enabled \
    --region us-east-1
```
*(Replace `<YOUR_EC2_INSTANCE_ID>` with your instance ID, e.g., `i-0123456789abcdef0`)*

---

### Step 7: Configure SSM Parameter Store
We will store all application configurations securely in AWS Systems Manager.
1. Search for **Systems Manager** in the AWS Console.
2. On the left sidebar, click **Parameter Store**, then click **Create parameter**.
3. Create the following parameters **exactly** as specified (be careful with case-sensitivity!):

| Name | Type | Value (Example) |
| :--- | :--- | :--- |
| `/project-dashboard/prod/DB_USER` | `String` | `postgres` |
| `/project-dashboard/prod/DB_PASSWORD` | `SecureString` | `choose_a_strong_password_123` |
| `/project-dashboard/prod/DB_NAME` | `String` | `project_db` |
| `/project-dashboard/prod/DATABASE_URL` | `SecureString` | `postgresql+asyncpg://postgres:choose_a_strong_password_123@db:5432/project_db` |
| `/project-dashboard/prod/SECRET_KEY` | `SecureString` | *Enter a random, long, secure string for JWT generation* |
| `/project-dashboard/prod/ACCESS_TOKEN_EXPIRE_MINUTES` | `String` | `60` |
| `/project-dashboard/prod/S3_BUCKET_NAME` | `String` | *Insert your S3 bucket name from Step 1* |

> ⚠️ **Critical Rule**: The names of these parameters after the `/` **must** match your Pydantic settings attributes in `config.py` (e.g., `/project-dashboard/prod/SECRET_KEY` matches `SECRET_KEY`). If they are misspelled or in lowercase, the application will crash.

---

## Part 2: Connecting and Preparing the EC2 Server

### Step 1: SSH into your EC2 Instance
Open **PowerShell** (on Windows) or **Terminal** (on Mac/Linux) and navigate to the folder where your `dashboard-key.pem` file was downloaded.

1. **Set permissions for the key** (Only required on Windows PowerShell):
   ```powershell
   icacls.exe .\dashboard-key.pem /grant:r "$($env:USERNAME):(R)"
   icacls.exe .\dashboard-key.pem /inheritance:r
   ```
   *(If on Mac/Linux, run: `chmod 400 dashboard-key.pem`)*

2. **Run the SSH command to enter your server**:
   ```powershell
   ssh -i .\dashboard-key.pem ec2-user@<YOUR_ELASTIC_IP>
   ```
   *(Replace `<YOUR_ELASTIC_IP>` with the public IP you set up in Part 1, Step 4).*
   *Type `yes` when prompted to confirm the connection.*

---

### Step 2: Install Docker and Docker Compose on EC2
Once you are logged into the EC2 instance, install Docker by pasting these commands:

```bash
# 1. Update the system package list
sudo dnf update -y

# 2. Install Docker
sudo dnf install docker -y

# 3. Start the Docker service and configure it to run on boot
sudo systemctl start docker
sudo systemctl enable docker

# 4. Give your current system user permission to run Docker without sudo
sudo usermod -aG docker ec2-user

# 5. Install the Docker Compose plugin
sudo dnf install docker-compose-plugin -y
```

> 🔄 **Crucial**: After running the `usermod` command, you must disconnect and reconnect to the server to apply the permissions:
> 1. Type `exit` to disconnect.
> 2. Run your SSH command again: `ssh -i .\dashboard-key.pem ec2-user@<YOUR_ELASTIC_IP>`

---

### Step 3: Upgrade Docker Buildx (To prevent buildx version errors)
Our Dockerfile relies on modern build steps. Upgrade the Buildx CLI plugin with these commands:

```bash
# Create the local directory for CLI plugins
mkdir -p ~/.docker/cli-plugins

# Download the latest Buildx v0.17.1 release binary
curl -SL https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64 -o ~/.docker/cli-plugins/docker-buildx

# Make the file executable
chmod +x ~/.docker/cli-plugins/docker-buildx

# Verify that buildx is 0.17.0 or newer
docker buildx version
```

---

## Part 3: Cloned Code and First-time Run

### Step 1: Clone your Codebase
Now, pull down your project files directly from GitHub onto your EC2 server:

```bash
# Clone the repository
git clone <YOUR_GITHUB_REPOSITORY_URL>

# Enter the project root directory
cd project-dashboard
```

---

### Step 2: Fetch SSM Variables and Generate the `.env` File
Docker Compose needs access to your database variables to boot up PostgreSQL. We can fetch our secure SSM parameters and generate a hidden `.env` file on our server with a single command:

```bash
aws ssm get-parameters-by-path \
  --path "/project-dashboard/prod/" \
  --with-decryption \
  --query "Parameters[*].[Name,Value]" \
  --output text \
  --region us-east-1 | sed 's|/project-dashboard/prod/||g' | awk '{print $1 "=" $2}' > .env
```

*To verify that your environment variables were successfully retrieved and written, run `cat .env`.*

---

### Step 3: Fix Logging Folder Ownership (To prevent startup crash)
Our application writes logs inside `/app/logs`. We need to create this folder on the host and assign permissions so the container can write to it:

```bash
# Create the host logs directory
mkdir -p ./logs

# Set ec2-user as the owner of this folder
sudo chown -R $USER:$USER ./logs

# Give read, write, and execute permissions
chmod -R 775 ./logs
```

---

### Step 4: Build and Boot Your Containers!
You are now ready to launch the entire environment!

```bash
# Build and run the app in background detached mode (-d)
docker compose up -d --build
```

To watch the application boot up and verify that everything loads perfectly:
```bash
docker compose logs -f app
```
*You should see uvicorn start up and log: `Uvicorn running on http://0.0.0.0:8000`.*

---

### Step 5: Run Database Migrations (Alembic)
Since this is a fresh database, run our Alembic migrations inside the running Docker container to create the database schemas and tables:

```bash
docker compose exec app alembic upgrade head
```

---

## Part 4: Verification

1. Open your web browser.
2. Navigate to your address:
   ```text
   http://<YOUR_ELASTIC_IP>:8000/docs
   ```
3. You will see the interactive **Swagger UI documentation**!
4. Expand the `/auth` registration route, click **Try it out**, enter details, and execute. If you get a green response code, **congratulations! Your project is securely running on AWS EC2!** 🎉

---

Please let me know if any steps need further refinement, or if you'd like to dive into the **S3 document upload/download service integration** or the **AWS Lambda S3-event processor** code!