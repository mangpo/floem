from dsl import *


def create_fork(name, n, type):
    outports = [Port("out%d" % (i+1), [type]) for i in range(n)]
    calls = ["out%d(x);" % (i+1) for i in range(n)]
    src = "(%s x) = in(); output { %s }" % (type, " ".join(calls))
    return create_element(name, [Port("in", [type])], outports, src)


def create_fork_instance(inst_name, n, type):
    ele_name = "_element_" + inst_name
    ele = create_fork(ele_name, n, type)
    return ele(inst_name)


def create_identity(name, type):
    src = "(%s x) = in(); output { out(x); }" % type
    return create_element(name, [Port("in", [type])], [Port("out", [type])], src)


def create_drop(name, type):
    return create_element(name, [Port("in", [type])], [], "in();")


def create_add(name, type):
    return create_element(name,
                          [Port("in1", [type]), Port("in2", [type])],
                          [Port("out", [type])],
                          r'''int x = in1() + in2(); output { out(x); }''')


def create_add1(name, type):
    src = "%s x = in() + 1; output { out(x); }" % type
    return create_element(name,
                          [Port("in", [type])],
                          [Port("out", [type])],
                          src)


def create_drop(name, type):
    return create_element(name,
                          [Port("in", [type])],
                          [],
                          r'''in();''')

def create_table(put_name, get_name, index_type, val_type, size):
    state_name = ("_table_%s_%d" % (val_type, size)).replace('*', '$')
    state_instance_name = "_table_%s" % put_name
    Table = create_state(state_name, "{0} data[{1}];".format(val_type, size), [[0]])
    TablePut = create_element(put_name,
                              [Port("in_index", [index_type]), Port("in_value", [val_type])], [],
                              r'''
              (%s index) = in_index();
              (%s val) = in_value();
              uint32_t key = index %s %d;
              if(this->data[key] == NULL) this->data[key] = val;
              else { printf("Hash collision! Key = %s\n", key); exit(-1); }
              ''' % (index_type, val_type, '%', size, '%d'),
                              None, [(state_name, "this")])

    TableGet = create_element(get_name,
                              [Port("in", [index_type])], [Port("out", [val_type])],
                              r'''
              (%s index) = in();
              uint32_t key = index %s %d;
              %s val = this->data[key];
              if(val == NULL) { printf("No such entry in this table. Key = %s\n", key); exit(-1); }
              this->data[key] = NULL;
              output { out(val); }
              ''' % (index_type, '%', size, val_type, '%d'), None, [(state_name, "this")])

    table = Table(state_instance_name)

    def put(name=None):
        if name is None:
            global fresh_id
            name = put_name + str(fresh_id)
            fresh_id += 1
        return TablePut(name, [table])

    def get(name=None):
        if name is None:
            global fresh_id
            name = get_name + str(fresh_id)
            fresh_id += 1
        return TableGet(name, [table])

    return put, get


def create_table_instances(put_name, get_name, index_type, val_type, size):
    put, get = create_table("_element_" + put_name, "_element_" + get_name, index_type, val_type, size)
    return put(put_name), get(get_name)


def create_inject(name, type, size, func, interval=50):
    st_name = name + "_state"
    st_inst_name = name + "_state_inst"
    state = create_state(st_name, "%s data[%d]; int p;" % (type, size), [[0],0])
    state_inst = state(st_inst_name)
    src = r'''
        if(this->p >= %d) { printf("Error: inject more than available entries.\n"); exit(-1); }
        int temp = this->p;
        this->p++;''' % size
    src += "output { out(this->data[temp]); }"
    element = create_element(name, [], [Port("out", [type])], src, None, [(st_name, "this")])
    populte_state(name, st_inst_name, st_name, type, size, func, interval)
    fresh_id = [0]

    def create(inst_name=None):
        if not inst_name:
            inst_name = name + "_inst" + str(fresh_id[0])
            fresh_id[0] += 1
        return element(inst_name, [state_inst])
    return create


def create_inject_instance(name, type, size, func):
    inject = create_inject(name, type, size, func)
    return inject()


def create_probe(name, type, size, func):
    st_name = name + "_state"
    st_inst_name = name + "_state_inst"
    state = create_state(st_name, "%s data[%d]; int p;" % (type, size), [[0],0])
    state_inst = state(st_inst_name)

    append = r'''
        if(this->p >= %d) { printf("Error: probe more than available entries.\n"); exit(-1); }
        this->data[this->p] = x;
        this->p++;''' % size
    src = "(%s x) = in(); %s output { out(x); }" % (type, append)
    element = create_element(name, [Port("in", [type])], [Port("out", [type])], src, None, [(st_name, "this")])
    compare_state(name, st_inst_name, st_name, type, size, func)

    def create(inst_name=None):
        if inst_name is None:
            global fresh_id
            inst_name = name + str(fresh_id)
            fresh_id += 1
        return element(inst_name, [state_inst])
    return create