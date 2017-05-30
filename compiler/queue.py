from dsl import *


def declare_circular_queue(name, type, size, blocking=False):
    prefix = "_%s_" % name
    state_name = prefix + "queue"

    Enqueue = create_element(prefix + "enqueue",
                             [Port("in", [type])], [],
                             r'''
           (%s x) = in();
           int next = this->tail + 1;
           if(next >= this->size) next = 0;
           if(next == this->head) {
             //printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             this->data[this->tail] = x;
             this->tail = next;
           }
           ''' % (type, name), None, [(state_name, "this")])

    if blocking:
        src = r'''
            %s x;
            while(this->head == this->tail) { __sync_synchronize(); }
            x = this->data[this->head];
            int next = this->head + 1;
            if(next >= this->size) next = 0;
            this->head = next;
            __sync_synchronize();
            output { out(x); }
            ''' % type
    else:
        src = r'''
            %s x;
            bool avail = false;
            __sync_synchronize();
            if(this->head == this->tail) {
                //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
                //exit(-1);
            } else {
                avail = true;
                x = this->data[this->head];
               int next = this->head + 1;
                if(next >= this->size) next = 0;
                this->head = next;
                __sync_synchronize();
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
        t2.run(deq)
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
    all = All(all_instance_name, [[ones[i] for i in range(n_cores)]])

    Enqueue = create_element(prefix + "enqueue_ele",
                             [Port("in_entry", [type]), Port("in_core", ["size_t"])], [],
                             r'''
           (size_t c) = in_core();
           (%s x) = in_entry();
           %s* p = this->cores[c];
           __sync_synchronize();
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             p->data[p->tail] = x;
             p->tail = next;
           }
           __sync_synchronize();
           ''' % (type, one_name, name), None, [(all_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
                             [], [Port("out", [type])],
                             r'''
           %s x;
           bool avail = false;
           if(this->head == this->tail) {
             //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
             //exit(-1);
           } else {
               avail = true;
               x = this->data[this->head];
               this->head = (this->head + 1) %s this->size;
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
    all = All(all_instance_name, [[ones[i] for i in range(n_cores)]])

    Enqueue = create_element(prefix + "enqueue_ele",
                             [Port("in", [type])], [],
                             r'''
           (%s x) = in();
           int next = this->tail + 1;
           if(next >= this->size) next = 0;
           if(next == this->head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             this->data[this->tail] = x;
             this->tail = next;
           }
           ''' % (type, name), None, [(one_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
                             [], [Port("out", [type])],
                             r'''

           static int c = 0;  // round robin schedule
           %s x;
           bool avail = false;
           int n = %d;
           __sync_synchronize();
           for(int i=0; i<n; i++) {
             int index = (c + i) %s n;
             %s* p = this->cores[index];
             if(p->head != p->tail) {
               avail = true;
               x = p->data[p->head];
               p->head = (p->head + 1) %s p->size;
               __sync_synchronize();
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

############################ Fixed-size copy queue ##############################

def create_copy_queue_many2many_inc_instances(name, type, size, n_cores, blocking=False):
    type_star = type + "*"
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    all_instance_name = all_name + "_inst"

    One = create_state(one_name, "int head; int tail; int size; %s data[%d];" % (type, size), [0,0,size,[0]])
    ones = [One(one_instance_name + str(i)) for i in range(n_cores)]

    All = create_state(all_name, "%s* cores[%d];" % (one_name, n_cores))
    all = All(all_instance_name, [[ones[i] for i in range(n_cores)]])

    Enqueue = create_element(prefix + "enqueue_ele",
                             [Port("in", [type_star, "size_t"])], [],
                             r'''
           (%s x, size_t c) = in();
           %s* p = this->cores[c];
           __sync_synchronize();
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             rte_memcpy(&p->data[p->tail], x, sizeof(%s));
             p->tail = next;
           }
           __sync_synchronize();
           ''' % (type_star, one_name, name, type), None, [(all_name, "this")])

    if blocking:
        src = r'''
        (size_t c) = in();
        %s* p = this->cores[c];
        while(p->head == p->tail) { __sync_synchronize(); }
        %s x = &p->data[p->head];
        output { out(x); }
            ''' % (one_name, type_star)
    else:
        src = r'''
        (size_t c) = in();
        %s* p = this->cores[c];
        %s x = NULL;
        bool avail = false;
        if(p->head == p->tail) {
            //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
            //exit(-1);
        } else {
            avail = true;
            x = &p->data[p->head];
        }
        output { out(x); }
        ''' % (one_name, type_star, name)

    Dequeue = create_element(prefix + "dequeue_ele",
                             [Port("in", ["size_t"])], [Port("out", [type_star])],
                             src, None, [(all_name, "this")])

    Advance = create_element(prefix + "dequeue_advance",
                             [Port("in", ["size_t"])], [],
                             r'''
        (size_t c) = in();
        %s* p = this->cores[c];
        p->head = (p->head + 1) %s p->size;
           ''' % (one_name, '%'), None, [(all_name, "this")])

    enq = Enqueue(prefix + "enqueue", [all])
    deq = Dequeue(prefix + "dequeue", [all])
    adv = Advance(prefix + "advance", [all])
    return enq, deq, adv


def create_copy_queue_many2many_batch_instances(name, type, size, n_cores):
    type_star = type + "*"
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    all_instance_name = all_name + "_inst"

    One = create_state(one_name, "int head; int tail; int size; %s data[%d];" % (type, size), [0,0,size,[0]])
    ones = [One(one_instance_name + str(i)) for i in range(n_cores)]

    All = create_state(all_name, "%s* cores[%d];" % (one_name, n_cores))
    all = All(all_instance_name, [[ones[i] for i in range(n_cores)]])

    Enqueue = create_element(prefix + "enqueue_ele",
                             [Port("in", [type_star, "size_t"])], [],
                             r'''
           (%s x, size_t c) = in();
           %s* p = this->cores[c];
           __sync_synchronize();
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue '%s' is full. A packet is dropped.\n");
           } else {
             rte_memcpy(&p->data[p->tail], x, sizeof(%s));
             p->tail = next;
           }
           __sync_synchronize();
           ''' % (type_star, one_name, name, type), None, [(all_name, "this")])

    Dequeue = create_element(prefix + "dequeue_ele",
                             [Port("in", ["size_t", "size_t"])], [Port("out", [type_star])],
                             r'''
        (size_t c, size_t peak) = in();
        %s* p = this->cores[c];
           %s x = NULL;
           bool avail = false;
           if(p->head + peak == p->tail) {
             //printf("Dequeue an empty circular queue '%s'. Default value is returned (for API call).\n");
             //exit(-1);
           } else {
               avail = true;
               x = &p->data[p->head + peak];
           }
           output { out(x); }
           ''' % (one_name, type_star, name), None, [(all_name, "this")])

    Advance = create_element(prefix + "dequeue_advance",
                             [Port("in", ["size_t", "size_t"])], [],
                             r'''
        (size_t c, size_t skip) = in();
        %s* p = this->cores[c];
        p->head = (p->head + skip) %s p->size;
           ''' % (one_name, '%'), None, [(all_name, "this")])

    enq = Enqueue(prefix + "enqueue", [all])
    deq = Dequeue(prefix + "dequeue", [all])
    adv = Advance(prefix + "advance", [all])
    return enq, deq, adv

############################ Variable-size queue ##############################

def create_circular_queue_variablesize_one2many(name, size, n_cores):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    one_instance_name = one_name + "_inst"
    one_deq_instance_name = one_name + "_deq_inst"
    all_instance_name = all_name + "_inst"
    all_eq_instance_name = all_name + "_deq_inst"

    Dummy = create_state(one_name + "_dummy", "uint8_t queue[%d];" % size)
    circular = create_state("circular_queue", "size_t len; size_t offset; void* queue;", None, False)
    dummies = [Dummy(one_name + "_dummy" + str(i)) for i in range(n_cores)]
    enq_ones = [circular(one_instance_name + str(i), [size, 0, dummies[i]])
            for i in range(n_cores)]
    deq_ones = [circular(one_deq_instance_name + str(i), [size, 0, dummies[i]])
            for i in range(n_cores)]

    All = create_state(all_name, "circular_queue* cores[%d];" % n_cores)
    enq_all = All(all_instance_name, [[enq_ones[i] for i in range(n_cores)]])
    deq_all = All(all_eq_instance_name, [[deq_ones[i] for i in range(n_cores)]])

    Enqueue_alloc = create_element(prefix + "enqueue_alloc_ele",
                                   [Port("in_len", ["size_t"]), Port("in_core", ["size_t"])],
                                   [Port("out", ["q_entry*"])],
                             r'''
           (size_t len) = in_len();
           (size_t c) = in_core();
           circular_queue *q = this->cores[c];
           //printf("ENQ core=%ld, queue=%p, eq=%d\n", c, q->queue, this->cores[1]==this->cores[3]);
           q_entry* entry = (q_entry*) enqueue_alloc(q, len);
           //if(entry == NULL) { printf("queue %d is full.\n", c); }
           //printf("ENQ' core=%ld, queue=%ld, entry=%ld\n", c, q->queue, entry);
           output { out(entry); }
           ''', None, [(all_name, "this")])

    Enqueue_submit = create_element(prefix + "enqueue_submit_ele",
                                    [Port("in", ["q_entry*"])], [],
                             r'''
           (q_entry* eqe) = in();
           enqueue_submit(eqe);
           ''')

    Dequeue_get = create_element(prefix + "dequeue_get_ele",
                             [Port("in", ["size_t"])], [Port("out", ["q_entry*"])],
                             r'''
        (size_t c) = in();
        circular_queue *q = this->cores[c];
        q_entry* x = dequeue_get(q);
        //if(c == 3) printf("DEQ core=%ld, queue=%p, entry=%ld\n", c, q->queue, x);
        output { out(x); }
           ''', None, [(all_name, "this")])

    Dequeue_release = create_element(prefix + "dequeue_release_ele",
                             [Port("in", ["q_entry*"])], [],
                             r'''
        (q_entry* eqe) = in();
        dequeue_release(eqe);
           ''')

    def enq_alloc(name=None):
        if not name:
            global fresh_id
            name = prefix + "enqueue_alloc" + str(fresh_id)
            fresh_id += 1
        return Enqueue_alloc(name, [enq_all])

    def deq_alloc(name=None):
        if not name:
            global fresh_id
            name = prefix + "dequeue_get" + str(fresh_id)
            fresh_id += 1
        return Dequeue_get(name, [deq_all])

    return enq_alloc, Enqueue_submit, deq_alloc, Dequeue_release


def create_circular_queue_variablesize_one2many_instances(name, size, n_cores):
    prefix = "_%s_" % name
    enq_alloc, enq_submit, deq_get, deq_release = create_circular_queue_variablesize_one2many(name, size, n_cores)
    return enq_alloc(prefix + "enqueue_alloc"), enq_submit(prefix + "enqueue_submit"), \
           deq_get(prefix + "dequeue_get"), deq_release(prefix + "dequeue_release")


def create_circular_queue_variablesize_many2one(name, size, n_cores, scan=None):
    prefix = "_%s_" % name
    one_name = prefix + "queue"
    all_name = prefix + "queues"
    all_name_scan = prefix + "queues_scan"
    one_instance_name = one_name + "_inst"
    one_deq_instance_name = one_name + "_deq_inst"
    all_instance_name = all_name + "_inst"
    all_eq_instance_name = all_name + "_deq_inst"

    Dummy = create_state(one_name + "_dummy", "uint8_t queue[%d];" % size)
    circular = create_state("circular_queue", "size_t len; size_t offset; void* queue;", None, False)
    circular_scan = create_state("circular_queue_scan", "size_t len; size_t offset; void* queue; size_t clean;", None, False)
    dummies = [Dummy(one_name + "_dummy" + str(i)) for i in range(n_cores)]

    All = create_state(all_name, "circular_queue* cores[%d];" % n_cores)
    All_scan = create_state(all_name_scan, "circular_queue_scan* cores[%d];" % n_cores)

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

    enq_ones = [circular_enq(one_instance_name + str(i), [size, 0, dummies[i], 0])
            for i in range(n_cores)]
    deq_ones = [circular_deq(one_deq_instance_name + str(i), [size, 0, dummies[i], 0])
            for i in range(n_cores)]

    enq_all = All_enq(all_instance_name, [[enq_ones[i] for i in range(n_cores)]])
    deq_all = All_deq(all_eq_instance_name, [[deq_ones[i] for i in range(n_cores)]])

    Enqueue_alloc = create_element(prefix + "enqueue_alloc_ele",
                                   [Port("in_core", ["size_t"]), Port("in_len", ["size_t"])],
                                   [Port("out", ["q_entry*"])],
                             r'''
           (size_t c) = in_core();
           (size_t len) = in_len();
           circular_queue *q = this->cores[c];
           q_entry* entry = (q_entry*) enqueue_alloc(q, len);
           output { out(entry); }
           ''', None, [(all_name_enq, "this")])

    Enqueue_submit = create_element(prefix + "enqueue_submit_ele",
                                    [Port("in", ["q_entry*"])], [],
                             r'''
           (q_entry* eqe) = in();
           enqueue_submit(eqe);
           ''')

    Dequeue_get = create_element(prefix + "dequeue_get_ele",
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

    Dequeue_release = create_element(prefix + "dequeue_release_ele",
                             [Port("in", ["q_entry*"])], [],
                             r'''
        (q_entry* eqe) = in();
        dequeue_release(eqe);
           ''')

    if scan:
        Scan = create_element(prefix + "scan_ele",
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


    def enq_alloc(name=None):
        if not name:
            global fresh_id
            name = prefix + "enqueue_alloc" + str(fresh_id)
            fresh_id += 1
        return Enqueue_alloc(name, [enq_all])

    def deq_alloc(name=None):
        if not name:
            global fresh_id
            name = prefix + "dequeue_get" + str(fresh_id)
            fresh_id += 1
        return Dequeue_get(name, [deq_all])

    def scan_instance(name=None):
        if not name:
            global fresh_id
            name = prefix + "scan" + str(fresh_id)
            fresh_id += 1
        if scan == "enq":
            return Scan(name, [enq_all])
        elif scan == "deq":
            return Scan(name, [deq_all])

    return enq_alloc, Enqueue_submit, deq_alloc, Dequeue_release, (scan and scan_instance)


def create_circular_queue_variablesize_many2one_instances(name, size, n_cores, scan=None):
    prefix = "_%s_" % name
    enq_alloc, enq_submit, deq_get, deq_release, scan = \
        create_circular_queue_variablesize_many2one(name, size, n_cores, scan)
    return enq_alloc(prefix + "enqueue_alloc"), enq_submit(prefix + "enqueue_submit"), \
           deq_get(prefix + "dequeue_get"), deq_release(prefix + "dequeue_release"), \
           (scan and scan(prefix + "scan"))
