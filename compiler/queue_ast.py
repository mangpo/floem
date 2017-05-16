from program import *

class Queue:
    def __init__(self, name, size, n_cores, n_cases):
        self.name = name
        self.size = size
        self.n_cores = n_cores
        self.n_cases = n_cases
        self.enq = None
        self.deq = None


class QueueVariableSizeOne2Many(Queue):
    def __init__(self, name, size, n_cores, n_cases):
        Queue.__init__(self, name, size, n_cores, n_cases)


fresh_id = 0


def circular_queue_variablesize_one2many(name, size, n_cores):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    one_deq_instance_name = one_name + "_deq_inst"
    all_instance_name = all_name + "_inst"
    all_eq_instance_name = all_name + "_deq_inst"

    Dummy = State(one_name + "_dummy", "uint8_t queue[%d];" % size)
    circular = State("circular_queue", "size_t len; size_t offset; void* queue;", None, False)
    dummies = [StateInstance(one_name + "_dummy", one_name + "_dummy" + str(i)) for i in range(n_cores)]
    enq_ones = [StateInstance("circular_queue", one_instance_name + str(i), [size, 0, dummies[i].name])
            for i in range(n_cores)]
    deq_ones = [StateInstance("circular_queue", one_deq_instance_name + str(i), [size, 0, dummies[i].name])
            for i in range(n_cores)]

    All = State(all_name, "circular_queue* cores[%d];" % n_cores)
    enq_all = StateInstance(all_name, all_instance_name, [[enq_ones[i].name for i in range(n_cores)]])
    deq_all = StateInstance(all_name, all_eq_instance_name, [[deq_ones[i].name for i in range(n_cores)]])

    states = [Dummy, circular, All]
    state_insts = dummies + enq_ones + deq_ones + [enq_all, deq_all]

    Enqueue_alloc = Element(prefix + "enqueue_alloc_ele",
                                   [Port("in", ["size_t", "size_t"])],
                                   [Port("out", ["q_entry*"])],
                             r'''
           (size_t len, size_t c) = in();
           circular_queue *q = this->cores[c];
           //printf("ENQ core=%ld, queue=%p, eq=%d\n", c, q->queue, this->cores[1]==this->cores[3]);
           q_entry* entry = (q_entry*) enqueue_alloc(q, len);
           //if(entry == NULL) { printf("queue %d is full.\n", c); }
           //printf("ENQ' core=%ld, queue=%ld, entry=%ld\n", c, q->queue, entry);
           output { out(entry); }
           ''', None, [(all_name, "this")])

    Enqueue_submit = Element(prefix + "enqueue_submit_ele",
                                    [Port("in", ["q_entry*"])], [],
                             r'''
           (q_entry* eqe) = in();
           enqueue_submit(eqe);
           ''')

    Dequeue_get = Element(prefix + "dequeue_get_ele",
                             [Port("in", ["size_t"])], [Port("out", ["q_entry*"])],
                             r'''
        (size_t c) = in();
        circular_queue *q = this->cores[c];
        q_entry* x = dequeue_get(q);
        //if(c == 3) printf("DEQ core=%ld, queue=%p, entry=%ld\n", c, q->queue, x);
        output { out(x); }
           ''', None, [(all_name, "this")])

    Dequeue_release = Element(prefix + "dequeue_release_ele",
                             [Port("in", ["q_entry*"])], [],
                             r'''
        (q_entry* eqe) = in();
        dequeue_release(eqe);
           ''')

    elements = [Enqueue_alloc, Enqueue_submit, Dequeue_get, Dequeue_release]

    def enq_alloc(name=None):
        if not name:
            global fresh_id
            name = prefix + "enqueue_alloc" + str(fresh_id)
            fresh_id += 1
        return ElementInstance(Enqueue_alloc.name, name, [enq_all.name])

    def enq_submit(name=None):
        if not name:
            global fresh_id
            name = prefix + "enqueue_submit" + str(fresh_id)
            fresh_id += 1
        return ElementInstance(Enqueue_submit.name, name)

    def deq_get(name=None):
        if not name:
            global fresh_id
            name = prefix + "dequeue_get" + str(fresh_id)
            fresh_id += 1
        return ElementInstance(Dequeue_get.name, name, [deq_all.name])

    def deq_release(name=None):
        if not name:
            global fresh_id
            name = prefix + "dequeue_release" + str(fresh_id)
            fresh_id += 1
        return ElementInstance(Dequeue_release.name, name)

    return states, state_insts, elements, enq_alloc, enq_submit, deq_get, deq_release
