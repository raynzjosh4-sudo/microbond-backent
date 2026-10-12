"""
Upload email brand assets to Cloudflare R2 under the 'email-assets/' prefix
and print the public URLs to add to .env as R2_PUBLIC_DOMAIN.
"""
import sys
sys.path.insert(0, '.')

import boto3
from botocore.config import Config
from pathlib import Path

# Load env
from dotenv import load_dotenv
load_dotenv()

import os
ACCOUNT_ID       = os.getenv("R2_ACCOUNT_ID")
ACCESS_KEY_ID    = os.getenv("R2_ACCESS_KEY_ID")
SECRET_KEY       = os.getenv("R2_SECRET_ACCESS_KEY")
ENDPOINT_URL     = os.getenv("R2_ENDPOINT_URL")
BUCKET           = os.getenv("R2_BUCKET_NAME")

if not all([ACCOUNT_ID, ACCESS_KEY_ID, SECRET_KEY, ENDPOINT_URL, BUCKET]):
    print("ERROR: Missing R2 credentials in .env")
    sys.exit(1)

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

ASSETS_DIR = Path("app/icon/email_optimized")
FILES = {
    "microbondicon.png":         "image/png",
    "topcodeimage.jpg":          "image/jpeg",
    "attachementtopimage.jpg":   "image/jpeg",
    "securityemailalertimage.jpg": "image/jpeg",
}

print(f"\nUploading to bucket: {BUCKET}\n")
for filename, content_type in FILES.items():
    local_path = ASSETS_DIR / filename
    if not local_path.exists():
        print(f"  SKIP  {filename} (not found in {ASSETS_DIR})")
        continue

    key = f"email-assets/{filename}"
    s3.upload_file(
        str(local_path),
        BUCKET,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000",  # 1-year cache
        }
    )
    size_kb = local_path.stat().st_size / 1024
    print(f"  OK    {filename}  ({size_kb:.1f} KB)  ->  {key}")

print("\nDone!")
print("\n--- Next step ---")
print("Go to your Cloudflare R2 dashboard → microbondmediastorage bucket")
print("→ Settings → Public Access → Enable 'R2.dev subdomain'")
print("Then copy the URL (e.g. https://pub-xxxx.r2.dev) and add to .env:")
print("R2_PUBLIC_DOMAIN=https://pub-xxxx.r2.dev")
print()
print("Your email image URLs will then be:")
for filename in FILES:
    print(f"  https://pub-xxxx.r2.dev/email-assets/{filename}")
