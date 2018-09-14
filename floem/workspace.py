from collection import InstancesCollection
import program


######################## Scope ##########################
decls = [[]]
decl_dict = {}
scope = [[]]
stack = []
inst_collection = [InstancesCollection()]


def workspace_reset():
    global decls, decl_dict, scope, stack, inst_collection
    decls = [[]]
    decl_dict = {}
    scope = [[]]
    stack = []
    inst_collection = [InstancesCollection()]


def get_last_decl():
    global decls
    assert len(decls) == 1, "Compile error: there are multiple scopes remained."
    return decls[0]


def decl_append(x):
    decls[-1].append(x)
    decl_dict[x.name] = x


def get_decl(x, env=decl_dict):
    if x in env:
        return env[x]
    elif '__up__' in env:
        return get_decl(x, env=env['__up__'])
    else:
        return False


def push_decl():
    decls.append([])
    global decl_dict
    decl_dict = {'__up__': decl_dict}


def pop_decl():
    global decl_dict
    decl_dict = decl_dict['__up__']

    global decls
    decl = decls[-1]
    decls = decls[:-1]
    return decl

def get_last_scope():
    global scope
    assert len(scope) == 1, "Compile error: there are multiple scopes remained."
    return scope[0]


def get_current_scope():
    return scope[-1]


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


def merge_scope():
    global scope, stack, inst_collection
    stack = stack[:-1]
    my_scope = scope[-1]
    scope = scope[:-1]
    scope[-1] = scope[-1] + my_scope
    my_collection = inst_collection[-1]
    inst_collection = inst_collection[:-1]
    inst_collection[-1].union(my_collection)
    return my_collection


def pop_scope():
    global scope, stack, inst_collection
    stack = stack[:-1]
    my_scope = scope[-1]
    my_collection = inst_collection[-1]
    scope = scope[:-1]
    inst_collection = inst_collection[:-1]
    return my_scope, my_collection


def get_current_collection():
    return inst_collection[-1]


def get_node_name(name):
    if len(stack) > 0:
        return "_".join(stack) + "_" + name
    else:
        return name




