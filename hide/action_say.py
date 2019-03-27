from dragonfly.engines.engine import get_engine
from dragonfly import ActionBase

engine = get_engine()

class Say(ActionBase):
    def __init__(self, text):
        ActionBase.__init__(self)
        self.__text = text

    def _execute(self, data):
        global engine
        say(self.__text)
        return True

def say(text):
    engine.speak(text)
