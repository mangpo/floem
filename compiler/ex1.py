from ast import *
from compiler import Compiler


e1 = Element("Fork",
             [Port("in", ["int","int"])],
             [Port("to_add", ["int"]), Port("to_sub", ["int"])], 
             r'''(int x, int y) = in(); to_add(x,y); to_sub(x,y);''')
e2 = Element("Add",
             [Port("in", ["int","int"])],
             [Port("out", ["int"])], 
             r'''(int x, int y) = in(); out(x+y);''')
e3 = Element("Sub",
             [Port("in", ["int","int"])],
             [Port("out", ["int"])], 
             r'''(int x, int y) = in(); out(x-y);''')
e4 = Element("Print",
             [Port("in", ["int"])],
             [], 
             r'''printf("%d\n",in());''')

compiler = Compiler([e1,e2,e3,e4])
compiler.defineInstance("Fork","Fork")
compiler.defineInstance("Add","Add")
compiler.defineInstance("Sub","Sub")
compiler.defineInstance("Print","Print")
compiler.connect("Fork","Add","to_add")
compiler.connect("Fork","Sub","to_sub")
compiler.connect("Add","Print")
compiler.connect("Sub","Print")
compiler.generateCode()
