#ifndef QUEUE_H
#define QUEUE_H

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

#define ALIGN 8U
#define FLAG_OWN 1
#define TYPE_NOP 0

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
} circular_queue;

typedef struct {
    uint16_t flags;
    uint16_t len;
} __attribute__((packed)) q_entry;

q_entry *enqueue_alloc(circular_queue* q, size_t len) {
    printf("enq: queue = %ld\n", q->queue);
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
        if ((*flags & FLAG_OWN) != 0) {
            q->offset = eqe_off;
            return NULL;
        }
        elen = flags[1];
        printf("1: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }
        total += elen;
        printf("2: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
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
    q->offset = (eqe_off + len) % qlen;
    return eqe;
}

void enqueue_submit(q_entry *e)
{
    e->flags |= FLAG_OWN;
    printf("enq_submit %ld %d\n", e, e->flags);
    fflush(stdout);
}

q_entry *dequeue_get(circular_queue* q) {
    printf("deq: queue = %ld\n", q->queue);
    q_entry* eqe = q->queue + q->offset;
    printf("deq_get %ld %d\n", eqe, eqe->flags);
    if(eqe->flags & FLAG_OWN) {
        q->offset = (q->offset + eqe->len) % q->len;
        return eqe;
    }
    else
        return NULL;
}

void dequeue_release(q_entry *e)
{
    e->flags &= ~FLAG_OWN;
    fflush(stdout);
}

#endif