from dsl2 import *
import workspace

q_buffer = 'q_buffer'
q_entry = 'q_entry'


class circular_queue(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    clean = Field(Size)
    id = Field(Int)
    entry_size = Field(Int)

    def init(self, len=0, queue=0, dma_cache=True, overlap=8, ready="NULL", done="NULL"):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.clean = 0
        self.entry_size = overlap
        self.declare = False
        if dma_cache:
            self.id = "create_dma_circular_queue((uint64_t) {0}, sizeof({1}), {2}, {3}, {4})" \
                .format(queue.name, queue.__class__.__name__, overlap, ready, done)
        else:
            self.id = 0


class circular_queue_lock(State):
    len = Field(Size)
    offset = Field(Size)
    queue = Field(Pointer(Void))
    clean = Field(Size)
    lock = Field('lock_t')
    id = Field(Int)
    entry_size = Field(Int)

    def init(self, len=0, queue=0, dma_cache=True, overlap=0, ready="NULL", done="NULL"):
        self.len = len
        self.offset = 0
        self.queue = queue
        self.clean = 0
        self.entry_size = overlap
        self.lock = lambda (x): 'qlock_init(&%s)' % x
        self.declare = False
        if dma_cache:
            self.id = "create_dma_circular_queue((uint64_t) {0}, sizeof({1}), {2}, {3}, {4})" \
                .format(queue.name, queue.__class__.__name__, overlap, ready, done)
        else:
            self.id = 0


def get_field_name(state, field):
    if isinstance(field, str):
        return field

    for s in state.__dict__:
        o = state.__dict__[s]
        if isinstance(o, Field):
            if o == field:
                return s


def create_queue_states(name, type, size, n_cores, overlap=0, dma_cache=True, nameext="", deqext="",
                        declare=True, enq_lock=False, deq_lock=False, variable_size=False):
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

    enq_infos = [enq(init=[size, storages[i], dma_cache, overlap, "enqueue_ready" + nameext, "enqueue_done" + nameext],
                     declare=declare, packed=False)
                 for i in range(n_cores)]
    deq_infos = [deq(init=[size, storages[i], dma_cache, overlap, "dequeue_ready" + nameext + deqext, "dequeue_done" + nameext],
                     declare=declare, packed=False)
                 for i in range(n_cores)]

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


def queue_variable_size(name, size, n_cores,
                        enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                        clean=False, core=False, checksum=False,
                        dma_cache=True, overlap=32):
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
    checksum_arg = "true" if checksum else "false"

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

    assert (size % overlap == 0), "queue_variable_size: size must be multiples of overlap parameter."

    enq_all, deq_all, EnqQueue, DeqQueue, Storage = \
        create_queue_states(name, Uint(8), size, n_cores,
                            overlap=overlap, dma_cache=dma_cache,
                            nameext="_var", deqext="_checksum" if checksum else "",
                            declare=False, enq_lock=enq_atomic, deq_lock=deq_atomic) # TODO: scan => clean

    class EnqueueAlloc(Element):
        this = Persistent(enq_all.__class__)
        def states(self): self.this = enq_all

        def configure(self):
            self.inp = Input(Size, Size)  # len, core
            self.out = Output(q_buffer)

        def impl(self):
            noblock_noatom = "q_buffer buff = enqueue_alloc((circular_queue*) q, len, %s);\n" % \
                             (clean_name)
            block_noatom = r'''
#ifdef QUEUE_STAT
    static size_t full = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE FULL[''' + name + r''']: q = %p, full/5s = %ld\n", q, full);
        full = 0;
        base = now;
    }
#endif
''' + r'''
#ifndef CAVIUM
    q_buffer buff = { NULL, 0 };
#else
    q_buffer buff = { NULL, 0, 0 };
#endif
    while(buff.entry == NULL) {
        buff = enqueue_alloc((circular_queue*) q, len, %s);
#ifdef QUEUE_STAT
        if(buff.entry == NULL) full++;
#endif
   }
   ''' % (clean_name)
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
            enqueue_submit(buf, %s);
            ''' % checksum_arg)

    class DequeueGet(Element):
        this = Persistent(deq_all.__class__)
        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(q_buffer, Size) if core else Output(q_buffer)

        def impl(self):
            noblock_noatom = "q_buffer buff = dequeue_get((circular_queue*) q);\n"
            block_noatom = r'''
#ifndef CAVIUM
    q_buffer buff = { NULL, 0 };
#else
    q_buffer buff = { NULL, 0, 0 };
#endif
    while(buff.entry == NULL) {
        buff = dequeue_get((circular_queue*) q);
    }
            '''
            noblock_atom = "qlock_lock(&q->lock);\n" + noblock_noatom + "qlock_unlock(&q->lock);\n"
            block_atom = "qlock_lock(&q->lock);\n" + block_noatom + "qlock_unlock(&q->lock);\n"

            if deq_blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                src = noblock_atom if deq_atomic else noblock_noatom

            src = r'''
#ifdef QUEUE_STAT
    static size_t empty = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE EMPTY[''' + name + r''']: q = %p, empty/5s = %ld\n", q, empty);
        empty = 0;
        base = now;
    }
