from program import *

class Queue:
    def __init__(self, name, size, n_cores, n_cases):
        self.name = name
        self.size = size
        self.n_cores = n_cores
        self.n_cases = n_cases
        self.enq = None
        self.deq = None
        self.scan = None
        self.scan_type = None


class QueueVariableSizeOne2Many(Queue):
    def __init__(self, name, size, n_cores, n_cases):
        Queue.__init__(self, name, size, n_cores, n_cases)


class QueueVariableSizeMany2One(Queue):
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


def circular_queue_variablesize_many2one(name, size, n_cores, scan=None):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    all_name_scan = prefix + "queues_scan"
    one_instance_name = one_name + "_inst"
    one_deq_instance_name = one_name + "_deq_inst"
    all_instance_name = all_name + "_inst"
    all_eq_instance_name = all_name + "_deq_inst"

    Dummy = State(one_name + "_dummy", "uint8_t queue[%d];" % size)
    circular = State("circular_queue", "size_t len; size_t offset; void* queue;", None, False)
    circular_scan = State("circular_queue_scan", "size_t len; size_t offset; void* queue; size_t clean;", None,
                                 False)
    dummies = [StateInstance(Dummy.name, one_name + "_dummy" + str(i)) for i in range(n_cores)]

    All = State(all_name, "circular_queue* cores[%d];" % n_cores)
    All_scan = State(all_name_scan, "circular_queue_scan* cores[%d];" % n_cores)

    if scan == "enq":
        circular_enq = circular_scan
        All_enq = All_scan
        all_name_enq = all_name_scan
    else:
        circular_enq = circular
        All_enq = All
        all_name_enq = all_name

    if scan == "deq":
        circular_deq = circular_scan
        All_deq = All_scan
        all_name_deq = all_name_scan
    else:
        circular_deq = circular
        All_deq = All
        all_name_deq = all_name

    enq_ones = [StateInstance(circular_enq.name, one_instance_name + str(i), [size, 0, dummies[i].name, 0])
                for i in range(n_cores)]
    deq_ones = [StateInstance(circular_deq.name, one_deq_instance_name + str(i), [size, 0, dummies[i].name, 0])
                for i in range(n_cores)]

    enq_all = StateInstance(All_enq.name, all_instance_name, [[enq_ones[i].name for i in range(n_cores)]])
    deq_all = StateInstance(All_deq.name, all_eq_instance_name, [[deq_ones[i].name for i in range(n_cores)]])

    states = [Dummy, circular, circular_scan, All, All_scan]
    state_insts = dummies + enq_ones + deq_ones + [enq_all, deq_all]

    Enqueue_alloc = Element(prefix + "enqueue_alloc_ele",
                                   [Port("in", ["size_t", "size_t"])],
                                   [Port("out", ["q_entry*"])],
                                   r'''
        (size_t len, size_t c) = in();
        circular_queue *q = this->cores[c];
        q_entry* entry = (q_entry*) enqueue_alloc(q, len);
        output { out(entry); }
        ''', None, [(all_name_enq, "this")])

    Enqueue_submit = Element(prefix + "enqueue_submit_ele",
                                    [Port("in", ["q_entry*"])], [],
                                    r'''
                  (q_entry* eqe) = in();
                  enqueue_submit(eqe);
                  ''')

    Dequeue_get = Element(prefix + "dequeue_get_ele",
                                 [], [Port("out", ["q_entry*"])],
                                 r'''
            static int c = 0;  // round robin schedule
            int n = %d;
            q_entry* x = NULL;
            for(int i=0; i<n; i++) {
                int index = (c + i) %s n;
                circular_queue* q = this->cores[index];
                x = dequeue_get(q);
                if(x != NULL) {
                    c = (index + 1) %s n;
                    break;
                }
            }
            output { out(x); }
               ''' % (n_cores, "%", "%"), None, [(all_name_deq, "this")])

    Dequeue_release = Element(prefix + "dequeue_release_ele",
                                     [Port("in", ["q_entry*"])], [],
                                     r'''
                (q_entry* eqe) = in();
                dequeue_release(eqe);
                   ''')

    if scan:
        Scan = Element(prefix + "scan_ele",
                              [Port("in_core", ["size_t"])],
                              [Port("out", ["q_entry*"])],
                              r'''
    (size_t c) = in_core();
    circular_queue_scan *q = this->cores[c];
    size_t off = q->offset;
    size_t len = q->len;
    size_t clean = q->clean;
    void* base = q->queue;
    //if(c==1 && cleaning.last != off) printf("SCAN: start, last = %ld, offset = %ld, clean = %ld\n", cleaning.last, off, clean);
    q_entry *entry = NULL;
    if (clean != off) {
        entry = (q_entry *) ((uintptr_t) base + clean);
        if ((entry->flags & FLAG_OWN) != 0) {
            entry = NULL;
        } else {
            q->clean = (clean + entry->len) % len;
        }
    }
    output { out(entry); }
            ''', None, [(all_name_scan, "this")])
    else:
        Scan = None

    elements = [Enqueue_alloc, Enqueue_submit, Dequeue_get, Dequeue_release]
    if Scan:
        elements.append(Scan)

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

    def scan_instance(name=None):
        if not name:
            global fresh_id
            name = prefix + "scan" + str(fresh_id)
            fresh_id += 1
        if scan == "enq":
            return ElementInstance(Scan.name, name, [enq_all.name])
        elif scan == "deq":
            return ElementInstance(Scan.name, name, [deq_all.name])

    return states, state_insts, elements, enq_alloc, enq_submit, deq_get, deq_release, (scan and scan_instance)
