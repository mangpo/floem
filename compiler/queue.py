from program import *
from dsl import *


def declare_circular_queue(name, type, size, blocking=False):
    prefix = "_%s_" % name
    state_name = prefix + "queue"

    Enqueue = create_element(prefix + "enqueue",
                             [Port("in", [type])], [],
                             r'''
           (%s x) = in();
           int next = this.tail + 1;
           if(next >= this.size) next = 0;
           if(next == this.head) {
             //printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             this.data[this.tail] = x;
             this.tail = next;
           }
           ''' % (type, name), None, [(state_name, "this")])

    if blocking:
        src = r'''
            %s x;
            while(this.head == this.tail) { fflush(stdout); }
            x = this.data[this.head];
            int next = this.head + 1;
            if(next >= this.size) next = 0;
            this.head = next;
            output { out(x); }
            ''' % type
    else:
        src = r'''
            fflush(stdout);
            %s x;
            bool avail = false;
            if(this.head == this.tail) {
                //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
                //exit(-1);
            } else {
                avail = true;
                x = this.data[this.head];
               int next = this.head + 1;
                if(next >= this.size) next = 0;
                this.head = next;
            }
            output switch { case avail: out(x); }
            ''' % (type, name)

    Dequeue = create_element(prefix + "dequeue", [], [Port("out", [type])],
                             src, None, [(state_name, "this")])

    Queue = create_state(state_name, "int head; int tail; int size; %s data[%d];" % (type, size),
                         [0, 0, size, [0]])

    return Queue, Enqueue, Dequeue


def create_circular_queue(name, type, size, blocking=False):
    prefix = "_%s_" % name
    Queue, Enqueue, Dequeue = declare_circular_queue(name, type, size, blocking)

    def func(x, t1, t2):
        queue = Queue()
        enq = Enqueue(prefix + "enqueue", [queue])
        deq = Dequeue(prefix + "dequeue", [queue])
        enq(x)
        y = deq()

        t1.run(enq)
        t2.run_start(deq)
        return y

    return create_composite(name, func)


def create_circular_queue_instance(name, type, size, blocking=False):
    ele_name = "_element_" + name
    ele = create_circular_queue(ele_name, type, size, blocking)
    return ele(name)


def create_circular_queue_instances(name, type, size, blocking=False):
    prefix = "_%s_" % name
    Queue, Enqueue, Dequeue = declare_circular_queue(name, type, size, blocking)
    queue = Queue()
    enq = Enqueue(prefix + "enqueue", [queue])
    deq = Dequeue(prefix + "dequeue", [queue])
    return enq, deq


