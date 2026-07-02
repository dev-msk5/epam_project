

# README: Secure Temporary Application Sharing via SSH Tunneling (Amazon Linux 2023)

This guide outlines how to use **SSH Local Port Forwarding** to securely share your Docker-hosted FastAPI app (`127.0.0.1:8000`) with your mentor. 

This is the most secure sharing method. It requires **zero web ports** to be opened to the public internet, and it automatically **encrypts all traffic** inside an SSH tunnel.

---

## 🛠️ Step 1: Configuration on Your EC2 Instance (Amazon Linux 2023)

To let your mentor tunnel into your EC2, you must temporarily add their SSH public key to your instance's authorized keys list.

### 1. Register Your Mentor's SSH Key
Log into your EC2 instance and run the following command to securely append your mentor's SSH public key (e.g., `ssh-ed25519 AAAAC3...` or `ssh-rsa AAAAB3...`) to your `authorized_keys` file:

```bash
# 1. Open the authorized_keys file in an editor (nano or vi)
nano ~/.ssh/authorized_keys
```
*Paste your mentor's public key on a new line at the bottom of this file, save, and exit (`Ctrl + O`, `Enter`, then `Ctrl + X` in nano).*

### 2. Verify Key Folder Permissions
SSH is extremely strict about file permissions. Run this command to guarantee AWS won't reject the connection:
```bash
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

---

## 🌐 Step 2: Configuration in the AWS EC2 Console

You must grant your mentor network access to connect to your instance's SSH port (Port 22).

1. Open your **AWS Console** and navigate to **EC2** ➔ **Instances** ➔ Select your instance.
2. Select the **Security** tab at the bottom and click on your **Security Group**.
3. Click **Edit inbound rules** and add the following rule:
   * **Type**: `SSH`
   * **Port Range**: `22`
   * **Source**: `Custom` ➔ Paste your **mentor's public IP** followed by `/32` (e.g., `203.0.113.50/32`).
4. Click **Save rules**.

---

## 🧑‍🏫 Step 3: Instructions to Send to Your Mentor

Copy and paste the template below and send it directly to your mentor:

```markdown
Hi! Here is how you can securely access the running Python/FastAPI project on my EC2 server:

### How to Connect:
1. Open your local computer's terminal.
2. Run the following SSH tunneling command (which forwards my EC2's internal web server directly to your local computer):
   
   ssh -N -L 8000:127.0.0.1:8000 ec2-user@<YOUR-EC2-PUBLIC-IP>

   *(Note: The terminal command will look like it is "hanging" or running forever; this is expected behavior, as the tunnel is active. Keep this terminal open.)*

3. Access the API and interactive docs:
   * **API Docs**: Open http://localhost:8000/docs in your browser.
   * **Local API Endpoints**: Test endpoints directly via http://localhost:8000.
```

---

## 🔒 Step 4: How to Revoke Access (Clean up)

When your mentor is finished reviewing your work, you can immediately lock your EC2 server back down with these two steps:

1. **Delete their SSH key**:
   ```bash
   nano ~/.ssh/authorized_keys
   ```
   *(Remove your mentor's public key line, then save and exit).*
   
2. **Remove their security rule**:
   Go back to your **AWS Security Group Inbound Rules** and delete the rule you added for your mentor's IP.

---