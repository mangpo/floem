#ifndef QUEUE_H
#define QUEUE_H

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <pthread.h>

#define ALIGN 8U
//#define FLAG_MASK 3
//#define FLAG_CLEAN 2
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


typedef pthread_mutex_t lock_t;

#define qlock_init(x) pthread_mutex_init(x, NULL)
#define qlock_lock(x) pthread_mutex_lock(x)
#define qlock_unlock(x) pthread_mutex_unlock(x)

static q_buffer enqueue_alloc(circular_queue* q, size_t len, void(*clean)(q_buffer)) {
    //printf("enq: queue = %ld\n", q->queue);
    volatile uint16_t *flags;
    q_entry *eqe, *dummy;
    size_t off, qlen, total, elen, eqe_off;
    void *eq;

    /* Align to header size */
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    eqe = (q_entry *) ((uintptr_t) eq + off);
    total = 0;
    do {
        flags = (volatile uint16_t *) ((uintptr_t) eq + off);
        __sync_synchronize();
        if ((*flags & FLAG_OWN) != 0) {
            q->offset = eqe_off;
            //printf("enq_alloc (NULL): queue = %ld, entry = %ld, flag = %ld\n", q->queue, eqe, *flags);
            q_buffer buff = { NULL, 0 };
            return buff;
        }
        elen = flags[1];
        //printf("off = %d, elen = %d\n", off, elen);
        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }
        q_buffer temp = { eqe, 0 };
        clean(temp); // TODO: loop over this when clean_offset != offset
        total += elen;
        if (total < len) {
            /* Need more */
            if (off + elen >= qlen) {
                /* No entries wrapping around: create dummy entry from current
                 * entry and start fresh */
                eqe->len = total;
                eqe->flags = FLAG_OWN | TYPE_NOP;
                eqe = eq;
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
        dummy = (q_entry *) ((uintptr_t) eqe + len);
        dummy->flags = 0;
        dummy->len = total - len;
    }
    eqe->len = len;
    eqe->flags = 0;
    //printf("enq_alloc (before): offset = %ld, len = %ld, mod = %ld\n", eqe_off, len, qlen);
    q->offset = (eqe_off + len) % qlen;
    //printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer buff = { eqe, 0 };
    return buff;
}

static void enqueue_submit(q_buffer buff)
{
    q_entry *e = buff.entry;
    if(e) {
        e->flags |= FLAG_OWN;
        //printf("enq_submit: entry = %p, len = %d\n", e, e->len);
        //__sync_fetch_and_or(&e->flags, FLAG_OWN);
        __sync_synchronize();
    }
}

static q_buffer dequeue_get(circular_queue* q) {
    q_entry* eqe = q->queue + q->offset;
    __sync_synchronize();
    if(eqe->flags & FLAG_OWN) {
        //printf("dequeue_get (before): entry = %p, len = %ld, mod = %ld\n", eqe, eqe->len, q->len);
        q->offset = (q->offset + eqe->len) % q->len;
        //printf("dequeue_get_return: entry = %p, offset = %ld\n", eqe, q->offset);
        q_buffer buff = { eqe, 0 };
        return buff;
    }
    else {
        q_buffer buff = { NULL, 0 };
        return buff;
    }
}

static void dequeue_release(q_buffer buff)
{
    q_entry *e = buff.entry;
    e->flags &= ~FLAG_OWN;
    //printf("release: entry=%p\n", e);
    //__sync_fetch_and_and(&e->flags, ~FLAG_OWN);
    __sync_synchronize();
}

static void no_clean(q_buffer buff) {}

#endif
