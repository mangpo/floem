#ifndef FLOEM_QUEUE_MANAGE_H
#define FLOEM_QUEUE_MANAGE_H
#include "cvmcs-nic.h"
#include "floem-util.h"

#define CAVIUM
#define BUFF_SIZE 2 * 1024

void init_dma_circular_queue();
int create_dma_circular_queue(uint64_t addr, int size, int overlap, 
			      int (*ready_scan)(void*), int (*done_scan)(void*));
void* smart_dma_read_local(int qid, size_t addr);
void* smart_dma_read(int qid, size_t addr, int size);
int smart_dma_write(int qid, size_t addr, int size, void* p);

void smart_info(int qid, size_t addr, int size);
void smart_dma_manage(int);

typedef struct _dma_segment {
  int id;
  uint32_t status, size;
  int count;
  uint64_t min, max, addr, addr_max, offset;
  uint64_t commit_max;
  uint8_t *buf;
#ifdef RUNTIME
  int comp;
#else
  cvm_dma_comp_ptr_t *comp;
#endif
  uint64_t starttime;
} CVMX_CACHE_LINE_ALIGNED dma_segment;

typedef struct _dma_circular_queue {
  int size, overlap, block_size, n, id;
  size_t addr, read_ready, write_ready;
  int read_ready_seg, write_ready_seg, write_start_seg, write_finish_seg;
  dma_segment *segments;
  int (*ready_scan)(void*);
  int (*done_scan)(void*);
  uint64_t last_read, last_write, write_gap;
  spinlock_t rlock, wlock;
} CVMX_CACHE_LINE_ALIGNED dma_circular_queue;

#define VALID    0
#define WRITING  1
#define INVALID  2
#define READING  3
#define RELEASE  4

#define DMA_WAIT    100000  // 83 us (0.5 us)
#define WRITE_WAIT 1000000      // 833 us

#endif
