from pycparser import c_parser, c_ast, c_generator
from copy import deepcopy

def rename_function_calls():
    pass

def remove_input_port(func_def, ele_name, inports):
    func_def.decl.name = ele_name
    func_def.decl.type.type.declname = ele_name
    stmts = func_def.body.block_items
    new_stmts = []
    port2args = {}
    for stmt in stmts:
        if type(stmt) == c_ast.Decl and type(stmt.init) == c_ast.FuncCall:
            funccall = stmt.init
            funcname = funccall.name.name
            if funcname in inports:
                if funccall.args:
                    raise Exception("Cannot pass an argument when retrieving data from an input port.")
                myDecl = deepcopy(stmt)
                myDecl.init = None
                port2args[funcname] = myDecl
                continue
        new_stmts.append(stmt)
    func_def.body.block_items = new_stmts
    params = [port2args[x] for x in inports]
    print func_def.decl.type.args
    func_def.decl.type.args = c_ast.ParamList(params)
    func_def.show()

def test():
    src = r'''
run(int xxx) {
  int i = in();
  out(i+1);
}
'''
    parser = c_parser.CParser()
    ast = parser.parse(src)
    print ast.ext
    ast.show()
    remove_input_port(ast.ext[0], "element", ["in"])
    generator = c_generator.CGenerator()

    print generator.visit(ast)

test()
