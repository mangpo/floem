from ast import *
from compiler import Compiler

s = State("Shared", "int sum;", "100")

e1 = Element("Sum",
             [Port("in", ["int"])],
             [],
             r'''this.sum += in(); printf("%d\n", this.sum);''',
             None,
             [("Shared", "this")])

compiler = Compiler([e1], [s])
compiler.newStateInstance("Shared", "s")
compiler.defineInstance("Sum", "sum1", ["s"])
compiler.defineInstance("Sum", "sum2", ["s"])
compiler.generateCode()
