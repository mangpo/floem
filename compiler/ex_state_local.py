from ast import *
from compiler import Compiler


e1 = Element("Sum",
             [Port("in", ["int"])],
             [],
             r'''this.sum += in(); printf("%d\n", this.sum);''',
             State("this", "int sum;", "100"))

compiler = Compiler([e1])
compiler.defineInstance("Sum", "sum1")
compiler.defineInstance("Sum", "sum2")
compiler.generateCode()
