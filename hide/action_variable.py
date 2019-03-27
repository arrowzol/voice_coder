from dragonfly import Text

numMap = {
    'one' : '1',
    'two' : '2',
    'three' : '3',
    'four' : '4',
    'five' : '5',
    'six' : '6',
    'seven' : '7',
    'eight' : '8',
    'nine' : '9',
    }

def numify(word):
    return numMap.get(word, word)

class Variable(Text):

    last = None

    def __init__(self, separator="", prefix="", first=None, rest=None):
        Text.__init__(self, "%(text)s")
        self._first = first
        self._rest = rest
        self._separator = separator
        self._prefix = prefix

    def _parse_spec(self, spec):
        Variable.last = self
        sp = [numify(word) for word in spec.lower().replace("-", " ").split(" ")]
        if self._first:
            sp[0] = self._first(sp[0])
        if self._rest:
            for i in xrange(1, len(sp)):
                sp[i] = self._rest(sp[i])
        spec = self._prefix + self._separator.join(sp)
        return Text._parse_spec(self, spec)

    def continueVariable(text):
        sp = [numify(word) for word in spec.lower().replace("-", " ").split(" ")]
        if self._rest:
            sp = [self._rest(x) for x in sp]
        spec = self._separator.join(sp)
        return spec

def cancelVariable():
    Variable.last = None
    
def continueVariable(text):
    if Variable.last:
        return last.continueVariable(text)
