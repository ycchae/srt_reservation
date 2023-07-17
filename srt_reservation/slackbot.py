import os
import requests

class SlackBot:
    def __init__(self, token_file, channel_file):
        try:
            token_path = f"{os.path.dirname(os.path.abspath(__file__))}/{token_file}"
            os.stat(token_path)
            with open(token_path, "r") as f:
                self.token = f.read().strip()
        except:
            print("Can't use slack bot. Wrong token path.")

        try:
            channel_path = f"{os.path.dirname(os.path.abspath(__file__))}/{channel_file}"
            os.stat(channel_path)
            with open(channel_path, "r") as f:
                self.channel = f.read().strip()
        except:
            print("Can't use slack bot. Wrong channel path.")

    def send_slack_bot_msg(self, msg):
        if self.token == "" or self.channel == "": return
        if msg == "": msg = "Empty msg"

        requests.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {self.token}"}, data={"channel": self.channel, "text": msg})
