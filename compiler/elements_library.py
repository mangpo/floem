from dsl import *


def create_fork(name, n, type):
    outports = [Port("out%d" % (i+1), [type]) for i in range(n)]
    calls = ["out%d(x);" % (i+1) for i in range(n)]
    src = "(%s x) = in(); output { %s }" % (type, " ".join(calls))
    return create_element(name, [Port("in", [type])], outports, src)


def create_identity(name, type):
    src = "(%s x) = in(); output { out(x); }" % type
    return create_element(name, [Port("in", [type])], [Port("out", [type])], src)


def create_add(name, type):
    src = "%s x = in1() + in2(); output { out(x); }" % type
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

def create_circular_queue(name, type, size):
    prefix = "_%s_" % name
    state_name = prefix + "queue"

    Enqueue = create_element(prefix+ "enqueue",
                             [Port("in", [type])], [],
                             r'''
           (%s x) = in();
           int next = this.tail + 1;
           if(next >= this.size) next = 0;
           if(next == this.head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             this.data[this.tail] = x;
             this.tail = next;
           }
           ''' % (type, name), None, [(state_name, "this")])

    Dequeue = create_element(prefix + "dequeue",
                             [], [Port("out", [type])],
                             r'''
           %s x;
           bool avail = false;
           if(this.head == this.tail) {
             printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
             //exit(-1);
           } else {
               avail = true;
               x = this.data[this.head];
               int next = this.head + 1;
               if(next >= this.size) next = 0;
               this.head = next;
           }
           output switch { case avail: out(x); }
           ''' % (type, name), None, [(state_name, "this")])

    Queue = create_state(state_name, "int head; int tail; int size; %s data[%d];" % (type, size),
                         [0,0,size, [0]])

    def func(x, t1, t2):
        queue = Queue()
        enq = Enqueue(prefix + "enqueue", [queue])
        deq = Dequeue(prefix + "dequeue", [queue])
        enq(x)
        y = deq()

        t1.run(False, enq)
        t2.run(True, deq)
        return y

    return create_composite(name, func)