from datetime import datetime


class EventLogger:

    def __init__(self):

        self.events = []

    # def add(self, message):

    #     now = datetime.now().strftime("%H:%M:%S")

    #     self.events.insert(0, f"[{now}] {message}")

    #     if len(self.events) > 200:
    #         self.events.pop()

    def add(self, text):

        now = datetime.now().strftime("%H:%M:%S")

        self.events.insert(0, f"{now}   {text}")

        self.events = self.events[:100]

    def get_events(self):

        return self.events


logger = EventLogger()
