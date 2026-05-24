import os
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not (url and key):
    raise ValueError("Environment variables are missing!")

client: Client = create_client(url, key)