#endif
''' + src + r'''
#ifdef QUEUE_STAT
    if(buff.entry == NULL) empty++;
#endif
'''

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


def queue_custom_owner_bit(name, entry_type, size, n_cores,
                           owner, owner_type, entry_mask, entry_use,
                           checksum=False, dma_cache=True,
                           enq_blocking=False, deq_blocking=False, enq_atomic=False, deq_atomic=False,
                           enq_output=False):
    """
    :param name: queue name
    :param entry_type: entry type
    :param size: number of entries of type type
    :param n_cores:
    :param owner: ownerbit field in type (owner = 0 --> empty entry)
    :param blocking:
    :param atomic:
    :return:
    """
    define_state(entry_type)
    owner = get_field_name(entry_type, owner)

    if isinstance(entry_type, type):
        decl = workspace.get_decl(entry_type.__name__)
        if decl:
            assert decl.fields[-1] == owner, \
                "The last field of queue entry type '%s' must be '%s'. Please specify 'layout' of state '%s' accordingly." \
                % (decl.name, owner, decl.name)

    owner_size = common.sizeof(owner_type)
    assert (owner_size == 4), "queue_custom_owner_bit currently only supports owner_type of 32 bytes."
    if owner_size == 2:
        entry_mask_nic = "nic_htons(%s)" % entry_mask
    elif owner_size == 4:
        entry_mask_nic = "nic_htonl(%s)" % entry_mask
    elif owner_size == 8:
        entry_mask_nic = "nic_htonp(%s)" % entry_mask
    else:
        entry_mask_nic = entry_mask

    entry_type = string_type(entry_type)
    type_star = entry_type + "*"
    if checksum:
        checksum_offset = "(uint64_t) &((%s) 0)->%s" % (type_star, checksum)
    else:
        checksum_offset = None
    type_offset = "(uint64_t) &((%s) 0)->%s" % (type_star, owner)
    sanitized_name = '_' + entry_type.replace(' ', '_')

    enq_all, deq_all, EnqQueue, DeqQueue, Storage = \
        create_queue_states(name, entry_type, size, n_cores,
                            overlap="sizeof(%s)" % entry_type, dma_cache=dma_cache,
                            nameext=sanitized_name, deqext="_checksum" if checksum else "",
                            declare=True, enq_lock=False, deq_lock=False)

    # Extra functions
    enqueue_ready = r'''
int enqueue_ready%s(void* buff) {
  %s dummy = (%s) buff;
  return (dummy->%s == 0)? sizeof(%s): 0;
}
    ''' % (sanitized_name, type_star, type_star, owner, entry_type)

    enqueue_done = r'''
int enqueue_done%s(void* buff) {
    %s dummy = (%s) buff;
    return (dummy->%s)? sizeof(%s): 0;
}
        ''' % (sanitized_name, type_star, type_star, owner, entry_type)

    dequeue_ready = r'''
int dequeue_ready%s(void* buff) {
    %s dummy = (%s) buff;
    %s type = dummy->%s & %s;
    return (type && type == dummy->%s);
}
''' % (sanitized_name, type_star, type_star, owner_type, owner, entry_mask_nic, owner)

    if checksum:
        dequeue_ready += r'''
int dequeue_ready%s_checksum(void* buff) {
  %s dummy = (%s) buff;
  %s type = dummy->%s & %s;
  if(type && type == dummy->%s) {
    uint8_t checksum = dummy->%s;
    uint64_t checksum_size = %s;
    uint8_t* p = (uint8_t*) buff;
    uint32_t i;
    for(i=0; i<checksum_size; i++)
      checksum ^= *(p+i);
    return (checksum == 0)? sizeof(%s): 0;
  }
  return 0;
}
    ''' % (sanitized_name, type_star, type_star, owner_type, owner, entry_mask_nic, owner, checksum, checksum_offset, entry_type)

    dequeue_done = r'''
