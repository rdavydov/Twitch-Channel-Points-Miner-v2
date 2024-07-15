from flask import Flask
from threading import Thread
import os

app = Flask('')


@app.route('/')
def main():
  return "Twitch Channel Points Miner is running."


def run():
  app.run(host="0.0.0.0", port=os.environ.get('PORT', 6060))


def keep_alive():
  server = Thread(target=run)
  server.start()
