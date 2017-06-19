from dsl2 import *


class QueueOffset(State):
    #len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))

    def init(self, len=0, offset=0, queue=0):
        #self.len = len
        self.offset = offset
        self.queue = queue


def queue_variable_size(name, size, n_cores):
    pass


def get_field_name(state, field):
    if isinstance(field, str):
        return field

    for s in state.__dict__:
        o = state.__dict__[s]
        if isinstance(o, Field):
            if o == field:
                return s


def queue_custom_owner_bit(name, type, size, n_cores, owner, blocking=False, atomic=False):
    owner = get_field_name(type, owner)
    prefix = "%s_" % name

    class Storage(State): data = Field(Array(type, size))
    Storage.__name__ = prefix + Storage.__name__

    class QueueCollection(State):
        cores = Field(Array(Pointer(QueueOffset), n_cores))
        def init(self, cores=[0]):
            self.cores = cores
    QueueCollection.__name__ = prefix + QueueCollection.__name__

    storages = [Storage() for i in range(n_cores)]
    enq_infos = [QueueOffset(init=[size, 0, storages[i]]) for i in range(n_cores)]
    deq_infos = [QueueOffset(init=[size, 0, storages[i]]) for i in range(n_cores)]
    enq_all = QueueCollection(init=[enq_infos])
    deq_all = QueueCollection(init=[deq_infos])

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
            %s* p = this->cores[c];
            %s* q = p->queue;
            ''' % (type_star, QueueOffset.__name__, Storage.__name__)
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
                        %s* p = this->cores[c];
                        %s* q = p->queue;
                        ''' % (QueueOffset.__name__, Storage.__name__)
                       #+ debug
                       + src
                       + "output { out(x); }\n")

    class Release(Element):
        def configure(self):
            self.inp = Input(type_star)

        def impl(self):
            self.run_c(r'''
            (%s x) = inp();
            x->%s = 0;
            ''' % (type_star, owner))

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Release.__name__ = prefix + Release.__name__

    return Enqueue, Dequeue, Release


def queue_shared_head_tail(name, type, size, n_cores):
    pass


