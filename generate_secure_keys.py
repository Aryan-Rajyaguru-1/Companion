#!/usr/bin/env python3
"""
===========================================
COMPANION AI - SECURE KEY GENERATOR (Python)
===========================================
This script generates secure random keys for your .env file
Run this to populate JWT_SECRET, API_KEY, and SECRET_KEY

Usage: python generate_secure_keys.py
"""

import secrets
import string

def generate_secure_key(length=32):
    """Generate a secure random key of specified length."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    print("🔐 Generating secure keys for Companion AI Framework...")
    print()

    # Generate JWT Secret (64 characters)
    jwt_secret = secrets.token_hex(32)
    print(f"JWT_SECRET={jwt_secret}")

    # Generate API Key (32 characters)
    api_key = generate_secure_key(32)
    print(f"API_KEY={api_key}")

    # Generate Flask Secret Key (32 characters)
    secret_key = generate_secure_key(32)
    print(f"SECRET_KEY={secret_key}")

    print()
    print("✅ Secure keys generated!")
    print()
    print("📝 Copy these values to your .env file:")
    print(f"   JWT_SECRET={jwt_secret}")
    print(f"   API_KEY={api_key}")
    print(f"   SECRET_KEY={secret_key}")
    print()
    print("⚠️  IMPORTANT: Keep these keys secure and never commit them to version control!")

    # Optionally write to .env file
    write_to_env = input("\n💾 Do you want to update your .env file with these keys? (y/N): ").lower().strip()
    if write_to_env == 'y':
        try:
            with open('.env', 'r') as f:
                env_content = f.read()

            # Update or add the keys
            env_lines = env_content.split('\n')
            updated = False

            for i, line in enumerate(env_lines):
                if line.startswith('JWT_SECRET='):
                    env_lines[i] = f'JWT_SECRET={jwt_secret}'
                    updated = True
                elif line.startswith('API_KEY='):
                    env_lines[i] = f'API_KEY={api_key}'
                    updated = True
                elif line.startswith('SECRET_KEY='):
                    env_lines[i] = f'SECRET_KEY={secret_key}'
                    updated = True

            # If not found, add them
            if not updated:
                env_lines.extend([
                    '',
                    f'JWT_SECRET={jwt_secret}',
                    f'API_KEY={api_key}',
                    f'SECRET_KEY={secret_key}'
                ])

            with open('.env', 'w') as f:
                f.write('\n'.join(env_lines))

            print("✅ .env file updated successfully!")

        except FileNotFoundError:
            print("❌ .env file not found. Please create it first.")
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")

if __name__ == "__main__":
    main()