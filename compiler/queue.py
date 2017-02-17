from program import *

def CircularQueueOneToMany(name, type, size, n_cores):
    prefix = "_%s_" % name
    state_name = prefix + "queue"
    states_name = prefix + "queues"
    one_core = State(state_name, "int head; int tail; int size; %s data[%d];" % (type, size), "0,0,%d,{0}" % size)
    multi_core = State(states_name, "%s cores[%d]" % (state_name, n_cores), "{0}") # TODO: init sizes

    enq = Element(prefix+ "enqueue",
                  [Port("in_entry", [type]), Port("in_core", ["size_t"])], [],
                  r'''
(size_t c) = in_core();
(%s x) = in_entry();
%s* p = &this.cores[c];
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
if(my->head == my->tail) {
  printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
  //exit(-1);
} else {
    avail = true;
    x = my->data[my->head];
    int next = my->head + 1;
    if(next >= my->size) next = 0;
    my->head = next;
}
output switch { case avail: out(x); }
''' % (type, name), [(state_name + '*', "my")], [(states_name, "this")])  # TODO: init local