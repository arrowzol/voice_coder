from dragonfly import *
import time

class MouseSequence(ActionBase):
    def __init__(self, action):
        ActionBase.__init__(self)
        self.__actions = action.split(';')
    def _execute(self, data):
        for action in self.__actions:
            count = 1
            if '*' in action:
                action, count = action.split('*')
                count = int(count)
            while count:
                Mouse(action).execute()
                count -= 1
                time.sleep(0.005)
    
checkMark = MouseSequence("<1,1>*5;<1,-1>*10;<-15,5>")

