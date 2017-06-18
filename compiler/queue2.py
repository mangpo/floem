from dsl2 import *


class QueueOffset(State):
    #len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))

    def init(self, len, offset, queue):
        #self.len = len
        self.offset = offset
        self.queue = queue


def queue_variable_size(name, size, n_cores):
    pass


def get_type(x):
    if isinstance(x, str):
        return x
    if isinstance(x, type):
        return x.__name__
    raise Exception("%s is not a data type." % x)


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
    type = get_type(type)
    prefix = "%s_" % name
    type_star = type + "*"

    class Storage(State): data = Field(Array(type, size))
    Storage.__name__ = prefix + Storage.__name__

    class QueueCollection(State):
        cores = Field(Array(QueueOffset, n_cores))
        def init(self, cores):
            self.cores = cores
    QueueCollection.__name__ = prefix + QueueCollection.__name__

    storages = [Storage() for i in range(n_cores)]
    enq_infos = [QueueOffset(init=[size, 0, storages[i]]) for i in range(n_cores)]
    deq_infos = [QueueOffset(init=[size, 0, storages[i]]) for i in range(n_cores)]
    enq_all = QueueCollection(init=[enq_infos])
    deq_all = QueueCollection(init=[deq_infos])

    atomic_src = r'''
    __sync_synchronize();
    size_t old = p->offset;
    size_t new = (old + 1) %s %d;
    while(!__sync_bool_compare_and_swap(&p->offset, old, new)) {
        old = p->offset;
        new = (old + 1) %s %d;
    }
    '''

    wait_then_copy = r'''
    while(p->data[old].%s != 0) __sync_synchronize();
    rte_memcpy(&p->data[old], x, sizeof(%s));
    __sync_synchronize();
    ''' % (owner, type)

    wait_then_get = r'''
    while(p->data[old].%s == 0) __sync_synchronize();
    %s x = &p->data[old];
    ''' % (owner, type_star)

    inc_offset = "p->offset = (p->offset + 1) %s %d;\n" % ('%', size)

    class Enqueue(Element):
        this = Persistent(QueueCollection)

        def states(self): self.this = enq_all

        def configure(self): self.inp = Input(type_star, Size)

        def impl(self):
            noblock_noatom = r'''
                __sync_synchronize();
                if(p->data[p->offset].%s == 0) {
                    rte_memcpy(&p->data[p->offset], x, sizeof(%s));
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
            ''' % (type_star, QueueOffset.__name__)
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
            if(p->data[p->offset].%s != 0) {
                x = &p->data[p->offset];
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

            self.run_c(r'''
                        (size_t c) = inp();
                        %s* p = this->cores[c];
                        ''' % (QueueOffset.__name__)
                       + src
                       + "output { out(x); }\n")

    class Release(Element):
        def configure(self):
            self.inp = Input(type_star)

        def impl(self):
            self.run_c(r'''
            (%s x) = inp();
            x.%s = 0;
            ''' % (type_star, owner))

    Enqueue.__name__ = prefix + Enqueue.__name__
    Dequeue.__name__ = prefix + Dequeue.__name__
    Release.__name__ = prefix + Release.__name__

    return Enqueue, Dequeue, Release


def queue_shared_head_tail(name, type, size, n_cores):
    pass


class Tuple(State):
    task = Field(Int)
    val = Field(Int)

Enq, Deq, Release = queue_custom_owner_bit('queue', Tuple, 16, 2, Tuple.task)
Enq()
Deq()
Release()
scope = pop_scope()
print