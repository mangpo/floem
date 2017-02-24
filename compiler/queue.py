from program import *
from dsl import *

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
           ''' % (type, one_name, name), None, [(all_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
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
             printf("Dequeue all empty circular queues '%s' for all cores. Default value is returned (for API call).\n");
             //exit(-1);
           }
           output switch { case avail: out(x); }
           ''' % (type, n_cores, '%', one_name, '%', '%', name), None, [(all_name, "this")])

    enqs = [Enqueue(prefix + "enqueue" + str(i), [ones[i]]) for i in range(n_cores)]
    deq = Dequeue(prefix + "dequeue", [all])
    return enqs, deq

def CircularQueueOneToMany(name, type, size, n_cores):  # TODO: make this return composite & ports can be parameterized.
    prefix = "_%s_" % name
    state_name = prefix + "queue"
    states_name = prefix + "queues"
    state_instance_name = state_name + "_inst[%s]" % n_cores
    states_instance_name = states_name + "_inst"

    one_core = State(state_name, "int head; int tail; int size; %s data[%d];" % (type, size), "{0,0,%d,{0}}" % size)
    state_instance = StateInstance(state_name, state_instance_name)

    multi_core = State(states_name, "%s* cores[%d];" % (state_name, n_cores))
    states_instance = StateInstance(states_name, states_instance_name, [AddressOf(state_instance_name)])

    enq = Element(prefix+ "enqueue",
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
''' % (type, state_name, name), None, [(states_name, "this")])

    deq = Element(prefix + "dequeue",
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
    this.head = (this.head + 1) %s this.size;
}
output switch { case avail: out(x); }
''' % (type, name, '%'), None, [(state_name, "this")])  # TODO: test wrap around

    enq_instance = ElementInstance(prefix + "enqueue", name + "_enq", [states_instance_name])
    deq_instance = ElementInstance(prefix + "dequeue", name + "_deq[%d]" % n_cores, [state_instance_name])

    return [one_core, multi_core, state_instance, states_instance, enq, deq, enq_instance, deq_instance], \
           enq_instance, deq_instance

def CircularQueueManyToOne(name, type, size, n_cores):
    prefix = "_%s_" % name
    state_name = prefix + "queue"
    states_name = prefix + "queues"
    state_instance_name = state_name + "_inst[%s]" % n_cores
    states_instance_name = states_name + "_inst"

    one_core = State(state_name, "int head; int tail; int size; %s data[%d];" % (type, size), "{0,0,%d,{0}}" % size)
    state_instance = StateInstance(state_name, state_instance_name)

    multi_core = State(states_name, "%s* cores[%d];" % (state_name, n_cores))
    states_instance = StateInstance(states_name, states_instance_name, [AddressOf(state_instance_name)])

    enq = Element(prefix + "enqueue",
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

    deq = Element(prefix + "dequeue",
                  [], [Port("out", [type])],
                  r'''
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
  printf("Dequeue all empty circular queues '%s' for all cores. Default value is returned (for API call).\n");
  //exit(-1);
}
output switch { case avail: out(x); }
''' % (type, n_cores, '%', state_name, '%', '%', name), None, [(states_name, "this")])

    enq_instance = ElementInstance(prefix + "enqueue", name + "_enq[%d]" % n_cores, [state_instance_name])
    deq_instance = ElementInstance(prefix + "dequeue", name + "_deq", [states_instance_name])

    return [one_core, multi_core, state_instance, states_instance, enq, deq, enq_instance, deq_instance], \
           enq_instance, deq_instance