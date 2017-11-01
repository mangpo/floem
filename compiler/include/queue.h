#ifndef QUEUE_H
#define QUEUE_H

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <pthread.h>


#define mb() 	asm volatile("mfence":::"memory")
#define CFLASH_SIZE 64
#define __force	__attribute__((force))

static inline void clflush(volatile void *__p)
{
	asm volatile("clflush %0" : "+m" (*(volatile char __force *)__p));
}

static void clflush_cache_range(void *vaddr, unsigned int size)
{
	void *vend = vaddr + size - 1;

	mb();

	for (; vaddr < vend; vaddr += CFLASH_SIZE) {
		clflush(vaddr);
	}

	/*
 	 * Flush any possible final partial cacheline:
  	 */
	clflush(vend);

	mb();
}

//#define OPTIMISTIC

#define ALIGN 8U
#define FLAG_INUSE 4
#define FLAG_CLEAN 2
#define FLAG_OWN 1

typedef struct {
  size_t len;
  size_t offset;
  void* queue;
  size_t clean;
  int id, entry_size;
  //pthread_mutex_t lock;
} circular_queue;

typedef struct {
  size_t len;
  size_t offset;
  void* queue;
  size_t clean;
  int id, entry_size;
  pthread_mutex_t lock;
} circular_queue_lock;

typedef struct {
    uint8_t flag;
    uint8_t task;
    uint16_t len;
    uint8_t checksum;
    uint8_t pad;
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

// Return 1 when entry is ready to read or being read.
static int dequeue_ready_var(void* p) {
  q_entry* e = p;
  if(e->pad != 0xff) return 0;
  if((e->flag & 0xf0) != 0) return 0;

  if(e->flag == FLAG_OWN) {
    uint8_t* x = p;
    uint8_t checksum = 0;
    /*
    int i;
    for(i=0; i<e->len; i++)
      checksum ^= x[i];
    */
    return (checksum == 0)? e->len: 0;
  }

  return 0;
}

static inline int dequeue_done_var(void* e) { return 0; }
static inline int enqueue_ready_var(void* e) { return 0; }
static inline int enqueue_done_var(void* e) { return 0; }

static void enqueue_submit(q_buffer buff);
static void no_clean(q_buffer buff) {}

static inline void check_flag(q_entry* e, int offset, const char *s) {
#if 1 //def DEBUG
  if(e->flag & 0xf0) {
    printf("%s: offset = %d, e = %p, e->flag = %d, e->len = %d, checksum = %d, pad = %d\n", s, offset, e, e->flag, e->len, e->checksum, e->pad);
  }
  assert((e->flag & 0xf0) == 0);
#endif
}

static inline void check_flag_val(q_entry* e, int offset, const char *s, uint8_t val) {
#if 1 //def DEBUG
  uint8_t flag = e->flag;
  if(flag != val)
    printf("%s: offset = %d, e = %p, e->flag = %d != %d\n", s, offset, e, flag, val);
  assert(flag == val);
#endif
}

static void enqueue_clean(circular_queue* q, void(*clean_func)(q_buffer)) {
    q_entry *eqe;
    __sync_synchronize();
    assert(q->clean < q->len);
    while (1) {
      eqe = (q_entry *) ((uintptr_t) q->queue + q->clean);
      check_flag(eqe, q->clean, "clean");
      __sync_synchronize();
      if (eqe->flag != FLAG_CLEAN) {
	break;
      }
      q_buffer temp = { eqe, 0 };
      clean_func(temp);
      eqe->flag = 0;
      __sync_synchronize();
      q->clean += q->entry_size;
      if(q->clean + q->entry_size > q->len) q->clean = 0;
    }
    __sync_synchronize();
}

static q_buffer enqueue_alloc(circular_queue* q, size_t len, void(*clean)(q_buffer)) {
  __sync_synchronize();
  assert(q->offset < q->len);
  assert(len <= q->entry_size);
  q_entry* eqe = q->queue + q->offset;
  len = (len + ALIGN - 1) & (~(ALIGN - 1));

  if(eqe->flag == FLAG_CLEAN) enqueue_clean(q, clean);

#ifdef OPTIMISTIC
  if(eqe->flag != FLAG_INUSE) {
#else
  if(eqe->flag == 0) {
#endif
    eqe->len = len;
    eqe->flag = FLAG_INUSE;
    eqe->task = 0;

    q->offset += q->entry_size;
    if(q->offset + q->entry_size > q->len) q->offset = 0;
    __sync_synchronize();
    //printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer buff = { eqe, 0 };
    return buff;
  }
  else {
    q_buffer buff = { NULL, 0 };
    return buff;
  }
}

static void enqueue_submit(q_buffer buff)
{
    q_entry *e = buff.entry;
    if(e) {
      	check_flag(e, -1, "enqueue_submit");
        __sync_synchronize();
	clflush_cache_range(&e[1], e->len - sizeof(q_entry));
        e->flag = FLAG_OWN;

	e->pad = 0xff;
        e->checksum = 0;
        uint8_t checksum = 0;
        uint8_t* p = (uint8_t*) e;
        int i;
        for(i=0; i<e->len; i++)
            checksum ^= p[i];
        e->checksum = checksum;
        __sync_synchronize();
    }
}

static q_buffer dequeue_get(circular_queue* q) {
  __sync_synchronize();
  assert(q->offset < q->len);
  q_entry* eqe = q->queue + q->offset;
  //if(eqe->flag == FLAG_OWN) {
  if(dequeue_ready_var(eqe)) {
    //printf("dequeue_get: len = %ld\n", eqe->len);
    check_flag(eqe, q->offset, "dequeue_get");
    check_flag_val(eqe, q->offset, "dequeue_get (before)", 1);
    
    eqe->flag |= FLAG_INUSE;
    check_flag_val(eqe, q->offset, "dequeue_get (after)", 5);
    //check_flag(eqe, q->offset, "dequeue_get");
    //printf("dequeue_get (before): entry = %p, len = %ld, mod = %ld\n", eqe, eqe->len, q->len);

    q->offset += q->entry_size;
    if(q->offset + q->entry_size > q->len) q->offset = 0;
    __sync_synchronize();
    //printf("dequeue_get_return: entry = %p, flag = %d, offset = %ld\n", eqe, eqe->flag, q->offset);
    
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
    
    e->checksum = e->pad = 0;
    e->flag = flag_clean;
    __SYNC;
}

static int create_dma_circular_queue(uint64_t addr, int size, int overlap, 
				     int (*ready_scan)(void*), int (*done_scan)(void*)) 
{ return 0; }

#endif
