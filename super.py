from dragonfly import *
from dragonfly.actions import keyboard
from hide.action_delay import Delay
from hide.action_variable import *
from hide.action_mouse import *
import time
import re
import sys
import exit_now as en
import yaml

_pause = 0.001
Typeable.MOD_DELAY = _pause

########################################
## utility functions
########################################

def flatten(l):
    r = []
    for ll in l:
        r.extend(ll)
    return r


########################################
## read configuration data
########################################

with open("super.yaml") as yaml_file:
    yaml_data = yaml.load(yaml_file, Loader=yaml.Loader)

escapeWord = yaml_data['escape']
escapeWordPlus = "+" + escapeWord

replayWord = yaml_data['replay']
replayWordPlus = "+" + replayWord

substitutions = {}
for f, t in [(substitute['from'], substitute['to']) for substitute in yaml_data['substitutions']]:
    firstWord = f[0]
    otherWords = f[1:]
    if firstWord in substitutions:
        substitutions[firstWord].append([otherWords, t])
    else:
        substitutions[firstWord] = [[otherWords, t],]
for v in substitutions.values():
    v.sort(lambda a,b:len(b[0]) - len(a[0]))

mangleMap = {}

for k, v in yaml_data['mangles'].items():
    delim = v.get("delimiter", "")
    xform = v.get("xform", "None")
    firstXform = v.get("firstXform", xform)
    mangleMap[k] = (delim, eval(firstXform), eval(xform))

commandWords = yaml_data['commands']
windowLeaps = yaml_data['windowLeaps']
soundsLike = yaml_data['soundsLike']
specialWords = yaml_data['special']

plainWords = yaml_data['words']
plainWords.extend((
    wordWithPlus[1:]
    for wordWithPlus
    in flatten((
        substitute['from']
        for substitute
        in yaml_data['substitutions']))))
plainWords.append(escapeWord)
plainWords.append(replayWord)
plainWords = set(plainWords)

########################################
## stages of processing speach
########################################

escaped = False
def substituteWords(words):
    global escaped

    # replace any word chains
    words2 = []
    i = 0
    while i < len(words):
        word = words[i]

        if escaped:
            words2.append(word)
            escaped = False
        elif word == escapeWordPlus:
            escaped = True
        else:
            if word in substitutions:
                for otherWords, replaceWord in substitutions[word]:
                    if not otherWords or words[i+1:i+len(otherWords)+1] == otherWords:
                        word = replaceWord
                        i += len(otherWords)
                        break
            words2.append(word)
        i += 1
    words = words2

    return words2


KEY_PATTERN = re.compile("^[*/]?[-]?[+]?_")
def phraseSplit(words):
    "split a list of words into a list of 'phrases', each phrase being a list of words to be processed separately"
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

def hide(word):
    if word and word.startswith('*'):
        return '*'*(len(word)-1)
    else:
        return word

def processText(text):
    words = flatten(text)
    print("RAW WORDS: [" + "|".join([repr(str(hide(word)))[1:-1] for word in words]) + "]")
    words = substituteWords(words)
    print("META WORDS: [" + "|".join([repr(str(hide(word)))[1:-1] for word in words]) + "]")
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
        print("-----------------------")
        print("START RECORDING MACRO")
        voiceEvents = []
        wasTrailingSpace = False
        return True
def stopMacro(words):
    global macroOn, macroEvents, voiceEvents, wasTrailingSpace
    if macroOn and len(words) >= 3 and words[:2] == ['+stop', '+macro']:
        words = tuple(words[2:])
        print('----- STOP MACRO %s'%(repr(words)))
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
            print('----- PLAY MACRO %s'%(repr(words)))
        else:
            print("COULD NOT PLAY MACRO %s from set %s"%(words, macros.keys()))
        voiceEvents = foundEvents
    
def processMacros():
    global voiceEvents, eventHistory, escaped, macroOn

    if len([1 for x in voiceEvents if x[0] != 'w']) == 0:
        words = [word for words in voiceEvents if words[0] == 'w' for word in words[1]]
        if words == [replayWordPlus]:
            print("REPLAY")
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
    print("-----------------------")
    if voiceEvents == [('w', [replayWordPlus])]:
        print("REPLAY")
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
                    wordLists.append((escapeWordPlus, name))
                    escaped = False
                else:
                    print("KEY:", spec)
                    keyboard.keyboard.send_keyboard_events(events)
                    eventHistory.append(('k', events))
            elif key == 'a':
                action, data, name = payload
                if escaped:
                    wordLists.append((escapeWordPlus, name))
                    escaped = False
                else:
                    print("EXEC:", name)
                    try:
                        action._execute(data)
                    except Exception, e:
                        print("Exception:", e)
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

class RecordActions(ActionBase):
    def __init__(self, actions, name="unknown"):
        ActionBase.__init__(self)
        self._actions = actions
        self._name = name
    def _execute(self, data):
        global voiceEvents
        for action in self._actions:
            voiceEvents.append(('a', (action, data, self._name)))

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

listenMap = {
    # quick exit
    "snooze":                           Function(lambda : en.exit_now()),

    "zook":                             ReleaseModifiers(),

    # dictation
    # meant to catch everything, but some words need help being recognized
    "<text>":                           RecordDictation("%(text)s"),

    # Literals
    "numb <nn>":                        RecordWord("-_%(nn)d"),

    # window navigation
    "list leaps":                       Function(lambda : FocusWindow.ls()),
}

listenMap.update([
    (wordWithPlus[1:], RecordWord(wordWithPlus))
    for wordWithPlus
    in substitutions.keys()])

listenMap.update([
    (word, RecordWord("+" + word))
    for word
    in plainWords])

listenMap.update([
    (sound, RecordWord(script))
    for sound, script
    in soundsLike.items()])

def createAction(scriptCommand):
    if scriptCommand[0:2] == "K:":
        return Key(scriptCommand[2:])
    elif scriptCommand[0:3] == "MS:":
        return MouseSequence(scriptCommand[3:])
    elif scriptCommand[0:2] == "M:":
        return Mouse(scriptCommand[2:], sound)
    elif scriptCommand[0:2] == "D:":
        action = createAction(scriptCommand[2:])
        if action:
            return DelayedAction(action)
    else:
        print "Special command not recognized:", scriptCommand

def createSpecialSequence(sound, script):
    actions = []
    if type(script) == str:
        action = createAction(script)
        if action:
            actions.append(action)
    elif type(script) == list:
        for scriptCommand in script:
            action = createAction(scriptCommand)
            if action:
                actions.append(action)
    return RecordActions(actions, sound)

listenMap.update([
    (sound, createSpecialSequence(script, script))
    for sound, script
    in specialWords.items()])

# commandWords overwrite plainWords
listenMap.update([
    (word, RecordWord("-" + word + " "))
    for word
    in commandWords])

listenMap.update([
    ("leap " + words, RecordAction(FocusWindow(title=theTitle)))
    for words, theTitle
    in windowLeaps.items()])

config            = Config("super edit")
config.cmd        = Section("Language section")
config.cmd.map    = Item(
    listenMap,
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

print "super.py Done loading"

