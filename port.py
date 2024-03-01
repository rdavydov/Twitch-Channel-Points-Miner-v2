import os

host = os.environ.get('HOST')
port = os.environ.get('PORT')

if host and port:
    print(f"The web service is running on {host}:{port}")
else:
    print("Host or port environment variables are not set")
