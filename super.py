from dragonfly import *
from dragonfly.actions import keyboard
from hide.action_delay import Delay
from hide.action_variable import *
from hide.action_mouse import *
import time
import re
import sys
import exit_now as en


_pause = 0.001
Typeable.MOD_DELAY = _pause

#---------------------------------------------------------------------------

ESCAPE_WORD = "+simon"

# WORD syntax
# [-] [+] [&] [_] <letters>
#   [-] - don't print the trailing space from the previous word
#   [+] - print a trailing space after this word later on (can be removed by the next word)
#   [&] - is a key
#   [_] - a "keyword", start a new phrase
metaWords = {
    # modifier keys
    "+caps":            "_caps",
    "+lift":            "_lift",
    "+jab":             "_jab",
    "+jive":            "_jive",

    # word mangling
    "+camel":           "_camel",
    "+lama":            "_lama",
    "+rhino":           "_rhino",
    "+squirrel":         "_squirrel",

    # alphabet
    "+al":              "-a",
    "+baz":             "-b",
    "+crow":            "-c",
    "+dow":             "-d",
    "+eel":             "-e",
    "+fox":             "-f",
    "+grays":           "-g",
    "+hoax":            "-h",
    "+imp":             "-i",
    "+junk":            "-j",
    "+kong":            "-k",
    "+loon":            "-l",
    "+mike":            "-m",
    "+nack":            "-n",
    "+booz":            "-o",
    "+punk":            "-p",
    "+quox":            "-q",
    "+raz":             "-r",
    "+sing":            "-s",
    "+tunk":            "-t",
    "+munk":            "-u",
    "+vack":            "-v",
    "+wump":            "-w",
    "+cross":           "-x",
    "+ying":            "-y",
    "+zoo":             "-z",

    # special characters
    "+scape":           "/-_\x1b",
    "+escape":          "/-_\x1b",
    "+slap":            "-_\r",
    "+kick":            "-_\t",
    "+gap":             "-_ ",
    "+dot":             "-_.",
    "+rock":            "-_(",
      # conflict rack/whack
      "+rack":          "-+_)",
    "+brick":           "-_[",
      "+brack":         "-+_]",
    "+squirm":          "_{",
      "+squack":        "-_}",
    "+tent":            "-_^",
    "+bent":            "-_<",
      "+vent":          "-_>",
    "+slash":           "-_/",
    "+blash":           "-_\\",
    "+quotes":          "-_\"",
    "+quote":           "-_'",
    "+ticker":          "-_`",
    "+fist":            "-_@",
    "+bench":           "-_&",
    "+boom":            "-_!",
    "+bang":            "-_!",
    "+ching":           "-_$",
    "+dasher":          "-_-",
    "+adder":           "-_+",
    "+quest":           "-_?",
    "+sharp":           "-_#",
    "+spark":           "-_*",
    "+sparker":         "+_*",
    "+under":           "-__",
    "+wormey":          "-_~",
    "+pipe":            "-_|",
    "+piper":           "-_ | ",
    "+pox":             "-_%",
    "+quiv":            "-_=",
    "+clunk":           "-+_,",
    "+clink":           "-_:",
    "+slim":            "-+_;",

    # "one" and "two" left out because they are often part of dictation
#    "+zero":            "-_0",
#    "+three":           "-_3",
#    "+four":            "-_4",
#    "+five":            "-_5",
#    "+six":             "-_6",
#    "+seven":           "-_7",
#    "+eight":           "-_8",
#    "+nine":            "-_9",

    # bash commands
    "+scat":            "-_cd ",
    "+dupe":            "-_cp ",
    "+trout":           "-_mv ",
    "+zap":             "-_rm ",
    "+ground":          "_~/",
    "+dark":            "_../",
    "+dirt":            "_./",
    "+maven":           "-_mvn ",

    # General programming help
    "+slam":            "-();",
    "+slamo":            "-<>();",
}

wordChains = {
    "-vim " : [["+diff"], "vimdiff "],
    "-vim " : [["+save"], "-_:wq\n"],
    "tar " : [["+get"], "target "],
    "+dot" : [["+pie"], "-_.py "],
    "+num" : [["+pie"], "+numpy "],
}

mangleMap = {
    "_camel": ('',  None,  lambda x : x[0].upper() + x[1:]),
    "_lama": ('', lambda x : x[0].upper() + x[1:], lambda x : x[0].upper() + x[1:]),
    "_rhino": ('_',  unicode.upper, unicode.upper),
    "_squirrel": ('_',  unicode.lower, unicode.lower),
    "_unused": ('-', None,  None ),
    "_despace": ('', None,  None ),
    "_dotword": ('.',  None,  None),
}

KEY = Key("")
SHIFT_DOWN = [(Keyboard.shift_code, True, Typeable.MOD_DELAY)]
SHIFT_UP = [(Keyboard.shift_code, False, Typeable.MOD_DELAY)]
CTRL_DOWN = [(Keyboard.ctrl_code, True, Typeable.MOD_DELAY)]
CTRL_UP = [(Keyboard.ctrl_code, False, Typeable.MOD_DELAY)]
ALT_DOWN = [(Keyboard.alt_code, True, Typeable.MOD_DELAY)]
ALT_UP = [(Keyboard.alt_code, False, Typeable.MOD_DELAY)]
modifierMap = {
    "_caps":  ('late', SHIFT_DOWN, SHIFT_UP),
    "_lift":  ('soon', SHIFT_DOWN, SHIFT_UP),
    "_jab":  ('soon', CTRL_DOWN, CTRL_UP),
    "_jive":  ('soon', ALT_DOWN, ALT_UP),
}


