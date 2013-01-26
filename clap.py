#!/usr/bin/env python3

"""command line arguments parser"""

import sys

__version__ = "0.0.2"
__vertuple__ = tuple( int(i) for i in __version__.split(".") )

class UnexpectedOptionError(Exception): pass
class SwitchValueError(Exception): pass
class NotParsedError(Exception): pass
class OptionNotFoundError(LookupError): pass

def _main():
    parser = Parser(short="v", long=["version", "help"], argv=sys.argv[1:])
    try:
        parser.parse()
        if parser.waspassed("-v") or parser.waspassed("--version"): print("clap (Command Line Arguments Parser) {0}".format(__version__))
        if parser.waspassed("--help"): 
            print("OPTIONS:\n\t--version  print version and exit\n\t--help     print this message\n")
            print("Author: Marek Marecki (triviuss@gmail.com)")
    except UnexpectedOptionError as e: 
        print("**clap: error: doesn't know what to do with '{0}'".format(str(e).split(": ")[-1]))
    finally:
        pass

class Parser():
    def __init__(self, short="", long=[], argv=[]):
        self.setshort(short)
        self.setlong(long)
        self.setargv(argv)
        self.opts, self.args = ([], [])
        self.parsed = False
    
    def setshort(self, opts):
        """
        Sets short options. Accepts string.
        """
        shorts = []
        for i, opt in enumerate(opts):
            try:
                if opts[i+1] == ":": opt += ":"
            except IndexError: 
                pass
            finally: 
                if opt != ":": shorts.append("-{0}".format(opt))
        self.descript_short = shorts

    def _splitshorts(self):
        """
        This method scans items passed from command line and splits any short options passed together eg. 
        '-lhR'. It this case the '-lhR' will become '-l', '-h', '-R'. 
        Connecting options that require a value is forbidden.
        """
        argv = []
        for i, arg in enumerate(self.argv):
            if self._areopts([ "-{0}".format(opt) for opt in list(arg)[1:] ], mode="s") and arg[0] == "-" and arg != "--": 
                arg = [ "-{0}".format(opt) for opt in list(arg)[1:] ]
            elif arg == "--":
                argv.append("--")
                break
            else: 
                arg = [arg]
            argv.extend(arg)
        self.argv = argv + self.argv[i+1:]

    def setlong(self, opts):
        """
        Sets long options. Accepts list of strings.
        """
        self.descript_long = opts

    def setargv(self, argv):
        """
        Sets list of arguments from command line or custom made (eg. generated by a client program).
        """
        self.argv = argv

    def getshorts(self):
        """
        Returns list of short options accepted by this instance of Parser().
        """
        return self.descript_short
    
    def getlongs(self):
        """
        Returns list of long options accepted by this instance of Parser().
        """
        return [ "--{0}".format(opt) for opt in self.descript_long ]
    
    def _areopts(self, opts, mode="b"):
        """
        Checks if given list contain only options accepted by this instance of Parser(). 
        You have to pass it in full form eg. `--verbose` and `-v`. 
        Value indicator (`:`) has to be explicitly given. 
        
        Modes are:
         *  's' - for short options,
         *  'l' - for long options,
         *  'b' - for types,
        """
        result = True
        for opt in opts:
            result = self.isopt(opt, mode=mode)
            if not result: break
        return result

    def isopt(self, opt, mode="b"):
        """
        Checks if given string is a valid option for this instance of Parser(). 
        You have to pass it in full form eg. `--verbose` and `-v`. 
        Value indicator (`:`) has to be explicitly given. 
        
        Modes are:
         *  's' - for short options,
         *  'l' - for long options,
         *  'b' - for types,
        """
        if mode == "s": result = opt in self.descript_short
        elif mode == "l": result = opt[2:] in self.descript_long
        else: result = self.isopt(opt, mode="s") or self.isopt(opt, mode="l")
        return result

    def check(self, strict=False):
        """
        Scans for problems in passed arguments. 
         *  missing values for options which require it.
        """
        for i, arg in enumerate(self.argv):
            if self.isopt("{0}:".format(arg)) and i+1 == len(self.argv): 
                raise SwitchValueError("'{0}' option requires a value but run out of arguments".format(self.argv[i]))
            if self.isopt("{0}:".format(arg)) and strict: 
                if self.isopt("{0}:".format(self.argv[i+1])) or self.isopt(self.argv[i+1]): 
                    raise SwitchValueError("'{0}' option requires a value but an option was found".format(self.argv[i]))
        
    def _parseopts(self):
        """
        Parses options from the command line and assigns values to them if needed.
        """
        opts = []
        i = 0
        while i < len(self.argv):
            opt = self.argv[i]
            if opt == "--":
                i += 1
                break
            elif self.isopt(opt):
                value = ""
            elif self.isopt("{0}:".format(opt)):
                i += 1
                if len(self.argv) <= i: raise SwitchValueError("'{0}' option requires a value but run out of arguments".format(opt))
                else: value = self.argv[i]
            elif opt[0] == "-":
                raise UnexpectedOptionError("unexpected option found: {0}".format(opt))
            else:
                break
            opts.append( (opt, value) )
            i += 1
        self.opts = opts
        return i
    
    def parse(self):
        """
        Parses contents of `argv` and splits them into options and arguments.
        """
        #   _parseopts() returns index at which it stopped parsing options 
        #   this means that after this index there are only arguments
        n = self._parseopts()
        self.args = self.argv[n:]
        self.parsed = True
    
    def listaccepted(self):
        """
        Returns list of options by this instance of Parser().
        """
        opts = []
        for opt in self.descript_short: opts.append(opt)
        for opt in self.descript_long: opts.append( "--{0}".format(opt) )
        while "--" in opts: opts.remove("--")
        return opts

    def waspassed(self, opt):
        """
        Checks if the given option was passed.
        Returns boolean value.
        """
        return opt in self.getpassed()
        
    def getpassed(self):
        """
        Returns list of options passed to this instance of Parser().
        """
        if not self.parsed: raise NotParsedError("getpassed() used on object with unparsed options")
        return [ opt for opt, value in self.opts ]

    def getopt(self, opt):
        """
        Returns options value or empty string if the option does not accept values.
        Raises OptionNotFoundError if option has not been found.
        """
        value = None
        for optkey, optvalue in self.opts:
            if optkey == opt:
                value = optvalue
                break
        if value == None: raise OptionNotFoundError("'{0}' not found in passed options".format(opt))
        return value

    def getargs(self):
        """
        Returns list of arguments passed from command line.
        """
        return self.args


if __name__ == "__main__": _main()
