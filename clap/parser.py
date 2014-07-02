"""RedCLAP parser module.
"""

from . import shared

try: from clap_typehandlers import TYPEHANDLERS
except ImportError: TYPEHANDLERS = {}
finally: pass


class ParsedUI:
    """Object returned by parser, containing parsed commandline arguments in a usale form.
    """
    def __init__(self):
        self._options = {}
        self._operands = []
        self._name = ''
        self._mode = None
        self._child, self._parent = None, None

    def __contains__(self, option):
        """Check if option is present.
        """
        return option in self._options

    def __iter__(self):
        """Return iterator over operands.
        """
        return iter(self._operands)

    def __str__(self):
        """Return name of current mode.
        """
        return self._name

    def __len__(self):
        """Return number of operands.
        """
        return len(self._operands)

    def _appendmode(self, mode):
        """Append parsed nested mode.
        """
        mode._parent = self
        self._child = mode

    def down(self):
        """Go to nested mode.
        """
        return (self._child if self._child is not None else self)

    def up(self):
        """Go to parent mode.
        """
        return (self._parent if self._parent is not None else self)

    def top(self):
        """Go to top of command chain.
        """
        cherry = self
        while cherry._parent is not None: cherry = cherry._parent
        return cherry

    def islast(self):
        """Return true if current mode has no nested modes.
        """
        return self._child is None

    def finalise(self):
        """Perform needed finalisation.
        """
        if self._child is not None:
            for k, v in self._options.items():
                is_global, match = False, None
                for o in self._mode.options(group='global'):
                    if o.match(k):
                        is_global, match = True, o
                        break
                if is_global:
                    if k in self._child._options and match.isplural() and not match.params(): self._child._options[k] += v
                    if k not in self._child._options: self._child._options[k] = v
            self._child.finalise()
        return self

    def get(self, key, tuplise=True):
        """Returns arguments passed to an option.
        - options that take no arguments return None,
        - options that are plural AND take no argument return number of times they were passed,
        - options that take exactly one argument return it directly,
        - options that take at least two arguments return tuple containing their arguments,
        - options that take at least one argument AND are plural return list of tuples containing arguments passed
          to each occurence of the option in input,
        
        Tuple-isation can be switched off by passing 'tuplise` parameter as false;
        in such case lists are returned for options that take at least two arguments and
        direct values for options taking one argumet or less.
        """
        option = self._mode.getopt(key)
        value = self._options[key]
        if option.isplural() and not option.params(): return value
        if not option.params(): return None
        if len(option.params()) == 1 and not option.isplural(): return value[0]
        if tuplise: value = ([tuple(v) for v in value] if option.isplural() else tuple(value))
        return value

    def operands(self):
        """Return copy of the list of operands.
        """
        return self._operands[:]


