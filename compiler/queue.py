from program import *

def CircularQueueOneToMany(name, type, size, n_cores):
    prefix = "_%s_" % name
    state_name = prefix + "queue"
    states_name = prefix + "queues"
    state_instance_name = state_name + "_inst[%s]" % n_cores
    states_instance_name = states_name + "_inst"

    one_core = State(state_name, "int head; int tail; int size; %s data[%d];" % (type, size), "{0,0,%d,{0}}" % size)
    # state_instances = []
    # for i in n_cores:
    #     instance = StateInstance(state_name, state_instance_name + str(i))
    #     state_instances.append(instance)
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
    int next = this.head + 1;
    if(next >= this.size) next = 0;
    this.head = next;
}
output switch { case avail: out(x); }
''' % (type, name), None, [(state_name, "this")])

    enq_instance = ElementInstance(prefix + "enqueue", name + "_enq", [states_instance_name])
    deq_instance = ElementInstance(prefix + "dequeue", name + "_deq[%d]" % n_cores, [state_instance_name])

    return [one_core, multi_core, state_instance, states_instance, enq, deq, enq_instance, deq_instance], \
           enq_instance, deq_instance