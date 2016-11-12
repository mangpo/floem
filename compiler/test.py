from pycparser import c_parser, c_ast

def rename_function_calls():
    pass

def remove_input_port(ast,ports):
    typ = type(ast);
    print typ
    body = ast.ext[0].body.block_items
    for stmt in body:
        if type(stmt) == c_ast.Decl and type(stmt.init) == c_ast.FuncCall:
            funccall = stmt.init
            name = funccall.name.name
            if name in ports:
                print name

def test():
    src = r'''
void run() {
  int i = in();
  out(i+1);
}
'''
    parser = c_parser.CParser()
    ast = parser.parse(src)
    ast.show()
    rename_function_calls()
    remove_input_port(ast,["in"])

test()
