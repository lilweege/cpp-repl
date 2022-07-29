#!/usr/bin/env python3

import subprocess
import os

import argparse

import tempfile

from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText

from pygments.lexers import CppLexer
from pygments.styles import get_style_by_name



def recompile(cflags, rargs, tempDir, lines):
    # TODO: allow more includes
    contents = "#include <stdio.h>\nint main(int argc, char** argv) {\n" + "\n".join(lines) + "\nreturn 0;}"

    srcFileName = os.path.join(tempDir.name, f"repl{len(lines)}.cpp")
    with open(srcFileName, "w+b") as srcFile:
        srcFile.write(contents.encode())

    binExt = ".exe" if os.name == 'nt' else ""
    binFileName = os.path.join(tempDir.name, f"repl{binExt}")

    compileResult = subprocess.run(["clang++", *cflags.split(), "-o", binFileName, srcFile.name])
    if compileResult.returncode != 0:
        return compileResult, None

    runResult = subprocess.run([binFileName, *rargs.split()],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return compileResult, runResult


def repl(args):
    tempDir = tempfile.TemporaryDirectory()

    isMultiline = False
    runError = 0
    lastLine = 1
    braceDiff = 0
    lines = []
    line = ""
    lexer = PygmentsLexer(CppLexer)
    history = InMemoryHistory()
    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
    )

    while True:
        try:
            color = "ansibrightgreen" if runError == 0 else "ansibrightred"
            basePromptText = f"[{len(lines)}]: "
            prompText = "..." + " "*(len(basePromptText)-3) \
                if line != "" else FormattedText([(color, basePromptText)])
            lastInput = session.prompt(prompText,
                lexer=lexer,
                style=style_from_pygments_cls(get_style_by_name("monokai")),
                include_default_pygments_style=False,
                multiline=isMultiline,
                prompt_continuation=lambda width, lineNo, wrapCount: "... " if wrapCount == 0 else "",
            )
        except KeyboardInterrupt:
            lastInput = ""
        except EOFError:
            break

        lastInput = lastInput.rstrip()

        # TODO: document this feature
        if lastInput.endswith("`"):
            print("")
            line = ""
            isMultiline = not isMultiline
            continue

        if not lastInput:
            print("")
            continue

        braceDiff += lastInput.count("{") - lastInput.count("}")

        line += lastInput
        if braceDiff > 0:
            continue

        lines.append(line)
        line = ""
        compileResult, runResult = recompile(args.cflags, args.rargs, tempDir, lines)
        if compileResult.returncode != 0:
            lines.pop()
            runError = None
        else:
            # FIXME: this gets messed up if stdout and stderr are both written to without flushing.
            # The output does not necessarily come in order
            runError = runResult.returncode
            output = runResult.stdout.decode().split("\n")
            if len(output) > lastLine:
                lineDiff = output[lastLine-1:-1]
                print("\n".join(lineDiff))
                lastLine = len(output)

        print("")

    tempDir.cleanup()


def main():
    parser = argparse.ArgumentParser(description="A basic REPL frontend for clang++")
    parser.add_argument("-cflags", dest="cflags", type=str, default="", help="Compiler flags passed to compiler.")
    parser.add_argument("-rargs", dest="rargs", type=str, default="", help="Command line arguments passed to the program.")
    args = parser.parse_args()
    repl(args)

if __name__ == "__main__":
    main()

