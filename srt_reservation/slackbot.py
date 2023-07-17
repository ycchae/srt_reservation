import os
import requests

class SlackBot:
    def __init__(self, token_file, channel_file):
        self.want_slack = False
        self.token = token_file
        self.channel = channel_file
        if self.token == "None" or self.channel == "None":
            return

        try:
            token_path = f"{os.path.dirname(os.path.abspath(__file__))}/{token_file}"
            os.stat(token_path)
            with open(token_path, "r") as f:
                self.token = f.read().strip()
        except:
            print("Can't use slack bot. Wrong token path.")
            return

        try:
            channel_path = f"{os.path.dirname(os.path.abspath(__file__))}/{channel_file}"
            os.stat(channel_path)
            with open(channel_path, "r") as f:
                self.channel = f.read().strip()
        except:
            print("Can't use slack bot. Wrong channel path.")
            return
        
        self.want_slack = True


    def send_slack_bot_msg(self, msg):
        if not self.want_slack: return
        if self.token == "" or self.channel == "": return
        if msg == "": msg = "Empty msg"

        requests.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {self.token}"}, data={"channel": self.channel, "text": msg})