int dequeue_done%s(void* buff) {
    %s dummy = (%s) buff;
    return (dummy->%s == 0)? sizeof(%s): 0;
}
        ''' % (sanitized_name, type_star, type_star, owner, entry_type)

    if entry_type not in Storage.extra_code or checksum:
        Storage.extra_code[entry_type] = enqueue_ready + enqueue_done + dequeue_ready + dequeue_done

    if checksum:
        checksum_code = r'''
    uint8_t checksum = 0;
    uint8_t *data = (uint8_t*) content;
    int checksum_size = %s;
    int i;
    for(i=0; i<checksum_size; i++)
      checksum ^= *(data+i);
    content->%s = checksum; 
    ''' % (checksum_offset, checksum)
        flush_code = "clflush_cache_range(content, type_offset);"
    else:
        checksum_code = ""
        flush_code = ""

    copy = r'''
    int type_offset = %s;
    assert(type_offset > 0);
    %s content = &q->data[old];
    memcpy(content, x, type_offset);
    __SYNC;
    %s
    content->%s = x->%s & %s;
    %s
    __SYNC;
    ''' % (type_offset, type_star, flush_code, owner, owner, entry_mask, checksum_code)

    atomic_src = r'''
    __SYNC;
    size_t old = p->offset;
    size_t new = (old + 1) %s %d;
    while(!__sync_bool_compare_and_swap64(&p->offset, old, new)) {
        old = p->offset;
        new = (old + 1) %s %d;
    }
    ''' % ('%', size, '%', size)

    wait_then_copy = r'''
    // still occupied. wait until empty

    while(q->data[old].%s != 0 || !__sync_bool_compare_and_swap(&q->data[old].%s, 0, %s)) {
        __SYNC;
    }
    %s
    '''% (owner, owner, entry_use, copy)

    init_read_cvm = r'''
        uintptr_t addr = (uintptr_t) &q->data[old];
        %s* entry;
        int size = sizeof(%s);
#ifdef DMA_CACHE
        entry = smart_dma_read(p->id, addr, size);
#else
        dma_read(addr, size, (void**) &entry);
#endif
        ''' % (entry_type, entry_type)

    wait_then_copy_cvm = r'''
#ifdef DMA_CACHE
    while(entry == NULL) entry = smart_dma_read(p->id, addr, size);
    assert(entry->%s == 0);
    memcpy(entry, x, size);
    smart_dma_write(p->id, addr, size, entry);
#else
    // TODO: potential race condition here -- slow and fast thread grab the same entry!
    // However, using typemask requires more DMA operations.

    while(entry->%s) dma_read_with_buf(addr, size, entry, 1);
    memcpy(entry, x, size);
    dma_write(addr, size, entry, 1);
#endif
        ''' % (owner, owner)

    wait_then_get = r'''
    %s x = &q->data[old];
    %s owner = x->%s;
    while(owner == 0 || (owner & %s) ||
          !__sync_bool_compare_and_swap(&x->%s, owner, owner | %s)) {
#ifdef QUEUE_STAT
        __sync_fetch_and_add(&empty[c], 1);
#endif
        __SYNC;
        owner = x->%s;
    }
    ''' % (type_star, owner_type, owner, entry_use, owner, entry_use, owner)

    wait_then_get_cvm = r'''
#ifdef DMA_CACHE
        while(entry == NULL) entry = smart_dma_read(p->id, addr, size);
        assert((entry->%s & %s) != 0);
#else
        // TODO: potential race condition here -- slow and fast thread grab the same entry!
        while(!dequeue_ready%s(entry)) dma_read_with_buf(addr, size, entry, 1);