voiceEvents = []
undoSoon = []
undoHold = []
wasTrailingSpace = False
def processPhrase(words):
    global undoSoon, wasTrailingSpace
    events = []
    undoLater = []
    wordDelim = ' '
    firstXlate = None
    restXlate = None
    firstWord = True
    isMangling = False

    for word in words:
        # modifier command: shift, ctrl, alt, ...
        if word in modifierMap:
            when, down, up = modifierMap[word]
            events.extend(down)
            if when == "soon":
                undoSoon.extend(up)
            else:
                undoLater.extend(up)

        # mangle command: initiate mangling
        elif word in mangleMap:
            if wasTrailingSpace and wordDelim:
                wasTrailingSpace = False
                typeable = keyboard.Keyboard.get_typeable(wordDelim)
                events.extend(typeable.events(_pause))
            isMangling = True
            mangleFirstWord = True
            wordDelim, firstXlate, restXlate = mangleMap[word]

        # just a word ...
        else:
            extraDelay = False
            if word[0] == '/':
                word = word[1:]
                extraDelay = True

            # strip off hide marker, mangle word
            if word[0] == '*':
                word = word[1:].replace(' ', '0')
                wordPrefix = str(int(word[:6])//23)
                word = wordPrefix + word[6:]
                wasTrailingSpace = False

            # process delimiter markers
            if word.startswith("-"):
                word = word[1:]
                wasTrailingSpace = False
            isTrailingSpace = word.startswith("+")
            if isTrailingSpace:
                word = word[1:]

            # strip of key work marker
            if word[0] == '_':
                word = word[1:]

            # add delimiter (space or other when mangling) between words
            if wasTrailingSpace and wordDelim:
                wasTrailingSpace = False
                typeable = keyboard.Keyboard.get_typeable(wordDelim)
                events.extend(typeable.events(_pause))

            # mangle word
            if isMangling:
                word = ''.join([c for c in word if
                    (c >= 'a' and c <= 'z')
                    or (c >= 'A' and c <= 'Z')
                    or (c >= '0' and c <= '9')])
                if mangleFirstWord:
                    if firstXlate:
                        word = firstXlate(unicode(word))
                else:
                    if restXlate:
                        word = restXlate(unicode(word))
                mangleFirstWord = False

            # turn word into events
            for c in word:
                typeable = keyboard.Keyboard.get_typeable(c)
                if extraDelay:
                    events.extend(typeable.events(0.1))
                else:
                    events.extend(typeable.events(_pause))
                if undoSoon:
                    events.extend(undoSoon)
                    undoSoon = []

            # next time, do the trailing space requested by this word
            wasTrailingSpace = isTrailingSpace
    events.extend(undoLater)
    if isMangling:
        wasTrailingSpace = True
    return events

def flatten(l):
    r = []
    for ll in l:
        r.extend(ll)
    return r

KEY_PATTERN = re.compile("^[*/]?[-]?[+]?_")
def phraseSplit(words):
    phrases = []
    phrase = []
    for word in words:
        if KEY_PATTERN.match(word):
            phrase = []
            phrase.append(word)
            phrases.append(phrase)
        else:
            if not phrase:
                phrases.append(phrase)
            phrase.append(word)
    return phrases

escaped = False
def addMetaWords(words):
    global escaped

    # replace any word chains
    words2 = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in wordChains:
            others, replaceWord = wordChains[word]
            if words[i+1:i+len(others)+1] == others:
                word = replaceWord
                i += len(others)
        words2.append(word)
        i += 1
    words = words2

    # replace meta words with their meta values
    words2 = []
    for word in words:
        if escaped:
            words2.append(word)
            escaped = False
        elif word == ESCAPE_WORD:
            escaped = True
        else:
            words2.append(metaWords.get(word, word))
    words = words2

    return words2

def hide(word):
    if word and word.startswith('*'):
        return '*'*(len(word)-1)
    else:
        return word

def processText(text):
    words = flatten(text)
    print "RAW WORDS: [" + "|".join([repr(str(hide(word)))[1:-1] for word in words]) + "]"
    words = addMetaWords(words)
    print "META WORDS: [" + "|".join([repr(str(hide(word)))[1:-1] for word in words]) + "]"
    phrases = phraseSplit(words)
#    print "PHRASES:"
#    print "".join(["  [" + "|".join([repr(str(word))[1:-1] for word in words]) + "]\n" for words in phrases]),
    events = flatten([processPhrase(phrase) for phrase in phrases])
    keyboard.keyboard.send_keyboard_events(events)
    return events

eventHistory = []

macroOn = False
macroEvents = []
macros = {}
def startMacro(words):
    global macroOn, voiceEvents, wasTrailingSpace
    if words == ['+start', '+macro']:
        macroOn = True
        print "-----------------------"
        print "START RECORDING MACRO"
        voiceEvents = []
        wasTrailingSpace = False
        return True
def stopMacro(words):
    global macroOn, macroEvents, voiceEvents, wasTrailingSpace
    if macroOn and len(words) >= 3 and words[:2] == ['+stop', '+macro']:
        words = tuple(words[2:])
        print '----- STOP MACRO %s'%(repr(words))
        macros[words] = macroEvents
        macroEvents = []
        voiceEvents = []
        macroOn = False
        wasTrailingSpace = False
        return True
def playMacro(words):
    global macroOn, macroEvents, voiceEvents
    if len(words) >= 2 and words[0] == '+macro':
        words = tuple(words[1:])
        foundEvents = macros.get(words, None)
        if foundEvents:
            wasTrailingSpace = False
            print '----- PLAY MACRO %s'%(repr(words))
        else:
            print "COULD NOT PLAY MACRO %s from set %s"%(words, macros.keys())
        voiceEvents = foundEvents
    
def processMacros():
    global voiceEvents, eventHistory, escaped, macroOn

    if len([1 for x in voiceEvents if x[0] != 'w']) == 0:
        words = [word for words in voiceEvents if words[0] == 'w' for word in words[1]]
        if words == ['+rip']:
            print "REPLAY"
            for key, payload in eventHistory:
                if key == 'k':
                    keyboard.keyboard.send_keyboard_events(payload)
                elif key == 'a':
                    action, data = payload
                    action._execute(data)
                    time.sleep(0.05)
                time.sleep(0.02)
            voiceEvents = []
            return True
        elif startMacro(words):
            return True
        elif stopMacro(words):
            return True
        else:
            playMacro(words)
    if macroOn:
        macroEvents.extend(voiceEvents)

def processVoiceEvents():
    global voiceEvents, undoSoon, undoHold, wasTrailingSpace, eventHistory, escaped
    if DelayedAction.action:
        DelayedAction.action._execute()
        DelayedAction.action = None
        time.sleep(0.02)
    if undoHold:
        keyboard.keyboard.send_keyboard_events(undoHold)
        undoHold = []
    wordLists = []
    print "-----------------------"
    if voiceEvents == [('w', ['+rip'])]:
        print "REPLAY"
        for key, payload in eventHistory:
            if key == 'k':
                keyboard.keyboard.send_keyboard_events(payload)
            elif key == 'a':
                action, data = payload
                action._execute(data)
                time.sleep(0.05)
            time.sleep(0.02)
        voiceEvents = []
    else:
        eventHistory = []
        for key, payload in voiceEvents:
            if key == 'w':
                wordLists.append(payload)
                continue
            if wordLists:
                eventHistory.append(('k', processText(wordLists)))
                wordLists = []
                time.sleep(0.02)
            wasTrailingSpace = False
            if key == 'k':
                spec, events, name = payload
                if escaped:
                    wordLists.append((ESCAPE_WORD, name))
                    escaped = False
                else:
                    print "KEY:", spec
                    keyboard.keyboard.send_keyboard_events(events)
                    eventHistory.append(('k', events))
            elif key == 'a':
                action, data, name = payload
                if escaped:
                    wordLists.append((ESCAPE_WORD, name))
                    escaped = False
                else:
                    print "EXEC:", name
                    try:
                        action._execute(data)
                    except Exception, e:
                        print "Exception:", e
                    eventHistory.append(('a', (action, data)))
                    time.sleep(0.05)
            time.sleep(0.02)
            if undoSoon:
                keyboard.keyboard.send_keyboard_events(undoSoon)
                eventHistory.append(('k', undoSoon))
                undoSoon = []
        if wordLists:
            eventHistory.append(('k', processText(wordLists)))
        if undoSoon:
            keyboard.keyboard.send_keyboard_events(undoSoon)
            eventHistory.append(('k', undoSoon))
            undoSoon = []
        voiceEvents = []
        escaped = False

class RecordKey(Key):
    def __init__(self, action, name=None):
        self._name = name
        Key.__init__(self, action)
    def _parse_spec(self, spec):
        if "_name" in self.__dict__:
            return (spec, Key._parse_spec(self, spec), self._name)
        else:
            return (spec, Key._parse_spec(self, spec), "x")
    def _execute_events(self, specEventsName):
        global voiceEvents
        voiceEvents.append(('k', specEventsName))

class RecordWord(Text):
    def _parse_spec(self, spec):
        return spec
    def _execute_events(self, spec):
        global voiceEvents
        voiceEvents.append(('w', [spec]))

class RecordDictation(Text):
    def _parse_spec(self, spec):
        return spec
    def _execute_events(self, spec):
        global voiceEvents
        voiceEvents.append(('w', ["+" + word for word in spec.split(" ")]))

class RecordAction(ActionBase):
    def __init__(self, action, name="unknown"):
        ActionBase.__init__(self)
        self._action = action
        self._name = name
    def _execute(self, data):
        global voiceEvents
        voiceEvents.append(('a', (self._action, data, self._name)))

class DelayedAction(ActionBase):
    action = None
    def __init__(self, action):
        ActionBase.__init__(self)
        self.__action = action
    def _execute(self, data):
        global undoSoon, undoHold
        if undoSoon:
            undoHold.extend(undoSoon)
            undoSoon = []
        if DelayedAction.action:
            DelayedAction.action._execute()
        DelayedAction.action = self.__action
        return True

class ReleaseModifiers(ActionBase):
    def _execute(self, data):
        global undoHold, wasTrailingSpace
        wasTrailingSpace = False
        if DelayedAction.action:
            DelayedAction.action._execute()
            DelayedAction.action = None
            time.sleep(0.1)
        if undoHold:
            keyboard.keyboard.send_keyboard_events(undoHold)
            undoHold = []

config            = Config("super edit")
config.cmd        = Section("Language section")
config.cmd.map    = Item(
    {
        "snooze":                           Function(lambda : en.exit_now()),
    # escape meta-words with this, should be the same as ESCAPE_WORD
    "simon":                            RecordWord("+simon"),

    # dictation
    "<text>":                           RecordDictation("%(text)s"),

    # conflict: bean/bin
#    "bean":                             RecordWord("+bean"),
    # conflict: junk/chunk
#    "chunk":                            RecordWord("+chunk"),
    "zap":                              RecordWord("+zap"),
    "add":                              RecordWord("+add"),
    "line":                             RecordWord("+line"),
    "trim":                             RecordWord("+trim"),
    "false":                            RecordWord("+false"),
    "true":                             RecordWord("+true"),
    "string":                           RecordWord("+string"),
    # conflict: left/lift
#    "left":                             RecordWord("+left"),
    "run":                              RecordWord("+run"),
    "request":                          RecordWord("+request"),
    "print":                            RecordWord("+print"),
    "response":                         RecordWord("+response"),
    "repeater":                         RecordWord("+repeater"),
    "get":                              RecordWord("+get"),
    "append":                           RecordWord("+append"),
    "other":                            RecordWord("+other"),
    "group":                            RecordWord("+group"),
    "age":                              RecordWord("+age"),
    "else":                             RecordWord("+else"),
    "open":                             RecordWord("+open"),
    "none":                             RecordWord("+none"),
    "read":                             RecordWord("+read"),
    "then":                             RecordWord("+then"),
    "body":                             RecordWord("+body"),
    "table":                            RecordWord("+table"),
    "this":                             RecordWord("+this"),
    "echo":                             RecordWord("+echo"),
    "scan":                             RecordWord("+scan"),
    "type":                             RecordWord("+type"),
    "types":                            RecordWord("+types"),
    "threshold":                        RecordWord("+threshold"),
    "boolen":                           RecordWord("+boolen"),
    "optimizer":                        RecordWord("+optimizer"),
    "optimize":                         RecordWord("+optimize"),
    "build":                            RecordWord("+build"),
    "avoid":                            RecordWord("+avoid"),
    "is":                               RecordWord("+is"),
    "break":                            RecordWord("+break"),
    "line":                             RecordWord("+line"),
    "phone":                            RecordWord("+phone"),
    "base":                             RecordWord("+base"),
    "less":                             RecordWord("+less"),
    "describe":                         RecordWord("+describe"),
    "rank":                             RecordWord("+rank"),
    "row":                              RecordWord("+row"),
    "stream":                           RecordWord("+stream"),
    "socket":                           RecordWord("+socket"),
    "sock":                             RecordWord("+sock"),
    "token":                            RecordWord("+token"),
    "tokenize":                         RecordWord("+tokenize"),
    "metro":                            RecordWord("+metro"),
    "boolean":                          RecordWord("+boolean"),
    "void":                             RecordWord("+void"),
    "length":                           RecordWord("+length"),
    "plug in":                          RecordWord("+plugin"),
    "array":                            RecordWord("+array"),
    "list":                             RecordWord("+list"),
    "eenume":                           RecordWord("+enum"),
    "sign":                             RecordWord("+sign"),
    "case":                             RecordWord("+case"),
    "enable":                           RecordWord("+enable"),
    "ignore":                           RecordWord("+ignore"),
    "mangle":                           RecordWord("+mangle"),
    "class":                            RecordWord("+class"),
    "defined":                          RecordWord("+defined"),
    "bit":                              RecordWord("+bit"),
    "cause":                            RecordWord("+cause"),
    "find":                             RecordWord("+find"),
    "import":                           RecordWord("+import"),
    "done":                             RecordWord("+done"),
    "iterator":                         RecordWord("+iterator"),
    "merge":                            RecordWord("+merge"),
    "cat":                              RecordWord("+cat"),
    "sequence":                         RecordWord("+sequence"),
    "eclipse":                          RecordWord("+eclipse"),
    "rows":                             RecordWord("+rows"),
    "float":                            RecordWord("+float"),
    "root":                             RecordWord("+root"),
    "column":                           RecordWord("+column"),
    "cipher":                           RecordWord("+cipher"),
    "logger":                           RecordWord("+logger"),
    "log":                              RecordWord("+log"),
    "drop":                             RecordWord("+drop"),
    "buffer":                           RecordWord("+buffer"),
    "buffered":                         RecordWord("+buffered"),
    "queue":                            RecordWord("+queue"),
    "queues":                           RecordWord("+queues"),
    "engine":                           RecordWord("+engine"),
    "raw":                              RecordWord("+raw"),
    "borrow":                           RecordWord("+borrow"),
    "borrowed":                         RecordWord("+borrowed"),
    "inventory":                        RecordWord("+inventory"),
    "quiz":                             RecordWord("+quiz"),
    "velocity":                         RecordWord("+velocity"),
    "accessor":                         RecordWord("+accessor"),
    "double":                           RecordWord("+double"),
    "mock":                             RecordWord("+mock"),
    "meta":                             RecordWord("+meta"),
    "trunk":                            RecordWord("+trunk"),
    "count":                            RecordWord("+count"),
    "warm":                             RecordWord("+warm"),
    "share":                            RecordWord("+share"),
    "select":                           RecordWord("+select"),
    "order":                            RecordWord("+order"),
    "tag":                              RecordWord("+tag"),
    "tags":                             RecordWord("+tags"),
    "decryption":                       RecordWord("+decryption"),
    "earth":                            RecordWord("+earth"),
    "octet":                            RecordWord("+octet"),
    "octets":                           RecordWord("+octets"),
#    "fork":                             RecordWord("+fork"),
    "decryption":                       RecordWord("+decryption"),
    "histogram":                        RecordWord("+histogram"),
    "will":                             RecordWord("+will"),
    "dictionary":                       RecordWord("+dictionary"),
    "graph":                            RecordWord("+graph"),
    "hide":                             RecordWord("+hide"),
    "cache":                            RecordWord("+cache"),
    "key":                              RecordWord("+key"),
    "size":                             RecordWord("+size"),
    "out":                              RecordWord("+out"),
    "span":                             RecordWord("+span"),
    "stop":                             RecordWord("+stop"),
    "pie":                              RecordWord("+pie"),
    "shape":                            RecordWord("+shape"),
    "make":                             RecordWord("+make"),
    "python":                           RecordWord("+python"),
    "work":                             RecordWord("+work"),
    "color":                            RecordWord("+color"),
    "sink":                             RecordWord("+sink"),
    "java":                             RecordWord("+java"),
    # interference: main/name
#    "main":                             RecordWord("+main"),
    "coalesce":                         RecordWord("+coalesce"),
    "file":                             RecordWord("+file"),
    "empty":                            RecordWord("+empty"),
    "hash":                             RecordWord("+hash"),
    "normalize":                        RecordWord("+normalize"),
    "with":                             RecordWord("+with"),
    "top":                              RecordWord("+top"),
    "macro":                            RecordWord("+macro"),
    "tool":                             RecordWord("+tool"),
    "divide":                           RecordWord("+divide"),
    "error":                            RecordWord("+error"),
    "link":                             RecordWord("+link"),
    "obscure":                          RecordWord("+obscure"),
    "method":                           RecordWord("+method"),
    "inner":                            RecordWord("+inner"),
    "outer":                            RecordWord("+outer"),
    "flush":                            RecordWord("+flush"),
    "headers":                          RecordWord("+headers"),
    "header":                           RecordWord("+header"),
    "split":                            RecordWord("+split"),
    "lines":                            RecordWord("+lines"),
    "close":                            RecordWord("+close"),
    "service":                          RecordWord("+service"),
    "clone":                            RecordWord("+clone"),
    "fetch":                            RecordWord("+fetch"),
    "origin":                           RecordWord("+origin"),
    "parse":                            RecordWord("+parse"),
    "parsed":                           RecordWord("+parsed"),
    "pandas":                           RecordWord("+pandas"),
    "global":                           RecordWord("+global"),
    "device":                           RecordWord("+device"),
    "tail":                             RecordWord("+tail"),
    "jira":                             RecordWord("+jira"),
    "cookie":                           RecordWord("+cookie"),
    "rest":                             RecordWord("+rest"),
    "devin":                            RecordWord("+devin"),
    "tunnel":                           RecordWord("+tunnel"),
    "pause":                            RecordWord("+pause"),
    "odin":                             RecordWord("+odin"),
    "brazil":                           RecordWord("+brazil"),
    "tab":                              RecordWord("+tab"),
    "weight":                           RecordWord("+weight"),
    "height":                           RecordWord("+height"),
    "width":                            RecordWord("+width"),
    "freight":                          RecordWord("+freight"),
    "ship":                             RecordWord("+ship"),
    "lot":                              RecordWord("+lot"),
    "pallet":                           RecordWord("+pallet"),
    "pallets":                          RecordWord("+pallets"),
    "client":                           RecordWord("+client"),
    "vendor":                           RecordWord("+vendor"),
    "carton":                           RecordWord("+carton"),
    "unstacked":                        RecordWord("+unstacked"),
    "pickup":                           RecordWord("+pickup"),
    "blob":                             RecordWord("+blob"),
    "address":                          RecordWord("+address"),
    "console":                          RecordWord("+console"),
    "forwarding":                       RecordWord("+forwarding"),
    "carrier":                          RecordWord("+carrier"),
    "amazon":                           RecordWord("+amazon"),
    "one day":                          RecordWord("+one day"),

    # Greek letters
    "alpha":                            RecordWord("+alpha"),
    # conflict: beta/data
    "beta":                             RecordWord("+beta"),
    "data":                             RecordWord("+data"),
    "theta":                            RecordWord("+theta"),
    "lambda":                           RecordWord("+lambda"),

    # Alternatives
    "conjunction":                      RecordWord("+and"),
    "write as in out":                  RecordWord("+write"),
#    "skip":                             RecordWord("+skip"),

    # Lingo
    # conflict: diff/def
    "diff":                             RecordWord("+diff"),
    "jay sawn":                         RecordWord("+json"),
    "dee dupe":                         RecordWord("+dedup"),
#    "hack":                             RecordWord("+hack"),
    "zip":                              RecordWord("+zip"),
    "template":                         RecordWord("+template"),
    "raise":                            RecordWord("+raise"),
    "to do":                            RecordWord("+TODO"),
    "hana":                             RecordWord("+hana"),
    "byte":                             RecordWord("+byte"),
    "bytes":                            RecordWord("+bytes"),
    "iterate":                          RecordWord("+iterate"),
    "iterator":                         RecordWord("+iterator"),
    "iterable":                         RecordWord("+iterable"),
    # conflict: dev/def
    #"dev":                              RecordWord("+dev"),
    "config":                           RecordWord("+config"),
    "parens":                           RecordWord("+parens"),
    "bin":                              RecordWord("+bin"),
    # conflict: column/k/com
    "dot com":                          RecordWord("-_.com"),
    "ex per":                           RecordWord("+expr"),
    "J. D. B. C.":                      RecordWord("+jdbc"),
    "ID":                               RecordWord("+id"),
    "you till":                         RecordWord("+util"),
    "you are al":                       RecordWord("+url"),
    "S. S. L.":                         RecordWord("+ssl"),
    "U. R. L.":                         RecordWord("+url"),
    "J. M. S.":                         RecordWord("+jms"),
    "H. T. T. P.":                      RecordWord("+http"),
    "H. T. T. P. S.":                   RecordWord("+https"),
    "serialize":                        RecordWord("+serialize"),
    "serializable":                     RecordWord("+serializable"),
    "yah mole":                         RecordWord("+yaml"),
    "ex later":                         RecordWord("+xlat"),
#    "init":                             RecordWord("+init"),
    #"sync":                             RecordWord("+sync"),
    # contact: lib/lambda/link
    "lib":                              RecordWord("+lib"),
#    "drools":                           RecordWord("+drools"),
#    "null":                             RecordWord("+null"),
#    "rule":                             RecordWord("+rule"),
#    "rules":                            RecordWord("+rules"),
    "gitter":                           RecordWord("+git", "+gitter"),
#    "role":                             RecordWord("+role"),
    "auth":                             RecordWord("+auth"),
    "jar":                              RecordWord("+jar"),
    "num":                              RecordWord("+num"),
    "poe joe":                          RecordWord("+pojo"),
    "char":                             RecordWord("+char"),
    "entry":                            RecordWord("+entry"),
    "kubernetes":                       RecordWord("+kubernetes"),
    "pull":                             RecordWord("+pull"),
    "blank":                            RecordWord("+blank"),
#    "pool":                             RecordWord("+pool"),
    "E. val":                           RecordWord("+eval"),
    "in foe sehk":                      RecordWord("+info-sec"),
    "pie charm":                        RecordWord("+pycharm"),
    "len":                              RecordWord("+len"),

    # Troublesome for bash
    # conflict: ping/bang
    "ping":                             RecordWord("ping "),
    # conflict: quota/quota hana/quarter/quote tar
    "quota":                            RecordWord("+quota"),
    "deploy":                           RecordWord("+deploy"),
    "show":                             RecordWord("+show"),
    "clean":                            RecordWord("+clean"),
    "all":                              RecordWord("+all"),
    # conflict: curl/cron
    "curl":                             RecordWord("curl "),
    # conflict kill/tail
    "kill":                             RecordWord("kill "),
    "ant":                              RecordWord("ant "),
    "maven":                            RecordWord("+maven"),
    # conflict: bash/blash/baz
    "bash":                             RecordWord("+bash"),
    "dupe":                             RecordWord("+dupe"),
    "trout":                            RecordWord("+trout"),

    # special commands
    # conflict: rip/grep
    "rip":                             RecordWord("+rip"),

    # modifier keys (meta words)
    "caps":                             RecordWord("+caps"),
    # conflict: left/lift
    "lift":                             RecordWord("+lift"), # shift
    "jab":                              RecordWord("+jab"),  # cntl
    "jive":                             RecordWord("+jive"), # alt

    # word mangling (meta words)
    "camel":                            RecordWord("+camel"),
    "dee space":                        RecordWord("_despace"),
    "lama":                             RecordWord("+lama"),
    "rhino":                            RecordWord("+rhino"),
    "squirrel":                         RecordWord("+squirrel"),
    "dot word":                         RecordWord("_dotword"),

    # alphabet (meta words)
    "al":                               RecordWord("+al"),
    # conflict: baz/bash
    "baz":                              RecordWord("+baz"),
    # conflict: crow/row
    "crow":                             RecordWord("+crow"),
    "dow":                              RecordWord("+dow"),
    "eel":                              RecordWord("+eel"),
    "fox":                              RecordWord("+fox"),
    "grays":                            RecordWord("+grays"),
    "hoax":                             RecordWord("+hoax"),
    "imp":                              RecordWord("+imp"),
    # conflict: junk/chunk
    "junk":                             RecordWord("+junk"),
    "kong":                             RecordWord("+kong"),
    # conflict floon/loon
    "loon":                             RecordWord("+loon"),
    "mike":                             RecordWord("+mike"),
    "nack":                             RecordWord("+nack"),
    "booz":                             RecordWord("+booz"),
    "punk":                             RecordWord("+punk"),
    "quox":                             RecordWord("+quox"),
    "raz":                              RecordWord("+raz"),
    # conflict sing/scene
    "sing":                             RecordWord("+sing"),
    "tunk":                             RecordWord("+tunk"),
    "munk":                             RecordWord("+munk"),
    "vack":                             RecordWord("+vack"),
    "wump":                             RecordWord("+wump"),
    "cross":                            RecordWord("+cross"),
    "ying":                             RecordWord("+ying"),
    "zoo":                              RecordWord("+zoo"),

    # special characters (meta words)
    "slap":                             RecordWord("+slap"),
    "kick [<n>]":                       RecordKey("tab:%(n)d", "+kick"),
    "gap [<n>]":                        RecordKey("space:%(n)d", "+gap"),
    "dot":                              RecordWord("+dot"),
    "rock":                             RecordWord("+rock"),
      # conflict rack/whack
      "rack":                           RecordWord("+rack"),
    "brick":                            RecordWord("+brick"),
      "brack":                          RecordWord("+brack"),
    "squirm":                           RecordWord("+squirm"),
      "squack":                         RecordWord("+squack"),
    "bent":                             RecordWord("+bent"),
      "vent":                           RecordWord("+vent"),
    # conflict escape/scape/skip
    "scape":                            RecordWord("+scape"),
    "escape":                           RecordWord("+escape"),
    "slash":                            RecordWord("+slash"),
    "blash":                            RecordWord("+blash"),
    "quotes":                           RecordWord("+quotes"),
    # conflict: quote/quota
    "quote":                            RecordWord("+quote"),
    "ticker":                           RecordWord("+ticker"),
    "fist":                             RecordWord("+fist"),
    "bench":                            RecordWord("+bench"),
    "boom":                             RecordWord("+boom"),
    # conflict: ping/bang
    "bang":                             RecordWord("+bang"),
    "tent":                             RecordWord("+tent"),
    "ching":                            RecordWord("+ching"),
    "dasher":                           RecordWord("+dasher"),
    "adder":                            RecordWord("+adder"),
    "quest":                            RecordWord("+quest"),
    "sharp":                            RecordWord("+sharp"),
    "spark":                            RecordWord("+spark"),
    "sparker":                          RecordWord("+sparker"),
    "under":                            RecordWord("+under"),
    "wormey":                           RecordWord("+wormey"),
    "pipe":                             RecordWord("+pipe"),
    "piper":                            RecordWord("+piper"),
    # conflict: pox/fox
    "pox":                              RecordWord("+pox"),
    "quiv":                             RecordWord("+quiv"),
    "slim":                             RecordWord("+slim"),
    "clunk":                            RecordWord("+clunk"),
    "clink":                            RecordWord("+clink"),

    # Combinations of special characters
    "slam":                             RecordWord("+slam"),
    "slamo":                            RecordWord("+slamo"),

    # Special Keys
    "slay [<n>]":                       RecordKey("c-c:%(n)d", "+slay"),
    "func <n>":                         RecordKey("f%(n)d"),

    # Copy paste
    "lick":                             RecordKey("c-c", "+lick") + MouseSequence("<1,1>*5;<1,-1>*10;<-15,5>"),
    "barf [<n>]":                       RecordKey("c-v:%(n)d", "+barf"),
    "chomp":                            RecordKey("c-x", "+chomp"),

    # Undo/Redo backspace
    "strike [<n>]":                     RecordKey("c-z:%(n)d", "+strike"),
    "whack [<n>]":                      RecordKey("backspace:%(n)d", "+whack"),
    "chop [<n>]":                      RecordKey("backspace:%(n)d", "+chop"),
    "wax [<n>]":                        RecordKey("delete:%(n)d", "wax"),
    "chip [<n>]":                       RecordKey("delete:%(n)d", "chip"),

    # Literals
    "numb <nn>":                        RecordWord("-_%(nn)d"),

    ## Mouse

    # left button
    "spike":                            RecordAction(Mouse("left"), "+spike"),
    "spin":                             RecordAction(Mouse("left:2"), "+spin"),
    "spoon":                            RecordAction(Mouse("left:3"), "+spoon"),

    "spook": (                          RecordAction(Mouse("left:down"), "+spook") +
                                        RecordAction(DelayedAction(Mouse("left:up")))),

    "bi spook": (                       RecordAction(
                                            Mouse("left, left:down"),
                                            "+bi-spook") +
                                        RecordAction(DelayedAction(Mouse("left:up")))
                                            ),

    "tri spook": (                      RecordAction(
                                            Mouse("left:2, left:down"),
                                            "+tri-spook") +
                                        RecordAction(DelayedAction(Mouse("left:up")))
                                            ),

    # right button
    "flike":                            RecordAction(Mouse("right"), "flike"),
    "flin":                             RecordAction(Mouse("right:2"), "flin"),
    # conflict floon/loon
#    "floon":                            RecordAction(Mouse("right:3"), "floon"),

    "fluk": (                           RecordAction(
                                            DelayedAction(Mouse("right:up"))) +
                                        RecordAction(Mouse("right:down"), "fluk")),

    # middle button
    "dike":                             RecordAction(Mouse("middle"), "dike"),
    # conflict din/in
#    "din":                              RecordAction(Mouse("middle:2"), "din"),
    "dune":                             RecordAction(Mouse("middle:3"), "+dune"),

    # conflict: dupe
#    "duke": (                           RecordAction(
#                                            DelayedAction(Mouse("middle:up")), "duke") +
#                                        RecordAction(Mouse("middle:down"), "duke2")),

    "zook":                             ReleaseModifiers(),

    # Navigation keys
    "list leaps":                       Function(lambda : FocusWindow.ls()),
    "leap up [<n>]":                    RecordKey("up:%(n)d", "leap up"),
    "leap down [<n>]":                  RecordKey("down:%(n)d", "leap down"),
    "leap right [<n>]":                 RecordKey("right:%(n)d", "leap right"),
    "leap left [<n>]":                  RecordKey("left:%(n)d", "leap left"),
    "leap top":                         RecordKey("c-home", "leap top"),
    "leap bottom":                      RecordKey("c-end", "leap bottom"),
    "page down [<n>]":                  RecordKey("pgdown:%(n)d", "page down"),
    "page up [<n>]":                    RecordKey("pgup:%(n)d", "page up"),

    # C/C++
    "stir cat":                         RecordWord("strcat"),
    "stir en cat":                      RecordWord("strncat"),
    "stir copy":                        RecordWord("strcpy"),
    "stir en copy":                     RecordWord("strncpy"),
    "stir length":                      RecordWord("strlen"),
    "mallock":                          RecordWord("malloc"),

    # Java
    "at link":                          RecordWord("{@link "),
    "sniff":                            RecordWord("if ("),
    "snile":                            RecordWord("while ("),
    "snore":                            RecordWord("for (", "+_snore"),
    "snitch":                           RecordWord("switch ("),
    "cliff":                            RecordWord("+return"),
    "print line":                       RecordWord("+println"),

    # Generic calcations
    "calc not":                         RecordWord("-_!"),
    "calc quiv":                        RecordWord("-_ == "),
    "calc not quiv":                    RecordWord("-_ != "),
    "calc great":                       RecordWord("-_ > "),
    "calc great quiv":                  RecordWord("-_ >= "),
    "calc less":                        RecordWord("-_ < "),
    "calc less quiv":                   RecordWord("-_ <= "),
    "calc up":                          RecordWord("-_ + "),
    "calc down":                        RecordWord("-_ - "),
    "calc times":                       RecordWord("-_ * "),
    "calc divide":                      RecordWord("-_ / "),
    "calc mod":                         RecordWord("-_ %% "),
    "calc or":                          RecordWord("-_ || "),
    "calc bit or":                      RecordWord("-_ | "),
    "calc and":                         RecordWord("-_ && "),
    "calc bit and":                     RecordWord("-_ & "),
    "calc ex or":                       RecordWord("-_ ^ "),
    "calc ink":                         RecordWord("-_++"),
    "calc deck":                        RecordWord("-_--"),
    "calc set":                         RecordWord("-_ = "),
    "calc up set":                      RecordWord("-_ += "),
    "calc down set":                    RecordWord("-_ -= "),
    "calc times set":                   RecordWord("-_ *= "),
    "calc divide set":                  RecordWord("-_ /= "),
    "calc mod set":                     RecordWord("-_ %= "),
    "calc or set":                      RecordWord("-_ ||= "),
    "calc bit or set":                  RecordWord("-_ |= "),
    "calc and set":                     RecordWord("-_ &&= "),
    "calc bit and set":                 RecordWord("-_ &= "),
    "calc ex or set":                   RecordWord("-_ ^= "),

    "calc turn":                        RecordWord("-_ ? "),
    "calc else":                        RecordWord("-_ : "),

    "calc sum":                         RecordWord("+sum"),
    "calc min":                         RecordWord("+min"),
    "calc max":                         RecordWord("+max"),

    # Java
    # conflict: int/end/tent/init
    "inter":                            RecordWord("+int"),
    "integer":                          RecordWord("+integer"),
    "bool":                             RecordWord("+bool"),

# tate is not a good keyword
#    "tate auto [wire | wired]":         RecordWord("_@Autowired"),
#    "tate test":                        RecordWord("_@Test"),
#    "tate bean":                        RecordWord("_@Bean"),
#    "tate value":                       RecordWord("_@Value(\"${"),
#    "tate component":                   RecordWord("_@Component"),
#    "tate controller":                  RecordWord("_@Controller"),

    # Python
    "def":                              RecordWord("-_def "),
    "el if":                            RecordWord("-_elif "),
    "dict":                             RecordWord("+dict"),

    # Hadoop
    "yarn":                             RecordWord("+yarn"),
    "oozie":                            RecordWord("+oozie"),
    "ha dupe":                          RecordWord("hadoop "),
    "ha duper":                         RecordWord("-hadoop fs -"),
    "pig":                              RecordWord("+pig"),
    "hive":                             RecordWord("+hive"),
    "dump":                             RecordWord("+dump"),
    "input":                            RecordWord("+input"),
    "tuple":                            RecordWord("+tuple"),
    "batch":                            RecordWord("+batch"),
    "go":                               RecordWord("+go"),
    "join":                             RecordWord("+join"),
    "man":                              RecordWord("+man"),
    "fail":                             RecordWord("+fail"),
    "failed":                           RecordWord("+failed"),
    "output":                           RecordWord("+output"),

    # Scala
    "scal ah":                          RecordWord("+scala"),
    "sequence type":                    RecordWord("_Seq["),
    "stream type":                      RecordWord("_Stream["),
    "mapping type":                     RecordWord("_Map["),
    "inter type":                       RecordWord("+_Int"),
    "login code <nn>":                  RecordWord("*062445%(nn)6s\r"),

    # eclipse
    "yikes":                            RecordKey("c-space"),
    "chase":                            RecordKey("f3"),
    "leap line <nn>":                   RecordKey("c-l") + RecordWord("%(nn)d\r"),
    "leap use":                         RecordKey("cs-g"),
    "leap type":                        RecordKey("cs-t"),
    "leap resource":                    RecordKey("cs-r"),
#    "kick types":                       RecordKey("cs-o"),
#    "kick type":                        RecordKey("cs-m"),
#    "kick error":                       RecordKey("c-1"),

    # Unix/bash commands
    "tar":                              RecordWord("tar "),
#    "tail":                             RecordWord("tail "),
    "head":                             RecordWord("head "),
    "gaze condor":                      RecordWord("-condor_ql | grep barn\r"),
    "gaze dear":                        RecordWord("-ll\r"),
    "gaze proc":                        RecordWord("-psx\r"),
    "gaze where":                       RecordWord("-pwd\r"),
    "scat":                             RecordWord("+scat"),
    "leap here":                        RecordWord("-cdwd\r"),
    # conflict: grep/group
    "grep":                             RecordWord("-grep "),
    "stream ed":                        RecordWord("-sed "),
    "meld":                             RecordWord("-meld "),
    "cron":                             RecordWord("+cron"),
    "cron tab":                         RecordWord("+crontab"),
    "make dear":                        RecordWord("-mkdir "),
    "awk":                              RecordWord("-awk "),
    "ex args":                          RecordWord("-xargs "),
    "vim":                              RecordWord("-vim "),

    "sue do":                           RecordWord("-sudo "),
    "my sequal | my SQL":               RecordWord("+mysql"),
    "chmod":                            RecordWord("-chmod "),
    # conflict: dark/tunk/under
    "dark":                             RecordWord("+dark"),
    "dirt":                             RecordWord("+dirt"),


    # window navigation
    "leap <n>": (                       RecordKey("alt:down", "+leap") +
                                        RecordKey("tab/4:%(n)d/4") +
                                        RecordKey("alt:up")),

    "leap unix":                        RecordAction(
            FocusWindow(title="Remote Desktop Connection"), "leap unix"),
    "leap mail":                        RecordAction(
            FocusWindow(title="Inbox - devbar@amazon.com - Outlook")),
    "leap reader":                      RecordAction(
            FocusWindow(title="Adobe Acrobat Reader")),
    "leap browse":                      RecordAction(
            FocusWindow(title="Mozilla Firefox")),
    "leap key [pass]":                  RecordAction(
            FocusWindow(title="KeePass")),
    "leap exel":                        RecordAction(
            FocusWindow(title=" - Excel")),
    "leap eclipse":                     RecordAction(
            FocusWindow(executable="eclipse.exe")),
        
#    "leap word":                        RecordAction(
#            FocusWindow(title="Microsoft Word")),

    #} + [(word[1:], RecordWord(word)) for word, symbol in metaWords.keys()],
    },
    namespace={
     "Key":   Key,
     "Text":  Text,
    }
)
namespace = config.load()

#---------------------------------------------------------------------------
# Here we prepare the list of formatting functions from the config file.

# Retrieve text-formatting functions from this module's config file.
#  Each of these functions must have a name that starts with "format_".
format_functions = {}
if namespace:
    for name, function in namespace.items():
     if name.startswith("format_") and callable(function):
        spoken_form = function.__doc__.strip()

        # We wrap generation of the Function action in a function so
        #  that its *function* variable will be local.  Otherwise it
        #  would change during the next iteration of the namespace loop.
        def wrap_function(function):
            def _function(dictation):
                formatted_text = function(dictation)
                Text(formatted_text).execute()
            return Function(_function)

        action = wrap_function(function)
        format_functions[spoken_form] = action


# Here we define the text formatting rule.
# The contents of this rule were built up from the "format_*"
#  functions in this module's config file.
if format_functions:
    class FormatRule(MappingRule):

        mapping  = format_functions
        extras   = [Dictation("dictation")]

else:
    FormatRule = None


#---------------------------------------------------------------------------
# Here we define the keystroke rule.

# This rule maps spoken-forms to actions.  Some of these 
#  include special elements like the number with name "n" 
#  or the dictation with name "text".  This rule is not 
#  exported, but is referenced by other elements later on.
#  It is derived from MappingRule, so that its "value" when 
#  processing a recognition will be the right side of the 
#  mapping: an action.
# Note that this rule does not execute these actions, it
#  simply returns them when it's value() method is called.
#  For example "up 4" will give the value Key("up:4").
# More information about Key() actions can be found here:
#  http://dragonfly.googlecode.com/svn/trunk/dragonfly/documentation/actionkey.html
class KeystrokeRule(MappingRule):

    exported = False

    mapping  = config.cmd.map
    extras   = [
                IntegerRef("n", 1, 100),
                IntegerRef("nn", 0, 100000000),
                Dictation("text"),
               ]
    defaults = {
                "n": 1,
               }
    # Note: when processing a recognition, the *value* of 
    #  this rule will be an action object from the right side 
    #  of the mapping given above.  This is default behavior 
    #  of the MappingRule class' value() method.  It also 
    #  substitutes any "%(...)." within the action spec
    #  with the appropriate spoken values.


#---------------------------------------------------------------------------
# Here we create an element which is the sequence of keystrokes.

# First we create an element that references the keystroke rule.
#  Note: when processing a recognition, the *value* of this element
#  will be the value of the referenced rule: an action.
alternatives = []
alternatives.append(RuleRef(rule=KeystrokeRule()))
if FormatRule:
    alternatives.append(RuleRef(rule=FormatRule()))
single_action = Alternative(alternatives)

# Second we create a repetition of keystroke elements.
#  This element will match anywhere between 1 and 16 repetitions
#  of the keystroke elements.  Note that we give this element
#  the name "sequence" so that it can be used as an extra in
#  the rule definition below.
# Note: when processing a recognition, the *value* of this element
#  will be a sequence of the contained elements: a sequence of
#  actions.
sequence = Repetition(single_action, min=1, max=16, name="sequence")


#---------------------------------------------------------------------------
# Here we define the top-level rule which the user can say.

# This is the rule that actually handles recognitions. 
#  When a recognition occurs, it's _process_recognition() 
#  method will be called.  It receives information about the 
#  recognition in the "extras" argument: the sequence of 
#  actions and the number of times to repeat them.
class RepeatRule(CompoundRule):

    # Here we define this rule's spoken-form and special elements.
    spec     = "<sequence> [replicate <n>]"
    extras   = [
                sequence,                 # Sequence of actions defined above.
                IntegerRef("n", 1, 100),  # Times to repeat the sequence.
               ]
    defaults = {
                "n": 1,                   # Default repeat count.
               }

    # This method gets called when this rule is recognized.
    # Arguments:
    #  - node -- root node of the recognition parse tree.
    #  - extras -- dict of the "extras" special elements:
    #     . extras["sequence"] gives the sequence of actions.
    #     . extras["n"] gives the repeat count.
    def _process_recognition(self, node, extras):
        sequence = extras["sequence"]   # A sequence of actions.
        count = extras["n"]             # An integer repeat count.
        for i in range(count):
            for action in sequence:
                action.execute()
        if not processMacros():
            processVoiceEvents()


#---------------------------------------------------------------------------
# Create and load this module's grammar.

grammar = Grammar("super")   # Create this module's grammar.
masterRule = RepeatRule()
grammar.add_rule(masterRule)    # Add the top-level rule.
grammar.load()
# grammar.deactivate_rule(masterRule)

def wake():
    global grammar
    grammar.activate_rule(masterRule)

def snooze():
    global grammar
    grammar.deactivate_rule(masterRule)

def unload():
    global grammar
    if grammar: grammar.unload()
    grammar = None