class Parser:
    """Object that, after being fed with command line arguments and mode,
    parses the arguments according to the mode.
    """
    def __init__(self, mode, argv=[]):
        self._args = argv
        self._mode, self._current = mode, mode
        self._parsed = {'options': {}, 'operands': []}
        self._breaker = False
        self._ui = None
        self._typehandlers = {'str': str, 'int': int, 'float': float}
        self._loadtypehandlers()

    def __contains__(self, option):
        """Checks if parser contains given option.
        """
        return option in self._parsed['options']

    def _loadtypehandlers(self):
        """Loads typehandlers from TYPEHANDLERS dict.
        """
        for name, callback in TYPEHANDLERS.items(): self._typehandlers[name] = callback

    def feed(self, argv):
        """Feed argv to parser.
        """
        self._args = argv
        return self

    def getargs(self):
        """Returns list of arguments.
        """
        return self._args

    def addTypeHandler(self, name, callback):
        """Registers type handler for custom type.
        """
        self._typehandlers[name] = callback
        return self

    def _getinput(self):
        """Returns list of options and arguments until '--' string or
        first non-option and non-option-argument string.
        Simple description: returns input without operands.
        """
        index, i = -1, 0
        input = []
        while i < len(self._args):
            item = self._args[i]
            #   if a breaker is encountered -> break
            if item == '--': break
            #   if non-option string is encountered and it's not an argument -> break
            if i == 0 and not shared.lookslikeopt(item): break
            if i > 0 and not shared.lookslikeopt(item) and not shared.lookslikeopt(self._args[i-1]): break
            if i > 0 and not shared.lookslikeopt(item) and shared.lookslikeopt(self._args[i-1]) and not self._mode.params(self._args[i-1]): break
            #   if non-option string is encountered and it's an argument
            #   increase counter by the number of arguments the option requests and
            #   proceed further
            if i > 0 and not shared.lookslikeopt(item) and shared.lookslikeopt(self._args[i-1]) and self._mode.params(self._args[i-1]):
                i += len(self._mode.params(self._args[i-1]))-1
            index = i
            i += 1
        if index >= 0:
            #   if index is at least equal to zero this means that some input was found
            input = self._args[:index+1]
        return input

    def _getoperands(self, heur=True):
        """Returns list of operands passed.
        """
        if heur and self._mode.modes() and self.getOperandsRange()[1] is not None: return self._getheuroperands()[0]
        n = len(self._getinput())
        operands = self._args[n:]
        if operands: self._breaker = (operands[0] == '--')
        if self._breaker and operands: operands.pop(0)
        operands = (operands[:operands.index('---')] if ('---' in operands and self._breaker) else operands[:])
        return operands

    def _isAcceptedInChildModes(self, option):
        """Return true if given option is accepted in at least one child mode.
        """
        accepted = False
        for m in self._mode.modes():
            if self._mode.getmode(m).accepts(option):
                accepted = True
                break
        return accepted

    def _heuralgo(self, opers):
        """Algorithm for fixed ranges of operands.
        """
        operands, nested = [], []
        i = 0
        while i < len(opers):
            item = opers[i]
            if self._mode.hasmode(item): break
            if shared.lookslikeopt(item):
                accepted = self._isAcceptedInChildModes(item)
                if accepted:
                    operands.pop(-1)
                    i -= 1
                    break
            operands.append(item)
            i += 1
        nested = opers[i:]
        return (operands, nested)

    def _getheuroperands(self):
        """Returns two-tuple: (operands-for-current-mode, items-for-child-mode).
        Uses simple algorithms to detect nested modes and split the operands.
        """
        n = len(self._getinput())
        operands = self._args[n:]
        breaker = ((operands[0] == '--') if operands else False)
        if breaker and operands: operands.pop(0)
        if not breaker:
            operands, nested = self._heuralgo(operands)
        else:
            nested = []
        return (operands, nested)

    def _ininput(self, option):
        """Check if given option is present in input.
        """
        is_in = False
        i = 0
        input = self._getinput()
        while i < len(input):
            s = input[i]
            if option.match(s):
                is_in = True
                break
            if shared.lookslikeopt(s) and self._mode.accepts(s): i += len(self._mode.getopt(s).params())
            i += 1
        return is_in

    def _strininput(self, string):
        """Check if given string is present in input.
        """
        is_in = False
        i = 0
        input = self._getinput()
        while i < len(input):
            s = input[i]
            if string == s:
                is_in = True
                break
            if shared.lookslikeopt(s) and self._mode.accepts(s): i += len(self._mode.getopt(s).params())
            i += 1
        return is_in

    def _whichaliasin(self, option):
        """Returns which variant of option (long or short) is present in input.
        Used internaly when checking input. Empty string indicates that no variant
        is present (option is not present).

        `option` takes precendence over `string`.

        :param option: option name
        :type option: str
        """
        input = self._getinput()
        #if string:
        #    name = string
        #    alias = self.alias(string)
        if option:
            name = str(option)
            alias = option.alias(name)
        variant = ''
        if name in input: variant = name
        if alias and (alias in input): variant = alias
        return variant

    def parse(self):
        """Parsing method for RedCLAP.
        """
        self._ui = ParsedUI()
        self._ui._mode = self._mode
        options = []
        operands = []
        input = self._getinput()
        i = 0
        while i < len(input):
            item = input[i]
            if shared.lookslikeopt(item) and self._mode.accepts(item) and not self._mode.params(item):
                options.append( (item, None) )
                alias = self._mode.alias(item)
                if alias != item: options.append( (alias, None) )
            elif shared.lookslikeopt(item) and self._mode.accepts(item) and self._mode.params(item):
                n = len(self._mode.params(item))
                params = input[i+1:i+1+n]
                for j, callback in enumerate(self._mode.params(item)):
                    if type(callback) is str: callback = self._typehandlers[callback]
                    params[j] = callback(params[j])
                options.append( (item, params) )
                alias = self._mode.alias(item)
                if alias != item: options.append( (alias, params) )
                i += n
            else:
                break
            i += 1
        for opt, args in options:
            if self._mode.getopt(opt)['plural'] and self._mode.getopt(opt).params():
                if opt not in self._parsed['options']: self._parsed['options'][opt] = []
                self._parsed['options'][opt].append(args)
            elif self._mode.getopt(opt)['plural'] and not self._mode.getopt(opt).params():
                if opt not in self._parsed['options']: self._parsed['options'][opt] = 0
                self._parsed['options'][opt] += 1
            else:
                self._parsed['options'][opt] = (tuple(args) if args is not None else args)
        operands, nested = self._getheuroperands()
        self._parsed['operands'] = operands
        self._ui._options = self._parsed['options']
        self._ui._operands = self._parsed['operands']
        if nested:
            name = nested.pop(0)
            mode = self._mode._modes[name]
            ui = Parser(mode).feed(nested).parse().ui()
            ui._name = name
            ui._mode = mode
            self._ui._appendmode(mode=ui)
        return self

    def ui(self):
        """Return parsed UI.
        """
        return self._ui

    def get(self, key, tuplise=True):
        """Returns arguments passed to an option.
        - options that take no arguments return None,
        - options that are plural AND take no argument return number of times they were passed,
        - options that take exactly one argument return it directly,
        - options that take at least two arguments return tuple containing their arguments,
        - options that take at least one argument AND are plural return list of tuples containing arguments passed
          to each occurence of the option in input,
        
        Tuple-isation can be switched off by passing 'tuplise` parameter as false;
        in such case lists are returned for options that take at least two arguments and
        direct values for options taking one argumet or less.
        """
        option = self._mode.getopt(key)
        value = self._parsed['options'][key]
        if option.isplural() and not option.params(): return value
        if not option.params(): return None
        if len(option.params()) == 1 and not option.isplural(): return value[0]
        if tuplise: value = ([tuple(v) for v in value] if option.isplural() else tuple(value))
        return value

    def getoperands(self):
        """Returns list of operands.
        """
        return self._parsed['operands']
