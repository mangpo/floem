from dsl2 import *

Qentry = 'q_entry'

class circular_queue(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue

class circular_queue_lock(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    lock = Field('pthread_mutex_t')
    layout = [len, offset, queue, lock]

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.lock = lambda (x): 'pthread_mutex_init(&%s, NULL)' % x

class circular_queue_scan(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    clean = Field(Size)

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.clean = 0

class circular_queue_lock_scan(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    lock = Field('pthread_mutex_t')
    clean = Field(Size)

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.lock = lambda (x): 'pthread_mutex_init(&%s, NULL)' % x
        self.clean = 0


def get_field_name(state, field):
    if isinstance(field, str):
        return field

    for s in state.__dict__:
        o = state.__dict__[s]
        if isinstance(o, Field):
            if o == field:
                return s


def create_queue_states(name, type, size, n_cores, declare=True, enq_lock=False, deq_lock=False, scan=False):
    prefix = "%s_" % name

    class Storage(State): data = Field(Array(type, size))

    Storage.__name__ = prefix + Storage.__name__

    storages = [Storage() for i in range(n_cores)]

    if enq_lock:
        enq = circular_queue_lock_scan if scan else circular_queue_lock
    else:
        enq = circular_queue_scan if scan else circular_queue

    if deq_lock:
        deq = circular_queue_lock_scan if scan else circular_queue_lock
    else:
        deq = circular_queue_scan if scan else circular_queue

    enq_infos = [enq(init=[size, storages[i]], declare=declare) for i in range(n_cores)]
    deq_infos = [deq(init=[size, storages[i]], declare=declare) for i in range(n_cores)]

    class EnqueueCollection(State):
        cores = Field(Array(Pointer(enq), n_cores))
        def init(self, cores=[0]): self.cores = cores

    EnqueueCollection.__name__ = prefix + EnqueueCollection.__name__

    class DequeueCollection(State):
        cores = Field(Array(Pointer(deq), n_cores))
        def init(self, cores=[0]): self.cores = cores

    DequeueCollection.__name__ = prefix + DequeueCollection.__name__

    # TODO: init pthread_mutex_init(&lock, NULL)

    enq_all = EnqueueCollection(init=[enq_infos])
    deq_all = DequeueCollection(init=[deq_infos])

    return enq_all, deq_all, enq, deq, Storage


def queue_variable_size(name, size, n_cores, blocking=False, enq_atomic=False, deq_atomic=False, scan=False, core=False):
    """
    :param name: queue name
    :param size: number of bytes
    :param n_cores:
    :param blocking:
    :param atomic:
    :return:
    """

    enq_all, deq_all, EnqQueue, DeqQueue, Storage = \
        create_queue_states(name, Uint(8), size, n_cores,
                            declare=False, enq_lock=enq_atomic, deq_lock=deq_atomic, scan=scan)

    class EnqueueAlloc(Element):
        this = Persistent(enq_all.__class__)
        def states(self): self.this = enq_all

        def configure(self):
            self.inp = Input(Size, Size)  # len, core
            self.out = Output('q_entry*')

        def impl(self):
            noblock_noatom = "q_entry* entry = (q_entry*) enqueue_alloc(q, len);\n"
            block_noatom = r'''
            q_entry* entry = NULL;
            do {
                entry = (q_entry*) enqueue_alloc(q, len);
            } while(entry == NULL)
            '''
            noblock_atom = "pthread_mutex_lock(&q->lock);\n" + noblock_noatom + "pthread_mutex_unlock(&q->lock);\n"
            block_atom = "pthread_mutex_lock(&q->lock);\n" + block_noatom + "pthread_mutex_unlock(&q->lock);\n"

            if blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                src = noblock_atom if enq_atomic else noblock_noatom

            self.run_c(r'''
            (size_t len, size_t c) = inp();
            %s *q = this->cores[c];  // TODO
            ''' % EnqQueue.__name__
                       + src + r'''
            //if(entry == NULL) { printf("queue %d is full.\n", c); }
            //printf("ENQ' core=%ld, queue=%ld, entry=%ld\n", c, q->queue, entry);
            output { out(entry); }
            ''')

    class EnqueueSubmit(Element):
        def configure(self):
            self.inp = Input('q_entry*')

        def impl(self):
            self.run_c(r'''
            (q_entry* eqe) = inp();
            enqueue_submit(eqe);
            ''')

    class DequeueGet(Element):
        this = Persistent(deq_all.__class__)
        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output('q_entry*', Size) if core else Output('q_entry*')

        def impl(self):
            noblock_noatom = "q_entry* entry = dequeue_get(q);\n"
            block_noatom = r'''
                        q_entry* entry = NULL;
                        do {
                            entry = dequeue_get(q);
                        } while(entry == NULL)
                        '''
            noblock_atom = "pthread_mutex_lock(&q->lock);\n" + noblock_noatom + "pthread_mutex_unlock(&q->lock);\n"
            block_atom = "pthread_mutex_lock(&q->lock);\n" + block_noatom + "pthread_mutex_unlock(&q->lock);\n"

            if blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                src = noblock_atom if deq_atomic else noblock_noatom

            self.run_c(r'''
        (size_t c) = inp();
        %s *q = this->cores[c];
        ''' % DeqQueue.__name__
                       + src + r'''
        //if(c == 3) printf("DEQ core=%ld, queue=%p, entry=%ld\n", c, q->queue, x); '''
                       + r'''
        output { out(%s); }
            ''' % ('entry, c' if core else 'entry'))

    class DequeueRelease(Element):
        def configure(self):
            self.inp = Input('q_entry*')

        def impl(self):
            self.run_c(r'''
            (q_entry* eqe) = inp();
            dequeue_release(eqe);
            ''')

    class ScanClean(Element):
        # For correctness, scan should be executed right before enqueue.
        # Even then, something bad can happen if the queue is completely full, off = clean; the queue won't get cleaned.
        this = Persistent(enq_all.__class__) if scan == 'enq' else Persistent(deq_all.__class__)

        def states(self):
            self.this = enq_all if scan == 'enq' else deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output('q_entry*', Size) if core else Output('q_entry*')

        def impl(self):
            self.run_c(r'''
    (size_t c) = inp();
    %s *q = this->cores[c]; ''' % (EnqQueue.__name__ if scan == 'enq' else DeqQueue.__name__)
                       + r'''
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
    }''' + r'''output { out(%s); }''' % ('entry, c' if core else 'entry'))

    prefix = name + "_"
    EnqueueAlloc.__name__ = prefix + EnqueueAlloc.__name__
    EnqueueSubmit.__name__ = prefix + EnqueueSubmit.__name__
    DequeueGet.__name__ = prefix + DequeueGet.__name__
    DequeueRelease.__name__ = prefix + DequeueRelease.__name__
    ScanClean.__name__ = prefix + ScanClean.__name__

    return EnqueueAlloc, EnqueueSubmit, DequeueGet, DequeueRelease, ScanClean if scan else None

# TODO
# 1. ScanRelease
# 2. Dequeue & Scan: output(type*, uintptr_t)
# 3. TxRelease & ScanRelease: input(type*, uintptr_t)
# 4. Cavium: sync, dma_read_with_buf
# 5. Make storm works again
def queue_custom_owner_bit(name, type, size, n_cores, owner,
                           blocking=False, enq_atomic=False, deq_atomic=False, scan=False, enq_output=False):
    """
    :param name: queue name
    :param type: entry type
    :param size: number of entries of type type
    :param n_cores:
    :param owner: ownerbit field in type (owner = 0 --> empty entry)
    :param blocking:
    :param atomic:
    :return:
    """
    owner = get_field_name(type, owner)
    prefix = "%s_" % name

    enq_all, deq_all, EnqQueue, DeqQueue, Storage = \
        create_queue_states(name, type, size, n_cores,
                            declare=True, enq_lock=False, deq_lock=False, scan=scan)

    type = string_type(type)
    type_star = type + "*"

    atomic_src = r'''
    __sync_synchronize();
    size_t old = p->offset;
    size_t new = (old + 1) %s %d;
    while(!__sync_bool_compare_and_swap(&p->offset, old, new)) {
        old = p->offset;
        new = (old + 1) %s %d;
    }
    ''' % ('%', size, '%', size)

    atomic_src_cvm = r'''
        size_t old = p->offset;
        size_t new = (old + 1) %s %d;
        while(!__sync_bool_compare_and_swap(&p->offset, old, new)) {
            old = p->offset;
            new = (old + 1) %s %d;
        }
        ''' % ('%', size, '%', size)  # TODO: __sync_bool_compare_and_swap

    wait_then_copy = r'''
    while(q->data[old].%s != 0) __sync_synchronize();
    rte_memcpy(&q->data[old], x, sizeof(%s));
    __sync_synchronize();
    ''' % (owner, type)

    init_read_cvm = r'''
        uintptr_t addr = &q->data[old];
        %s* entry;
        int size = sizeof(%s);
        dma_read(addr, size, &entry);
        ''' % (type, type)

    wait_then_copy_cvm = init_read_cvm + r'''
        while(entry->%s) dma_read_with_buff(addr, size, &entry);
        memcpy(entry, x, size);
        dma_write(addr, size, entry);
        ''' % (owner)  # TODO: dma_read_with_buff

    wait_then_get = r'''
    while(q->data[old].%s == 0) __sync_synchronize();
    %s x = &q->data[old];
    ''' % (owner, type_star)

    wait_then_get_cvm = init_read_cvm + r'''
        while(entry->%s == 0) dma_read_with_buff(addr, size, &entry);
        %s* x = entry;
        ''' % (owner, type)

    inc_offset = "p->offset = (p->offset + 1) %s %d;\n" % ('%', size)

    class Enqueue(Element):
        this = Persistent(enq_all.__class__)

        def states(self): self.this = enq_all

        def configure(self):
            self.inp = Input(type_star, Size)
            if enq_output:
                self.out = Output(type_star)

        def impl(self):
            noblock_noatom = r'''
                __sync_synchronize();
                if(q->data[p->offset].%s == 0) {
                    rte_memcpy(&q->data[p->offset], x, sizeof(%s));
                    p->offset = (p->offset + 1) %s %d;
                    __sync_synchronize();
                }
                ''' % (owner, type, '%', size)

            block_noatom = "size_t old = p->offset;\n" + wait_then_copy + inc_offset

            block_atom = atomic_src_cvm + wait_then_copy

            if blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                if enq_atomic:
                    raise Exception("Unimplemented for non-blocking but atomic.")
                else:
                    src = noblock_noatom

            out_src = "output { out(x); }\n" if enq_output else ''

            self.run_c(r'''
            (%s x, size_t c) = inp();
            circular_queue* p = this->cores[c];
            %s* q = p->queue;
            ''' % (type_star, Storage.__name__)
                       + src + out_src)

        def impl_cavium(self):
            noblock_noatom = "size_t old = p->offset;\n" + init_read_cvm + r'''
                if(entry->%s == 0) {
                    memcpy(entry, x, size);
                    dma_write(addr, size, entry);
                    p->offset = (p->offset + 1) %s %d;
                }
                ''' % (owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + wait_then_copy_cvm + inc_offset

            block_atom = atomic_src_cvm + wait_then_copy_cvm

            if blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                if enq_atomic:
                    raise Exception("Unimplemented for non-blocking but atomic.")
                else:
                    src = noblock_noatom

            out_src = "dma_free(entry); \noutput { out(x); }\n" if enq_output else 'dma_free(entry);\n'

            self.run_c(r'''
            (%s x, size_t c) = inp();
            circular_queue* p = this->cores[c];
            %s* q = p->queue;
            ''' % (type_star, Storage.__name__)
                       + src + out_src)

    class Dequeue(Element):
        this = Persistent(deq_all.__class__)

        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(type_star, 'uintptr_t')

        def impl(self):
            noblock_noatom = r'''
            %s x = NULL;
            __sync_synchronize();
            if(q->data[p->offset].%s != 0) {
                x = &q->data[p->offset];
                p->offset = (p->offset + 1) %s %d;
            }
            ''' % (type_star, owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + wait_then_get + inc_offset

            block_atom = atomic_src + wait_then_get

            if blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                if deq_atomic:
                    raise Exception("Unimplemented for non-blocking but atomic.")
                else:
                    src = noblock_noatom

            debug = r'''printf("deq %ld\n", c);'''

            self.run_c(r'''
                        (size_t c) = inp();
                        circular_queue* p = this->cores[c];
                        %s* q = p->queue;
                        ''' % Storage.__name__
                       #+ debug
                       + src
                       + "output { out(x, 0); }\n")

        def impl_cavium(self):
            noblock_noatom = "size_t old = p->offset;\n" + init_read_cvm + r'''
            %s x = NULL;
            if(entry->%s != 0) {
                x = entry;
                p->offset = (p->offset + 1) %s %d;
            }
            ''' % (type_star, owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + wait_then_get_cvm + inc_offset

            block_atom = atomic_src_cvm + wait_then_get_cvm

            if blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                if deq_atomic:
                    raise Exception("Unimplemented for non-blocking but atomic.")
                else:
                    src = noblock_noatom

            debug = r'''printf("deq %ld\n", c);'''

            self.run_c(r'''
                        (size_t c) = inp();
                        circular_queue* p = this->cores[c];
                        %s* q = p->queue;
                        ''' % Storage.__name__
                       #+ debug
                       + src
                       + "output { out(x, addr); }\n")

    class Release(Element):
        def configure(self):
            self.inp = Input(type_star, 'uintptr_t')

        def impl(self):
            self.run_c(r'''
            (%s x, uintptr_t addr) = inp();
            if(x) x->%s = 0;
            ''' % (type_star, owner))

        def impl_cavium(self):
            self.run_c(r'''
            (%s x, uintptr_t addr) = inp();
            if(x) {
                x->%s = 0;
                dma_write(addr, size, x);
                dma_free(x);
            }
            ''' % (type_star, owner))


    class Scan(Element):
        this = Persistent(enq_all.__class__) if scan == 'enq' else Persistent(deq_all.__class__)

        def states(self):
            self.this = enq_all if scan == 'enq' else deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(type_star, 'uintptr_t')

        def impl(self):
            self.run_c(r'''
    (size_t c) = in_core();
    circular_queue_scan *q = this->cores[c];
    %s* p = q->queue;
    %s* entry = NULL;
    if (q->clean != q->offset) {
        entry = &p->data[q->clean];
        if ((entry->%s) != 0) {
            entry = NULL;
        } else {
            q->clean = (q->clean + 1) %s q->len;
        }
    }
    output { out(entry, 0); }
            ''' % (Storage.__name__, type, owner, '%'))

        def impl_cavium(self):
            self.run_c(r'''
    (size_t c) = in_core();
    circular_queue_scan *q = this->cores[c];
    %s* p = q->queue;
    %s* entry = NULL;
    uintptr_t addr;
    if (q->clean != q->offset) {
        addr = &q->data[q->clean];
        dma_read(addr, sizeof(%s), &entry);
        if ((entry->%s) != 0) {
            dma_free(entry);
            entry = NULL;
        } else {
            q->clean = (q->clean + 1) %s q->len;
        }
    }
    output { out(entry, addr); }
            ''' % (Storage.__name__, type, type, owner, '%'))

    class ScanRelease(Element):
        def configure(self):
            self.inp = Input(type_star, 'uintptr_t')

        def impl(self):
            self.run_c("")

        def impl_cavium(self):
            self.run_c(r'''
            (%s x, uintptr_t addr) = inp();
            if(x) {
                dma_free(x);
            }
            ''' % (type_star, owner))

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Release.__name__ = prefix + Release.__name__
    Scan.__name__ = prefix + Scan.__name__
    ScanRelease.__name__ = prefix + ScanRelease.__name__

    return Enqueue, Dequeue, Release, Scan if scan else None, ScanRelease if scan else None


def queue_shared_head_tail(name, type, size, n_cores):
    pass


