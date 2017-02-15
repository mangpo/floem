from graph import *
from program import *

def Fork(name, n, type):
    outports = [Port("out%d" % (i+1), [type]) for i in range(n)]
    calls = ["out%d(x);" % (i+1) for i in range(n)]
    src = "(%s x) = in(); output { %s }" % (type, " ".join(calls))
    return Element(name, [Port("in", [type])], outports, src)


def IdentityElement(name, type):
    src = "(%s x) = in(); output { out(x); }" % type
    return Element(name, [Port("in", [type])], [Port("out", [type])], src)


def InjectElement2(name, type, state, size):
    src = r'''
    if(this.p >= %d) { printf("Error: inject more than available entries.\n"); exit(-1); }
    int temp = this.p;
    this.p++;''' % size
    src += "output { out(this.data[temp]); }"
    return Element(name, [], [Port("out", [type])],
                   src, None, [(state, "this")])


def ProbeState(name, type, size):
    return State(name, "%s data[%d]; int p;" % (type, size), "0,0")


def InjectProbeState(name, type, size):
    return State(name, "%s data[%d]; int p;" % (type, size), "0,0")


def ProbeElement(name, type, state, size):
    # TODO: need mutex lock (c) or atomic compare and swap (cpp)
    append = r'''
    if(this.p >= %d) { printf("Error: probe more than available entries.\n"); exit(-1); }
    this.data[this.p] = x;
    this.p++;''' % size
    src = "(%s x) = in(); %s output { out(x); }" % (type, append)
    return Element(name, [Port("in", [type])], [Port("out", [type])],
                   src, None, [(state, "this")])


Fork2 = Fork("Fork2", 2, "int")
Fork3 = Fork("Fork3", 3, "int")
Forward = IdentityElement("Forward", "int")
Add = Element("Add",
              [Port("in1", ["int"]), Port("in2", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in1() + in2(); output { out(x); }''')

Inc = Element("Inc",
              [Port("in", ["int"])],
              [Port("out", ["int"])],
              r'''int x = in() + 1; output { out(x); }''')

Drop = Element("Drop",
              [Port("in", ["int"])],
              [],
              r'''in();''')


def CircularQueue(name, type, size):
    enq = Element("Enqueue",
                  [Port("in", [type])], [],
                  r'''
(%s x) = in();
int next = this.tail + 1;
if(next >= this.size) next = 0;
if(next == this.head) {
  printf("Circular queue is full. A packet is dropped.\n");
} else {
  this.data[this.tail] = x;
  this.tail = next;
}
''' % type, None, [("Queue", "this")])

    deq = Element("Dequeue",
                  [], [Port("out", [type])],
                  r'''
%s x = NULL;
if(this.head == this.tail) {
  printf("Dequeue an empty circular queue.\n");
  exit(-1);
} else {
    x = this.data[this.head];
    int next = this.head + 1;
    if(next >= this.size) next = 0;
    this.head = next;
}
output { out(x); }
''' % type, None, [("Queue", "this")])

    q = Composite(name,
                  [Port("in", ("enq", "in"))],
                  [Port("out", ("deq", "out"))],
                  [Port("dequeue", ("deq", None))],
                  [],
                  Program(
                      State("Queue", "int head; int tail; int size; %s data[%d];" % (type, size), "0,0,%d,{0}" % size),
                      enq, deq,
                      StateInstance("Queue", "queue"),
                      ElementInstance("Enqueue", "enq", ["queue"]),
                      ElementInstance("Dequeue", "deq", ["queue"]),
                  ))
    return q

def Table(name, val_type, size):
    return State(name, "{0} data[{1}];".format(val_type, size), "{0}")

def TableInsert(name, state_name, index_type, val_type, size):
    e = Element(name,
                [Port("in_index", [index_type]), Port("in_value", [val_type])], [],
                r'''
(%s index) = in_index();
(%s val) = in_value();
uint32_t key = index %s %d;
if(this.data[key] == NULL) this.data[key] = val;
else { printf("Hash collision!\n"); exit(-1); }
''' % (index_type, val_type, '%', size), None, [(state_name, "this")])
    return e

def TableGetRemove(name, state_name, index_type, val_type, size):
    e = Element(name,
                [Port("in", [index_type])], [Port("out", [val_type])],
                r'''
(%s index) = in();
uint32_t key = index %s %d;
%s val = this.data[key];
if(val == NULL) { printf("No such entry in this table.\n"); exit(-1); }
this.data[key] = NULL;
output { out(val); }
''' % (index_type, '%', size, val_type), None, [(state_name, "this")])
    return e

def get_table_collection(index_type, val_type, size, insert_instance_name, get_instance_name):
    """
    :param index_type:
    :param val_type:
    :param size:
    :param insert_instance_name:
    :param get_instance_name:
    :return: (state, insert_element, get_element, state_instance, insert_instance, get_instance)
    """
    state_name = ("_table_%s_%d" % (val_type, size)).replace('*', '$')
    state_instance_name = ("_t_%s" % insert_instance_name).replace('*', '$')
    state = Table(state_name, val_type, size)
    state_instance = StateInstance(state_name, state_instance_name)

    insert_element = TableInsert("_element_" + insert_instance_name, state_name, index_type, val_type, size)
    get_element = TableGetRemove("_element_" + get_instance_name, state_name, index_type, val_type, size)
    insert_instance = ElementInstance("_element_" + insert_instance_name, insert_instance_name, [state_instance_name])
    get_instance = ElementInstance("_element_" + get_instance_name, get_instance_name, [state_instance_name])
    return (state, insert_element, get_element, state_instance, insert_instance, get_instance)


