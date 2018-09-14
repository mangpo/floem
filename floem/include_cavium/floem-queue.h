#ifndef FLOEM_QUEUE_H
#define FLOEM_QUEUE_H

#include <cvmx-atomic.h>
#include "cvmcs-nic.h"
#include "floem-util.h"

#define FLAG_INUSE 4
#define FLAG_CLEAN 2
#define FLAG_OWN 1

typedef struct {
  size_t len;
  size_t offset;
  void* queue;
  size_t clean;
  int id;
  uint32_t entry_size;
} circular_queue;

typedef struct {
  size_t len;
  size_t offset;
  void* queue;
  size_t clean;
  int id;
  uint32_t entry_size;
  lock_t lock;
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
  int qid;
} q_buffer;

q_buffer enqueue_alloc(circular_queue* q, size_t len, int gap, void(*clean)(q_buffer));
void enqueue_submit(q_buffer buf, bool check);
q_buffer dequeue_get(circular_queue* q);
void dequeue_release(q_buffer buf, uint8_t flag_clean);
void no_clean(q_buffer buff);
int dequeue_ready_var(void*);
int dequeue_ready_var_checksum(void*);
int dequeue_done_var(void*);
int enqueue_ready_var(void*);
int enqueue_done_var(void*);

#endif
