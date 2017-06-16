from collection import InstancesCollection
import program
import compiler
import desugaring

######################## Scope ##########################
scope = [[]]
stack = []
inst_collection = [InstancesCollection()]


def reset():
    global scope, stack, inst_collection
    scope = [[]]
    stack = []
    inst_collection = [InstancesCollection()]


def get_scope():
    return scope


def scope_append(x):
    scope[-1].append(x)
    if isinstance(x, program.ElementInstance):
        inst_collection[-1].add(x.name)
    elif isinstance(x, program.Connect):
        inst_collection[-1].add(x.ele1)
        inst_collection[-1].add(x.ele2)


def scope_prepend(x):
    scope[-1].insert(0, x)


def push_scope(name):
    scope.append([])
    stack.append(name)
    inst_collection.append(InstancesCollection())


def pop_scope():
    global scope, stack, inst_collection
    stack = stack[:-1]
    my_scope = scope[-1]
    scope = scope[:-1]
    scope[-1] = scope[-1] + my_scope
    my_collection = inst_collection[-1]
    inst_collection = inst_collection[:-1]
    return my_collection


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name

####################### Compiler #########################
class Compiler:
    def __init__(self):
        self.desugar_mode = "impl"
        self.resource = True
        self.remove_unused = True

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

        # Compiler option
        self.I = None

    def generate_graph(self, filename="tmp"):
        assert len(scope) == 1, "Compile error: there are multiple scopes remained."
        p1 = program.Program(*scope[0])
        p2 = desugaring.desugar(p1, self.desugar_mode)
        dp = desugaring.insert_fork(p2)
        g = compiler.generate_graph(dp, self.resource, self.remove_unused, filename, None)  # TODO: state_mapping
        return g

    def generate_code(self):
        compiler.generate_code(self.generate_graph(), ".c", self.testing, self.include)

    def generate_code_and_run(self, expect=None):
        compiler.generate_code_and_run(self.generate_graph(), self.testing, self.desugar_mode, expect, self.include, self.depend)

    def generate_code_and_compile(self):
        compiler.generate_code_and_compile(self.generate_graph(), self.testing, self.desugar_mode, self.include, self.depend)

    def generate_code_as_header(self, header='tmp'):
        compiler.generate_code_as_header(self.generate_graph(header), self.testing, self.desugar_mode, self.include)

    def compile_and_run(self, name):
        compiler.compile_and_run(name, self.depend)


