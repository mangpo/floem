from dsl2 import *

q_buffer = 'q_buffer'
q_entry = 'q_entry'

class circular_queue(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    clean = Field(Size)

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.clean = 0
        self.declare = False

class circular_queue_lock(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    clean = Field(Size)
    lock = Field('lock_t')
    layout = [len, offset, queue, clean, lock]

    def init(self, len=0, queue=0):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.clean = 0
        self.lock = lambda (x): 'qlock_init(&%s)' % x
        self.declare = False

# class circular_queue_scan(State):
#     len = Field(Size)
#     offset = Field(Size)
#     queue = Field(Pointer(Void))
#     clean = Field(Size)
#
#     def init(self, len=0, queue=0):
#         self.len = len
#         self.offset = 0
#         self.queue = queue
#         self.clean = 0
#         self.declare = False
#
# class circular_queue_lock_scan(State):
#     len = Field(Size)
#     offset = Field(Size)
#     queue = Field(Pointer(Void))
#     lock = Field('lock_t')
#     clean = Field(Size)
#
#     def init(self, len=0, queue=0):
#         self.len = len
#         self.offset = 0
#         self.queue = queue
#         self.lock = lambda (x): 'qlock_init(&%s)' % x
#         self.clean = 0
#         self.declare = False


def get_field_name(state, field):
    if isinstance(field, str):
        return field

    for s in state.__dict__:
        o = state.__dict__[s]
        if isinstance(o, Field):
            if o == field:
                return s


def create_queue_states(name, type, size, n_cores, declare=True, enq_lock=False, deq_lock=False):
    prefix = "%s_" % name

    class Storage(State): data = Field(Array(type, size))

    Storage.__name__ = prefix + Storage.__name__

    storages = [Storage() for i in range(n_cores)]

    if enq_lock:
        enq = circular_queue_lock
    else:
        enq = circular_queue

    if deq_lock:
        deq = circular_queue_lock
    else:
        deq = circular_queue

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


def queue_variable_size(name, size, n_cores, enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                        clean=False, core=False):
    """
    :param name: queue name
    :param size: number of bytes
    :param n_cores:
    :param blocking:
    :param atomic:
    :return:
    """

    prefix = name + "_"
    clean_name = "clean"

    class Clean(Element):
        def configure(self):
            self.inp = Input(q_buffer)
            self.out = Output(q_buffer)
            self.special = 'clean'

        def impl(self):
            self.run_c(r'''
            (q_buffer buf) = inp();
            output { out(buf); }
            ''')
    Clean.__name__ = prefix + Clean.__name__
    if clean:
        clean_inst = Clean(name=clean_name)
        clean_name = clean_inst.name
    else:
        clean_inst = None
        clean_name = "no_clean"

    enq_all, deq_all, EnqQueue, DeqQueue, Storage = \
        create_queue_states(name, Uint(8), size, n_cores,
                            declare=False, enq_lock=enq_atomic, deq_lock=deq_atomic) # TODO: scan => clean

    class EnqueueAlloc(Element):
        this = Persistent(enq_all.__class__)
        def states(self): self.this = enq_all

        def configure(self):
            self.inp = Input(Size, Size)  # len, core
            self.out = Output(q_buffer)

        def impl(self):
            noblock_noatom = "q_buffer buff = enqueue_alloc(q, len, %s);\n" % clean_name
            block_noatom = r'''
                        q_buffer buff = { NULL, 0 };
                        while(buff.entry == NULL) {
                            buff = enqueue_alloc(q, len, %s);
                        }
                        ''' % clean_name
            noblock_atom = "qlock_lock(&q->lock);\n" + noblock_noatom + "qlock_unlock(&q->lock);\n"
            block_atom = "qlock_lock(&q->lock);\n" + block_noatom + "qlock_unlock(&q->lock);\n"

            if enq_blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                src = noblock_atom if enq_atomic else noblock_noatom

            self.run_c(r'''
                        (size_t len, size_t c) = inp();
                        %s *q = this->cores[c];
                        ''' % EnqQueue.__name__
                       + src + r'''
                        //if(entry == NULL) { printf("queue %d is full.\n", c); }
                        //printf("ENQ' core=%ld, queue=%ld, entry=%ld\n", c, q->queue, entry);
                        output { out(buff); }
                        ''')

    class EnqueueSubmit(Element):
        def configure(self):
            self.inp = Input(q_buffer)

        def impl(self):
            self.run_c(r'''
            (q_buffer buf) = inp();
            enqueue_submit(buf);
            ''')

    class DequeueGet(Element):
        this = Persistent(deq_all.__class__)
        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(q_buffer, Size) if core else Output(q_buffer)

        def impl(self):
            noblock_noatom = "q_buffer buff = dequeue_get(q);\n"
            block_noatom = r'''
            q_buffer buff = { NULL, 0 };
            while(buff.entry == NULL) {
                buff = dequeue_get(q);
            }
            '''
            noblock_atom = "qlock_lock(&q->lock);\n" + noblock_noatom + "qlock_unlock(&q->lock);\n"
            block_atom = "qlock_lock(&q->lock);\n" + block_noatom + "qlock_unlock(&q->lock);\n"

            if deq_blocking:
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
                        ''' % ('buff, c' if core else 'buff'))

    class DequeueRelease(Element):
        def configure(self):
            self.inp = Input(q_buffer)

        def impl(self):
            if clean:
                self.run_c(r'''
                            (q_buffer buf) = inp();
                            dequeue_release(buf, FLAG_CLEAN);
                            ''')
            else:
                self.run_c(r'''
                            (q_buffer buf) = inp();
                            dequeue_release(buf, 0);
                            ''')

    EnqueueAlloc.__name__ = prefix + EnqueueAlloc.__name__
    EnqueueSubmit.__name__ = prefix + EnqueueSubmit.__name__
    DequeueGet.__name__ = prefix + DequeueGet.__name__
    DequeueRelease.__name__ = prefix + DequeueRelease.__name__

    return EnqueueAlloc, EnqueueSubmit, DequeueGet, DequeueRelease, clean_inst

def queue_custom_owner_bit(name, type, size, n_cores, owner,
                           enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False, enq_output=False):
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
                            declare=True, enq_lock=False, deq_lock=False)

    type = string_type(type)
    type_star = type + "*"

    copy = r'''
    int off = sizeof(x->%s);
    uintptr_t addr1 = (uintptr_t) &q->data[old] + off;
    uintptr_t addr2 = (uintptr_t) x + off;
    rte_memcpy((void*) addr1, (void*) addr2, sizeof(%s) - off);
    __sync_synchronize();
    q->data[old].%s = x->%s;
    __sync_synchronize();
    ''' % (owner, type, owner, owner)

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
        while(!cvmx_atomic_compare_and_store64(&p->offset, old, new)) {
            old = p->offset;
            new = (old + 1) %s %d;
        }
        ''' % ('%', size, '%', size)

    wait_then_copy = r'''
    while(q->data[old].%s != 0) __sync_synchronize();
    %s
    ''' % (owner, copy)

    init_read_cvm = r'''
        uintptr_t addr = (uintptr_t) &q->data[old];
        %s* entry;
        int size = sizeof(%s);
        dma_read(addr, size, (void**) &entry, &read_lock);
        ''' % (type, type)

    wait_then_copy_cvm = r'''
        while(entry->%s) dma_read_with_buf(addr, size, (void**) &entry, &read_lock);
        memcpy(entry, x, size);
        dma_write(addr, size, entry, &write_lock);
        ''' % (owner)  # TODO: check if dma_write is atomic?

    wait_then_get = r'''
    while(q->data[old].%s == 0) __sync_synchronize();
    %s x = &q->data[old];
    ''' % (owner, type_star)

    wait_then_get_cvm = r'''
        while(entry->%s == 0) dma_read_with_buf(addr, size, (void**) &entry, &read_lock);
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

            stat = r'''
#ifdef QUEUE_STAT
    static size_t drop = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE DROP[''' + name + r''']: q = %p, drop/5s = %ld\n", q, drop);
        drop = 0;
        base = now;
    }
#endif
            '''

            noblock_noatom = stat + r'''
                __sync_synchronize();
                size_t old = p->offset;
                if(q->data[old].%s == 0) {
                    %s
                    p->offset = (p->offset + 1) %s %d;
                }
#ifdef QUEUE_STAT
                else __sync_fetch_and_add(&drop, 1);
#endif
                ''' % (owner, copy, '%', size)

            noblock_atom = stat + r'''
    __sync_synchronize();
    bool success = false;
    size_t old = p->offset;
    while(q->data[old].%s == 0) {
        size_t new = (old + 1) %s %d;
        if(__sync_bool_compare_and_swap(&p->offset, old, new)) {
            %s
            success = true;
            break;
        }
        old = p->offset;
        __sync_synchronize();
    }
#ifdef QUEUE_STAT
    if(!success) __sync_fetch_and_add(&drop, 1);
#endif
                            ''' % (owner, '%', size, copy)

            block_noatom = "size_t old = p->offset;\n" + wait_then_copy + inc_offset

            block_atom = atomic_src + wait_then_copy

            if enq_blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                src = noblock_atom if enq_atomic else noblock_noatom

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
                    dma_write(addr, size, entry, &write_lock);
                    p->offset = (p->offset + 1) %s %d;
                }
                ''' % (owner, '%', size)

            noblock_atom = "size_t old = p->offset;\n" + init_read_cvm + r'''
                while(entry->%s == 0) {
                    size_t new = (old + 1) %s %d;
                    if(__sync_bool_compare_and_swap(&p->offset, old, new)) {
                        dma_write(addr, size, entry, &write_lock);
                        break;
                    }
                    old = p->offset;
                    addr = (uintptr_t) &q->data[old];
                    dma_read(addr, size, (void**) &entry, &read_lock);
                }
                ''' % (owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + init_read_cvm + wait_then_copy_cvm + inc_offset

            block_atom = atomic_src_cvm + init_read_cvm + wait_then_copy_cvm

            if enq_blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                src = noblock_atom if enq_atomic else noblock_noatom

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
            self.out = Output(q_buffer)

        def impl(self):
            noblock_noatom = r'''
            %s x = NULL;
            __sync_synchronize();
            if(q->data[p->offset].%s != 0) {
                x = &q->data[p->offset];
                p->offset = (p->offset + 1) %s %d;
            }
            ''' % (type_star, owner, '%', size)

            noblock_atom = r'''
            %s x = NULL;
            __sync_synchronize();
            size_t old = p->offset;
            while(q->data[old].%s != 0) {
                size_t new = (old + 1) %s %d;
                if(__sync_bool_compare_and_swap(&p->offset, old, new)) {
                    x = &q->data[old];
                    break;
                }
                old = p->offset;
                __sync_synchronize();
            }
            ''' % (type_star, owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + wait_then_get + inc_offset

            block_atom = atomic_src + wait_then_get

            if deq_blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                src = noblock_atom if deq_atomic else noblock_noatom

            debug = r'''printf("deq %ld\n", c);'''

            self.run_c(r'''
                        (size_t c) = inp();
                        circular_queue* p = this->cores[c];
                        %s* q = p->queue;
                        ''' % Storage.__name__
                       #+ debug
                       + src
                       + r'''
                       q_buffer tmp = {(void*) x, 0};
                       output { out(tmp); }''')

        def impl_cavium(self):
            noblock_noatom = "size_t old = p->offset;\n" + init_read_cvm + r'''
            %s x = NULL;
            if(entry->%s != 0) {
                x = entry;
                p->offset = (p->offset + 1) %s %d;
            } else {
                dma_free(entry);
            }
            ''' % (type_star, owner, '%', size)

            noblock_atom = "size_t old = p->offset;\n" + init_read_cvm + r'''
            %s x = NULL;
            bool success = false;
            while(entry->%s != 0) {
                size_t new = (old + 1) %s %d;
                if(__sync_bool_compare_and_swap(&p->offset, old, new)) {
                    x = entry;
                    success = true;
                    break;
                }
                old = p->offset;
                addr = (uintptr_t) &q->data[old];
                dma_read(addr, size, (void**) &entry, &read_lock);
            }
            if(!success) dma_free(entry);
            ''' % (type_star, owner, '%', size)

            block_noatom = "size_t old = p->offset;\n" + init_read_cvm + wait_then_get_cvm + inc_offset

            block_atom = atomic_src_cvm + init_read_cvm + wait_then_get_cvm

            if deq_blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                src = noblock_atom if deq_atomic else noblock_noatom

            debug = r'''printf("deq %ld\n", c);'''

            self.run_c(r'''
                        (size_t c) = inp();
                        circular_queue* p = this->cores[c];
                        %s* q = p->queue;
                        ''' % Storage.__name__
                       #+ debug
                       + src
                       + r'''
                       q_buffer tmp = {(void*) x, addr};
                       output { out(tmp); }''')

    class Release(Element):
        def configure(self):
            self.inp = Input(q_buffer)

        def impl(self):
            self.run_c(r'''
            (q_buffer buff) = inp();
            %s x = (%s) buff.entry;
            if(x) x->%s = 0;
            ''' % (type_star, type_star, owner))

        def impl_cavium(self):
            self.run_c(r'''
            (q_buffer buff) = inp();
            %s x = (%s) buff.entry;
            if(x) {
                x->%s = 0;
                dma_write(buff.addr, sizeof(%s), x, &write_lock);
                dma_free(x);
            }
            ''' % (type_star, type_star, owner, type))


    return Enqueue, Dequeue, Release


def queue_shared_head_tail(name, type, size, n_cores):
    pass