def create_circular_queue_one2many_instances(name, type, size, n_cores):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    all_instance_name = all_name + "_inst"

    One = create_state(one_name, "int head; int tail; int size; %s data[%d];" % (type, size), [0,0,size,[0]])
    ones = [One(one_instance_name + str(i)) for i in range(n_cores)]

    All = create_state(all_name, "%s* cores[%d];" % (one_name, n_cores))
    all = All(all_instance_name, [AddressOf(ones[i]) for i in range(n_cores)])

    Enqueue = create_element(prefix + "enqueue_ele",
                             [Port("in_entry", [type]), Port("in_core", ["size_t"])], [],
                             r'''
           (size_t c) = in_core();
           (%s x) = in_entry();
           %s* p = this.cores[c];
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             p->data[p->tail] = x;
             p->tail = next;
           }
            fflush(stdout);
           ''' % (type, one_name, name), None, [(all_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
                             [], [Port("out", [type])],
                             r'''
           %s x;
           bool avail = false;
           if(this.head == this.tail) {
             //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
             //exit(-1);
           } else {
               avail = true;
               x = this.data[this.head];
               this.head = (this.head + 1) %s this.size;
           }
           output switch { case avail: out(x); }
           ''' % (type, name, '%'), None, [(one_name, "this")])

    enq = Enqueue(prefix + "enqueue", [all])
    deqs = [Dequeue(prefix + "dequeue" + str(i), [ones[i]]) for i in range(n_cores)]
    return enq, deqs

def create_circular_queue_many2one_instances(name, type, size, n_cores):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    all_instance_name = all_name + "_inst"

    One = create_state(one_name, "int head; int tail; int size; %s data[%d];" % (type, size), [0,0,size,[0]])
    ones = [One(one_instance_name + str(i)) for i in range(n_cores)]

    All = create_state(all_name, "%s* cores[%d];" % (one_name, n_cores))
    all = All(all_instance_name, [AddressOf(ones[i]) for i in range(n_cores)])

    Enqueue = create_element(prefix + "enqueue_ele",
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
           ''' % (type, name), None, [(one_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
                             [], [Port("out", [type])],
                             r'''
            fflush(stdout);
           static int c = 0;  // round robin schedule
           %s x;
           bool avail = false;
           int n = %d;
           for(int i=0; i<n; i++) {
             int index = (c + i) %s n;
             %s* p = this.cores[index];
             if(p->head != p->tail) {
               avail = true;
               x = p->data[p->head];
               p->head = (p->head + 1) %s p->size;
               c = (index + 1) %s n;
               break;
             }
           }
           if(!avail) {
             //printf("Dequeue all empty circular queues '%s' for all cores. Default value is returned (for API call).\n");
             //exit(-1);
           } else {
             //printf("Dequeue: YES\n");
           }
           output switch { case avail: out(x); }
           ''' % (type, n_cores, '%', one_name, '%', '%', name), None, [(all_name, "this")])

    enqs = [Enqueue(prefix + "enqueue" + str(i), [ones[i]]) for i in range(n_cores)]
    deq = Dequeue(prefix + "dequeue", [all])
    return enqs, deq

##########################################################

def create_circular_queue_variablesize_one2many_instances(name, size, n_cores):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    one_deq_instance_name = one_name + "_deq_inst"
    all_instance_name = all_name + "_inst"

    Dummy = create_state(one_name + "_dummy", "uint8_t queue[%d];" % size)
    dummies = [Dummy(one_name + "_dummy" + str(i)) for i in range(n_cores)]
    ones = [create_state_instance_from("circular_queue", one_instance_name + str(i), [size, 0, AddressOf(dummies[i])])
            for i in range(n_cores)]
    deq_ones = [create_state_instance_from("circular_queue", one_deq_instance_name + str(i), [size, 0, AddressOf(dummies[i])])
            for i in range(n_cores)]

    All = create_state(all_name, "circular_queue* cores[%d];" % n_cores)
    all = All(all_instance_name, [AddressOf(ones[i]) for i in range(n_cores)])

    Enqueue_alloc = create_element(prefix + "enqueue_alloc_ele",
                                   [Port("in_len", ["size_t"]), Port("in_core", ["size_t"])],
                                   [Port("out", ["q_entry*"])],
                             r'''
           (size_t len) = in_len();
           (size_t c) = in_core();
           circular_queue *q = this.cores[c];
           q_entry* entry = (q_entry*) enqueue_alloc(q, len);
           output { out(entry); }
           ''', None, [(all_name, "this")])

    Enqueue_submit = create_element(prefix + "enqueue_submit_ele",
                                    [Port("in", ["q_entry*"])], [],
                             r'''
           (q_entry* eqe) = in();
           enqueue_submit(eqe);
           ''')

    Dequeue_get = create_element(prefix + "dequeue_get_ele",
                             [], [Port("out", ["q_entry*"])],
                             r'''
        q_entry* x = dequeue_get(&this);
        printf("deq_get = %ld\n", x);
        output switch { case (x != NULL): out(x); }
           ''', None, [("circular_queue", "this")])

    Dequeue_release = create_element(prefix + "dequeue_release_ele",
                             [Port("in", ["q_entry*"])], [],
                             r'''
        (q_entry* eqe) = in();
        dequeue_release(eqe);
           ''')

    enq_alloc = Enqueue_alloc(prefix + "enqueue_alloc", [all])
    enq_submit = Enqueue_submit(prefix + "enqueue_submit")
    deqs_get = [Dequeue_get(prefix + "dequeue_get" + str(i), [deq_ones[i]]) for i in range(n_cores)]
    deqs_release = [Dequeue_release(prefix + "dequeue_release" + str(i),) for i in range(n_cores)]
    return enq_alloc, enq_submit, deqs_get, deqs_release
