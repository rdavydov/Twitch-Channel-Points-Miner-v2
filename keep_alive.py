from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def main():
  return "Twitch Channel Points Miner is alive."


def run():
  app.run(host="0.0.0.0", port=6060)


def keep_alive():
  server = Thread(target=run)
  server.start()
