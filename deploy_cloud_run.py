import os
import subprocess
import json

PROJECT_ID = "project-bd29d7f8-c65f-4597-b7b"
REGION = "australia-southeast1"

# Read .env file
env_vars = {}
with open('backend/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            # Remove quotes if present
            val = val.strip().strip('"').strip("'")
            env_vars[key.strip()] = val

# Define which vars go to Secret Manager
SECRET_KEYS = [
    "OPENAI_API_KEY", 
    "APPWRITE_API_KEY", 
    "DEEPGRAM_API_KEY", 
    "STRIPE_SECRET_KEY", 
    "COALCREEK_APP_PASSWORD",
    "TWILIO_AUTH_TOKEN",
    "CARTESIA_API_KEY",
    "SMTP_PASSWORD"
]

# We need the project number to grant IAM roles
def get_project_number():
    cmd = f"gcloud projects describe {PROJECT_ID} --format='value(projectNumber)'"
    return subprocess.check_output(cmd, shell=True).decode().strip()

project_number = get_project_number()
service_account = f"{project_number}-compute@developer.gserviceaccount.com"

print(f"Service Account: {service_account}")

# Grant Vertex AI User role for ADC
print("Granting Vertex AI User role to service account...")
subprocess.run(
    f"gcloud projects add-iam-policy-binding {PROJECT_ID} --member='serviceAccount:{service_account}' --role='roles/aiplatform.user'",
    shell=True, stdout=subprocess.DEVNULL
)

# 1. Create secrets and add IAM policy
secrets_map = []
for key in SECRET_KEYS:
    if key not in env_vars or not env_vars[key]:
        continue
    
    val = env_vars[key]
    secret_name = key.lower().replace('_', '-')
    
    print(f"Creating secret: {secret_name}")
    # Create secret (ignore if exists)
    subprocess.run(
        f"gcloud secrets create {secret_name} --replication-policy=automatic --project={PROJECT_ID}", 
        shell=True, stderr=subprocess.DEVNULL
    )
    
    # Add new version
    process = subprocess.Popen(
        f"gcloud secrets versions add {secret_name} --data-file=- --project={PROJECT_ID}", 
        stdin=subprocess.PIPE, shell=True
    )
    process.communicate(input=val.encode())
    
    # Grant Cloud Run service account access
    subprocess.run(
        f"gcloud secrets add-iam-policy-binding {secret_name} --member='serviceAccount:{service_account}' --role='roles/secretmanager.secretAccessor' --project={PROJECT_ID}",
        shell=True, stdout=subprocess.DEVNULL
    )
    
    secrets_map.append(f"{key}={secret_name}:latest")

# 2. Prepare regular env vars
IGNORE_KEYS = ["BACKEND_URL", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"]
env_vars_map = []
for key, val in env_vars.items():
    if key not in SECRET_KEYS and key not in IGNORE_KEYS:
        env_vars_map.append(f"{key}={val}")

# Add python env
env_vars_map.append("PYTHONUNBUFFERED=1")
env_vars_map.append("BACKEND_URL=https://ovela-backend-278930799830.australia-southeast1.run.app")

# 3. Deploy to Cloud Run
set_secrets_flag = ",".join(secrets_map)
set_env_vars_flag = ",".join(env_vars_map)

deploy_cmd = [
    "gcloud", "run", "deploy", "ovela-backend",
    "--source", "./backend",
    "--region", REGION,
    "--project", PROJECT_ID,
    "--allow-unauthenticated",
    "--min-instances", "1",
    "--no-cpu-throttling",
]

if env_vars_map:
    deploy_cmd.extend(["--set-env-vars", set_env_vars_flag])

if secrets_map:
    deploy_cmd.extend(["--set-secrets", set_secrets_flag])

print("Deploying to Cloud Run...")
print(" ".join(deploy_cmd))

subprocess.run(deploy_cmd)
