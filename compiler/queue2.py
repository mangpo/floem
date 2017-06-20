from dsl2 import *


class circular_queue(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))

    def init(self, len=0, offset=0, queue=0):
        self.len = len
        self.offset = offset
        self.queue = queue


class circular_queue_lock(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    lock = Field('pthread_mutex_t')

    def init(self, len=0, offset=0, queue=0, lock=None):
        self.len = len
        self.offset = offset
        self.queue = queue
        self.lock = lock


def get_field_name(state, field):
    if isinstance(field, str):
        return field

    for s in state.__dict__:
        o = state.__dict__[s]
        if isinstance(o, Field):
            if o == field:
                return s

def create_queue_states(name, type, size, n_cores, declare=True, lock=False):
    prefix = "%s_" % name

    class Storage(State): data = Field(Array(type, size))

    Storage.__name__ = prefix + Storage.__name__

    class QueueCollection(State):
        cores = Field(Array(Pointer(circular_queue), n_cores))

        def init(self, cores=[0]):
            self.cores = cores

    QueueCollection.__name__ = prefix + QueueCollection.__name__

    storages = [Storage() for i in range(n_cores)]
    if not lock:
        enq_infos = [circular_queue(init=[size, 0, storages[i]], declare=declare) for i in range(n_cores)]
        deq_infos = [circular_queue(init=[size, 0, storages[i]], declare=declare) for i in range(n_cores)]
    else:
        f = lambda(lock): 'pthread_mutex_init(&%s, NULL)' % lock
        enq_infos = [circular_queue_lock(init=[size, 0, storages[i], f], declare=declare) for i in range(n_cores)]
        deq_infos = [circular_queue_lock(init=[size, 0, storages[i], f], declare=declare) for i in range(n_cores)]
    # TODO: init pthread_mutex_init(&lock, NULL)
    enq_all = QueueCollection(init=[enq_infos])
    deq_all = QueueCollection(init=[deq_infos])

    return enq_all, deq_all, Storage, QueueCollection

def queue_variable_size(name, size, n_cores, blocking=False, atomic=False):
    """
    :param name: queue name
    :param size: number of bytes
    :param n_cores:
    :param blocking:
    :param atomic:
    :return:
    """
    prefix = "%s_" % name

    enq_all, deq_all, Storage, QueueCollection = create_queue_states(name, Uint(8), size, n_cores, declare=False)
    type = string_type(type)
    type_star = type + "*"

    class EnqueueAlloc(Element):
        this = Persistent(QueueCollection)

        def configure(self):
            self.inp = Input(Size, Size)  # len, core
            self.out = Output('q_entry*')

        def impl(self):
            noblock_noatom = "q_entry* entry = (q_entry*) enqueue_alloc(q, len);\n""

            block_noatom = r'''
            q_entry* entry = NULL;
            do {
                entry = (q_entry*) enqueue_alloc(q, len);
            } while(entry == NULL)
            '''

            noblock_atom = "pthread_mutex_lock(&q->lock);\n" + noblock_noatom + "pthread_mutex_unlock(&q->lock);\n"

            block_atom = "pthread_mutex_lock(&q->lock);\n" + block_noatom + "pthread_mutex_unlock(&q->lock);\n"

            if blocking:
                src = block_atom if atomic else block_noatom
            else:
                src = noblock_atom if atomic else noblock_noatom

            self.run_c(r'''
            (size_t len, size_t c) = inp();
            %s *q = this->cores[c];  // TODO
            ''' % ('circular_queue_lock' if atomic else 'circular_queue')
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



def queue_custom_owner_bit(name, type, size, n_cores, owner, blocking=False, atomic=False):
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

    enq_all, deq_all, Storage, QueueCollection = create_queue_states(name, type, size, n_cores, declare=True)
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

    wait_then_copy = r'''
    while(q->data[old].%s != 0) __sync_synchronize();
    rte_memcpy(&q->data[old], x, sizeof(%s));
    __sync_synchronize();
    ''' % (owner, type)

    wait_then_get = r'''
    while(q->data[old].%s == 0) __sync_synchronize();
    %s x = &q->data[old];
    ''' % (owner, type_star)

    inc_offset = "p->offset = (p->offset + 1) %s %d;\n" % ('%', size)

    class Enqueue(Element):
        this = Persistent(QueueCollection)

        def states(self): self.this = enq_all

        def configure(self): self.inp = Input(type_star, Size)

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

            block_atom = atomic_src + wait_then_copy

            if blocking:
                src = block_atom if atomic else block_noatom
            else:
                if atomic:
                    raise Exception("Unimplemented for non-blocking but atomic.")
                else:
                    src = noblock_noatom

            self.run_c(r'''
            (%s x, size_t c) = inp();
            circular_queue* p = this->cores[c];
            %s* q = p->queue;
            ''' % (type_star, Storage.__name__)
                       + src)

    class Dequeue(Element):
        this = Persistent(QueueCollection)

        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(type_star)

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
                src = block_atom if atomic else block_noatom
            else:
                if atomic:
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
                       + "output { out(x); }\n")

    class Release(Element):
        def configure(self):
            self.inp = Input(type_star)

        def impl(self):
            self.run_c(r'''
            (%s x) = inp();
            if(x) x->%s = 0;
            ''' % (type_star, owner))

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Release.__name__ = prefix + Release.__name__

    return Enqueue, Dequeue, Release


def queue_shared_head_tail(name, type, size, n_cores):
    pass