#endif
        %s* x = entry;
        ''' % (sanitized_name, owner, entry_mask_nic, entry_type)

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
    static size_t drop[10] = {0};
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        base = now;
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE DROP[''' + name + r''']\n");
        for(int i=0;i<8;i++) { 
          if(drop[i]) printf("queue[%ld]: drop/5s = %ld\n", i, drop[i]);
          drop[i] = 0;
        }
    }
#endif
            '''

            noblock_noatom = stat + r'''
                __SYNC;
                size_t old = p->offset;
                if(q->data[old].%s == 0) {
                    %s
            //printf("enqueue[%s]: offset = %s\n", c, p->offset);
                    p->offset = (p->offset + 1) %s %d;
                }
#ifdef QUEUE_STAT
                else __sync_fetch_and_add(&drop[c], 1);
#endif
                ''' % (owner, copy, '%d', '%ld','%', size)

            noblock_atom = stat + r'''
    __SYNC;
    bool success = false;
    size_t old2, old = p->offset;
    %s owner = q->data[old].%s;
    while(owner == 0 || owner == %s) {
        if(owner == 0 && __sync_bool_compare_and_swap(&q->data[old].%s, 0, %s)) {
            // increase offset
            old2 = p->offset;
            while(!__sync_bool_compare_and_swap(&p->offset, old2, (old2 + 1) %s %d)) {
                __SYNC;
                old2 = p->offset;
            }
            %s
            success = true;
            //printf("enqueue[%s]: offset = %s\n", c, old);
            break;
        }
        old = (old + 1) %s %d;
        owner = q->data[old].%s;
        __SYNC;
    }
#ifdef QUEUE_STAT
    if(!success) __sync_fetch_and_add(&drop[c], 1);
#endif
    ''' % (owner_type, owner, entry_use, owner, entry_use, '%', size, copy, '%d', '%ld', '%', size, owner)

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
#ifdef DMA_CACHE
        smart_dma_write(p->id, addr, size, entry);
#else
        dma_write(addr, size, entry, 1);
#endif
        p->offset = (p->offset + 1) %s %d;
    }
    ''' % (owner, '%', size)

            noblock_atom = "size_t old = p->offset;\n" + init_read_cvm + r'''
#ifdef DMA_CACHE
    while(entry) {
#else
    // TODO: potential race condition for non DMA_CACHE

    while(entry->%s == 0) {
#endif
        size_t new = (old + 1) %s %d;
        if(cvmx_atomic_compare_and_store64(&p->offset, old, new)) {
            assert(entry->%s == 0);
            memcpy(entry, x, size);
#ifdef DMA_CACHE
            smart_dma_write(p->id, addr, size, entry);
#else
            dma_write(addr, size, entry, 1);
#endif
            break;
        }
        old = p->offset;
        addr = (uintptr_t) &q->data[old];
#ifdef DMA_CACHE
        entry = smart_dma_read(p->id, addr, size);
#else
        dma_read_with_buf(addr, size, entry, 1);
#endif
    }
    ''' % (owner, '%', size, owner)

            block_noatom = "size_t old = p->offset;\n" + init_read_cvm + wait_then_copy_cvm + inc_offset

            block_atom = atomic_src + init_read_cvm + wait_then_copy_cvm

            if enq_blocking:
                src = block_atom if enq_atomic else block_noatom
            else:
                src = noblock_atom if enq_atomic else noblock_noatom

            dma_free = r'''
#ifndef DMA_CACHE
    dma_free(entry);
#endif
    '''
            out_src = "output { out(x); }\n" if enq_output else ""


            self.run_c(r'''
            (%s x, size_t c) = inp();
            circular_queue* p = this->cores[c];
            %s* q = p->queue;
            ''' % (type_star, Storage.__name__)
                       + src + dma_free + out_src)

    class Dequeue(Element):
        this = Persistent(deq_all.__class__)

        def states(self): self.this = deq_all

        def configure(self):
            self.inp = Input(Size)
            self.out = Output(q_buffer)

        def impl(self):
            noblock_noatom = r'''
            %s x = NULL;
            __SYNC;
            if((q->data[p->offset].%s & %s) != 0) {
                x = &q->data[p->offset];
                p->offset = (p->offset + 1) %s %d;
            }
            ''' % (type_star, owner, entry_mask, '%', size)

            noblock_atom = r'''
    %s x = NULL;
    __SYNC;
    size_t old2, old = p->offset;
    %s owner = q->data[old].%s;
    while((owner & %s) != 0) {
        if((owner & %s) == 0 && __sync_bool_compare_and_swap(&q->data[old].%s, owner, owner | %s)) {
            // increase offset
            old2 = p->offset;
            while(!__sync_bool_compare_and_swap(&p->offset, old2, (old2 + 1) %s %d)) {
                __SYNC;
                old2 = p->offset;
            }
            x = &q->data[old];
            break;
        }
        old = (old + 1) %s %d;
        owner = q->data[old].%s;
        __SYNC;
    }
    ''' % (type_star, owner_type, owner, entry_mask, entry_use, owner, entry_use, '%', size, '%', size, owner)

            block_noatom = "size_t old = p->offset;\n" + wait_then_get + inc_offset

            block_atom = atomic_src + wait_then_get

            if deq_blocking:
                src = block_atom if deq_atomic else block_noatom
            else:
                src = noblock_atom if deq_atomic else noblock_noatom

            src = r'''
#ifdef QUEUE_STAT
    static size_t empty[10] = {0};
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE EMPTY[''' + name + r''']\n");
        base = now;
        for(int i=0;i<10;i++) {
          if(empty[i]) printf("queue[%ld]: empty/5s = %ld\n", i, empty[i]);
          empty[i] = 0;
        }
    }
