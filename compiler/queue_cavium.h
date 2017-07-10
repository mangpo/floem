#ifndef QUEUE_H
#define QUEUE_H

#define ALIGN 8U
#define FLAG_OWN 1
#define TYPE_NOP 0
#define TYPE_SHIFT 8
#define TYPE_MASK  0xFF00

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    //pthread_mutex_t lock;
} circular_queue;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    pthread_mutex_t lock;
} circular_queue_lock;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
} circular_queue_scan;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    pthread_mutex_t lock;
    size_t clean;
} circular_queue_lock_scan;

typedef struct {
    uint16_t flags;
    uint16_t len;
} __attribute__((packed)) q_entry;

typedef struct {
    q_entry* entry;
    uintptr_t addr;
} q_buffer;

typedef cvmx_spinlock_t lock_t;

inline void lock_init(lock_t* lock) {
    cvmx_spinlock_init(lock);
}

inline void lock_lock(lock_t* lock) {
    cvmx_spinlock_lock(lock);
}

inline void lock_unlock(lock_t* lock) {
    cvmx_spinlock_unlock(lock);
}

static q_buffer enqueue_alloc(circular_queue* q, size_t len) {
    //printf("enq: queue = %ld\n", q->queue);
    uint16_t flags, elen;
    uintptr_t addr, dummy_addr;
    q_entry *eqe, *dummy;
    size_t off, qlen, total, eqe_off;
    void *eq;

    /* Align to header size */
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    addr = (uintptr_t) eq + off;
    total = 0;
    do {
        dma_read(addr, sizeof(q_entry), (void**) &eqe, &read_lock);
        flags = eqe->flags;
        elen= eqe->len;
        if ((flags & FLAG_OWN) != 0) {
            q->offset = eqe_off;
            //printf("enq_alloc (NULL): queue = %ld, entry = %ld, flag = %ld\n", q->queue, eqe, *flags);
            dma_free(eqe);
            q_buffer buff = { NULL, 0 };
            return buff;
        }
        //printf("1: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }
        total += elen;
        //printf("2: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
        if (total < len) {
            /* Need more */
            if (off + elen >= qlen) {
                /* No entries wrapping around: create dummy entry from current
                 * entry and start fresh */
                eqe->len = total;
                eqe->flags = FLAG_OWN | TYPE_NOP;
                dma_write(addr, sizeof(q_entry), eqe, &write_lock);
                dma_free(eqe);
                addr = eq;
                eqe_off = off = 0;
                total = 0;
            } else {
                off = (off + elen) % qlen;
            }
        }
    } while (total < len);
    /* Too much space, split up and create dummy entry */
    if (total > len) {
        assert(total - len >= sizeof(q_entry));
        dummy_addr = addr + len;
        dma_read(dummy_addr, sizeof(q_entry), (void**) &dummy, &read_lock);
        dummy->flags = 0;
        dummy->len = total - len;
        dma_write(dummy_addr, sizeof(q_entry), dummy, &write_lock);
        dma_free(dummy_addr);
    }
    eqe->len = len;
    eqe->flags = 0;
    dma_write(addr, sizeof(q_entry), eqe, &write_lock);
    dma_free(eqe);
    dma_read(addr, len, (void**) &eqe, &read_lock);
    //printf("enq_alloc (before): offset = %ld, len = %ld, mod = %ld\n", eqe_off, len, qlen);
    q->offset = (eqe_off + len) % qlen;
    //printf("enq_alloc: queue = %ld, entry = %ld, len = %ld, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer ret = { eqe, addr };
    return ret;
}

static void enqueue_submit(q_buffer buf)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    e->flags |= FLAG_OWN;
    dma_write(addr, e->len, e, &write_lock);
    dma_free(e);
    //printf("enq_submit: entry = %ld, len = %d\n", e, e->len);
    //__sync_fetch_and_or(&e->flags, FLAG_OWN);
}

static q_buffer dequeue_get(circular_queue* q) {
    q_entry* eqe;
    uintptr_t addr = q->queue + q->offset;
    dma_read(addr, sizeof(q_entry), (void**) &eqe, &read_lock);
    __sync_synchronize();
    if(eqe->flags & FLAG_OWN) {
        //printf("dequeue_get (before): entry = %ld, len = %ld, mod = %ld\n", eqe, eqe->len, q->len);
        uint16_t elen = eqe->len;
        q->offset = (q->offset + elen) % q->len;
        dma_free(eqe);
        dma_read(addr, elen, (void**) &eqe, &read_lock);
        //printf("dequeue_get_return: entry = %ld, offset = %ld\n", eqe, q->offset);
        q_buffer ret = { eqe, addr };
        return ret;
    }
    else {
        dma_free(eqe);
        q_buffer ret = { NULL, 0 };
        return ret;
    }
}

static void dequeue_release(q_buffer buf)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    e->flags &= ~FLAG_OWN;
    dma_write(addr, sizeof(uint16_t), e, &write_lock);
    dma_free(e);
    //printf("release: entry=%ld\n", e);
    //__sync_fetch_and_and(&e->flags, ~FLAG_OWN);
}

static q_buffer next_clean(circular_queue_scan* q) {
    size_t off = q->offset;
    size_t len = q->len;
    size_t clean = q->clean;
    void* base = q->queue;
    //if(c==1 && cleaning.last != off) printf("SCAN: start, last = %ld, offset = %ld, clean = %ld\n", cleaning.last, off, clean);
    q_entry *eqe = NULL;
    uintptr_t addr;
    if (clean != off) {
        uintptr_t addr = (uintptr_t) base + clean;
        dma_read(addr, sizeof(q_entry), (void**) &eqe, &read_lock);
        if ((eqe->flags & FLAG_OWN) != 0) {
            dma_free(eqe);
            eqe = NULL;
        } else {
            uintptr_t elen = eqe->len;
            q->clean = (clean + elen) % len;
            dma_free(eqe);
            dma_read(addr, elen, (void**) &eqe, &read_lock);
        }
    }
    q_buffer ret = { eqe, addr };
    return ret;
}

static void clean_release(q_buffer buf)
{
    q_entry *e = buf.entry;
    dma_free(e);
}

#endif