#ifndef QUEUE_H
#define QUEUE_H

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <pthread.h>

#define ALIGN 8U
#define FLAG_MASK 7
#define FLAG_INUSE 4
#define FLAG_CLEAN 2
#define FLAG_OWN 1
#define TYPE_NOP 0
#define TYPE_SHIFT 8
#define TYPE_MASK  0xFF00


typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
    //pthread_mutex_t lock;
} circular_queue;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
    pthread_mutex_t lock;
} circular_queue_lock;

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
#define __SYNC __sync_synchronize()
#define __sync_fetch_and_add32(ptr, inc) __sync_fetch_and_add(ptr, inc)
#define __sync_fetch_and_add64(ptr, inc) __sync_fetch_and_add(ptr, inc)
#define __sync_fetch_and_sub32(ptr, inc) __sync_fetch_and_sub(ptr, inc)
#define __sync_fetch_and_sub64(ptr, inc) __sync_fetch_and_sub(ptr, inc)
#define __sync_bool_compare_and_swap32(ptr, old, new) __sync_bool_compare_and_swap(ptr, old, new)
#define __sync_bool_compare_and_swap64(ptr, old, new) __sync_bool_compare_and_swap(ptr, old, new)

static void no_clean(q_buffer buff) {}

static inline void check_flag(q_entry* e, int offset, const char *s) {
#ifdef DEBUG
  if(e->flags & 0xf0f0) {
    printf("%s: offset = %d, e = %p, e->flags = %d, e->len = %d\n", s, offset, e, e->flags, e->len);
  }
  assert((e->flags & 0xf0f0) == 0);
#endif
}

static inline void check_flag_val(q_entry* e, int offset, const char *s, uint8_t val) {
  uint8_t flag = e->flags & FLAG_MASK;
  if(flag != val)
    printf("%s: offset = %d, e = %p, e->flags = %d != %d\n", s, offset, e, flag, val);
  assert(flag == val);
}

static void enqueue_clean(circular_queue* q, void(*clean_func)(q_buffer)) {
    size_t off, clean, qlen;
    q_entry *eqe;
    void *eq;

    __sync_synchronize();
    clean = q->clean;
    qlen = q->len;
    eq = q->queue;
    assert(clean < qlen);
    while (1) {
        eqe = (q_entry *) ((uintptr_t) eq + clean);
	check_flag(eqe, clean, "clean");
	__sync_synchronize();
        if ((eqe->flags & FLAG_MASK) != FLAG_CLEAN) {
            break;
        }
        q_buffer temp = { eqe, 0 };
        clean_func(temp);
        eqe->flags = 0;
	__sync_synchronize();
        clean = (clean + eqe->len) % qlen;
        assert(clean < qlen);
    }
    q->clean = clean;
    __sync_synchronize();
}


static q_buffer enqueue_alloc(circular_queue* q, size_t len, void(*clean)(q_buffer)) {

  //printf("enq: queue = %p\n", q->queue);
    volatile uint16_t *flags;
    q_entry *eqe, *dummy;
    size_t off, qlen, total, elen, eqe_off;
    void *eq;

    /* Align to header size */
    __sync_synchronize();
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    eqe = (q_entry *) ((uintptr_t) eq + off);
    total = 0;
    
    if(off >= qlen) printf("off = %ld, qlen = %ld\n", off, qlen);
    assert(off < qlen && qlen < 65536);

#if 0
    static q_entry* prev_addr = 0;
    static size_t count = 0;

    if(eqe != prev_addr) {
      prev_addr = eqe;
      count = 0;
    }
#endif

    do {
        flags = (volatile uint16_t *) ((uintptr_t) eq + off);
        __sync_synchronize();
	    check_flag(eqe, off, "enqueue_alloc");  // TODO: wrong
        if ((*flags & (FLAG_OWN | FLAG_INUSE)) != 0) {
            q->offset = eqe_off;

#if 0
            if(eqe == prev_addr) count++;
            if(count > 20000 && (count % 10000) == 0)
	      printf("enq_alloc (NULL): queue = %ld, entry = %ld, flag = %ld, len = %ld, offset = %ld\n", q->queue, eqe, *flags, len, off);
#endif

            q_buffer buff = { NULL, 0 };
            return buff;
        }
        enqueue_clean(q, clean);
        elen = flags[1];
        //printf("off = %d, elen = %d\n", off, elen);
        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }

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
    eqe->flags = FLAG_INUSE;

    q->offset = (eqe_off + len) % qlen;
    __sync_synchronize();
    //printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer buff = { eqe, 0 };
    return buff;
}

static void enqueue_submit(q_buffer buff)
{
    q_entry *e = buff.entry;
    if(e) {
      	check_flag(e, -1, "enqueue_submit");

        e->flags = (e->flags & TYPE_MASK) | FLAG_OWN;
        //printf("enq_submit: entry = %p, len = %d\n", e, e->len);
        //__sync_fetch_and_or(&e->flags, FLAG_OWN);
        __sync_synchronize();
    }
}

static q_buffer dequeue_get(circular_queue* q) {
  __sync_synchronize();
  assert(q->offset < q->len);
  q_entry* eqe = q->queue + q->offset;
  //if(eqe->flags) printf("dequeue_get: q = %p, offset = %ld, flags = %d\n", q->queue, q->offset, eqe->flags);
  if((eqe->flags & FLAG_MASK) == FLAG_OWN) {
    check_flag_val(eqe, q->offset, "dequeue_get (before)", 1);
    
    eqe->flags |= FLAG_INUSE;
    check_flag_val(eqe, q->offset, "dequeue_get (after)", 5);
    //check_flag(eqe, q->offset, "dequeue_get");
    //printf("dequeue_get (before): entry = %p, len = %ld, mod = %ld\n", eqe, eqe->len, q->len);
    q->offset = (q->offset + eqe->len) % q->len;
    __sync_synchronize();
    //printf("dequeue_get_return: entry = %p, flags = %d, offset = %ld\n", eqe, eqe->flags, q->offset);
    
    q_buffer buff = { eqe, 0 };
    return buff;
  }
  else {
    q_buffer buff = { NULL, 0 };
    return buff;
  }
}

static void dequeue_release(q_buffer buff, uint8_t flag_clean)
{
    q_entry *e = buff.entry;
    check_flag_val(e, -1, "dequeue_release", 5);
    //check_flag(e, -1, "dequeue_release");
    
    e->flags = (e->flags & TYPE_MASK) | flag_clean;
    //check_flag(e, -1, "enqueue_release");
    //printf("release: entry=%p\n", e);
    //__sync_fetch_and_and(&e->flags, ~FLAG_OWN);
    __sync_synchronize();
}


#endif
