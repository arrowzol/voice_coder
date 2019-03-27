import time
from dragonfly import ActionBase

class Delay(ActionBase):
    action = None

    def __init__(self, delay):
        ActionBase.__init__(self)
        self.__delay = delay

    def _execute(self, data):
        time.sleep(self.__delay)
        return True