#endif
''' + src + r'''  
#ifdef QUEUE_STAT
    if(x == NULL)  __sync_fetch_and_add(&empty[c], 1);
#endif
'''

            self.run_c(r'''
    (size_t c) = inp();
    circular_queue* p = this->cores[c];
    %s* q = p->queue;
    ''' % Storage.__name__
                       + src
                       + r'''
    q_buffer tmp = {(void*) x, 0};
    output { out(tmp); }''')

        def impl_cavium(self):
            noblock_noatom = "size_t old = p->offset;\n" + init_read_cvm + r'''
    %s x = NULL;
#ifdef DMA_CACHE
    if(entry) {
        assert((entry->%s & %s) != 0);
#else
    if(dequeue_ready%s(entry)) {
#endif
        x = entry;
        p->offset = (p->offset + 1) %s %d;
    } else {
#ifndef DMA_CACHE
        dma_free(entry);
#endif
    }
    ''' % (type_star, owner, entry_mask_nic, sanitized_name, '%', size)

            noblock_atom = "size_t old = p->offset;\n" + init_read_cvm + r'''
    %s x = NULL;
    bool success = false;
#ifdef DMA_CACHE
    while(entry) {
#else
    // TODO: potential race condition for non DMA_CACHE

    while(dequeue_ready%s(entry)) {
#endif
        size_t new = (old + 1) %s %d;
        if(__sync_bool_compare_and_swap(&p->offset, old, new)) {
            x = entry;
            success = true;
            assert((entry->%s & %s) != 0);
            break;
        }
        old = p->offset;
        addr = (uintptr_t) &q->data[old];
#ifdef DMA_CACHE
        entry = smart_dma_read(p->id, addr, size);
#else
        dma_read_with_buf(addr, size, entry, 1);
#endif
    }
    if(!success) {
#ifndef DMA_CACHE
        dma_free(entry);
#endif
    }
    ''' % (type_star, sanitized_name, '%', size, owner, entry_mask_nic)

            block_noatom = "size_t old = p->offset;\n" + init_read_cvm + wait_then_get_cvm + inc_offset

            block_atom = atomic_src + init_read_cvm + wait_then_get_cvm

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
                       q_buffer tmp = {(void*) x, addr, p->id};
                       output { out(tmp); }''')

    class Release(Element):
        def configure(self):
            self.inp = Input(q_buffer)

        def impl(self):
            set_owner = "x->%s = 0; __SYNC;" % owner
            set_checksum = "x->%s = 0; __SYNC;" % checksum if checksum else ""

            self.run_c(r'''
    (q_buffer buff) = inp();
    %s x = (%s) buff.entry;
    if(x) {
        %s
        %s
    }
    ''' % (type_star, type_star, set_checksum, set_owner))

        def impl_cavium(self):
            set_owner = "x->%s = 0;" % owner
            set_checksum = "x->%s = 0;" % checksum if checksum else ""
            self.run_c(r'''
    (q_buffer buff) = inp();
    %s x = (%s) buff.entry;
    if(x) {
        %s
        %s
#ifdef DMA_CACHE
        smart_dma_write(buff.qid, buff.addr, sizeof(%s), x);
#else
        dma_write(buff.addr, sizeof(%s), x, 1);
        dma_free(x);
#endif
    }
            ''' % (type_star, type_star, set_checksum, set_owner, entry_type, entry_type))


    return Enqueue, Dequeue, Release


def queue_shared_head_tail(name, type, size, n_cores):
    pass


